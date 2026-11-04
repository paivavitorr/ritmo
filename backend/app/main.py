from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import engine
from app.routers import saude


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
        allow_credentials=True,  # refresh token em cookie httpOnly (F1)
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(saude.router)
    return app


app = create_app()
