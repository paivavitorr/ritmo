from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status

from app.core.errors import ConflitoError, NaoEncontradoError
from app.dependencies import CurrentUserDep, SessionDep
from app.models.categoria import Categoria
from app.repositories.categoria import CategoriaRepository
from app.schemas.categoria import CategoriaCreate, CategoriaRead, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.get("", response_model=list[CategoriaRead])
async def listar_categorias(
    usuario: CurrentUserDep,
    session: SessionDep,
) -> list[CategoriaRead]:
    repo = CategoriaRepository(session)
    categorias = await repo.listar_do_usuario(usuario.id)
    return [CategoriaRead.model_validate(c) for c in categorias]


@router.post("", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED)
async def criar_categoria(
    dados: CategoriaCreate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> CategoriaRead:
    repo = CategoriaRepository(session)
    kwargs: dict[str, object] = {
        "usuario_id": usuario.id,
        "nome": dados.nome,
        "cor": dados.cor,
        "icone": dados.icone,
        "conta_como_produtiva": dados.conta_como_produtiva,
        "meta_semanal_min": dados.meta_semanal_min,
        "ordem": dados.ordem,
    }
    if dados.id is not None:
        kwargs["id"] = dados.id

    categoria = Categoria(**kwargs)
    await repo.criar(categoria)
    await session.commit()
    await session.refresh(categoria)
    return CategoriaRead.model_validate(categoria)


@router.get("/{categoria_id}", response_model=CategoriaRead)
async def obter_categoria(
    categoria_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> CategoriaRead:
    repo = CategoriaRepository(session)
    categoria = await repo.obter_do_usuario(usuario.id, categoria_id)
    if categoria is None:
        raise NaoEncontradoError("Categoria não encontrada")
    return CategoriaRead.model_validate(categoria)


@router.patch("/{categoria_id}", response_model=CategoriaRead)
async def atualizar_categoria(
    categoria_id: UUID,
    dados: CategoriaUpdate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> CategoriaRead:
    repo = CategoriaRepository(session)
    categoria = await repo.obter_do_usuario(usuario.id, categoria_id)
    if categoria is None:
        raise NaoEncontradoError("Categoria não encontrada")

    campos = dados.model_dump(exclude_unset=True)
    if campos:
        for campo, valor in campos.items():
            setattr(categoria, campo, valor)
        categoria.versao += 1
        await session.commit()
        await session.refresh(categoria)
    return CategoriaRead.model_validate(categoria)


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_categoria(
    categoria_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> None:
    repo = CategoriaRepository(session)
    categoria = await repo.obter_do_usuario(usuario.id, categoria_id)
    if categoria is None:
        raise NaoEncontradoError("Categoria não encontrada")

    if await repo.esta_em_uso_ativo(usuario.id, categoria_id):
        raise ConflitoError("Não é possível excluir uma categoria que está em uso")

    categoria.excluido_em = datetime.now(UTC)
    categoria.versao += 1
    await session.commit()
