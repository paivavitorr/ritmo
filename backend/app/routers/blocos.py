from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.core.errors import AppError, ConflitoError, NaoEncontradoError
from app.core.tempo import data_local_no_fuso, garantir_utc
from app.dependencies import CurrentUserDep, SessionDep
from app.models.bloco import Bloco, PausaPlanejada
from app.models.execucao import Execucao, PausaExecucao
from app.repositories.bloco import BlocoRepository
from app.repositories.categoria import CategoriaRepository
from app.repositories.execucao import ExecucaoRepository
from app.schemas.bloco import (
    BlocoCreate,
    BlocoRead,
    BlocoUpdate,
    PausaPlanejadaRead,
)
from app.schemas.execucao import ExecucaoRead
from app.services.horas_liquidas import Intervalo, segundos_liquidos

router = APIRouter(prefix="/blocos", tags=["blocos"])


def calcular_segundos_liquidos_bloco(bloco: Bloco) -> int:
    base = Intervalo(bloco.inicio, bloco.fim)
    pausas = [Intervalo(p.inicio, p.fim) for p in bloco.pausas_planejadas]
    return segundos_liquidos(base, pausas)


def serializar_bloco(bloco: Bloco) -> BlocoRead:
    return BlocoRead(
        id=bloco.id,
        usuario_id=bloco.usuario_id,
        categoria_id=bloco.categoria_id,
        modelo_bloco_id=bloco.modelo_bloco_id,
        tipo=bloco.tipo,  # type: ignore[arg-type]
        titulo=bloco.titulo,
        notas=bloco.notas,
        data_local=bloco.data_local,
        inicio=bloco.inicio,
        fim=bloco.fim,
        desvinculado=bloco.desvinculado,
        pausas_planejadas=[PausaPlanejadaRead.model_validate(p) for p in bloco.pausas_planejadas],
        segundos_liquidos_planejados=calcular_segundos_liquidos_bloco(bloco),
        versao=bloco.versao,
        criado_em=bloco.criado_em,
        atualizado_em=bloco.atualizado_em,
    )


def _verificar_if_match(if_match: str | None, versao_atual: int) -> None:
    if if_match is None:
        return
    limpo = if_match.strip().strip('"')
    try:
        esperada = int(limpo)
    except ValueError as exc:
        raise AppError(400, "Cabeçalho If-Match inválido", "if_match_invalido") from exc
    if esperada != versao_atual:
        raise ConflitoError("Conflito de versão: o bloco foi modificado por outra operação")


@router.get("", response_model=list[BlocoRead])
async def listar_blocos(
    de: Annotated[date, Query(...)],
    ate: Annotated[date, Query(...)],
    usuario: CurrentUserDep,
    session: SessionDep,
) -> list[BlocoRead]:
    if ate < de:
        raise AppError(422, "A data final deve ser maior ou igual à inicial", "validacao")
    repo = BlocoRepository(session)
    blocos = await repo.listar_por_periodo(usuario.id, de, ate)
    return [serializar_bloco(b) for b in blocos]


@router.post("", response_model=BlocoRead, status_code=status.HTTP_201_CREATED)
async def criar_bloco(
    dados: BlocoCreate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> BlocoRead:
    cat_repo = CategoriaRepository(session)
    if await cat_repo.obter_do_usuario(usuario.id, dados.categoria_id) is None:
        raise NaoEncontradoError("Categoria não encontrada")

    data_ref = (
        dados.data_local
        if dados.data_local is not None
        else data_local_no_fuso(dados.inicio, usuario.fuso)
    )
    pausas_orm = [
        PausaPlanejada(
            **({"id": p.id} if p.id is not None else {}),
            inicio=p.inicio,
            fim=p.fim,
        )
        for p in dados.pausas
    ]
    kwargs: dict[str, object] = {
        "usuario_id": usuario.id,
        "categoria_id": dados.categoria_id,
        "tipo": dados.tipo,
        "titulo": dados.titulo,
        "notas": dados.notas,
        "data_local": data_ref,
        "inicio": dados.inicio,
        "fim": dados.fim,
        "desvinculado": False,
        "pausas_planejadas": pausas_orm,
    }
    if dados.id is not None:
        kwargs["id"] = dados.id

    repo = BlocoRepository(session)
    bloco = Bloco(**kwargs)
    await repo.criar(bloco)
    await session.commit()
    recarregado = await repo.obter_do_usuario(usuario.id, bloco.id)
    assert recarregado is not None
    return serializar_bloco(recarregado)


@router.get("/{bloco_id}", response_model=BlocoRead)
async def obter_bloco(
    bloco_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> BlocoRead:
    repo = BlocoRepository(session)
    bloco = await repo.obter_do_usuario(usuario.id, bloco_id)
    if bloco is None:
        raise NaoEncontradoError("Bloco não encontrado")
    return serializar_bloco(bloco)


@router.patch("/{bloco_id}", response_model=BlocoRead)
async def atualizar_bloco(
    bloco_id: UUID,
    dados: BlocoUpdate,
    usuario: CurrentUserDep,
    session: SessionDep,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> BlocoRead:
    repo = BlocoRepository(session)
    bloco = await repo.obter_do_usuario(usuario.id, bloco_id)
    if bloco is None:
        raise NaoEncontradoError("Bloco não encontrado")

    _verificar_if_match(if_match, bloco.versao)

    campos = dados.model_dump(exclude_unset=True)
    if "categoria_id" in campos:
        cat_repo = CategoriaRepository(session)
        if await cat_repo.obter_do_usuario(usuario.id, campos["categoria_id"]) is None:
            raise NaoEncontradoError("Categoria não encontrada")

    novo_inicio = garantir_utc(dados.inicio if dados.inicio is not None else bloco.inicio)
    novo_fim = garantir_utc(dados.fim if dados.fim is not None else bloco.fim)
    if novo_fim <= novo_inicio:
        raise AppError(422, "O fim do bloco deve ser posterior ao início", "validacao")

    pausas_para_validar = (
        [(garantir_utc(p.inicio), garantir_utc(p.fim)) for p in dados.pausas]
        if dados.pausas is not None
        else [(garantir_utc(p.inicio), garantir_utc(p.fim)) for p in bloco.pausas_planejadas]
    )
    for p_ini, p_fim in pausas_para_validar:
        if p_ini < novo_inicio or p_fim > novo_fim:
            raise AppError(
                422,
                "As pausas planejadas devem ficar contidas dentro do bloco",
                "validacao",
            )

    if campos:
        data_local_anterior = bloco.data_local
        if "pausas" in campos and dados.pausas is not None:
            bloco.pausas_planejadas.clear()
            for p in dados.pausas:
                bloco.pausas_planejadas.append(
                    PausaPlanejada(
                        **({"id": p.id} if p.id is not None else {}),
                        inicio=p.inicio,
                        fim=p.fim,
                    )
                )
            campos.pop("pausas")

        if "inicio" in campos and "data_local" not in campos:
            bloco.data_local = data_local_no_fuso(novo_inicio, usuario.fuso)

        for campo, valor in campos.items():
            setattr(bloco, campo, valor)

        # Editar uma instância gerada pelo modelo a desvincula para não ser sobrescrita.
        # Se a data local mudou, limpa `modelo_bloco_id` para não colidir na constraint
        # `uq_bloco_modelo_data_local` caso já exista instância do modelo na nova data.
        if bloco.modelo_bloco_id is not None:
            bloco.desvinculado = True
            if bloco.data_local != data_local_anterior:
                bloco.modelo_bloco_id = None

        bloco.versao += 1
        await session.commit()
        recarregado = await repo.obter_do_usuario(usuario.id, bloco.id)
        assert recarregado is not None
        return serializar_bloco(recarregado)

    return serializar_bloco(bloco)


@router.delete("/{bloco_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_bloco(
    bloco_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> None:
    repo = BlocoRepository(session)
    bloco = await repo.obter_do_usuario(usuario.id, bloco_id)
    if bloco is None:
        raise NaoEncontradoError("Bloco não encontrado")

    bloco.excluido_em = datetime.now(UTC)
    bloco.versao += 1
    await session.commit()


@router.post(
    "/{bloco_id}/confirmar",
    response_model=ExecucaoRead,
    status_code=status.HTTP_201_CREATED,
)
async def confirmar_bloco_como_planejado(
    bloco_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ExecucaoRead:
    """Cria uma `Execucao` concluída idêntica ao bloco planejado ('Fiz como planejado')."""
    repo = BlocoRepository(session)
    bloco = await repo.obter_do_usuario(usuario.id, bloco_id)
    if bloco is None:
        raise NaoEncontradoError("Bloco não encontrado")

    pausas_exec = [PausaExecucao(inicio=p.inicio, fim=p.fim) for p in bloco.pausas_planejadas]
    liq = calcular_segundos_liquidos_bloco(bloco)

    exec_repo = ExecucaoRepository(session)
    execucao = Execucao(
        usuario_id=usuario.id,
        categoria_id=bloco.categoria_id,
        bloco_id=bloco.id,
        inicio=bloco.inicio,
        fim=bloco.fim,
        status="concluida",
        origem="confirmacao",
        segundos_liquidos=liq,
        pausas=pausas_exec,
    )
    await exec_repo.criar(execucao)
    await session.commit()
    recarregada = await exec_repo.obter_do_usuario(usuario.id, execucao.id)
    assert recarregada is not None
    return ExecucaoRead.model_validate(recarregada)
