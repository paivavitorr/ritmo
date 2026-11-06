"""Worker de lembretes: `python -m app.worker`.

Roda o loop de despacho de Web Push fora da API, com shutdown gracioso em SIGTERM/SIGINT.
"""

import asyncio
import contextlib
import logging
import signal

from app.config import get_settings
from app.core.logging import configurar_logging
from app.db import SessionLocal, engine
from app.services.lembrete import processar_lembretes_pendentes

logger = logging.getLogger(__name__)

INTERVALO_SEG = 30


async def loop_despachador(parar: asyncio.Event, intervalo: float = INTERVALO_SEG) -> None:
    """Despacha lembretes pendentes a cada `intervalo` segundos até `parar` ser sinalizado."""
    while not parar.is_set():
        try:
            async with SessionLocal() as session:
                await processar_lembretes_pendentes(session)
        except Exception:
            logger.exception("Erro no ciclo de despacho de lembretes")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(parar.wait(), timeout=intervalo)


async def main() -> None:
    configurar_logging(get_settings().ambiente)
    parar = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sinal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sinal, parar.set)

    logger.info("Worker de lembretes iniciado")
    try:
        await loop_despachador(parar)
    finally:
        await engine.dispose()
        logger.info("Worker de lembretes encerrado")


if __name__ == "__main__":
    asyncio.run(main())
