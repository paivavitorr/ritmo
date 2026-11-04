from datetime import time
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, SmallInteger, String, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, EntidadeMixin


class ModeloBloco(EntidadeMixin, Base):
    """Bloco da rotina semanal que se repete e pode ser materializado em datas."""

    __tablename__ = "modelo_bloco"

    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    categoria_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("categoria.id", ondelete="RESTRICT"), index=True
    )
    titulo: Mapped[str] = mapped_column(String(120))
    dia_semana: Mapped[int] = mapped_column(SmallInteger, index=True)  # 0=domingo .. 6=sábado
    hora_inicio: Mapped[time] = mapped_column(Time(timezone=False))
    hora_fim: Mapped[time] = mapped_column(Time(timezone=False))
    pausas: Mapped[list[dict[str, int]]] = mapped_column(JSON, default=list)
    lembretes: Mapped[list[int]] = mapped_column(JSON, default=list)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("pausas", [])
        kwargs.setdefault("lembretes", [])
        super().__init__(**kwargs)
