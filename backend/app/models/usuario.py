from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.db import Base, EntidadeMixin, TimestampMixin


class Usuario(EntidadeMixin, Base):
    __tablename__ = "usuario"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(Text)
    nome: Mapped[str] = mapped_column(String(100))
    fuso: Mapped[str] = mapped_column(String(64), default="America/Manaus")
    inicio_semana: Mapped[int] = mapped_column(SmallInteger, default=1)
    antecedencia_padrao_min: Mapped[int] = mapped_column(SmallInteger, default=10)


class SessaoRefresh(TimestampMixin, Base):
    """Sessão de refresh token com suporte a rotação e revogação em cadeia (família)."""

    __tablename__ = "sessao_refresh"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    familia_id: Mapped[UUID] = mapped_column(Uuid, index=True, default=uuid7)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    substituido_por_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, default=None)
