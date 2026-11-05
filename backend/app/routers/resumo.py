from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.errors import AppError
from app.core.tempo import limites_utc_do_dia
from app.dependencies import CurrentUserDep, SessionDep
from app.repositories.bloco import BlocoRepository
from app.repositories.categoria import CategoriaRepository
from app.repositories.execucao import ExecucaoRepository
from app.schemas.resumo import ResumoPeriodoResponse
from app.services.resumo import calcular_resumo_periodo

router = APIRouter(prefix="/resumo", tags=["resumo"])


@router.get("", response_model=ResumoPeriodoResponse)
async def obter_resumo(
    de: Annotated[date, Query(...)],
    ate: Annotated[date, Query(...)],
    agrupar: Annotated[Literal["dia", "semana"], Query()] = "dia",
    usuario: CurrentUserDep = None,  # type: ignore[assignment]
    session: SessionDep = None,  # type: ignore[assignment]
) -> ResumoPeriodoResponse:
    if ate < de:
        raise AppError(422, "A data final deve ser maior ou igual à inicial", "validacao")

    # Limites em UTC considerando o fuso do usuário
    inicio_utc, _ = limites_utc_do_dia(de, usuario.fuso)
    _, fim_utc = limites_utc_do_dia(ate, usuario.fuso)

    cat_repo = CategoriaRepository(session)
    bloco_repo = BlocoRepository(session)
    exec_repo = ExecucaoRepository(session)

    categorias = await cat_repo.listar_do_usuario(usuario.id)
    blocos = await bloco_repo.listar_por_periodo(usuario.id, de, ate)
    execucoes = await exec_repo.listar_por_intervalo_utc(usuario.id, inicio_utc, fim_utc)

    return calcular_resumo_periodo(
        de=de,
        ate=ate,
        fuso_str=usuario.fuso,
        agrupamento=agrupar,
        categorias=categorias,
        blocos=blocos,
        execucoes=execucoes,
    )
