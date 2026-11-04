from collections.abc import Sequence
from dataclasses import dataclass

from app.services.horas_liquidas import (
    Intervalo,
    intersecao_listas,
    mesclar_intervalos,
    recortar_intervalos,
)


@dataclass(frozen=True, slots=True)
class BlocoAderenciaInput:
    """Representação pura de um bloco e das execuções associadas a ele."""

    bloco: Intervalo
    pausas_bloco: tuple[Intervalo, ...] = ()
    intervalos_execucao_liquidos: tuple[Intervalo, ...] = ()


def aderencia_volume(segundos_executados: int, segundos_planejados: int) -> float:
    """Taxa de aderência de volume (`[0.0, 1.0]`): `min(exec, plan) / plan`.

    Se nada foi planejado (`segundos_planejados <= 0`), retorna `1.0`.
    """
    if segundos_planejados <= 0:
        return 1.0
    exec_pos = max(0, segundos_executados)
    return min(exec_pos, segundos_planejados) / segundos_planejados


def aderencia_temporal_bloco(
    bloco: Intervalo,
    pausas_bloco: Sequence[Intervalo],
    intervalos_execucao_liquidos: Sequence[Intervalo],
) -> float:
    """Taxa de aderência temporal (`[0.0, 1.0]`) de um bloco:

    `|intervalos_liquidos(exec) ∩ intervalos_liquidos(bloco)| / liquido(bloco)`
    """
    liquidos_bloco = recortar_intervalos(bloco, pausas_bloco)
    total_bloco = sum(iv.segundos for iv in liquidos_bloco)
    if total_bloco <= 0:
        return 1.0
    exec_unidos = mesclar_intervalos(intervalos_execucao_liquidos)
    comuns = intersecao_listas(liquidos_bloco, exec_unidos)
    segundos_comuns = sum(iv.segundos for iv in comuns)
    return min(1.0, segundos_comuns / total_bloco)


def aderencia_ponderada_dia(itens: Sequence[BlocoAderenciaInput]) -> float:
    """Média ponderada da aderência temporal pelos segundos líquidos planejados de cada bloco."""
    numerador = 0.0
    denominador = 0
    for item in itens:
        liquidos_bloco = recortar_intervalos(item.bloco, item.pausas_bloco)
        peso = sum(iv.segundos for iv in liquidos_bloco)
        if peso <= 0:
            continue
        taxa = aderencia_temporal_bloco(
            item.bloco,
            item.pausas_bloco,
            item.intervalos_execucao_liquidos,
        )
        numerador += taxa * peso
        denominador += peso

    if denominador == 0:
        return 1.0
    return numerador / denominador
