import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import registrar_exception_handlers
from app.db import SessionLocal, engine
from app.routers import (
    auth,
    blocos,
    categorias,
    execucoes,
    modelos_semana,
    push,
    resumo,
    saude,
    sync,
)
from app.services.lembrete import processar_lembretes_pendentes

logger = logging.getLogger(__name__)


async def _worker_despachador_lembretes() -> None:
    """Loop em segundo plano que despacha Web Push a cada 30 segundos."""
    while True:
        try:
            async with SessionLocal() as session:
                await processar_lembretes_pendentes(session)
        except Exception:
            logger.exception("Erro no ciclo de despacho de lembretes em segundo plano")
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    tarefa_worker: asyncio.Task[None] | None = None
    if settings.despachador_ativo and settings.ambiente != "teste":
        tarefa_worker = asyncio.create_task(_worker_despachador_lembretes())

    yield

    if tarefa_worker is not None:
        tarefa_worker.cancel()
        with suppress(asyncio.CancelledError):
            await tarefa_worker

    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Ritmo API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origens,
        allow_credentials=True,  # refresh token em cookie httpOnly
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registrar_exception_handlers(app)
    app.include_router(saude.router)
    app.include_router(auth.router)
    app.include_router(categorias.router)
    app.include_router(modelos_semana.router)
    app.include_router(blocos.router)
    app.include_router(execucoes.router)
    app.include_router(resumo.router)
    app.include_router(sync.router)
    app.include_router(push.router)
    return app


app = create_app()
