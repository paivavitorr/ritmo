import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

# Testes unitários usam SQLite em memória; integração real roda contra o Postgres do compose.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
