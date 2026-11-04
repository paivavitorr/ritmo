from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, MetaData, Uuid, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool
from uuid6 import uuid7

from app.config import get_settings

# Convenção de nomes estável para constraints (migrações Alembic previsíveis).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Campos de auditoria/sincronização comuns a todas as entidades."""

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EntidadeMixin(TimestampMixin):
    """Mixin base com UUIDv7, controle otimista de versão e soft delete."""

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    versao: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    excluido_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


_settings = get_settings()
_is_sqlite_memory = _settings.database_url.endswith(":memory:")
engine = create_async_engine(
    _settings.database_url,
    echo=_settings.sql_echo,
    pool_pre_ping=not _is_sqlite_memory,
    poolclass=StaticPool if _is_sqlite_memory else None,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
