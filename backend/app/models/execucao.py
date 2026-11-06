from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db import Base, EntidadeMixin, TimestampMixin

StatusExecucao = Literal["em_andamento", "concluida", "parcial", "pulada"]
OrigemExecucao = Literal["cronometro", "confirmacao", "manual"]


class Execucao(EntidadeMixin, Base):
    """Registro do tempo realmente executado (com ou sem bloco planejado)."""

    __tablename__ = "execucao"
    __table_args__ = (
        # Um único cronômetro em andamento por usuário.
        Index(
            "uq_execucao_usuario_em_andamento",
            "usuario_id",
            unique=True,
            postgresql_where=text("status = 'em_andamento' AND excluido_em IS NULL"),
            sqlite_where=text("status = 'em_andamento' AND excluido_em IS NULL"),
        ),
        Index("ix_execucao_usuario_inicio", "usuario_id", "inicio"),
        Index("ix_execucao_usuario_atualizado_em", "usuario_id", "atualizado_em"),
    )

    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("usuario.id", ondelete="CASCADE"))
    categoria_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("categoria.id", ondelete="RESTRICT"), index=True
    )
    bloco_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("bloco.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(String(20), default="em_andamento")
    origem: Mapped[str] = mapped_column(String(20), default="cronometro")
    segundos_liquidos: Mapped[int] = mapped_column(Integer, default=0)

    pausas: Mapped[list["PausaExecucao"]] = relationship(
        back_populates="execucao",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PausaExecucao.inicio",
    )


class PausaExecucao(TimestampMixin, Base):
    __tablename__ = "pausa_execucao"
    __table_args__ = (CheckConstraint("fim IS NULL OR fim > inicio", name="fim_valido"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    execucao_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("execucao.id", ondelete="CASCADE"), index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    execucao: Mapped[Execucao] = relationship(back_populates="pausas")
