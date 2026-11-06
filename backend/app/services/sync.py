"""Regras puras de sincronização (sem I/O)."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.core.tempo import garantir_utc
from app.services.horas_liquidas import Intervalo, segundos_liquidos

MARGEM_CURSOR = timedelta(seconds=2)
LIMITE_MUDANCAS_POR_ENTIDADE = 2000


def tem_conflito_de_versao(versao_base: int | None, versao_servidor: int) -> bool:
    """`versao_base` ausente significa "sem checagem" (a última escrita vence)."""
    return versao_base is not None and versao_base != versao_servidor


def segundos_liquidos_execucao(
    inicio: datetime,
    fim: datetime | None,
    pausas: Sequence[tuple[datetime, datetime | None]],
) -> int:
    """Horas líquidas considerando só as pausas efetivas (fechadas e com duração positiva)."""
    if fim is None or garantir_utc(fim) <= garantir_utc(inicio):
        return 0
    efetivas = [
        Intervalo(p_ini, p_fim)
        for p_ini, p_fim in pausas
        if p_fim is not None and garantir_utc(p_fim) > garantir_utc(p_ini)
    ]
    return segundos_liquidos(Intervalo(inicio, fim), efetivas)


def cursor_inicial(agora: datetime) -> datetime:
    """Instante base do cursor: início da consulta menos uma margem para relógios/commits."""
    return garantir_utc(agora) - MARGEM_CURSOR


def escolher_cursor(base: datetime, limites_truncados: Sequence[datetime]) -> datetime:
    """Cursor da resposta: se alguma lista foi truncada, retoma do ponto mais antigo atingido."""
    candidatos = [base, *(garantir_utc(t) - timedelta(microseconds=1) for t in limites_truncados)]
    return min(candidatos)


def formatar_cursor(instante: datetime) -> str:
    return garantir_utc(instante).astimezone(UTC).isoformat()
