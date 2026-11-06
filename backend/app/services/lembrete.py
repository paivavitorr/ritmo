import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.tempo import garantir_utc
from app.models.bloco import Bloco
from app.models.lembrete import Lembrete
from app.repositories.lembrete import MAX_TENTATIVAS, LembreteRepository

logger = logging.getLogger(__name__)

BACKOFF_SEGUNDOS = (30, 120, 600)
RETRY_AFTER_MAXIMO_S = 3600
ENVIOS_SIMULTANEOS = 10
TOLERANCIA_ATRASO_AGENDAMENTO = timedelta(minutes=2)


@dataclass(frozen=True, slots=True)
class ResultadoEnvio:
    """Resultado de um envio Web Push a uma assinatura."""

    estado: Literal["ok", "expirada", "limitada", "erro"]
    retry_after_s: int | None = None
    erro: str | None = None


@dataclass(frozen=True, slots=True)
class _AssinaturaEnvio:
    id: UUID
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True, slots=True)
class _TrabalhoEnvio:
    lembrete_id: UUID
    payload: dict[str, object]
    assinaturas: tuple[_AssinaturaEnvio, ...]


def _ler_retry_after(valor: str | None) -> int | None:
    if valor is None:
        return None
    try:
        return max(1, min(int(valor), RETRY_AFTER_MAXIMO_S))
    except ValueError:
        return None  # data HTTP (formato raro em push services): usa o backoff


def disparar_notificacao_push(
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: Mapping[str, object],
    timeout: int = 5,
) -> ResultadoEnvio:
    """Envia payload JSON via Web Push protocolo VAPID (chamada síncrona e bloqueante)."""
    settings = get_settings()
    subscription_info = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": p256dh,
            "auth": auth,
        },
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_claim_email},
            timeout=timeout,
        )
        return ResultadoEnvio("ok")
    except WebPushException as ex:
        logger.warning("Falha ao enviar web push para %s: %s", endpoint, ex)
        resposta = ex.response
        codigo = resposta.status_code if resposta is not None else None
        if codigo in {404, 410}:
            return ResultadoEnvio("expirada", erro=str(ex))
        if codigo == 429:
            retry = _ler_retry_after(resposta.headers.get("Retry-After"))
            return ResultadoEnvio("limitada", retry_after_s=retry, erro=str(ex))
        return ResultadoEnvio("erro", erro=str(ex))
    except Exception as ex:
        logger.warning("Erro inesperado no web push para %s: %s", endpoint, ex)
        return ResultadoEnvio("erro", erro=str(ex))


def _titulo_lembrete(antecedencia_min: int, titulo_bloco: str) -> str:
    if antecedencia_min <= 0:
        return f"Agora: {titulo_bloco}"
    return f"Em {antecedencia_min} min: {titulo_bloco}"


async def agendar_lembrete_para_bloco(
    session: AsyncSession,
    bloco: Bloco,
    antecedencia_min: int,
    *,
    antecedencias: Sequence[int] | None = None,
    agora: datetime | None = None,
) -> Lembrete | None:
    """Recria os lembretes pendentes do bloco (um por antecedência).

    `antecedencias` (ex.: `ModeloBloco.lembretes`) tem prioridade sobre `antecedencia_min`
    (padrão do usuário) quando não vazia. Não recria lembrete já enviado para o mesmo horário.
    Retorna o primeiro lembrete criado.
    """
    agora = garantir_utc(agora) if agora is not None else datetime.now(UTC)
    repo = LembreteRepository(session)
    await repo.cancelar_lembretes_do_bloco(bloco.id)

    valores = sorted({a for a in (antecedencias or []) if a >= 0}) or [antecedencia_min]
    primeiro: Lembrete | None = None
    for antecedencia in valores:
        disparar_em = garantir_utc(bloco.inicio) - timedelta(minutes=antecedencia)
        # Disparo já vencido há mais que a tolerância: não cria lembrete no passado
        if disparar_em < agora - TOLERANCIA_ATRASO_AGENDAMENTO:
            continue
        if await repo.existe_disparado(bloco.id, antecedencia, disparar_em):
            continue
        lembrete = await repo.criar_lembrete(
            Lembrete(
                usuario_id=bloco.usuario_id,
                bloco_id=bloco.id,
                disparar_em=disparar_em,
                antecedencia_min=antecedencia,
                status="pendente",
                titulo=_titulo_lembrete(antecedencia, bloco.titulo),
                corpo="Seu próximo bloco de rotina começa em breve.",
            )
        )
        primeiro = primeiro or lembrete
    return primeiro


async def _preparar_trabalhos(
    repo: LembreteRepository, lote: Sequence[Lembrete], agora: datetime
) -> list[_TrabalhoEnvio]:
    """Fase 1 (dentro da transação): resolve o destino de cada lembrete reivindicado."""
    blocos = await repo.obter_inicio_dos_blocos([lemb.bloco_id for lemb in lote])
    assinaturas = await repo.listar_assinaturas_de_usuarios(
        list({lemb.usuario_id for lemb in lote})
    )

    trabalhos: list[_TrabalhoEnvio] = []
    for lemb in lote:
        info = blocos.get(lemb.bloco_id)
        if info is None or info[1] is not None:
            lemb.status = "cancelado"
        elif agora > garantir_utc(info[0]):
            lemb.status = "expirado"  # o bloco já começou: aviso perdeu o sentido
        elif not assinaturas[lemb.usuario_id]:
            lemb.status = "sem_dispositivo"
        else:
            trabalhos.append(
                _TrabalhoEnvio(
                    lembrete_id=lemb.id,
                    payload={
                        "titulo": lemb.titulo,
                        "corpo": lemb.corpo or "Seu próximo bloco de rotina começa em breve.",
                        "url": "/",
                        "lembrete_id": str(lemb.id),
                        "bloco_id": str(lemb.bloco_id),
                    },
                    assinaturas=tuple(
                        _AssinaturaEnvio(a.id, a.endpoint, a.p256dh, a.auth)
                        for a in assinaturas[lemb.usuario_id]
                    ),
                )
            )
            continue
        lemb.versao += 1
    return trabalhos


async def _enviar_trabalhos(
    trabalhos: Sequence[_TrabalhoEnvio],
) -> list[list[ResultadoEnvio]]:
    """Fase 2 (fora de qualquer transação): envia em threads, com concorrência limitada."""
    limite = asyncio.Semaphore(ENVIOS_SIMULTANEOS)

    async def enviar(trabalho: _TrabalhoEnvio, ass: _AssinaturaEnvio) -> ResultadoEnvio:
        async with limite:
            try:
                return await asyncio.to_thread(
                    disparar_notificacao_push,
                    ass.endpoint,
                    ass.p256dh,
                    ass.auth,
                    trabalho.payload,
                )
            except Exception as ex:
                logger.warning(
                    "Erro ao despachar push do lembrete %s: %s", trabalho.lembrete_id, ex
                )
                return ResultadoEnvio("erro", erro=str(ex))

    return [
        list(await asyncio.gather(*(enviar(t, ass) for ass in t.assinaturas))) for t in trabalhos
    ]


def _atraso_proxima_tentativa(tentativas: int, resultados: Sequence[ResultadoEnvio]) -> timedelta:
    retry_after = max(
        (r.retry_after_s for r in resultados if r.estado == "limitada" and r.retry_after_s),
        default=None,
    )
    if retry_after is not None:
        return timedelta(seconds=retry_after)
    indice = min(max(tentativas, 1), len(BACKOFF_SEGUNDOS)) - 1
    return timedelta(seconds=BACKOFF_SEGUNDOS[indice])


async def _registrar_resultado(
    session: AsyncSession,
    repo: LembreteRepository,
    trabalho: _TrabalhoEnvio,
    resultados: Sequence[ResultadoEnvio],
    agora: datetime,
) -> None:
    """Fase 3: grava o desfecho de um lembrete e commita (um commit por lembrete)."""
    lemb = await repo.obter_por_id(trabalho.lembrete_id)
    if lemb is None or lemb.status != "enviando":
        return

    expiradas = [
        ass.id
        for ass, res in zip(trabalho.assinaturas, resultados, strict=True)
        if res.estado == "expirada"
    ]
    await repo.remover_assinaturas(expiradas)

    erros = [r.erro for r in resultados if r.erro]
    if any(r.estado == "ok" for r in resultados):
        lemb.status = "disparado"
        lemb.ultimo_erro = None
    elif len(expiradas) == len(trabalho.assinaturas):
        lemb.status = "sem_dispositivo"
        lemb.ultimo_erro = erros[0] if erros else None
    else:
        lemb.ultimo_erro = erros[0] if erros else None
        if lemb.tentativas >= MAX_TENTATIVAS:
            lemb.status = "erro"
        else:
            lemb.status = "pendente"
            lemb.disparar_em = agora + _atraso_proxima_tentativa(lemb.tentativas, resultados)
    lemb.versao += 1
    await session.commit()


async def processar_lembretes_pendentes(
    session: AsyncSession,
    agora: datetime | None = None,
) -> int:
    """Despacha os lembretes vencidos em três fases, sem segurar lock durante HTTP.

    1. Reivindica um lote (`SKIP LOCKED`), marca `enviando` e commita.
    2. Envia fora da transação (pywebpush é síncrono: `asyncio.to_thread`).
    3. Grava o resultado, commitando por lembrete.

    Lembretes presos em `enviando` há mais de 5 min voltam a `pendente`. Retorna quantos
    lembretes foram enviados à fase de envio.
    """
    agora = garantir_utc(agora) if agora is not None else datetime.now(UTC)
    repo = LembreteRepository(session)

    await repo.recuperar_enviando_presos(agora)
    lote = await repo.reivindicar_para_disparo(agora)
    trabalhos = await _preparar_trabalhos(repo, lote, agora)
    await session.commit()
    if not trabalhos:
        return 0

    resultados = await _enviar_trabalhos(trabalhos)
    for trabalho, resultado in zip(trabalhos, resultados, strict=True):
        await _registrar_resultado(session, repo, trabalho, resultado, agora)
    return len(trabalhos)
