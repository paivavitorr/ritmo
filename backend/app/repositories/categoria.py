from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bloco import Bloco
from app.models.categoria import Categoria
from app.models.execucao import Execucao
from app.models.modelo_semana import ModeloBloco

CATEGORIAS_PADRAO: tuple[tuple[str, str, bool, int], ...] = (
    ("Trabalho", "ardosia", True, 1),
    ("Estudo", "glicinia", True, 2),
    ("Treino", "salvia", True, 3),
    ("Descanso", "ceu", False, 4),
    ("Pessoal", "manteiga", True, 5),
    ("Compromissos", "rosa-cha", True, 6),
)


class CategoriaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def listar_do_usuario(self, usuario_id: UUID) -> list[Categoria]:
        stmt = (
            select(Categoria)
            .where(
                Categoria.usuario_id == usuario_id,
                Categoria.excluido_em.is_(None),
            )
            .order_by(Categoria.ordem.asc(), Categoria.nome.asc())
        )
        resultado = await self.session.execute(stmt)
        return list(resultado.scalars().all())

    async def obter_do_usuario(self, usuario_id: UUID, categoria_id: UUID) -> Categoria | None:
        stmt = select(Categoria).where(
            Categoria.id == categoria_id,
            Categoria.usuario_id == usuario_id,
            Categoria.excluido_em.is_(None),
        )
        resultado = await self.session.execute(stmt)
        return resultado.scalar_one_or_none()

    async def criar(self, categoria: Categoria) -> Categoria:
        self.session.add(categoria)
        await self.session.flush()
        return categoria

    async def criar_padroes_do_usuario(self, usuario_id: UUID) -> list[Categoria]:
        criadas: list[Categoria] = []
        for nome, cor, produtiva, ordem in CATEGORIAS_PADRAO:
            cat = Categoria(
                usuario_id=usuario_id,
                nome=nome,
                cor=cor,
                conta_como_produtiva=produtiva,
                ordem=ordem,
            )
            self.session.add(cat)
            criadas.append(cat)
        await self.session.flush()
        return criadas

    async def esta_em_uso_ativo(self, usuario_id: UUID, categoria_id: UUID) -> bool:
        for modelo in (Bloco, ModeloBloco, Execucao):
            stmt = select(func.count()).where(
                modelo.usuario_id == usuario_id,
                modelo.categoria_id == categoria_id,
                modelo.excluido_em.is_(None),
            )
            total = (await self.session.execute(stmt)).scalar_one()
            if total > 0:
                return True
        return False
