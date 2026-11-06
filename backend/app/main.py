import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import registrar_exception_handlers
from app.core.logging import RequestIdMiddleware, configurar_logging
from app.db import engine
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
from app.worker import loop_despachador


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configurar_logging(settings.ambiente)
    parar = asyncio.Event()
    tarefa_worker: asyncio.Task[None] | None = None
    # Loop embutido só quando ativo; em produção use `python -m app.worker`.
    if settings.despachador_ativo and settings.ambiente != "teste":
        tarefa_worker = asyncio.create_task(loop_despachador(parar))

    yield

    if tarefa_worker is not None:
        parar.set()
        await tarefa_worker

    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ritmo API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_habilitado else None,
        redoc_url="/redoc" if settings.docs_habilitado else None,
        openapi_url="/openapi.json" if settings.docs_habilitado else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origens,
        allow_credentials=True,  # refresh token em cookie httpOnly
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestIdMiddleware)  # mais externo: cobre CORS e respostas de erro

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
