from datetime import date, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db import Base, EntidadeMixin, TimestampMixin

TipoBloco = Literal["rotina", "compromisso"]


class Bloco(EntidadeMixin, Base):
    """Instância concreta de um bloco de tempo em uma data local."""

    __tablename__ = "bloco"
    __table_args__ = (
        CheckConstraint("fim > inicio", name="fim_maior_que_inicio"),
        UniqueConstraint(
            "modelo_bloco_id",
            "data_local",
            name="uq_bloco_modelo_data_local",
        ),
        Index("ix_bloco_usuario_data_local", "usuario_id", "data_local"),
        Index("ix_bloco_usuario_atualizado_em", "usuario_id", "atualizado_em"),
    )

    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("usuario.id", ondelete="CASCADE"))
    categoria_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("categoria.id", ondelete="RESTRICT"), index=True
    )
    modelo_bloco_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("modelo_bloco.id", ondelete="SET NULL"), nullable=True, default=None
    )
    tipo: Mapped[str] = mapped_column(String(20), default="rotina")
    titulo: Mapped[str] = mapped_column(String(120))
    notas: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    data_local: Mapped[date] = mapped_column(Date, index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    desvinculado: Mapped[bool] = mapped_column(Boolean, default=False)

    pausas_planejadas: Mapped[list["PausaPlanejada"]] = relationship(
        back_populates="bloco",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PausaPlanejada.inicio",
    )


class PausaPlanejada(TimestampMixin, Base):
    __tablename__ = "pausa_planejada"
    __table_args__ = (CheckConstraint("fim > inicio", name="fim_maior_que_inicio"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    bloco_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("bloco.id", ondelete="CASCADE"), index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    bloco: Mapped[Bloco] = relationship(back_populates="pausas_planejadas")
