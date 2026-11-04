from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import registrar_exception_handlers
from app.db import engine
from app.routers import auth, blocos, categorias, execucoes, modelos_semana, saude


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
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
    return app


app = create_app()
