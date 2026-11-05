from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.tempo import garantir_utc
from app.models.bloco import Bloco
from app.models.categoria import Categoria
from app.models.execucao import Execucao
from app.schemas.resumo import (
    CategoriaResumo,
    FaixaDia,
    FaixaIntervalo,
    ResumoPeriodoResponse,
)
from app.services.aderencia import (
    BlocoAderenciaInput,
    aderencia_ponderada_dia,
    aderencia_volume,
)
from app.services.horas_liquidas import (
    Intervalo,
    mesclar_intervalos,
    recortar_intervalos,
    segundos_liquidos,
)


def quebrar_intervalo_por_dias(
    inicio_utc: datetime,
    fim_utc: datetime,
    fuso_str: str,
) -> list[tuple[date, datetime, datetime]]:
    """Divide um intervalo que eventualmente cruza a meia-noite em fatias locais por dia."""
    tz = ZoneInfo(fuso_str)
    ini_local = garantir_utc(inicio_utc).astimezone(tz)
    fim_local = garantir_utc(fim_utc).astimezone(tz)
    if fim_local <= ini_local:
        return []

    fatias: list[tuple[date, datetime, datetime]] = []
    cursor = ini_local
    while cursor < fim_local:
        data_atual = cursor.date()
        meia_noite_seguinte = datetime(
            data_atual.year, data_atual.month, data_atual.day, tzinfo=tz
        ) + timedelta(days=1)
        proximo_corte = min(fim_local, meia_noite_seguinte)
        fatias.append((data_atual, cursor.astimezone(UTC), proximo_corte.astimezone(UTC)))
        cursor = proximo_corte

    return fatias


def calcular_resumo_periodo(
    de: date,
    ate: date,
    fuso_str: str,
    agrupamento: Literal["dia", "semana"],
    categorias: list[Categoria],
    blocos: list[Bloco],
    execucoes: list[Execucao],
) -> ResumoPeriodoResponse:
    mapa_cats = {c.id: c for c in categorias}

    # Indexar execuções por bloco_id para cálculo de aderência temporal bloco a bloco
    execs_por_bloco: dict[UUID, list[Execucao]] = defaultdict(list)
    execs_avulsas: list[Execucao] = []

    for ex in execucoes:
        if ex.status == "pulada":
            continue
        if ex.bloco_id is not None:
            execs_por_bloco[ex.bloco_id].append(ex)
        else:
            execs_avulsas.append(ex)

    # 1. Agrupamento por Categoria e por Dia
    segundos_plan_por_cat: dict[UUID, int] = defaultdict(int)
    segundos_exec_planejado_por_cat: dict[UUID, int] = defaultdict(int)
    segundos_plan_por_dia: dict[date, int] = defaultdict(int)
    segundos_exec_por_dia: dict[date, int] = defaultdict(int)
    segundos_exec_avulso_total = 0

    bloco_aderencia_inputs: list[BlocoAderenciaInput] = []
    bloco_inputs_por_cat: dict[UUID, list[BlocoAderenciaInput]] = defaultdict(list)
    bloco_inputs_por_dia: dict[date, list[BlocoAderenciaInput]] = defaultdict(list)

    tz = ZoneInfo(fuso_str)

    for b in blocos:
        base_bloco = Intervalo(garantir_utc(b.inicio), garantir_utc(b.fim))
        pausas_bloco = tuple(
            Intervalo(garantir_utc(p.inicio), garantir_utc(p.fim))
            for p in b.pausas_planejadas
            if garantir_utc(p.fim) > garantir_utc(p.inicio)
        )
        plan_liq = segundos_liquidos(base_bloco, list(pausas_bloco))
        segundos_plan_por_cat[b.categoria_id] += plan_liq
        data_local_bloco = garantir_utc(b.inicio).astimezone(tz).date()
        segundos_plan_por_dia[data_local_bloco] += plan_liq

        # Intervalos líquidos reais das execuções vinculadas a este bloco
        ivs_exec_bloco: list[Intervalo] = []
        for ex in execs_por_bloco.get(b.id, []):
            fim_ex = ex.fim if ex.fim is not None else datetime.now(UTC)
            if fim_ex <= ex.inicio:
                continue
            base_ex = Intervalo(garantir_utc(ex.inicio), garantir_utc(fim_ex))
            pausas_ex = []
            for p in ex.pausas:
                p_fim = p.fim if p.fim is not None else fim_ex
                if garantir_utc(p_fim) > garantir_utc(p.inicio):
                    pausas_ex.append(Intervalo(garantir_utc(p.inicio), garantir_utc(p_fim)))
            ivs_exec_bloco.extend(recortar_intervalos(base_ex, pausas_ex))

        # Segundos executados atribuídos a esta categoria via planejamento
        segundos_exec_bloco = sum(iv.segundos for iv in mesclar_intervalos(ivs_exec_bloco))
        segundos_exec_planejado_por_cat[b.categoria_id] += segundos_exec_bloco
        segundos_exec_por_dia[data_local_bloco] += segundos_exec_bloco

        inp = BlocoAderenciaInput(
            bloco=base_bloco,
            pausas_bloco=pausas_bloco,
            intervalos_execucao_liquidos=tuple(ivs_exec_bloco),
        )
        bloco_aderencia_inputs.append(inp)
        bloco_inputs_por_cat[b.categoria_id].append(inp)
        bloco_inputs_por_dia[data_local_bloco].append(inp)

    # Execuções avulsas (sem planejamento prévio)
    for ex in execs_avulsas:
        fim_ex = ex.fim if ex.fim is not None else datetime.now(UTC)
        if fim_ex <= ex.inicio:
            continue
        base_ex = Intervalo(garantir_utc(ex.inicio), garantir_utc(fim_ex))
        pausas_ex = []
        for p in ex.pausas:
            p_fim = p.fim if p.fim is not None else fim_ex
            if garantir_utc(p_fim) > garantir_utc(p.inicio):
                pausas_ex.append(Intervalo(garantir_utc(p.inicio), garantir_utc(p_fim)))
        liq_avulso = segundos_liquidos(base_ex, pausas_ex)
        segundos_exec_avulso_total += liq_avulso
        data_local_ex = garantir_utc(ex.inicio).astimezone(tz).date()
        segundos_exec_por_dia[data_local_ex] += liq_avulso

    lista_categorias_resumo: list[CategoriaResumo] = []
    for cat in categorias:
        plan = segundos_plan_por_cat[cat.id]
        exec_plan = segundos_exec_planejado_por_cat[cat.id]
        if plan == 0 and exec_plan == 0:
            continue

        taxa_vol = aderencia_volume(exec_plan, plan)
        taxa_temp = (
            aderencia_ponderada_dia(bloco_inputs_por_cat[cat.id])
            if bloco_inputs_por_cat[cat.id]
            else 1.0
        )

        lista_categorias_resumo.append(
            CategoriaResumo(
                categoria_id=cat.id,
                nome=cat.nome,
                cor=cat.cor,
                conta_como_produtiva=cat.conta_como_produtiva,
                segundos_planejados=plan,
                segundos_executados=exec_plan,
                segundos_liquidos_aderentes=min(exec_plan, plan),
                aderencia_volume=taxa_vol,
                aderencia_temporal=taxa_temp,
                eh_espontaneo=False,
            )
        )

    # Linha especial para avulsos/espontâneos (se houver)
    if segundos_exec_avulso_total > 0:
        lista_categorias_resumo.append(
            CategoriaResumo(
                categoria_id=None,
                nome="Sem planejamento / Espontâneo",
                cor="ardosia",
                conta_como_produtiva=True,
                segundos_planejados=0,
                segundos_executados=segundos_exec_avulso_total,
                segundos_liquidos_aderentes=segundos_exec_avulso_total,
                aderencia_volume=1.0,
                aderencia_temporal=1.0,
                eh_espontaneo=True,
            )
        )

    # 2. Faixa do Dia por data no fuso
    faixas_por_data: dict[date, tuple[list[FaixaIntervalo], list[FaixaIntervalo]]] = defaultdict(
        lambda: ([], [])
    )

    for b in blocos:
        cat_opt = mapa_cats.get(b.categoria_id)
        nome_cat = cat_opt.nome if cat_opt else "Geral"
        cor_cat = cat_opt.cor if cat_opt else "ardosia"

        fatias = quebrar_intervalo_por_dias(b.inicio, b.fim, fuso_str)
        for d, ini_fat, fim_fat in fatias:
            faixas_por_data[d][0].append(
                FaixaIntervalo(
                    inicio_iso=ini_fat.isoformat(),
                    fim_iso=fim_fat.isoformat(),
                    tipo="planejado",
                    categoria_id=b.categoria_id,
                    categoria_nome=nome_cat,
                    categoria_cor=cor_cat,
                    titulo=b.titulo,
                    status=None,
                )
            )

    for ex in execucoes:
        if ex.status == "pulada":
            continue
        cat_opt = mapa_cats.get(ex.categoria_id)
        nome_cat = cat_opt.nome if cat_opt else "Geral"
        cor_cat = cat_opt.cor if cat_opt else "ardosia"
        fim_ex = ex.fim if ex.fim is not None else datetime.now(UTC)
        if fim_ex <= ex.inicio:
            continue

        fatias = quebrar_intervalo_por_dias(ex.inicio, fim_ex, fuso_str)
        for d, ini_fat, fim_fat in fatias:
            faixas_por_data[d][1].append(
                FaixaIntervalo(
                    inicio_iso=ini_fat.isoformat(),
                    fim_iso=fim_fat.isoformat(),
                    tipo="executado",
                    categoria_id=ex.categoria_id,
                    categoria_nome=nome_cat,
                    categoria_cor=cor_cat,
                    titulo=nome_cat if ex.bloco_id is None else "Execução",
                    status=ex.status,
                )
            )

    faixas_dias: list[FaixaDia] = []
    cursor_data = de
    while cursor_data <= ate:
        plan_list, exec_list = faixas_por_data[cursor_data]
        seg_plan_dia = segundos_plan_por_dia[cursor_data]
        seg_exec_dia = segundos_exec_por_dia[cursor_data]
        taxa_vol_dia = aderencia_volume(seg_exec_dia, seg_plan_dia)

        # Blocos desse dia (avaliados no fuso local) para aderência temporal
        blocos_dia = bloco_inputs_por_dia.get(cursor_data, [])
        taxa_temp_dia = aderencia_ponderada_dia(blocos_dia) if blocos_dia else 1.0

        faixas_dias.append(
            FaixaDia(
                data=cursor_data,
                segundos_planejados=seg_plan_dia,
                segundos_executados=seg_exec_dia,
                aderencia_volume=taxa_vol_dia,
                aderencia_temporal=taxa_temp_dia,
                planejados=plan_list,
                executados=exec_list,
            )
        )
        cursor_data += timedelta(days=1)

    total_plan = sum(c.segundos_planejados for c in lista_categorias_resumo)
    total_exec = sum(c.segundos_executados for c in lista_categorias_resumo)
    geral_vol = aderencia_volume(total_exec, total_plan)
    geral_temp = aderencia_ponderada_dia(bloco_aderencia_inputs) if bloco_aderencia_inputs else 1.0

    return ResumoPeriodoResponse(
        de=de,
        ate=ate,
        agrupamento=agrupamento,
        total_segundos_planejados=total_plan,
        total_segundos_executados=total_exec,
        aderencia_volume_geral=geral_vol,
        aderencia_temporal_geral=geral_temp,
        categorias=lista_categorias_resumo,
        faixas_dias=faixas_dias,
    )
