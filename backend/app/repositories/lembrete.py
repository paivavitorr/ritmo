from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lembrete import Lembrete, PushAssinatura


class LembreteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def obter_assinatura_por_endpoint(self, endpoint: str) -> PushAssinatura | None:
        stmt = select(PushAssinatura).where(PushAssinatura.endpoint == endpoint)
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def salvar_assinatura(self, assinatura: PushAssinatura) -> PushAssinatura:
        self.session.add(assinatura)
        await self.session.flush()
        return assinatura

    async def listar_assinaturas_usuario(self, usuario_id: UUID) -> list[PushAssinatura]:
        stmt = select(PushAssinatura).where(PushAssinatura.usuario_id == usuario_id)
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def remover_assinatura_por_endpoint(self, endpoint: str) -> None:
        ass = await self.obter_assinatura_por_endpoint(endpoint)
        if ass is not None:
            await self.session.delete(ass)

    async def criar_lembrete(self, lembrete: Lembrete) -> Lembrete:
        self.session.add(lembrete)
        await self.session.flush()
        return lembrete

    async def cancelar_lembretes_do_bloco(self, bloco_id: UUID) -> None:
        stmt = select(Lembrete).where(
            Lembrete.bloco_id == bloco_id,
            Lembrete.status == "pendente",
            Lembrete.excluido_em.is_(None),
        )
        resultado = await self.session.execute(stmt)
        for lemb in resultado.scalars().all():
            lemb.status = "cancelado"
            lemb.versao += 1

    async def obter_pendentes_para_disparo(
        self, ate_utc: datetime, limite: int = 50
    ) -> list[Lembrete]:
        stmt = (
            select(Lembrete)
            .where(
                Lembrete.status == "pendente",
                Lembrete.excluido_em.is_(None),
                Lembrete.disparar_em <= ate_utc,
            )
            .order_by(Lembrete.disparar_em.asc())
            .limit(limite)
            .with_for_update(skip_locked=True)
        )
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())
