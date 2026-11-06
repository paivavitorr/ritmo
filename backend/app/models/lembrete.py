from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.db import Base, EntidadeMixin, TimestampMixin

StatusLembrete = Literal[
    "pendente",
    "enviando",
    "disparado",
    "cancelado",
    "erro",
    "sem_dispositivo",
    "expirado",
]


class PushAssinatura(TimestampMixin, Base):
    """Assinatura Web Push do navegador do usuário."""

    __tablename__ = "push_assinatura"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True, index=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(String(100))
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class Lembrete(EntidadeMixin, Base):
    """Agendamento de notificação antes do início de um bloco."""

    __tablename__ = "lembrete"
    __table_args__ = (
        Index(
            "ix_lembrete_disparar_em_pendente",
            "disparar_em",
            postgresql_where=text("status = 'pendente'"),
            sqlite_where=text("status = 'pendente'"),
        ),
    )

    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    bloco_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("bloco.id", ondelete="CASCADE"), index=True
    )
    disparar_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    antecedencia_min: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(20), default="pendente", index=True)
    titulo: Mapped[str] = mapped_column(String(150))
    corpo: Mapped[str | None] = mapped_column(Text, nullable=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    tentativa_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    ultimo_erro: Mapped[str | None] = mapped_column(Text, nullable=True)
