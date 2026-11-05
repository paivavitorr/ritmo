from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execucao import Execucao


class ExecucaoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def listar_por_intervalo_utc(
        self, usuario_id: UUID, inicio_utc: datetime, fim_utc: datetime
    ) -> list[Execucao]:
        stmt = (
            select(Execucao)
            .options(selectinload(Execucao.pausas))
            .where(
                Execucao.usuario_id == usuario_id,
                Execucao.excluido_em.is_(None),
                Execucao.inicio < fim_utc,
                (Execucao.fim.is_(None)) | (Execucao.fim > inicio_utc),
            )
            .order_by(Execucao.inicio.asc())
        )
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def obter_do_usuario(self, usuario_id: UUID, execucao_id: UUID) -> Execucao | None:
        stmt = (
            select(Execucao)
            .options(selectinload(Execucao.pausas))
            .where(
                Execucao.id == execucao_id,
                Execucao.usuario_id == usuario_id,
                Execucao.excluido_em.is_(None),
            )
        )
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def listar_em_andamento(
        self, usuario_id: UUID, for_update: bool = False
    ) -> list[Execucao]:
        stmt = (
            select(Execucao)
            .options(selectinload(Execucao.pausas))
            .where(
                Execucao.usuario_id == usuario_id,
                Execucao.excluido_em.is_(None),
                Execucao.status == "em_andamento",
                Execucao.fim.is_(None),
            )
            .order_by(Execucao.inicio.desc())
        )
        if for_update:
            stmt = stmt.with_for_update()
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def listar_por_bloco(self, usuario_id: UUID, bloco_id: UUID) -> list[Execucao]:
        stmt = (
            select(Execucao)
            .options(selectinload(Execucao.pausas))
            .where(
                Execucao.usuario_id == usuario_id,
                Execucao.bloco_id == bloco_id,
                Execucao.excluido_em.is_(None),
            )
            .order_by(Execucao.inicio.asc())
        )
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def criar(self, execucao: Execucao) -> Execucao:
        self.session.add(execucao)
        await self.session.flush()
        return execucao
