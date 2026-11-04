from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bloco import Bloco


class BlocoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def listar_por_periodo(self, usuario_id: UUID, de: date, ate: date) -> list[Bloco]:
        stmt = (
            select(Bloco)
            .options(selectinload(Bloco.pausas_planejadas))
            .where(
                Bloco.usuario_id == usuario_id,
                Bloco.excluido_em.is_(None),
                Bloco.data_local >= de,
                Bloco.data_local <= ate,
            )
            .order_by(Bloco.inicio.asc())
        )
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def obter_do_usuario(self, usuario_id: UUID, bloco_id: UUID) -> Bloco | None:
        stmt = (
            select(Bloco)
            .options(selectinload(Bloco.pausas_planejadas))
            .where(
                Bloco.id == bloco_id,
                Bloco.usuario_id == usuario_id,
                Bloco.excluido_em.is_(None),
            )
        )
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def obter_por_modelo_e_data(
        self,
        usuario_id: UUID,
        modelo_bloco_id: UUID,
        data_local: date,
        incluir_excluidos: bool = True,
    ) -> Bloco | None:
        stmt = (
            select(Bloco)
            .options(selectinload(Bloco.pausas_planejadas))
            .where(
                Bloco.usuario_id == usuario_id,
                Bloco.modelo_bloco_id == modelo_bloco_id,
                Bloco.data_local == data_local,
            )
        )
        if not incluir_excluidos:
            stmt = stmt.where(Bloco.excluido_em.is_(None))
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def listar_vinculados_por_periodo(
        self,
        usuario_id: UUID,
        de: date,
        ate: date,
        incluir_excluidos: bool = True,
    ) -> list[Bloco]:
        stmt = (
            select(Bloco)
            .options(selectinload(Bloco.pausas_planejadas))
            .where(
                Bloco.usuario_id == usuario_id,
                Bloco.modelo_bloco_id.is_not(None),
                Bloco.data_local >= de,
                Bloco.data_local <= ate,
            )
        )
        if not incluir_excluidos:
            stmt = stmt.where(Bloco.excluido_em.is_(None))
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def criar(self, bloco: Bloco) -> Bloco:
        self.session.add(bloco)
        await self.session.flush()
        return bloco
