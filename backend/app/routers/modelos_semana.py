from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, status

from app.core.errors import AppError, NaoEncontradoError
from app.dependencies import CurrentUserDep, SessionDep
from app.models.modelo_semana import ModeloBloco
from app.repositories.categoria import CategoriaRepository
from app.repositories.modelo_semana import ModeloBlocoRepository
from app.routers.blocos import serializar_bloco
from app.schemas.bloco import BlocoRead
from app.schemas.modelo_semana import (
    ModeloBlocoCreate,
    ModeloBlocoRead,
    ModeloBlocoUpdate,
    _duracao_minutos_modelo,
)
from app.services.modelo_semana import MaterializadorSemanaService

router = APIRouter(tags=["modelos-semana"])


@router.get("/modelos-bloco", response_model=list[ModeloBlocoRead])
async def listar_modelos(
    usuario: CurrentUserDep,
    session: SessionDep,
) -> list[ModeloBlocoRead]:
    repo = ModeloBlocoRepository(session)
    modelos = await repo.listar_do_usuario(usuario.id)
    return [ModeloBlocoRead.model_validate(m) for m in modelos]


@router.post(
    "/modelos-bloco",
    response_model=ModeloBlocoRead,
    status_code=status.HTTP_201_CREATED,
)
async def criar_modelo(
    dados: ModeloBlocoCreate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ModeloBlocoRead:
    cat_repo = CategoriaRepository(session)
    if await cat_repo.obter_do_usuario(usuario.id, dados.categoria_id) is None:
        raise NaoEncontradoError("Categoria não encontrada")

    repo = ModeloBlocoRepository(session)
    kwargs: dict[str, object] = {
        "usuario_id": usuario.id,
        "categoria_id": dados.categoria_id,
        "titulo": dados.titulo,
        "dia_semana": dados.dia_semana,
        "hora_inicio": dados.hora_inicio,
        "hora_fim": dados.hora_fim,
        "pausas": [p.model_dump() for p in dados.pausas],
        "lembretes": list(dados.lembretes),
        "ativo": dados.ativo,
    }
    if dados.id is not None:
        kwargs["id"] = dados.id

    modelo = ModeloBloco(**kwargs)
    await repo.criar(modelo)
    await session.commit()
    await session.refresh(modelo)
    return ModeloBlocoRead.model_validate(modelo)


@router.patch("/modelos-bloco/{modelo_id}", response_model=ModeloBlocoRead)
async def atualizar_modelo(
    modelo_id: UUID,
    dados: ModeloBlocoUpdate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> ModeloBlocoRead:
    repo = ModeloBlocoRepository(session)
    modelo = await repo.obter_do_usuario(usuario.id, modelo_id)
    if modelo is None:
        raise NaoEncontradoError("Modelo de bloco não encontrado")

    campos = dados.model_dump(exclude_unset=True)
    if "categoria_id" in campos:
        cat_repo = CategoriaRepository(session)
        if await cat_repo.obter_do_usuario(usuario.id, campos["categoria_id"]) is None:
            raise NaoEncontradoError("Categoria não encontrada")

    hora_ini = dados.hora_inicio if dados.hora_inicio is not None else modelo.hora_inicio
    hora_fim = dados.hora_fim if dados.hora_fim is not None else modelo.hora_fim
    pausas_dict = (
        [p.model_dump() for p in dados.pausas] if dados.pausas is not None else modelo.pausas
    )
    duracao_total = _duracao_minutos_modelo(hora_ini, hora_fim)
    for p in pausas_dict:
        if int(p["offset_min"]) + int(p["duracao_min"]) > duracao_total:
            raise AppError(
                422,
                "A pausa do modelo excede a duração total do bloco",
                "validacao",
            )

    if dados.lembretes is not None:
        for lemb in dados.lembretes:
            if lemb < 0 or lemb > 1440:
                raise AppError(
                    422,
                    "Antecedência de lembrete deve estar entre 0 e 1440 minutos",
                    "validacao",
                )

    if campos:
        if "pausas" in campos:
            campos["pausas"] = pausas_dict
        for campo, valor in campos.items():
            setattr(modelo, campo, valor)
        modelo.versao += 1
        await session.commit()
        await session.refresh(modelo)

    return ModeloBlocoRead.model_validate(modelo)


@router.delete("/modelos-bloco/{modelo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_modelo(
    modelo_id: UUID,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> None:
    repo = ModeloBlocoRepository(session)
    modelo = await repo.obter_do_usuario(usuario.id, modelo_id)
    if modelo is None:
        raise NaoEncontradoError("Modelo de bloco não encontrado")

    modelo.excluido_em = datetime.now(UTC)
    modelo.versao += 1
    await session.commit()


@router.post("/semanas/{inicio}/aplicar-modelo", response_model=list[BlocoRead])
async def aplicar_modelo(
    inicio: date,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> list[BlocoRead]:
    service = MaterializadorSemanaService(session)
    blocos = await service.aplicar_modelo_na_semana(usuario, inicio)
    return [serializar_bloco(b) for b in blocos]
