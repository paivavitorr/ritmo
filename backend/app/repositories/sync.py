from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bloco import Bloco
from app.models.categoria import Categoria
from app.models.execucao import Execucao
from app.models.modelo_semana import ModeloBloco


class SyncRepository:
    """Acesso a entidades sincronizáveis, incluindo as excluídas (soft delete)."""

    def __init__(self, session: AsyncSession, usuario_id: UUID) -> None:
        self.session = session
        self.usuario_id = usuario_id

    async def obter[T: (Bloco, Categoria, Execucao, ModeloBloco)](
        self, modelo: type[T], entidade_id: UUID
    ) -> T | None:
        stmt = select(modelo).where(modelo.id == entidade_id, modelo.usuario_id == self.usuario_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def id_pertence_a_outro_usuario[T: (Bloco, Categoria, Execucao, ModeloBloco)](
        self, modelo: type[T], entidade_id: UUID
    ) -> bool:
        stmt = select(modelo.id).where(
            modelo.id == entidade_id, modelo.usuario_id != self.usuario_id
        )
        return (await self.session.execute(stmt)).first() is not None

    async def listar_alteradas[T: (Bloco, Categoria, Execucao, ModeloBloco)](
        self, modelo: type[T], desde: datetime | None, limite: int
    ) -> list[T]:
        """Entidades (ativas e excluídas) com `atualizado_em > desde`, mais antigas primeiro."""
        stmt = select(modelo).where(modelo.usuario_id == self.usuario_id)
        if desde is not None:
            stmt = stmt.where(modelo.atualizado_em > desde)
        stmt = stmt.order_by(modelo.atualizado_em.asc(), modelo.id.asc()).limit(limite)
        return list((await self.session.execute(stmt)).scalars().all())
