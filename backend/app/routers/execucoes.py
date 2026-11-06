from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.errors import AppError, ConflitoError, NaoEncontradoError
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
from app.services.execucao import (
    conflito_se_integridade,
    encerrar_execucao_aberta,
    recalcular_liquido,
    registrar_confirmacao_bloco,
    validar_coerencia,
)
from app.services.horas_liquidas import validar_periodo

router = APIRouter(prefix="/execucoes", tags=["execucoes"])


@router.get("", response_model=list[ExecucaoRead])
async def listar_execucoes(
    de: Annotated[date, Query(...)],
    ate: Annotated[date, Query(...)],
    usuario: CurrentUserDep,
    session: SessionDep,
) -> list[ExecucaoRead]:
    validar_periodo(de, ate)

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
    liq = recalcular_liquido(dados.inicio, dados.fim, pausas_orm)

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
    async with conflito_se_integridade(session, "Já existe uma execução com este id"):
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
    # `instante` no passado: só encerra a aberta se ela começou antes dele.
    for aberta in abertas:
        if garantir_utc(aberta.inicio) >= agora:
            raise ConflitoError(
                "Já existe uma execução em andamento iniciada após o instante informado"
            )
    for aberta in abertas:
        encerrar_execucao_aberta(aberta, agora, status_final="concluida")

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
    async with conflito_se_integridade(
        session, "Já existe uma execução em andamento ou o id informado já existe"
    ):
        await session.flush()  # grava o encerramento antes de inserir a nova
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
    bloco = await BlocoRepository(session).obter_do_usuario(usuario.id, dados.bloco_id)
    if bloco is None:
        raise NaoEncontradoError("Bloco não encontrado")

    execucao = await registrar_confirmacao_bloco(session, bloco, datetime.now(UTC), dados.status)
    return ExecucaoRead.model_validate(execucao)


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

    novo_inicio = dados.inicio if dados.inicio is not None else execucao.inicio
    novo_fim = dados.fim if dados.fim is not None else execucao.fim
    novo_status = dados.status if dados.status is not None else execucao.status

    substituir_pausas = "pausas" in campos and dados.pausas is not None
    pausas_finais: list[PausaExecucao] = []
    if substituir_pausas and dados.pausas is not None:
        for p in dados.pausas:
            kwargs_p: dict[str, object] = {"inicio": p.inicio, "fim": p.fim}
            if p.id is not None:
                kwargs_p["id"] = p.id
            pausas_finais.append(PausaExecucao(**kwargs_p))
        campos.pop("pausas")
    else:
        pausas_finais = list(execucao.pausas)

    validar_coerencia(novo_status, novo_inicio, novo_fim, pausas_finais)

    if substituir_pausas:
        execucao.pausas.clear()
        execucao.pausas.extend(pausas_finais)

    for campo, valor in campos.items():
        setattr(execucao, campo, valor)

    execucao.segundos_liquidos = recalcular_liquido(
        execucao.inicio, execucao.fim, list(execucao.pausas)
    )
    execucao.versao += 1
    async with conflito_se_integridade(session, "Já existe outra execução em andamento"):
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
    encerrar_execucao_aberta(execucao, garantir_utc(instante_req), status_final=status_final)

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
