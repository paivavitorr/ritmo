import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool

# Testes usam SQLite em memória compartilhada (StaticPool) para manter as tabelas
# criadas durante a fixture ao longo de todas as conexões do teste.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import app.models  # noqa: F401
from app.db import Base, engine
from app.main import create_app


@pytest.fixture(autouse=True)
async def _preparar_banco() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


__all__ = ["StaticPool"]
