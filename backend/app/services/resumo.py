from collections import defaultdict
from collections.abc import Sequence
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
    SemanaResumo,
)
from app.services.aderencia import (
    BlocoAderenciaInput,
    aderencia_ponderada_dia,
    aderencia_volume,
)
from app.services.horas_liquidas import (
    Intervalo,
    fatiar_por_dia_no_fuso,
    mesclar_intervalos,
    recortar_intervalos,
    segundos_liquidos,
)

COR_PADRAO = "ardosia"
NOME_PADRAO = "Geral"

ChaveCatDia = tuple[UUID, date]


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


def inicio_da_semana(dia: date, inicio_semana: int = 1) -> date:
    """Primeiro dia da semana de `dia`. `inicio_semana`: 0=domingo .. 6=sábado (padrão 1=segunda).

    Mesma convenção de `inicioDaSemanaIso` no frontend.
    """
    dia_semana = (dia.weekday() + 1) % 7
    return dia - timedelta(days=(dia_semana - inicio_semana) % 7)


def _fim_efetivo(execucao: Execucao, agora: datetime) -> datetime:
    return garantir_utc(execucao.fim) if execucao.fim is not None else agora


def _intervalos_liquidos_execucao(execucao: Execucao, agora: datetime) -> list[Intervalo]:
    """Intervalos líquidos reais (sem pausas) de uma execução; abertas terminam em `agora`."""
    fim = _fim_efetivo(execucao, agora)
    inicio = garantir_utc(execucao.inicio)
    if fim <= inicio:
        return []
    pausas: list[Intervalo] = []
    for p in execucao.pausas:
        p_ini = garantir_utc(p.inicio)
        p_fim = garantir_utc(p.fim) if p.fim is not None else fim
        if p_fim > p_ini:
            pausas.append(Intervalo(p_ini, p_fim))
    return recortar_intervalos(Intervalo(inicio, fim), pausas)


def _segundos_por_grupo(
    grupos: dict[ChaveCatDia, list[Intervalo]],
) -> dict[ChaveCatDia, int]:
    return {
        chave: sum(iv.segundos for iv in mesclar_intervalos(ivs)) for chave, ivs in grupos.items()
    }


def _faixa_intervalo(
    tipo: Literal["planejado", "executado"],
    inicio: datetime,
    fim: datetime,
    categoria_id: UUID,
    mapa_cats: dict[UUID, Categoria],
    titulo: str | None,
    status: str | None,
) -> FaixaIntervalo:
    cat = mapa_cats.get(categoria_id)
    nome = cat.nome if cat else NOME_PADRAO
    return FaixaIntervalo(
        inicio_iso=inicio.isoformat(),
        fim_iso=fim.isoformat(),
        tipo=tipo,
        categoria_id=categoria_id,
        categoria_nome=nome,
        categoria_cor=cat.cor if cat else COR_PADRAO,
        titulo=titulo if titulo is not None else nome,
        status=status,
    )


def calcular_resumo_periodo(
    de: date,
    ate: date,
    fuso_str: str,
    agrupamento: Literal["dia", "semana"],
    categorias: Sequence[Categoria],
    blocos: Sequence[Bloco],
    execucoes: Sequence[Execucao],
    agora: datetime,
    inicio_semana: int = 1,
) -> ResumoPeriodoResponse:
    """Calcula o resumo de `[de, ate]` (datas locais no fuso do usuário). Função pura.

    - Blocos e execuções são fatiados na meia-noite local; só entram as fatias dentro do período.
    - Horas executadas vão para `execucao.categoria_id`, pelo intervalo real da execução
      (independente de o bloco vinculado estar no período ou ter sido excluído).
    - Execuções sem bloco viram linhas "espontâneas" da própria categoria.
    - Aderência é `None` quando nada foi planejado.
    """
    agora = garantir_utc(agora)
    mapa_cats = {c.id: c for c in categorias}

    def no_periodo(dia: date) -> bool:
        return de <= dia <= ate

    # 1. Execuções: intervalos líquidos por bloco e por (categoria, dia)
    liquidos_por_bloco: dict[UUID, list[Intervalo]] = defaultdict(list)
    vinculadas: dict[ChaveCatDia, list[Intervalo]] = defaultdict(list)
    avulsas: dict[ChaveCatDia, list[Intervalo]] = defaultdict(list)

    for ex in execucoes:
        if ex.status == "pulada":
            continue
        liquidos = _intervalos_liquidos_execucao(ex, agora)
        if not liquidos:
            continue
        if ex.bloco_id is not None:
            liquidos_por_bloco[ex.bloco_id].extend(liquidos)
        destino = vinculadas if ex.bloco_id is not None else avulsas
        for dia, fatias in fatiar_por_dia_no_fuso(liquidos, fuso_str).items():
            if no_periodo(dia):
                destino[(ex.categoria_id, dia)].extend(fatias)

    exec_vinculada = _segundos_por_grupo(vinculadas)
    exec_avulsa = _segundos_por_grupo(avulsas)

    # 2. Blocos: planejado e insumos de aderência temporal por fatia diária
    plano: dict[ChaveCatDia, int] = defaultdict(int)
    inputs_todos: list[BlocoAderenciaInput] = []
    inputs_por_cat: dict[UUID, list[BlocoAderenciaInput]] = defaultdict(list)
    inputs_por_dia: dict[date, list[BlocoAderenciaInput]] = defaultdict(list)

    for b in blocos:
        base = Intervalo(garantir_utc(b.inicio), garantir_utc(b.fim))
        pausas = tuple(
            Intervalo(garantir_utc(p.inicio), garantir_utc(p.fim))
            for p in b.pausas_planejadas
            if garantir_utc(p.fim) > garantir_utc(p.inicio)
        )
        execucao_bloco = tuple(liquidos_por_bloco.get(b.id, ()))
        for dia, fatias in fatiar_por_dia_no_fuso([base], fuso_str).items():
            if not no_periodo(dia):
                continue
            for fatia in fatias:
                plano[(b.categoria_id, dia)] += segundos_liquidos(fatia, pausas)
                inp = BlocoAderenciaInput(
                    bloco=fatia,
                    pausas_bloco=pausas,
                    intervalos_execucao_liquidos=execucao_bloco,
                )
                inputs_todos.append(inp)
                inputs_por_cat[b.categoria_id].append(inp)
                inputs_por_dia[dia].append(inp)

    # 3. Agregações por categoria e por dia
    plan_cat: dict[UUID, int] = defaultdict(int)
    plan_dia: dict[date, int] = defaultdict(int)
    aderentes_cat: dict[UUID, int] = defaultdict(int)
    aderentes_dia: dict[date, int] = defaultdict(int)
    vinc_cat: dict[UUID, int] = defaultdict(int)
    avul_cat: dict[UUID, int] = defaultdict(int)
    exec_dia: dict[date, int] = defaultdict(int)

    for (cat_id, dia), seg in plano.items():
        plan_cat[cat_id] += seg
        plan_dia[dia] += seg
        aderente = min(seg, exec_vinculada.get((cat_id, dia), 0))
        aderentes_cat[cat_id] += aderente
        aderentes_dia[dia] += aderente
    for (cat_id, dia), seg in exec_vinculada.items():
        vinc_cat[cat_id] += seg
        exec_dia[dia] += seg
    for (cat_id, dia), seg in exec_avulsa.items():
        avul_cat[cat_id] += seg
        exec_dia[dia] += seg

    ids_ordenados: list[UUID] = [c.id for c in categorias]
    vistos = set(ids_ordenados)
    for cat_id in [*plan_cat, *vinc_cat, *avul_cat]:
        if cat_id not in vistos:
            vistos.add(cat_id)
            ids_ordenados.append(cat_id)

    linhas: list[CategoriaResumo] = []
    for cat_id in ids_ordenados:
        plan = plan_cat.get(cat_id, 0)
        executado = vinc_cat.get(cat_id, 0)
        if plan == 0 and executado == 0:
            continue
        cat = mapa_cats.get(cat_id)
        linhas.append(
            CategoriaResumo(
                categoria_id=cat_id,
                nome=cat.nome if cat else NOME_PADRAO,
                cor=cat.cor if cat else COR_PADRAO,
                conta_como_produtiva=cat.conta_como_produtiva if cat else True,
                segundos_planejados=plan,
                segundos_executados=executado,
                segundos_liquidos_aderentes=aderentes_cat.get(cat_id, 0),
                aderencia_volume=aderencia_volume(aderentes_cat.get(cat_id, 0), plan),
                aderencia_temporal=aderencia_ponderada_dia(inputs_por_cat.get(cat_id, [])),
                eh_espontaneo=False,
            )
        )

    for cat_id in ids_ordenados:
        espontaneo = avul_cat.get(cat_id, 0)
        if espontaneo <= 0:
            continue
        cat = mapa_cats.get(cat_id)
        linhas.append(
            CategoriaResumo(
                categoria_id=cat_id,
                nome=f"{cat.nome if cat else NOME_PADRAO} (espontâneo)",
                cor=cat.cor if cat else COR_PADRAO,
                conta_como_produtiva=cat.conta_como_produtiva if cat else True,
                segundos_planejados=0,
                segundos_executados=espontaneo,
                segundos_liquidos_aderentes=0,
                aderencia_volume=None,
                aderencia_temporal=None,
                eh_espontaneo=True,
            )
        )

    # 4. Faixas por dia (planejado x executado)
    faixas_por_data: dict[date, tuple[list[FaixaIntervalo], list[FaixaIntervalo]]] = defaultdict(
        lambda: ([], [])
    )
    for b in blocos:
        for dia, ini_fat, fim_fat in quebrar_intervalo_por_dias(b.inicio, b.fim, fuso_str):
            if no_periodo(dia):
                faixas_por_data[dia][0].append(
                    _faixa_intervalo(
                        "planejado", ini_fat, fim_fat, b.categoria_id, mapa_cats, b.titulo, None
                    )
                )
    for ex in execucoes:
        if ex.status == "pulada":
            continue
        fim_ex = _fim_efetivo(ex, agora)
        titulo = None if ex.bloco_id is None else "Execução"
        for dia, ini_fat, fim_fat in quebrar_intervalo_por_dias(ex.inicio, fim_ex, fuso_str):
            if no_periodo(dia):
                faixas_por_data[dia][1].append(
                    _faixa_intervalo(
                        "executado", ini_fat, fim_fat, ex.categoria_id, mapa_cats, titulo, ex.status
                    )
                )

    faixas_dias: list[FaixaDia] = []
    dia_cursor = de
    while dia_cursor <= ate:
        planejados, executados = faixas_por_data.get(dia_cursor, ([], []))
        faixas_dias.append(
            FaixaDia(
                data=dia_cursor,
                segundos_planejados=plan_dia.get(dia_cursor, 0),
                segundos_executados=exec_dia.get(dia_cursor, 0),
                aderencia_volume=aderencia_volume(
                    aderentes_dia.get(dia_cursor, 0), plan_dia.get(dia_cursor, 0)
                ),
                aderencia_temporal=aderencia_ponderada_dia(inputs_por_dia.get(dia_cursor, [])),
                planejados=planejados,
                executados=executados,
            )
        )
        dia_cursor += timedelta(days=1)

    semanas: list[SemanaResumo] = []
    if agrupamento == "semana":
        semanas = _agregar_semanas(
            faixas_dias, aderentes_dia, inputs_por_dia, inicio_semana=inicio_semana
        )

    total_plan = sum(plan_cat.values())
    total_exec = sum(linha.segundos_executados for linha in linhas)
    return ResumoPeriodoResponse(
        de=de,
        ate=ate,
        agrupamento=agrupamento,
        total_segundos_planejados=total_plan,
        total_segundos_executados=total_exec,
        aderencia_volume_geral=aderencia_volume(sum(aderentes_cat.values()), total_plan),
        aderencia_temporal_geral=aderencia_ponderada_dia(inputs_todos),
        categorias=linhas,
        faixas_dias=faixas_dias,
        semanas=semanas,
    )


def _agregar_semanas(
    faixas_dias: Sequence[FaixaDia],
    aderentes_dia: dict[date, int],
    inputs_por_dia: dict[date, list[BlocoAderenciaInput]],
    inicio_semana: int,
) -> list[SemanaResumo]:
    por_semana: dict[date, list[FaixaDia]] = defaultdict(list)
    for faixa in faixas_dias:
        por_semana[inicio_da_semana(faixa.data, inicio_semana)].append(faixa)

    resultado: list[SemanaResumo] = []
    for inicio, dias in sorted(por_semana.items()):
        plan = sum(d.segundos_planejados for d in dias)
        aderentes = sum(aderentes_dia.get(d.data, 0) for d in dias)
        inputs = [inp for d in dias for inp in inputs_por_dia.get(d.data, [])]
        resultado.append(
            SemanaResumo(
                inicio=dias[0].data,
                fim=dias[-1].data,
                inicio_semana=inicio,
                segundos_planejados=plan,
                segundos_executados=sum(d.segundos_executados for d in dias),
                aderencia_volume=aderencia_volume(aderentes, plan),
                aderencia_temporal=aderencia_ponderada_dia(inputs),
            )
        )
    return resultado
