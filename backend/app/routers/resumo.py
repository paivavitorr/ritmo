from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.tempo import limites_utc_do_dia
from app.dependencies import CurrentUserDep, SessionDep
from app.repositories.bloco import BlocoRepository
from app.repositories.categoria import CategoriaRepository
from app.repositories.execucao import ExecucaoRepository
from app.schemas.resumo import ResumoPeriodoResponse
from app.services.horas_liquidas import validar_periodo
from app.services.resumo import calcular_resumo_periodo

router = APIRouter(prefix="/resumo", tags=["resumo"])


@router.get("", response_model=ResumoPeriodoResponse)
async def obter_resumo(
    de: Annotated[date, Query(...)],
    ate: Annotated[date, Query(...)],
    usuario: CurrentUserDep,
    session: SessionDep,
    agrupar: Annotated[Literal["dia", "semana"], Query()] = "dia",
) -> ResumoPeriodoResponse:
    validar_periodo(de, ate)

    # Limites em UTC considerando o fuso do usuário
    inicio_utc, _ = limites_utc_do_dia(de, usuario.fuso)
    _, fim_utc = limites_utc_do_dia(ate, usuario.fuso)

    categorias = await CategoriaRepository(session).listar_do_usuario(usuario.id)
    # Um dia a mais antes: blocos que começam na véspera e cruzam a meia-noite
    blocos = await BlocoRepository(session).listar_por_periodo(
        usuario.id, de - timedelta(days=1), ate
    )
    execucoes = await ExecucaoRepository(session).listar_por_intervalo_utc(
        usuario.id, inicio_utc, fim_utc
    )

    return calcular_resumo_periodo(
        de=de,
        ate=ate,
        fuso_str=usuario.fuso,
        agrupamento=agrupar,
        categorias=categorias,
        blocos=blocos,
        execucoes=execucoes,
        agora=datetime.now(UTC),
        inicio_semana=usuario.inicio_semana,
    )
