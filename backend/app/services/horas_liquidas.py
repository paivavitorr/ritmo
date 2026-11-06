from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.errors import AppError
from app.core.tempo import garantir_utc, limites_utc_do_dia

LIMITE_DIAS_PERIODO = 92


@dataclass(frozen=True, slots=True)
class Intervalo:
    """Intervalo semiaberto `[inicio, fim)` em UTC."""

    inicio: datetime
    fim: datetime

    def __post_init__(self) -> None:
        i = garantir_utc(self.inicio)
        f = garantir_utc(self.fim)
        if f < i:
            raise ValueError("O fim do intervalo não pode ser anterior ao início")
        object.__setattr__(self, "inicio", i)
        object.__setattr__(self, "fim", f)

    @property
    def segundos(self) -> int:
        return max(0, round((self.fim - self.inicio).total_seconds()))


def validar_periodo(de: date, ate: date, limite_dias: int = LIMITE_DIAS_PERIODO) -> None:
    """Garante `de <= ate` e `ate - de <= limite_dias`; caso contrário, levanta 422."""
    if ate < de:
        raise AppError(422, "A data final deve ser maior ou igual à inicial", "validacao")
    if (ate - de).days > limite_dias:
        raise AppError(
            422, f"O período não pode ultrapassar {limite_dias} dias", "periodo_muito_longo"
        )


def mesclar_intervalos(intervalos: Sequence[Intervalo]) -> list[Intervalo]:
    """Ordena e funde intervalos sobrepostos ou adjacentes."""
    nao_vazios = [iv for iv in intervalos if iv.fim > iv.inicio]
    if not nao_vazios:
        return []
    ordenados = sorted(nao_vazios, key=lambda x: (x.inicio, x.fim))
    resultado: list[Intervalo] = [ordenados[0]]
    for atual in ordenados[1:]:
        ultimo = resultado[-1]
        if atual.inicio <= ultimo.fim:
            if atual.fim > ultimo.fim:
                resultado[-1] = Intervalo(ultimo.inicio, atual.fim)
        else:
            resultado.append(atual)
    return resultado


def recortar_intervalos(
    base: Intervalo,
    pausas: Sequence[Intervalo],
) -> list[Intervalo]:
    """Retorna os subintervalos de `base` após subtrair todas as `pausas`.

    Pausas fora de `base` são truncadas aos limites de `base`; pausas sobrepostas
    são fundidas antes da subtração (nunca descontadas em dobro).
    """
    if base.fim <= base.inicio:
        return []

    pausas_recortadas: list[Intervalo] = []
    for p in pausas:
        ini = max(base.inicio, p.inicio)
        fim = min(base.fim, p.fim)
        if fim > ini:
            pausas_recortadas.append(Intervalo(ini, fim))

    pausas_unidas = mesclar_intervalos(pausas_recortadas)
    if not pausas_unidas:
        return [base]

    liquidos: list[Intervalo] = []
    cursor = base.inicio
    for p in pausas_unidas:
        if p.inicio > cursor:
            liquidos.append(Intervalo(cursor, p.inicio))
        cursor = max(cursor, p.fim)
    if cursor < base.fim:
        liquidos.append(Intervalo(cursor, base.fim))
    return liquidos


def segundos_liquidos(base: Intervalo, pausas: Sequence[Intervalo] = ()) -> int:
    """Total em segundos de `base` descontando `pausas`."""
    return sum(iv.segundos for iv in recortar_intervalos(base, pausas))


def intersecao_listas(
    lista_a: Sequence[Intervalo],
    lista_b: Sequence[Intervalo],
) -> list[Intervalo]:
    """Retorna a interseção de duas listas de intervalos (após mesclagem)."""
    a = mesclar_intervalos(lista_a)
    b = mesclar_intervalos(lista_b)
    resultado: list[Intervalo] = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        ini = max(a[i].inicio, b[j].inicio)
        fim = min(a[i].fim, b[j].fim)
        if fim > ini:
            resultado.append(Intervalo(ini, fim))
        if a[i].fim < b[j].fim:
            i += 1
        else:
            j += 1
    return resultado


def fatiar_por_dia_no_fuso(
    intervalos: Sequence[Intervalo],
    fuso_iana: str,
) -> dict[date, list[Intervalo]]:
    """Divide intervalos que cruzam a meia-noite local em fatias por `date` no fuso do usuário."""
    tz = ZoneInfo(fuso_iana)
    por_dia: dict[date, list[Intervalo]] = {}
    for iv in mesclar_intervalos(intervalos):
        if iv.fim <= iv.inicio:
            continue
        dia_atual = iv.inicio.astimezone(tz).date()
        dia_final = (iv.fim - timedelta(microseconds=1)).astimezone(tz).date()
        while dia_atual <= dia_final:
            ini_dia, fim_dia = limites_utc_do_dia(dia_atual, fuso_iana)
            ini_fatia = max(iv.inicio, ini_dia)
            fim_fatia = min(iv.fim, fim_dia)
            if fim_fatia > ini_fatia:
                por_dia.setdefault(dia_atual, []).append(Intervalo(ini_fatia, fim_fatia))
            dia_atual += timedelta(days=1)
    return por_dia
