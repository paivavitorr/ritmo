from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter

from app.core.tempo import garantir_utc
from app.dependencies import CurrentUserDep, SessionDep
from app.models.bloco import Bloco, PausaPlanejada
from app.models.execucao import Execucao, PausaExecucao
from app.repositories.bloco import BlocoRepository
from app.repositories.execucao import ExecucaoRepository
from app.schemas.sync import (
    ItemMutacaoSync,
    ItemResultadoSync,
    SyncBatchRequest,
    SyncBatchResponse,
)
from app.services.horas_liquidas import Intervalo, segundos_liquidos

router = APIRouter(prefix="/sync", tags=["sync"])


async def _processar_mutacao_bloco(
    m: ItemMutacaoSync,
    usuario_id: object,
    session: SessionDep,
) -> ItemResultadoSync:
    repo = BlocoRepository(session)
    bloco = await repo.obter_do_usuario(usuario_id, m.entidade_id)  # type: ignore[arg-type]

    if m.acao == "excluir":
        if bloco is not None and bloco.excluido_em is None:
            bloco.excluido_em = datetime.now(UTC)
            bloco.versao += 1
            return ItemResultadoSync(
                mutacao_id=m.id, status="aplicado", versao_servidor=bloco.versao
            )
        return ItemResultadoSync(mutacao_id=m.id, status="ignorado", mensagem="Já excluído")

    if m.acao == "criar":
        if bloco is not None:
            # Já existe no servidor: LWW com verificação de timestamp
            if garantir_utc(bloco.atualizado_em) > garantir_utc(m.criado_em):
                return ItemResultadoSync(
                    mutacao_id=m.id,
                    status="ignorado",
                    mensagem="Alteração no servidor é mais recente",
                    versao_servidor=bloco.versao,
                )
            for k, v in m.payload.items():
                if k not in {"id", "usuario_id", "pausas"} and hasattr(bloco, k):
                    if k in {"inicio", "fim"} and isinstance(v, str):
                        setattr(bloco, k, garantir_utc(datetime.fromisoformat(v)))
                    elif k == "data_local" and isinstance(v, str):
                        setattr(bloco, k, date.fromisoformat(v))
                    else:
                        setattr(bloco, k, v)
            bloco.versao += 1
            return ItemResultadoSync(
                mutacao_id=m.id, status="aplicado", versao_servidor=bloco.versao
            )

        pausas_data = m.payload.get("pausas", [])
        pausas_orm = []
        if isinstance(pausas_data, list):
            for p in pausas_data:
                if isinstance(p, dict):
                    pausas_orm.append(
                        PausaPlanejada(
                            inicio=garantir_utc(datetime.fromisoformat(str(p["inicio"]))),
                            fim=garantir_utc(datetime.fromisoformat(str(p["fim"]))),
                        )
                    )

        data_local_val = m.payload.get("data_local")
        dt_local = date.fromisoformat(str(data_local_val)) if data_local_val else m.criado_em.date()
        novo = Bloco(
            id=m.entidade_id,
            usuario_id=usuario_id,
            categoria_id=UUID(str(m.payload["categoria_id"])),
            tipo=m.payload.get("tipo", "rotina"),
            titulo=m.payload.get("titulo", "Sem título"),
            notas=m.payload.get("notas"),
            data_local=dt_local,
            inicio=garantir_utc(datetime.fromisoformat(str(m.payload["inicio"]))),
            fim=garantir_utc(datetime.fromisoformat(str(m.payload["fim"]))),
            pausas_planejadas=pausas_orm,
        )
        await repo.criar(novo)
        return ItemResultadoSync(mutacao_id=m.id, status="aplicado", versao_servidor=novo.versao)

    if m.acao == "atualizar":
        if bloco is None:
            return ItemResultadoSync(
                mutacao_id=m.id, status="erro", mensagem="Bloco não encontrado"
            )
        # Last-Write-Wins: verifica timestamp
        if garantir_utc(bloco.atualizado_em) > garantir_utc(m.criado_em):
            return ItemResultadoSync(
                mutacao_id=m.id,
                status="ignorado",
                mensagem="Alteração no servidor é mais recente",
                versao_servidor=bloco.versao,
            )
        for k, v in m.payload.items():
            if k not in {"id", "usuario_id", "pausas"} and hasattr(bloco, k):
                if k in {"inicio", "fim"} and isinstance(v, str):
                    setattr(bloco, k, garantir_utc(datetime.fromisoformat(v)))
                elif k == "data_local" and isinstance(v, str):
                    setattr(bloco, k, date.fromisoformat(v))
                else:
                    setattr(bloco, k, v)
        bloco.versao += 1
        return ItemResultadoSync(mutacao_id=m.id, status="aplicado", versao_servidor=bloco.versao)

    return ItemResultadoSync(mutacao_id=m.id, status="ignorado")


async def _processar_mutacao_execucao(
    m: ItemMutacaoSync,
    usuario_id: object,
    session: SessionDep,
) -> ItemResultadoSync:
    repo = ExecucaoRepository(session)
    execucao = await repo.obter_do_usuario(usuario_id, m.entidade_id)  # type: ignore[arg-type]

    if m.acao == "excluir":
        if execucao is not None and execucao.excluido_em is None:
            execucao.excluido_em = datetime.now(UTC)
            execucao.versao += 1
            return ItemResultadoSync(
                mutacao_id=m.id, status="aplicado", versao_servidor=execucao.versao
            )
        return ItemResultadoSync(mutacao_id=m.id, status="ignorado")

    if m.acao in {"criar", "atualizar"}:
        if execucao is None:
            ini = garantir_utc(datetime.fromisoformat(str(m.payload["inicio"])))
            fim_str = m.payload.get("fim")
            fim = garantir_utc(datetime.fromisoformat(str(fim_str))) if fim_str else None
            pausas_orm = []
            pausas_raw = m.payload.get("pausas")
            pausas_list = pausas_raw if isinstance(pausas_raw, list) else []
            for p in pausas_list:
                if isinstance(p, dict):
                    p_fim = (
                        garantir_utc(datetime.fromisoformat(str(p["fim"])))
                        if p.get("fim")
                        else None
                    )
                    pausas_orm.append(
                        PausaExecucao(
                            inicio=garantir_utc(datetime.fromisoformat(str(p["inicio"]))),
                            fim=p_fim,
                        )
                    )
            liq = 0
            if fim is not None:
                liq = segundos_liquidos(
                    Intervalo(ini, fim),
                    [
                        Intervalo(p.inicio, p.fim)
                        for p in pausas_orm
                        if p.fim is not None and p.fim > p.inicio
                    ],
                )
            nova = Execucao(
                id=m.entidade_id,
                usuario_id=usuario_id,
                categoria_id=UUID(str(m.payload["categoria_id"])),
                bloco_id=UUID(str(m.payload["bloco_id"])) if m.payload.get("bloco_id") else None,
                inicio=ini,
                fim=fim,
                status=m.payload.get("status", "concluida"),
                origem=m.payload.get("origem", "manual"),
                segundos_liquidos=liq,
                pausas=pausas_orm,
            )
            await repo.criar(nova)
            return ItemResultadoSync(
                mutacao_id=m.id, status="aplicado", versao_servidor=nova.versao
            )

        # Atualização LWW
        for k, v in m.payload.items():
            if k not in {"id", "usuario_id", "pausas"} and hasattr(execucao, k):
                if k in {"inicio", "fim"} and isinstance(v, str):
                    setattr(execucao, k, garantir_utc(datetime.fromisoformat(v)))
                else:
                    setattr(execucao, k, v)
        if execucao.fim is not None and execucao.fim > execucao.inicio:
            execucao.segundos_liquidos = segundos_liquidos(
                Intervalo(execucao.inicio, execucao.fim),
                [
                    Intervalo(p.inicio, p.fim)
                    for p in execucao.pausas
                    if p.fim is not None and p.fim > p.inicio
                ],
            )
        execucao.versao += 1
        return ItemResultadoSync(
            mutacao_id=m.id, status="aplicado", versao_servidor=execucao.versao
        )

    return ItemResultadoSync(mutacao_id=m.id, status="ignorado")


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
                if m.entidade == "bloco":
                    res = await _processar_mutacao_bloco(m, usuario.id, session)
                elif m.entidade == "execucao":
                    res = await _processar_mutacao_execucao(m, usuario.id, session)
                else:
                    res = ItemResultadoSync(
                        mutacao_id=m.id, status="ignorado", mensagem="Entidade não suportada"
                    )
            resultados.append(res)
        except Exception as e:
            resultados.append(ItemResultadoSync(mutacao_id=m.id, status="erro", mensagem=str(e)))

    await session.commit()
    return SyncBatchResponse(processadas=len(resultados), resultados=resultados)
