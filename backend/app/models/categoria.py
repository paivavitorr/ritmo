from typing import Literal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, EntidadeMixin

CorCategoria = Literal[
    "ardosia",
    "glicinia",
    "salvia",
    "ceu",
    "manteiga",
    "rosa-cha",
    "pessego",
]

CORES_CATEGORIA: tuple[CorCategoria, ...] = (
    "ardosia",
    "glicinia",
    "salvia",
    "ceu",
    "manteiga",
    "rosa-cha",
    "pessego",
)


class Categoria(EntidadeMixin, Base):
    __tablename__ = "categoria"
    __table_args__ = (Index("ix_categoria_usuario_atualizado_em", "usuario_id", "atualizado_em"),)

    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("usuario.id", ondelete="CASCADE"))
    nome: Mapped[str] = mapped_column(String(40))
    cor: Mapped[str] = mapped_column(String(20))
    icone: Mapped[str | None] = mapped_column(String(40), nullable=True, default=None)
    conta_como_produtiva: Mapped[bool] = mapped_column(Boolean, default=True)
    meta_semanal_min: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    ordem: Mapped[int] = mapped_column(SmallInteger, default=0)
