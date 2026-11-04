from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.errors import AppError, NaoEncontradoError
from app.core.tempo import garantir_utc, limites_utc_do_dia
from app.dependencies import CurrentUserDep, SessionDep
from app.models.execucao import Execucao, PausaExecucao
from app.repositories.bloco import BlocoRepository
from app.repositories.categoria import CategoriaRepository
from app.repositories.execucao import ExecucaoRepository
from app.schemas.execucao import ExecucaoCreate, ExecucaoRead, ExecucaoUpdate
from app.services.horas_liquidas import Intervalo, segundos_liquidos

router = APIRouter(prefix="/execucoes", tags=["execucoes"])


def _recalcular_liquido(
    inicio: datetime,
    fim: datetime | None,
    pausas: list[PausaExecucao],
) -> int:
    if fim is None:
        return 0
    ini_utc = garantir_utc(inicio)
    fim_utc = garantir_utc(fim)
    if fim_utc <= ini_utc:
        return 0
    base = Intervalo(ini_utc, fim_utc)
    intervalos_pausa = [
        Intervalo(p.inicio, p.fim)
        for p in pausas
        if p.fim is not None and garantir_utc(p.fim) > garantir_utc(p.inicio)
    ]
    return segundos_liquidos(base, intervalos_pausa)


@router.get("", response_model=list[ExecucaoRead])
async def listar_execucoes(
    de: Annotated[date, Query(...)],
    ate: Annotated[date, Query(...)],
    usuario: CurrentUserDep,
    session: SessionDep,
) -> list[ExecucaoRead]:
    if ate < de:
        raise AppError(422, "A data final deve ser maior ou igual à inicial", "validacao")

    inicio_utc, _ = limites_utc_do_dia(de, usuario.fuso)
    _, fim_utc = limites_utc_do_dia(ate, usuario.fuso)

    repo = ExecucaoRepository(session)
    execucoes = await repo.listar_por_intervalo_utc(usuario.id, inicio_utc, fim_utc)
    return [ExecucaoRead.model_validate(e) for e in execucoes]


@router.post("", response_model=ExecucaoRead, status_code=status.HTTP_201_CREATED)
async def criar_execucao(
    dados: ExecucaoCreate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ExecucaoRead:
    cat_repo = CategoriaRepository(session)
    if await cat_repo.obter_do_usuario(usuario.id, dados.categoria_id) is None:
        raise NaoEncontradoError("Categoria não encontrada")

    if dados.bloco_id is not None:
        bloco_repo = BlocoRepository(session)
        if await bloco_repo.obter_do_usuario(usuario.id, dados.bloco_id) is None:
            raise NaoEncontradoError("Bloco não encontrado")

    pausas_orm = [
        PausaExecucao(
            **({"id": p.id} if p.id is not None else {}),
            inicio=p.inicio,
            fim=p.fim,
        )
        for p in dados.pausas
    ]
    liq = _recalcular_liquido(dados.inicio, dados.fim, pausas_orm)

    kwargs: dict[str, object] = {
        "usuario_id": usuario.id,
        "categoria_id": dados.categoria_id,
        "bloco_id": dados.bloco_id,
        "inicio": dados.inicio,
        "fim": dados.fim,
        "status": dados.status,
        "origem": dados.origem,
        "segundos_liquidos": liq,
        "pausas": pausas_orm,
    }
    if dados.id is not None:
        kwargs["id"] = dados.id

    repo = ExecucaoRepository(session)
    execucao = Execucao(**kwargs)
    await repo.criar(execucao)
    await session.commit()
    recarregada = await repo.obter_do_usuario(usuario.id, execucao.id)
    assert recarregada is not None
    return ExecucaoRead.model_validate(recarregada)


@router.get("/{execucao_id}", response_model=ExecucaoRead)
async def obter_execucao(
    execucao_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ExecucaoRead:
    repo = ExecucaoRepository(session)
    execucao = await repo.obter_do_usuario(usuario.id, execucao_id)
    if execucao is None:
        raise NaoEncontradoError("Execução não encontrada")
    return ExecucaoRead.model_validate(execucao)


@router.patch("/{execucao_id}", response_model=ExecucaoRead)
async def atualizar_execucao(
    execucao_id: UUID,
    dados: ExecucaoUpdate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ExecucaoRead:
    repo = ExecucaoRepository(session)
    execucao = await repo.obter_do_usuario(usuario.id, execucao_id)
    if execucao is None:
        raise NaoEncontradoError("Execução não encontrada")

    campos = dados.model_dump(exclude_unset=True)
    if "categoria_id" in campos:
        cat_repo = CategoriaRepository(session)
        if await cat_repo.obter_do_usuario(usuario.id, campos["categoria_id"]) is None:
            raise NaoEncontradoError("Categoria não encontrada")

    if "bloco_id" in campos and campos["bloco_id"] is not None:
        bloco_repo = BlocoRepository(session)
        if await bloco_repo.obter_do_usuario(usuario.id, campos["bloco_id"]) is None:
            raise NaoEncontradoError("Bloco não encontrado")

    novo_ini = garantir_utc(dados.inicio if dados.inicio is not None else execucao.inicio)
    fim_base = dados.fim if dados.fim is not None else execucao.fim
    novo_fim = garantir_utc(fim_base) if fim_base is not None else None
    if novo_fim is not None and novo_fim <= novo_ini:
        raise AppError(422, "O fim da execução deve ser posterior ao início", "validacao")

    if "pausas" in campos and dados.pausas is not None:
        for p in dados.pausas:
            p_ini = garantir_utc(p.inicio)
            p_fim = garantir_utc(p.fim)
            if p_ini < novo_ini or (novo_fim is not None and p_fim > novo_fim):
                raise AppError(
                    422,
                    "As pausas devem ficar dentro do intervalo da execução",
                    "validacao",
                )
        execucao.pausas.clear()
        for p in dados.pausas:
            execucao.pausas.append(
                PausaExecucao(
                    **({"id": p.id} if p.id is not None else {}),
                    inicio=p.inicio,
                    fim=p.fim,
                )
            )
        campos.pop("pausas")
    else:
        for p_existente in execucao.pausas:
            pe_ini = garantir_utc(p_existente.inicio)
            pe_fim = garantir_utc(p_existente.fim) if p_existente.fim is not None else None
            if pe_ini < novo_ini or (
                novo_fim is not None and pe_fim is not None and pe_fim > novo_fim
            ):
                raise AppError(
                    422,
                    "As pausas existentes ficam fora do novo intervalo da execução",
                    "validacao",
                )

    for campo, valor in campos.items():
        setattr(execucao, campo, valor)

    execucao.segundos_liquidos = _recalcular_liquido(
        execucao.inicio, execucao.fim, list(execucao.pausas)
    )
    execucao.versao += 1
    await session.commit()
    recarregada = await repo.obter_do_usuario(usuario.id, execucao.id)
    assert recarregada is not None
    return ExecucaoRead.model_validate(recarregada)


@router.delete("/{execucao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_execucao(
    execucao_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> None:
    repo = ExecucaoRepository(session)
    execucao = await repo.obter_do_usuario(usuario.id, execucao_id)
    if execucao is None:
        raise NaoEncontradoError("Execução não encontrada")

    execucao.excluido_em = datetime.now(UTC)
    execucao.versao += 1
    await session.commit()
