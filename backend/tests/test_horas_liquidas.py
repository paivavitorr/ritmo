from datetime import UTC, date, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.aderencia import (
    BlocoAderenciaInput,
    aderencia_ponderada_dia,
    aderencia_temporal_bloco,
    aderencia_volume,
)
from app.services.horas_liquidas import (
    Intervalo,
    fatiar_por_dia_no_fuso,
    intersecao_listas,
    mesclar_intervalos,
    recortar_intervalos,
    segundos_liquidos,
)

BASE_UTC = datetime(2026, 11, 4, 0, 0, tzinfo=UTC)


@st.composite
def estrategia_intervalo(draw: st.DrawFn, max_offset: int = 86400) -> Intervalo:
    ini_seg = draw(st.integers(min_value=0, max_value=max_offset))
    dur_seg = draw(st.integers(min_value=0, max_value=36000))
    ini = BASE_UTC + timedelta(seconds=ini_seg)
    fim = ini + timedelta(seconds=dur_seg)
    return Intervalo(ini, fim)


@settings(max_examples=100)
@given(
    base=estrategia_intervalo(),
    pausas=st.lists(estrategia_intervalo(), max_size=8),
)
def test_propriedade_segundos_liquidos_limites_e_idempotencia(
    base: Intervalo,
    pausas: list[Intervalo],
) -> None:
    liq = segundos_liquidos(base, pausas)
    assert 0 <= liq <= base.segundos

    # Duplicar pausas (sobreposição total) jamais desconta em dobro
    assert segundos_liquidos(base, [*pausas, *pausas]) == liq

    # Subintervalos recortados não se sobrepõem e estão contidos em `base`
    fatias = recortar_intervalos(base, pausas)
    for idx, f in enumerate(fatias):
        assert f.inicio >= base.inicio
        assert f.fim <= base.fim
        if idx > 0:
            assert f.inicio >= fatias[idx - 1].fim


@settings(max_examples=80)
@given(
    bloco=estrategia_intervalo(),
    pausas=st.lists(estrategia_intervalo(), max_size=5),
    execs=st.lists(estrategia_intervalo(), max_size=5),
)
def test_propriedade_aderencia_temporal_entre_zero_e_um(
    bloco: Intervalo,
    pausas: list[Intervalo],
    execs: list[Intervalo],
) -> None:
    taxa = aderencia_temporal_bloco(bloco, pausas, execs)
    assert 0.0 <= taxa <= 1.0

    # Quando a execução cobre exatamente os intervalos líquidos planejados, aderência é 1.0
    liquidos = recortar_intervalos(bloco, pausas)
    assert aderencia_temporal_bloco(bloco, pausas, liquidos) == 1.0


def test_fatiar_meia_noite_no_fuso_manaus() -> None:
    # 23:00 de 04/11 até 07:00 de 05/11 em America/Manaus (UTC-4)
    # Em UTC: 05/11 03:00 até 05/11 11:00 (total 8h = 28800s)
    ini = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)
    fim = datetime(2026, 11, 5, 11, 0, tzinfo=UTC)
    fatias = fatiar_por_dia_no_fuso([Intervalo(ini, fim)], "America/Manaus")

    assert set(fatias.keys()) == {date(2026, 11, 4), date(2026, 11, 5)}
    seg_dia_4 = sum(iv.segundos for iv in fatias[date(2026, 11, 4)])
    seg_dia_5 = sum(iv.segundos for iv in fatias[date(2026, 11, 5)])
    assert seg_dia_4 == 3600  # 23h-00h = 1h
    assert seg_dia_5 == 7 * 3600  # 00h-07h = 7h


def test_transicao_dst_america_new_york() -> None:
    # Em 2026-11-01 (fall back em America/New_York), o dia local tem 25 horas.
    # Um bloco de 04:00 UTC a 08:00 UTC em 2026-11-01 atravessa a mudança de EDT para EST.
    ini = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)
    fim = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
    iv = Intervalo(ini, fim)
    assert iv.segundos == 4 * 3600

    fatias = fatiar_por_dia_no_fuso([iv], "America/New_York")
    total_fatiado = sum(f.segundos for lista in fatias.values() for f in lista)
    assert total_fatiado == iv.segundos


def test_intersecao_e_aderencia_ponderada() -> None:
    b1 = Intervalo(
        datetime(2026, 11, 4, 12, 0, tzinfo=UTC),
        datetime(2026, 11, 4, 14, 0, tzinfo=UTC),
    )
    b2 = Intervalo(
        datetime(2026, 11, 4, 15, 0, tzinfo=UTC),
        datetime(2026, 11, 4, 17, 0, tzinfo=UTC),
    )
    # b1 executado 100% (2h), b2 executado 50% (1h de 2h) -> média ponderada = 0.75
    e1 = b1
    e2 = Intervalo(
        datetime(2026, 11, 4, 15, 0, tzinfo=UTC),
        datetime(2026, 11, 4, 16, 0, tzinfo=UTC),
    )
    media = aderencia_ponderada_dia(
        [
            BlocoAderenciaInput(bloco=b1, intervalos_execucao_liquidos=(e1,)),
            BlocoAderenciaInput(bloco=b2, intervalos_execucao_liquidos=(e2,)),
        ]
    )
    assert abs(media - 0.75) < 1e-9
    assert aderencia_volume(3600, 7200) == 0.5
    assert aderencia_volume(9000, 7200) == 1.0
    assert aderencia_volume(100, 0) == 1.0
    assert len(mesclar_intervalos([b1, b2])) == 2
    assert len(intersecao_listas([b2], [e2])) == 1
