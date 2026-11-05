from datetime import UTC, date, datetime, timedelta
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
from app.schemas.execucao import (
    ExecucaoConfirmarBlocoRequest,
    ExecucaoCreate,
    ExecucaoIniciarRequest,
    ExecucaoRead,
    ExecucaoTransicaoRequest,
    ExecucaoUpdate,
)
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


def _encerrar_execucao_aberta(
    execucao: Execucao,
    instante: datetime,
    status_final: str = "concluida",
) -> None:
    ini_utc = garantir_utc(execucao.inicio)
    fim_efetivo = max(instante, ini_utc + timedelta(seconds=1))
    for p in execucao.pausas:
        if p.fim is None:
            p_ini = garantir_utc(p.inicio)
            p.fim = max(fim_efetivo, p_ini + timedelta(seconds=1))
            if garantir_utc(p.fim) > fim_efetivo:
                fim_efetivo = garantir_utc(p.fim)
    execucao.fim = fim_efetivo
    execucao.status = status_final
    execucao.segundos_liquidos = _recalcular_liquido(
        execucao.inicio, execucao.fim, list(execucao.pausas)
    )
    execucao.versao += 1


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


@router.get("/ativa", response_model=ExecucaoRead | None)
async def obter_execucao_ativa(
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ExecucaoRead | None:
    repo = ExecucaoRepository(session)
    abertas = await repo.listar_em_andamento(usuario.id)
    if not abertas:
        return None
    return ExecucaoRead.model_validate(abertas[0])


@router.post("/iniciar", response_model=ExecucaoRead, status_code=status.HTTP_201_CREATED)
async def iniciar_execucao(
    dados: ExecucaoIniciarRequest,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ExecucaoRead:
    agora = garantir_utc(dados.instante) if dados.instante is not None else datetime.now(UTC)

    categoria_id = dados.categoria_id
    if dados.bloco_id is not None:
        bloco_repo = BlocoRepository(session)
        bloco = await bloco_repo.obter_do_usuario(usuario.id, dados.bloco_id)
        if bloco is None:
            raise NaoEncontradoError("Bloco não encontrado")
        if categoria_id is None:
            categoria_id = bloco.categoria_id

    if categoria_id is None:
        raise AppError(422, "Informe categoria_id ou bloco_id para iniciar a execução", "validacao")

    cat_repo = CategoriaRepository(session)
    if await cat_repo.obter_do_usuario(usuario.id, categoria_id) is None:
        raise NaoEncontradoError("Categoria não encontrada")

    repo = ExecucaoRepository(session)
    abertas = await repo.listar_em_andamento(usuario.id, for_update=True)
    for aberta in abertas:
        _encerrar_execucao_aberta(aberta, agora, status_final="concluida")

    kwargs: dict[str, object] = {
        "usuario_id": usuario.id,
        "categoria_id": categoria_id,
        "bloco_id": dados.bloco_id,
        "inicio": agora,
        "fim": None,
        "status": "em_andamento",
        "origem": "cronometro",
        "segundos_liquidos": 0,
        "pausas": [],
    }
    if dados.id is not None:
        kwargs["id"] = dados.id

    nova = Execucao(**kwargs)
    await repo.criar(nova)
    await session.commit()
    recarregada = await repo.obter_do_usuario(usuario.id, nova.id)
    assert recarregada is not None
    return ExecucaoRead.model_validate(recarregada)


@router.post("/confirmar-bloco", response_model=ExecucaoRead)
async def confirmar_bloco_como_planejado(
    dados: ExecucaoConfirmarBlocoRequest,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ExecucaoRead:
    bloco_repo = BlocoRepository(session)
    bloco = await bloco_repo.obter_do_usuario(usuario.id, dados.bloco_id)
    if bloco is None:
        raise NaoEncontradoError("Bloco não encontrado")

    repo = ExecucaoRepository(session)
    existentes = await repo.listar_por_bloco(usuario.id, bloco.id)

    pausas_planejadas = [PausaExecucao(inicio=p.inicio, fim=p.fim) for p in bloco.pausas_planejadas]
    liq = (
        0
        if dados.status == "pulada"
        else _recalcular_liquido(bloco.inicio, bloco.fim, pausas_planejadas)
    )

    if existentes:
        # Prioriza a execução em andamento (se houver) ou a mais recente
        principal = next(
            (e for e in existentes if e.status == "em_andamento" and e.fim is None),
            existentes[-1],
        )
        for extra in existentes:
            if extra.id == principal.id:
                continue
            if extra.status == "em_andamento" and extra.fim is None:
                _encerrar_execucao_aberta(extra, datetime.now(UTC), status_final="concluida")
            extra.excluido_em = datetime.now(UTC)
            extra.versao += 1

        principal.categoria_id = bloco.categoria_id
        principal.inicio = bloco.inicio
        principal.fim = bloco.fim
        principal.status = dados.status
        principal.origem = "confirmacao"
        principal.pausas.clear()
        for p in pausas_planejadas:
            principal.pausas.append(p)
        principal.segundos_liquidos = liq
        principal.versao += 1
        alvo_id = principal.id
    else:
        nova = Execucao(
            usuario_id=usuario.id,
            categoria_id=bloco.categoria_id,
            bloco_id=bloco.id,
            inicio=bloco.inicio,
            fim=bloco.fim,
            status=dados.status,
            origem="confirmacao",
            segundos_liquidos=liq,
            pausas=pausas_planejadas,
        )
        await repo.criar(nova)
        alvo_id = nova.id

    await session.commit()
    recarregada = await repo.obter_do_usuario(usuario.id, alvo_id)
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
            kwargs_p: dict[str, object] = {
                "inicio": p.inicio,
                "fim": p.fim,
            }
            if p.id is not None:
                kwargs_p["id"] = p.id
            execucao.pausas.append(PausaExecucao(**kwargs_p))
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


@router.post("/{execucao_id}/pausar", response_model=ExecucaoRead)
async def pausar_execucao(
    execucao_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
    dados: ExecucaoTransicaoRequest | None = None,
) -> ExecucaoRead:
    repo = ExecucaoRepository(session)
    execucao = await repo.obter_do_usuario(usuario.id, execucao_id)
    if execucao is None:
        raise NaoEncontradoError("Execução não encontrada")
    if execucao.status != "em_andamento" or execucao.fim is not None:
        raise AppError(409, "Apenas execuções em andamento podem ser pausadas", "conflito")

    pausa_aberta = next((p for p in execucao.pausas if p.fim is None), None)
    if pausa_aberta is not None:
        raise AppError(409, "A execução já está pausada", "conflito")

    instante_req = dados.instante if dados and dados.instante is not None else datetime.now(UTC)
    ini_utc = garantir_utc(execucao.inicio)
    instante_efetivo = max(garantir_utc(instante_req), ini_utc)

    execucao.pausas.append(PausaExecucao(inicio=instante_efetivo, fim=None))
    execucao.versao += 1
    await session.commit()
    recarregada = await repo.obter_do_usuario(usuario.id, execucao.id)
    assert recarregada is not None
    return ExecucaoRead.model_validate(recarregada)


@router.post("/{execucao_id}/retomar", response_model=ExecucaoRead)
async def retomar_execucao(
    execucao_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
    dados: ExecucaoTransicaoRequest | None = None,
) -> ExecucaoRead:
    repo = ExecucaoRepository(session)
    execucao = await repo.obter_do_usuario(usuario.id, execucao_id)
    if execucao is None:
        raise NaoEncontradoError("Execução não encontrada")
    if execucao.status != "em_andamento" or execucao.fim is not None:
        raise AppError(409, "Apenas execuções em andamento podem ser retomadas", "conflito")

    pausa_aberta = next((p for p in execucao.pausas if p.fim is None), None)
    if pausa_aberta is None:
        raise AppError(409, "A execução não possui pausa em aberto", "conflito")

    instante_req = dados.instante if dados and dados.instante is not None else datetime.now(UTC)
    p_ini = garantir_utc(pausa_aberta.inicio)
    pausa_aberta.fim = max(garantir_utc(instante_req), p_ini + timedelta(seconds=1))
    execucao.versao += 1
    await session.commit()
    recarregada = await repo.obter_do_usuario(usuario.id, execucao.id)
    assert recarregada is not None
    return ExecucaoRead.model_validate(recarregada)


@router.post("/{execucao_id}/concluir", response_model=ExecucaoRead)
async def concluir_execucao(
    execucao_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
    dados: ExecucaoTransicaoRequest | None = None,
) -> ExecucaoRead:
    repo = ExecucaoRepository(session)
    execucao = await repo.obter_do_usuario(usuario.id, execucao_id)
    if execucao is None:
        raise NaoEncontradoError("Execução não encontrada")
    if execucao.status != "em_andamento" or execucao.fim is not None:
        raise AppError(409, "A execução já foi concluída", "conflito")

    instante_req = dados.instante if dados and dados.instante is not None else datetime.now(UTC)
    status_final = dados.status if dados is not None else "concluida"
    _encerrar_execucao_aberta(execucao, garantir_utc(instante_req), status_final=status_final)

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
