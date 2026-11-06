from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tempo import garantir_utc
from app.models.bloco import Bloco
from app.models.lembrete import Lembrete, PushAssinatura

MAX_TENTATIVAS = 3
ENVIANDO_PRESO_APOS = timedelta(minutes=5)


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

    async def listar_assinaturas_de_usuarios(
        self, usuario_ids: Sequence[UUID]
    ) -> dict[UUID, list[PushAssinatura]]:
        """Todas as assinaturas dos usuários numa única query (evita N+1)."""
        por_usuario: dict[UUID, list[PushAssinatura]] = {uid: [] for uid in usuario_ids}
        if not usuario_ids:
            return por_usuario
        stmt = select(PushAssinatura).where(PushAssinatura.usuario_id.in_(set(usuario_ids)))
        resultado = await self.session.execute(stmt)
        for ass in resultado.scalars().all():
            por_usuario[ass.usuario_id].append(ass)
        return por_usuario

    async def remover_assinatura_por_endpoint(self, endpoint: str) -> None:
        ass = await self.obter_assinatura_por_endpoint(endpoint)
        if ass is not None:
            await self.session.delete(ass)

    async def remover_assinaturas(self, assinatura_ids: Sequence[UUID]) -> None:
        for ass_id in assinatura_ids:
            ass = await self.session.get(PushAssinatura, ass_id)
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

    async def existe_disparado(
        self, bloco_id: UUID, antecedencia_min: int, disparar_em: datetime
    ) -> bool:
        """Já existe lembrete enviado para o mesmo bloco, antecedência e horário de disparo?"""
        stmt = select(Lembrete.disparar_em).where(
            Lembrete.bloco_id == bloco_id,
            Lembrete.antecedencia_min == antecedencia_min,
            Lembrete.status == "disparado",
            Lembrete.excluido_em.is_(None),
        )
        resultado = await self.session.execute(stmt)
        alvo = garantir_utc(disparar_em)
        return any(garantir_utc(enviado_em) == alvo for enviado_em in resultado.scalars().all())

    async def recuperar_enviando_presos(self, agora: datetime) -> int:
        """Lembretes em `enviando` há mais de 5 min (worker morreu) voltam a `pendente`.

        Quem já esgotou as tentativas vai para `erro`.
        """
        limite = agora - ENVIANDO_PRESO_APOS
        condicao = (
            Lembrete.status == "enviando",
            Lembrete.tentativa_em.is_not(None),
            Lembrete.tentativa_em < limite,
        )
        esgotados = await self.session.execute(
            update(Lembrete)
            .where(*condicao, Lembrete.tentativas >= MAX_TENTATIVAS)
            .values(status="erro", ultimo_erro="Envio interrompido", versao=Lembrete.versao + 1)
        )
        retomados = await self.session.execute(
            update(Lembrete).where(*condicao).values(status="pendente", versao=Lembrete.versao + 1)
        )
        return int(esgotados.rowcount or 0) + int(retomados.rowcount or 0)  # type: ignore[attr-defined]

    async def reivindicar_para_disparo(self, agora: datetime, limite: int = 50) -> list[Lembrete]:
        """Seleciona lembretes vencidos com `SKIP LOCKED` e os marca como `enviando`.

        O chamador deve commitar logo em seguida para liberar o lock antes de qualquer HTTP.
        """
        stmt = (
            select(Lembrete)
            .where(
                Lembrete.status == "pendente",
                Lembrete.excluido_em.is_(None),
                Lembrete.disparar_em <= agora,
            )
            .order_by(Lembrete.disparar_em.asc())
            .limit(limite)
            .with_for_update(skip_locked=True)
        )
        resultado = await self.session.execute(stmt)
        lembretes = list(resultado.scalars().all())
        for lemb in lembretes:
            lemb.status = "enviando"
            lemb.tentativa_em = agora
            lemb.tentativas += 1
            lemb.versao += 1
        return lembretes

    async def obter_inicio_dos_blocos(
        self, bloco_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[datetime, datetime | None]]:
        """`bloco_id -> (inicio, excluido_em)` numa única query."""
        if not bloco_ids:
            return {}
        stmt = select(Bloco.id, Bloco.inicio, Bloco.excluido_em).where(Bloco.id.in_(set(bloco_ids)))
        resultado = await self.session.execute(stmt)
        return {bid: (inicio, excluido) for bid, inicio, excluido in resultado.all()}

    async def obter_por_id(self, lembrete_id: UUID) -> Lembrete | None:
        return await self.session.get(Lembrete, lembrete_id)
