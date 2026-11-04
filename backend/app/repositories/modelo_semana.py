from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modelo_semana import ModeloBloco


class ModeloBlocoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def listar_do_usuario(
        self, usuario_id: UUID, apenas_ativos: bool = False
    ) -> list[ModeloBloco]:
        stmt = select(ModeloBloco).where(
            ModeloBloco.usuario_id == usuario_id,
            ModeloBloco.excluido_em.is_(None),
        )
        if apenas_ativos:
            stmt = stmt.where(ModeloBloco.ativo.is_(True))
        stmt = stmt.order_by(ModeloBloco.dia_semana.asc(), ModeloBloco.hora_inicio.asc())
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def obter_do_usuario(self, usuario_id: UUID, modelo_id: UUID) -> ModeloBloco | None:
        stmt = select(ModeloBloco).where(
            ModeloBloco.id == modelo_id,
            ModeloBloco.usuario_id == usuario_id,
            ModeloBloco.excluido_em.is_(None),
        )
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def criar(self, modelo: ModeloBloco) -> ModeloBloco:
        self.session.add(modelo)
        await self.session.flush()
        return modelo
