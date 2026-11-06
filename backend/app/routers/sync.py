import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ValidationError

from app.core.errors import AppError
from app.core.tempo import data_local_no_fuso, garantir_utc
from app.db import EntidadeMixin
from app.dependencies import CurrentUserDep, SessionDep
from app.models.bloco import Bloco, PausaPlanejada
from app.models.categoria import Categoria
from app.models.execucao import Execucao, PausaExecucao
from app.models.modelo_semana import ModeloBloco
from app.models.usuario import Usuario
from app.repositories.bloco import BlocoRepository
from app.repositories.categoria import CategoriaRepository
from app.repositories.lembrete import LembreteRepository
from app.repositories.sync import SyncRepository
from app.routers.blocos import serializar_bloco
from app.schemas.bloco import BlocoCreate, BlocoUpdate
from app.schemas.categoria import CategoriaCreate, CategoriaRead, CategoriaUpdate
from app.schemas.execucao import ExecucaoRead
from app.schemas.modelo_semana import ModeloBlocoRead
from app.schemas.sync import (
    ExcluidoSync,
    ExecucaoSyncCreate,
    ExecucaoSyncUpdate,
    ItemMutacaoSync,
    ItemResultadoSync,
    SyncBatchRequest,
    SyncBatchResponse,
    SyncMudancasResponse,
    validar_pausas_no_intervalo,
)
from app.services.lembrete import agendar_lembrete_para_bloco
from app.services.sync import (
    LIMITE_MUDANCAS_POR_ENTIDADE,
    cursor_inicial,
    escolher_cursor,
    formatar_cursor,
    segundos_liquidos_execucao,
    tem_conflito_de_versao,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

MSG_REFERENCIA_INVALIDA = "Referência inválida"
MSG_ERRO_INTERNO = "Erro interno ao processar a mutação"


class _MutacaoRejeitada(Exception):
    """Falha de regra de negócio com mensagem segura para devolver ao cliente."""


def _resultado(
    m: ItemMutacaoSync,
    status: str,
    mensagem: str | None = None,
    versao: int | None = None,
    entidade: dict[str, object] | None = None,
) -> ItemResultadoSync:
    return ItemResultadoSync.model_validate(
        {
            "mutacao_id": m.id,
            "status": status,
            "mensagem": mensagem,
            "versao_servidor": versao,
            "entidade_servidor": entidade,
        }
    )


def _validar[S: BaseModel](schema: type[S], payload: dict[str, object]) -> S:
    """Valida o payload com o schema da entidade; campos desconhecidos/de servidor são ignorados."""
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        campos = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        detalhe = f": {', '.join(campos)}" if campos else ""
        raise _MutacaoRejeitada(f"Payload inválido{detalhe}") from exc


def _pre_atualizar(
    m: ItemMutacaoSync,
    entidade: EntidadeMixin | None,
    serializar: dict[str, object] | None,
) -> ItemResultadoSync | None:
    """Resultado antecipado de `atualizar` (inexistente/excluída ou conflito) ou `None`."""
    if entidade is None or entidade.excluido_em is not None:
        return _resultado(m, "ignorado", "Entidade não encontrada")
    if tem_conflito_de_versao(m.versao_base, entidade.versao):
        return _resultado(m, "conflito", "Conflito de versão", entidade.versao, serializar)
    return None


def _pre_excluir(m: ItemMutacaoSync, entidade: EntidadeMixin | None) -> ItemResultadoSync | None:
    if entidade is None:
        return _resultado(m, "ignorado", "Entidade não encontrada")
    if entidade.excluido_em is not None:
        return _resultado(m, "aplicado", "Já excluída", entidade.versao)
    return None


def _marcar_excluida(entidade: EntidadeMixin) -> None:
    entidade.excluido_em = datetime.now(UTC)
    entidade.versao += 1


async def _garantir_categoria(session: SessionDep, usuario: Usuario, categoria_id: UUID) -> None:
    if await CategoriaRepository(session).obter_do_usuario(usuario.id, categoria_id) is None:
        raise _MutacaoRejeitada(MSG_REFERENCIA_INVALIDA)


async def _garantir_bloco(session: SessionDep, usuario: Usuario, bloco_id: UUID) -> None:
    if await BlocoRepository(session).obter_do_usuario(usuario.id, bloco_id) is None:
        raise _MutacaoRejeitada(MSG_REFERENCIA_INVALIDA)


# --- Bloco ----------------------------------------------------------------------------------


async def _processar_bloco(
    m: ItemMutacaoSync, usuario: Usuario, session: SessionDep, repo: SyncRepository
) -> ItemResultadoSync:
    bloco = await repo.obter(Bloco, m.entidade_id)

    if m.acao == "excluir":
        antecipado = _pre_excluir(m, bloco)
        if antecipado is not None or bloco is None:
            return antecipado or _resultado(m, "ignorado")
        _marcar_excluida(bloco)
        await LembreteRepository(session).cancelar_lembretes_do_bloco(bloco.id)
        return _resultado(m, "aplicado", versao=bloco.versao)

    if m.acao == "criar":
        if bloco is not None:
            return _resultado(m, "aplicado", "Já existente", bloco.versao)
        if await repo.id_pertence_a_outro_usuario(Bloco, m.entidade_id):
            raise _MutacaoRejeitada(MSG_REFERENCIA_INVALIDA)
        dados = _validar(BlocoCreate, m.payload)
        await _garantir_categoria(session, usuario, dados.categoria_id)
        novo = Bloco(
            id=m.entidade_id,
            usuario_id=usuario.id,
            categoria_id=dados.categoria_id,
            tipo=dados.tipo,
            titulo=dados.titulo,
            notas=dados.notas,
            data_local=(
                dados.data_local
                if dados.data_local is not None
                else data_local_no_fuso(dados.inicio, usuario.fuso)
            ),
            inicio=dados.inicio,
            fim=dados.fim,
            desvinculado=False,
            pausas_planejadas=[
                PausaPlanejada(
                    **({"id": p.id} if p.id is not None else {}), inicio=p.inicio, fim=p.fim
                )
                for p in dados.pausas
            ],
        )
        session.add(novo)
        await session.flush()
        await agendar_lembrete_para_bloco(session, novo, usuario.antecedencia_padrao_min)
        return _resultado(m, "aplicado", versao=novo.versao)

    # atualizar
    antecipado = _pre_atualizar(
        m, bloco, serializar_bloco(bloco).model_dump(mode="json") if bloco else None
    )
    if antecipado is not None or bloco is None:
        return antecipado or _resultado(m, "ignorado")
    dados_up = _validar(BlocoUpdate, m.payload)
    campos = dados_up.model_dump(exclude_unset=True)
    if "categoria_id" in campos:
        await _garantir_categoria(session, usuario, campos["categoria_id"])

    novo_inicio = dados_up.inicio if dados_up.inicio is not None else garantir_utc(bloco.inicio)
    novo_fim = dados_up.fim if dados_up.fim is not None else garantir_utc(bloco.fim)
    if novo_fim <= novo_inicio:
        raise _MutacaoRejeitada("O fim do bloco deve ser posterior ao início")
    pausas = (
        [(p.inicio, p.fim) for p in dados_up.pausas]
        if dados_up.pausas is not None
        else [(garantir_utc(p.inicio), garantir_utc(p.fim)) for p in bloco.pausas_planejadas]
    )
    if any(p_ini < novo_inicio or p_fim > novo_fim for p_ini, p_fim in pausas):
        raise _MutacaoRejeitada("As pausas planejadas devem ficar contidas dentro do bloco")

    data_local_anterior = bloco.data_local
    if dados_up.pausas is not None:
        bloco.pausas_planejadas.clear()
        for p in dados_up.pausas:
            bloco.pausas_planejadas.append(
                PausaPlanejada(
                    **({"id": p.id} if p.id is not None else {}), inicio=p.inicio, fim=p.fim
                )
            )
    campos.pop("pausas", None)
    if "inicio" in campos and "data_local" not in campos:
        bloco.data_local = data_local_no_fuso(novo_inicio, usuario.fuso)
    for campo, valor in campos.items():
        setattr(bloco, campo, valor)

    # Editar instância gerada por modelo a desvincula (mesma regra do REST).
    if bloco.modelo_bloco_id is not None:
        bloco.desvinculado = True
        if bloco.data_local != data_local_anterior:
            bloco.modelo_bloco_id = None

    bloco.versao += 1
    await session.flush()
    await agendar_lembrete_para_bloco(session, bloco, usuario.antecedencia_padrao_min)
    return _resultado(m, "aplicado", versao=bloco.versao)


# --- Categoria ------------------------------------------------------------------------------


async def _processar_categoria(
    m: ItemMutacaoSync, usuario: Usuario, session: SessionDep, repo: SyncRepository
) -> ItemResultadoSync:
    categoria = await repo.obter(Categoria, m.entidade_id)

    if m.acao == "excluir":
        antecipado = _pre_excluir(m, categoria)
        if antecipado is not None or categoria is None:
            return antecipado or _resultado(m, "ignorado")
        if await CategoriaRepository(session).esta_em_uso_ativo(usuario.id, categoria.id):
            raise _MutacaoRejeitada("Não é possível excluir uma categoria que está em uso")
        _marcar_excluida(categoria)
        return _resultado(m, "aplicado", versao=categoria.versao)

    if m.acao == "criar":
        if categoria is not None:
            return _resultado(m, "aplicado", "Já existente", categoria.versao)
        if await repo.id_pertence_a_outro_usuario(Categoria, m.entidade_id):
            raise _MutacaoRejeitada(MSG_REFERENCIA_INVALIDA)
        dados = _validar(CategoriaCreate, m.payload)
        nova = Categoria(
            id=m.entidade_id,
            usuario_id=usuario.id,
            nome=dados.nome,
            cor=dados.cor,
            icone=dados.icone,
            conta_como_produtiva=dados.conta_como_produtiva,
            meta_semanal_min=dados.meta_semanal_min,
            ordem=dados.ordem,
        )
        session.add(nova)
        await session.flush()
        return _resultado(m, "aplicado", versao=nova.versao)

    antecipado = _pre_atualizar(
        m,
        categoria,
        CategoriaRead.model_validate(categoria).model_dump(mode="json") if categoria else None,
    )
    if antecipado is not None or categoria is None:
        return antecipado or _resultado(m, "ignorado")
    for campo, valor in _validar(CategoriaUpdate, m.payload).model_dump(exclude_unset=True).items():
        setattr(categoria, campo, valor)
    categoria.versao += 1
    await session.flush()
    return _resultado(m, "aplicado", versao=categoria.versao)


# --- Execução -------------------------------------------------------------------------------


def _liquido(execucao: Execucao) -> int:
    return segundos_liquidos_execucao(
        execucao.inicio, execucao.fim, [(p.inicio, p.fim) for p in execucao.pausas]
    )


async def _processar_execucao(
    m: ItemMutacaoSync, usuario: Usuario, session: SessionDep, repo: SyncRepository
) -> ItemResultadoSync:
    execucao = await repo.obter(Execucao, m.entidade_id)

    if m.acao == "excluir":
        antecipado = _pre_excluir(m, execucao)
        if antecipado is not None or execucao is None:
            return antecipado or _resultado(m, "ignorado")
        _marcar_excluida(execucao)
        return _resultado(m, "aplicado", versao=execucao.versao)

    if m.acao == "criar":
        if execucao is not None:
            return _resultado(m, "aplicado", "Já existente", execucao.versao)
        if await repo.id_pertence_a_outro_usuario(Execucao, m.entidade_id):
            raise _MutacaoRejeitada(MSG_REFERENCIA_INVALIDA)
        dados = _validar(ExecucaoSyncCreate, m.payload)
        await _garantir_categoria(session, usuario, dados.categoria_id)
        if dados.bloco_id is not None:
            await _garantir_bloco(session, usuario, dados.bloco_id)
        pausas_orm = [
            PausaExecucao(**({"id": p.id} if p.id is not None else {}), inicio=p.inicio, fim=p.fim)
            for p in dados.pausas
        ]
        nova = Execucao(
            id=m.entidade_id,
            usuario_id=usuario.id,
            categoria_id=dados.categoria_id,
            bloco_id=dados.bloco_id,
            inicio=dados.inicio,
            fim=dados.fim,
            status=dados.status,
            origem=dados.origem,
            segundos_liquidos=segundos_liquidos_execucao(
                dados.inicio, dados.fim, [(p.inicio, p.fim) for p in dados.pausas]
            ),
            pausas=pausas_orm,
        )
        session.add(nova)
        await session.flush()
        return _resultado(m, "aplicado", versao=nova.versao)

    antecipado = _pre_atualizar(
        m,
        execucao,
        ExecucaoRead.model_validate(execucao).model_dump(mode="json") if execucao else None,
    )
    if antecipado is not None or execucao is None:
        return antecipado or _resultado(m, "ignorado")
    dados_up = _validar(ExecucaoSyncUpdate, m.payload)
    campos = dados_up.model_dump(exclude_unset=True)
    if "categoria_id" in campos:
        await _garantir_categoria(session, usuario, campos["categoria_id"])
    if campos.get("bloco_id") is not None:
        await _garantir_bloco(session, usuario, campos["bloco_id"])

    novo_ini = dados_up.inicio if dados_up.inicio is not None else garantir_utc(execucao.inicio)
    fim_base = dados_up.fim if dados_up.fim is not None else execucao.fim
    novo_fim = garantir_utc(fim_base) if fim_base is not None else None
    if novo_fim is not None and novo_fim <= novo_ini:
        raise _MutacaoRejeitada("O fim da execução deve ser posterior ao início")

    try:
        if dados_up.pausas is not None:
            validar_pausas_no_intervalo(novo_ini, novo_fim, dados_up.pausas)
        else:
            existentes = [
                (garantir_utc(p.inicio), garantir_utc(p.fim) if p.fim is not None else None)
                for p in execucao.pausas
            ]
            if any(
                p_ini < novo_ini
                or (novo_fim is not None and p_fim is not None and p_fim > novo_fim)
                for p_ini, p_fim in existentes
            ):
                raise ValueError("As pausas existentes ficam fora do novo intervalo")
    except ValueError as exc:
        raise _MutacaoRejeitada(str(exc)) from exc

    if dados_up.pausas is not None:
        execucao.pausas.clear()
        for p in dados_up.pausas:
            execucao.pausas.append(
                PausaExecucao(
                    **({"id": p.id} if p.id is not None else {}), inicio=p.inicio, fim=p.fim
                )
            )
    campos.pop("pausas", None)
    for campo, valor in campos.items():
        setattr(execucao, campo, valor)

    # Recalcula com as pausas efetivas (já atualizadas acima).
    execucao.segundos_liquidos = _liquido(execucao)
    execucao.versao += 1
    await session.flush()
    return _resultado(m, "aplicado", versao=execucao.versao)


async def _processar_mutacao(
    m: ItemMutacaoSync, usuario: Usuario, session: SessionDep
) -> ItemResultadoSync:
    repo = SyncRepository(session, usuario.id)
    if m.entidade == "bloco":
        return await _processar_bloco(m, usuario, session, repo)
    if m.entidade == "categoria":
        return await _processar_categoria(m, usuario, session, repo)
    if m.entidade == "execucao":
        return await _processar_execucao(m, usuario, session, repo)
    # Modelos semanais são geridos apenas via REST (materialização de blocos no servidor).
    return _resultado(m, "ignorado", "Entidade não suportada")


@router.post("/batch", response_model=SyncBatchResponse)
async def sincronizar_mutacoes(
    dados: SyncBatchRequest,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> SyncBatchResponse:
    resultados: list[ItemResultadoSync] = []

    for m in dados.mutacoes:
        try:
            async with session.begin_nested():
                res = await _processar_mutacao(m, usuario, session)
        except _MutacaoRejeitada as exc:
            res = _resultado(m, "erro", str(exc))
        except Exception:
            logger.exception("Falha ao processar mutação de sync %s", m.id)
            res = _resultado(m, "erro", MSG_ERRO_INTERNO)
        resultados.append(res)

    await session.commit()
    return SyncBatchResponse(processadas=len(resultados), resultados=resultados)


@router.get("/mudancas", response_model=SyncMudancasResponse)
async def listar_mudancas(
    usuario: CurrentUserDep,
    session: SessionDep,
    desde: Annotated[str | None, Query()] = None,
) -> SyncMudancasResponse:
    desde_dt: datetime | None = None
    if desde:
        try:
            desde_dt = garantir_utc(datetime.fromisoformat(desde))
        except ValueError as exc:
            raise AppError(422, "Parâmetro 'desde' inválido (use ISO 8601)", "validacao") from exc

    base = cursor_inicial(datetime.now(UTC))
    repo = SyncRepository(session, usuario.id)
    lim = LIMITE_MUDANCAS_POR_ENTIDADE
    blocos = await repo.listar_alteradas(Bloco, desde_dt, lim)
    categorias = await repo.listar_alteradas(Categoria, desde_dt, lim)
    execucoes = await repo.listar_alteradas(Execucao, desde_dt, lim)
    modelos = await repo.listar_alteradas(ModeloBloco, desde_dt, lim)

    truncados = [
        lista[-1].atualizado_em
        for lista in (blocos, categorias, execucoes, modelos)
        if len(lista) >= lim
    ]
    excluidos = (
        [ExcluidoSync(entidade="bloco", id=b.id) for b in blocos if b.excluido_em is not None]
        + [ExcluidoSync(entidade="categoria", id=c.id) for c in categorias if c.excluido_em]
        + [ExcluidoSync(entidade="execucao", id=e.id) for e in execucoes if e.excluido_em]
        + [ExcluidoSync(entidade="modelo_bloco", id=x.id) for x in modelos if x.excluido_em]
    )
    return SyncMudancasResponse(
        blocos=[serializar_bloco(b) for b in blocos if b.excluido_em is None],
        categorias=[CategoriaRead.model_validate(c) for c in categorias if c.excluido_em is None],
        execucoes=[ExecucaoRead.model_validate(e) for e in execucoes if e.excluido_em is None],
        modelos_bloco=[ModeloBlocoRead.model_validate(x) for x in modelos if x.excluido_em is None],
        excluidos=excluidos,
        cursor=formatar_cursor(escolher_cursor(base, truncados)),
        tem_mais=bool(truncados),
    )
