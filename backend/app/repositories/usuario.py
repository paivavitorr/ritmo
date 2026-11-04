from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usuario import SessaoRefresh, Usuario


class UsuarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        stmt = select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.excluido_em.is_(None),
        )
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def obter_por_email(self, email: str, incluir_excluidos: bool = False) -> Usuario | None:
        stmt = select(Usuario).where(Usuario.email == email.strip().lower())
        if not incluir_excluidos:
            stmt = stmt.where(Usuario.excluido_em.is_(None))
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def criar(self, usuario: Usuario) -> Usuario:
        self.session.add(usuario)
        await self.session.flush()
        return usuario


class SessaoRefreshRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def criar(self, sessao: SessaoRefresh) -> SessaoRefresh:
        self.session.add(sessao)
        await self.session.flush()
        return sessao

    async def obter_por_hash(self, token_hash: str) -> SessaoRefresh | None:
        stmt = select(SessaoRefresh).where(SessaoRefresh.token_hash == token_hash)
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def revogar_familia(self, familia_id: UUID, instante: datetime) -> None:
        stmt = (
            update(SessaoRefresh)
            .where(
                SessaoRefresh.familia_id == familia_id,
                SessaoRefresh.revogado_em.is_(None),
            )
            .values(revogado_em=instante)
        )
        await self.session.execute(stmt)
