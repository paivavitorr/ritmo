from datetime import date

from httpx import AsyncClient

from app.services.resumo import inicio_da_semana


async def _usuario(client: AsyncClient) -> tuple[dict[str, str], dict[str, str]]:
    """Registra um usuário (America/Manaus, UTC-4) e devolve (headers, {nome: categoria_id})."""
    r = await client.post(
        "/auth/registrar",
        json={
            "email": "resumo@exemplo.com",
            "senha": "senha-segura-123",
            "nome": "Resumo",
            "fuso": "America/Manaus",
        },
    )
    assert r.status_code == 201
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cats = (await client.get("/categorias", headers=headers)).json()
    return headers, {c["nome"]: c["id"] for c in cats}


async def _bloco(
    client: AsyncClient, headers: dict[str, str], cat: str, inicio: str, fim: str
) -> str:
    r = await client.post(
        "/blocos",
        headers=headers,
        json={"categoria_id": cat, "titulo": "Bloco", "inicio": inicio, "fim": fim},
    )
    assert r.status_code == 201
    return str(r.json()["id"])


async def _execucao(
    client: AsyncClient,
    headers: dict[str, str],
    cat: str,
    inicio: str,
    fim: str,
    bloco_id: str | None = None,
) -> None:
    r = await client.post(
        "/execucoes",
        headers=headers,
        json={
            "categoria_id": cat,
            "bloco_id": bloco_id,
            "inicio": inicio,
            "fim": fim,
            "status": "concluida",
        },
    )
    assert r.status_code == 201


async def test_execucao_vinculada_a_bloco_fora_do_periodo_e_contada(client: AsyncClient) -> None:
    headers, cats = await _usuario(client)
    # Bloco no dia 05; a execução vinculada acontece no dia 06 (08:00-09:00 local)
    bloco_id = await _bloco(
        client, headers, cats["Estudo"], "2026-11-05T12:00:00Z", "2026-11-05T14:00:00Z"
    )
    await _execucao(
        client, headers, cats["Estudo"], "2026-11-06T12:00:00Z", "2026-11-06T13:00:00Z", bloco_id
    )

    r = await client.get("/resumo?de=2026-11-06&ate=2026-11-06", headers=headers)
    assert r.status_code == 200
    dados = r.json()
    linha = next(c for c in dados["categorias"] if c["categoria_id"] == cats["Estudo"])
    assert linha["segundos_executados"] == 3600
    assert linha["segundos_planejados"] == 0
    assert linha["aderencia_volume"] is None
    assert dados["total_segundos_executados"] == 3600


async def test_horas_vao_para_categoria_da_execucao_e_avulsa_usa_a_propria(
    client: AsyncClient,
) -> None:
    headers, cats = await _usuario(client)
    bloco_id = await _bloco(
        client, headers, cats["Estudo"], "2026-11-06T12:00:00Z", "2026-11-06T14:00:00Z"
    )
    # Execução vinculada ao bloco de Estudo, mas registrada em Trabalho
    await _execucao(
        client, headers, cats["Trabalho"], "2026-11-06T12:00:00Z", "2026-11-06T13:00:00Z", bloco_id
    )
    # Avulsa em Descanso (não produtiva)
    await _execucao(
        client, headers, cats["Descanso"], "2026-11-06T15:00:00Z", "2026-11-06T15:30:00Z"
    )

    dados = (await client.get("/resumo?de=2026-11-06&ate=2026-11-06", headers=headers)).json()
    por_id = {(c["categoria_id"], c["eh_espontaneo"]): c for c in dados["categorias"]}

    trabalho = por_id[(cats["Trabalho"], False)]
    assert trabalho["segundos_executados"] == 3600
    assert trabalho["segundos_planejados"] == 0
    estudo = por_id[(cats["Estudo"], False)]
    assert estudo["segundos_executados"] == 0
    assert estudo["segundos_planejados"] == 7200

    avulsa = por_id[(cats["Descanso"], True)]
    assert avulsa["segundos_executados"] == 1800
    assert avulsa["conta_como_produtiva"] is False
    assert avulsa["aderencia_volume"] is None


async def test_execucao_cruzando_meia_noite_local_e_recortada_no_periodo(
    client: AsyncClient,
) -> None:
    headers, cats = await _usuario(client)
    # 22:00 de 05/11 até 02:00 de 06/11 no horário local (UTC-4)
    await _execucao(
        client, headers, cats["Trabalho"], "2026-11-06T02:00:00Z", "2026-11-06T06:00:00Z"
    )

    so_dia_06 = (await client.get("/resumo?de=2026-11-06&ate=2026-11-06", headers=headers)).json()
    assert so_dia_06["total_segundos_executados"] == 7200
    assert so_dia_06["faixas_dias"][0]["segundos_executados"] == 7200

    dois_dias = (await client.get("/resumo?de=2026-11-05&ate=2026-11-06", headers=headers)).json()
    assert dois_dias["total_segundos_executados"] == 14400
    assert [f["segundos_executados"] for f in dois_dias["faixas_dias"]] == [7200, 7200]


async def test_agrupamento_por_semana(client: AsyncClient) -> None:
    headers, cats = await _usuario(client)
    # 06/11/2026 é sexta; semanas (segunda a domingo): 02-08/11 e 09-15/11
    for dia in ("2026-11-06", "2026-11-09", "2026-11-10"):
        bloco_id = await _bloco(
            client, headers, cats["Estudo"], f"{dia}T12:00:00Z", f"{dia}T14:00:00Z"
        )
        await _execucao(
            client, headers, cats["Estudo"], f"{dia}T12:00:00Z", f"{dia}T13:00:00Z", bloco_id
        )

    r = await client.get("/resumo?de=2026-11-06&ate=2026-11-10&agrupar=semana", headers=headers)
    assert r.status_code == 200
    semanas = r.json()["semanas"]
    assert [(s["inicio_semana"], s["inicio"], s["fim"]) for s in semanas] == [
        ("2026-11-02", "2026-11-06", "2026-11-08"),
        ("2026-11-09", "2026-11-09", "2026-11-10"),
    ]
    assert [s["segundos_planejados"] for s in semanas] == [7200, 14400]
    assert [s["segundos_executados"] for s in semanas] == [3600, 7200]
    assert [s["aderencia_volume"] for s in semanas] == [0.5, 0.5]

    por_dia = (await client.get("/resumo?de=2026-11-06&ate=2026-11-10", headers=headers)).json()
    assert por_dia["semanas"] == []


async def test_sem_plano_aderencia_e_nula(client: AsyncClient) -> None:
    headers, cats = await _usuario(client)
    await _execucao(client, headers, cats["Estudo"], "2026-11-06T12:00:00Z", "2026-11-06T13:00:00Z")

    dados = (await client.get("/resumo?de=2026-11-06&ate=2026-11-07", headers=headers)).json()
    assert dados["aderencia_volume_geral"] is None
    assert dados["aderencia_temporal_geral"] is None
    assert all(f["aderencia_volume"] is None for f in dados["faixas_dias"])
    assert all(f["aderencia_temporal"] is None for f in dados["faixas_dias"])


async def test_limite_de_periodo_de_92_dias(client: AsyncClient) -> None:
    headers, _ = await _usuario(client)
    for rota in ("/resumo", "/blocos", "/execucoes"):
        ok = await client.get(f"{rota}?de=2026-01-01&ate=2026-04-03", headers=headers)
        assert ok.status_code == 200, rota
        longo = await client.get(f"{rota}?de=2026-01-01&ate=2026-04-04", headers=headers)
        assert longo.status_code == 422, rota
        invertido = await client.get(f"{rota}?de=2026-01-02&ate=2026-01-01", headers=headers)
        assert invertido.status_code == 422, rota


def test_inicio_da_semana_segue_convencao_do_frontend() -> None:
    sexta = date(2026, 11, 6)
    assert inicio_da_semana(sexta) == date(2026, 11, 2)  # segunda (padrão)
    assert inicio_da_semana(sexta, 0) == date(2026, 11, 1)  # domingo
    assert inicio_da_semana(date(2026, 11, 8)) == date(2026, 11, 2)  # domingo pertence à anterior
    assert inicio_da_semana(date(2026, 11, 2)) == date(2026, 11, 2)
