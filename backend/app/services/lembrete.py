import asyncio
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.tempo import garantir_utc
from app.models.bloco import Bloco
from app.models.lembrete import Lembrete
from app.repositories.lembrete import LembreteRepository

logger = logging.getLogger(__name__)


def disparar_notificacao_push(
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: Mapping[str, object],
    timeout: int = 5,
) -> bool:
    """Envia payload JSON via Web Push protocolo VAPID (chamada síncrona)."""
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
        return True
    except WebPushException as ex:
        # 410 Gone ou 404 indica assinatura expirada/revogada no navegador
        logger.warning("Falha ao enviar web push para %s: %s", endpoint, ex)
        if ex.response and ex.response.status_code in {404, 410}:
            return False
        raise


async def agendar_lembrete_para_bloco(
    session: AsyncSession,
    bloco: Bloco,
    antecedencia_min: int,
) -> Lembrete | None:
    """Cancela lembretes anteriores e cria agendamento para o início do bloco menos antecedência."""
    repo = LembreteRepository(session)
    await repo.cancelar_lembretes_do_bloco(bloco.id)

    disparar_em = garantir_utc(bloco.inicio) - timedelta(minutes=antecedencia_min)
    # Se o momento de disparo já passou há mais de 2 minutos, não cria lembrete no passado
    if disparar_em < datetime.now(UTC) - timedelta(minutes=2):
        return None

    lembrete = Lembrete(
        usuario_id=bloco.usuario_id,
        bloco_id=bloco.id,
        disparar_em=disparar_em,
        antecedencia_min=antecedencia_min,
        status="pendente",
        titulo=f"Em {antecedencia_min} min: {bloco.titulo}",
        corpo="Seu próximo bloco de rotina começa em breve.",
    )
    return await repo.criar_lembrete(lembrete)


async def processar_lembretes_pendentes(session: AsyncSession) -> int:
    """Busca lembretes vencidos com SKIP LOCKED e envia via Web Push de forma não bloqueante."""
    agora = datetime.now(UTC)
    repo = LembreteRepository(session)
    pendentes = await repo.obter_pendentes_para_disparo(agora)

    disparados = 0
    for lembrete in pendentes:
        assinaturas = await repo.listar_assinaturas_usuario(lembrete.usuario_id)
        if not assinaturas:
            lembrete.status = "sem_dispositivo"
            lembrete.versao += 1
            continue

        payload: dict[str, object] = {
            "titulo": lembrete.titulo,
            "corpo": lembrete.corpo or "Seu próximo bloco de rotina começa em breve.",
            "url": "/",
            "lembrete_id": str(lembrete.id),
            "bloco_id": str(lembrete.bloco_id),
        }

        sucesso_algum = False
        for ass in assinaturas:
            try:
                ok = await asyncio.to_thread(
                    disparar_notificacao_push,
                    ass.endpoint,
                    ass.p256dh,
                    ass.auth,
                    payload,
                )
                if ok:
                    sucesso_algum = True
                else:
                    # Assinatura expirada: remove do banco
                    await session.delete(ass)
            except Exception as e:
                lembrete.ultimo_erro = str(e)
                logger.warning(
                    "Erro ao despachar push para lembrete %s no endpoint %s: %s",
                    lembrete.id,
                    ass.endpoint,
                    e,
                )

        lembrete.tentativas += 1
        if sucesso_algum:
            lembrete.status = "disparado"
        elif lembrete.tentativas >= 3:
            lembrete.status = "erro"
        # Se falhou mas tentativas < 3, continua "pendente" para retentar no próximo ciclo
        lembrete.versao += 1
        disparados += 1

    await session.commit()
    return disparados
