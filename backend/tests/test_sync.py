from typing import Any
from uuid import uuid4

from httpx import AsyncClient

Headers = dict[str, str]


async def _registrar(client: AsyncClient, email: str) -> tuple[Headers, str]:
    r = await client.post(
        "/auth/registrar",
        json={
            "email": email,
            "senha": "senha-segura-123",
            "nome": "Ana",
            "fuso": "America/Manaus",
        },
    )
    assert r.status_code == 201
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cats = await client.get("/categorias", headers=headers)
    return headers, cats.json()[0]["id"]


def _mut(
    entidade: str,
    acao: str,
    entidade_id: str,
    payload: dict[str, Any] | None = None,
    versao_base: int | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "entidade": entidade,
        "acao": acao,
        "entidade_id": entidade_id,
        "payload": payload or {},
        "criado_em": "2026-11-04T12:00:00Z",
        "versao_base": versao_base,
    }


def _bloco_payload(categoria_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "categoria_id": categoria_id,
        "titulo": "Foco",
        "inicio": "2026-11-05T02:00:00Z",  # 22h do dia 04 em Manaus (UTC-4)
        "fim": "2026-11-05T04:00:00Z",
        **extra,
    }


async def _batch(client: AsyncClient, headers: Headers, *mutacoes: dict[str, Any]) -> list[Any]:
    r = await client.post("/sync/batch", headers=headers, json={"mutacoes": list(mutacoes)})
    assert r.status_code == 200, r.text
    return r.json()["resultados"]


async def test_mass_assignment_ignorado(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    bid = str(uuid4())
    payload = _bloco_payload(
        cat,
        versao=99,
        excluido_em="2026-01-01T00:00:00Z",
        usuario_id=str(uuid4()),
        segundos_liquidos_planejados=1,
    )
    [res] = await _batch(client, headers, _mut("bloco", "criar", bid, payload))
    assert res["status"] == "aplicado"
    assert res["versao_servidor"] == 1

    r = await client.get(f"/blocos/{bid}", headers=headers)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["versao"] == 1
    assert corpo["segundos_liquidos_planejados"] == 7200
    # data_local calculada no fuso do usuário (22h do dia 04 em Manaus), não em UTC
    assert corpo["data_local"] == "2026-11-04"

    [up] = await _batch(
        client,
        headers,
        _mut("bloco", "atualizar", bid, {"versao": 50, "titulo": "Novo"}, versao_base=1),
    )
    assert up["status"] == "aplicado"
    assert up["versao_servidor"] == 2


async def test_payload_invalido_vira_erro_generico(client: AsyncClient) -> None:
    headers, _ = await _registrar(client, "a@exemplo.com")
    [res] = await _batch(
        client, headers, _mut("bloco", "criar", str(uuid4()), {"titulo": "sem categoria"})
    )
    assert res["status"] == "erro"
    assert "categoria_id" in res["mensagem"]


async def test_fk_de_outro_usuario_e_erro(client: AsyncClient) -> None:
    h1, cat1 = await _registrar(client, "a@exemplo.com")
    h2, cat2 = await _registrar(client, "b@exemplo.com")

    [res] = await _batch(client, h2, _mut("bloco", "criar", str(uuid4()), _bloco_payload(cat1)))
    assert res["status"] == "erro"

    # execução apontando para bloco de outro usuário
    bloco_id = str(uuid4())
    await _batch(client, h1, _mut("bloco", "criar", bloco_id, _bloco_payload(cat1)))
    exec_payload = {
        "categoria_id": cat2,
        "bloco_id": bloco_id,
        "inicio": "2026-11-05T02:00:00Z",
        "fim": "2026-11-05T03:00:00Z",
    }
    [res2] = await _batch(client, h2, _mut("execucao", "criar", str(uuid4()), exec_payload))
    assert res2["status"] == "erro"
    assert "SELECT" not in (res2["mensagem"] or "")


async def test_replay_de_criar_e_idempotente(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    bid = str(uuid4())
    m = _mut("bloco", "criar", bid, _bloco_payload(cat))
    [r1] = await _batch(client, headers, m)
    [r2] = await _batch(client, headers, {**m, "id": str(uuid4()), "payload": {"titulo": "Outro"}})
    assert r1["status"] == r2["status"] == "aplicado"
    assert r2["versao_servidor"] == 1
    corpo = (await client.get(f"/blocos/{bid}", headers=headers)).json()
    assert corpo["titulo"] == "Foco"

    # replay após exclusão continua idempotente e não ressuscita
    await _batch(client, headers, _mut("bloco", "excluir", bid))
    [r3] = await _batch(client, headers, m)
    assert r3["status"] == "aplicado"
    assert (await client.get(f"/blocos/{bid}", headers=headers)).status_code == 404


async def test_criar_com_id_de_outro_usuario_e_erro(client: AsyncClient) -> None:
    h1, cat1 = await _registrar(client, "a@exemplo.com")
    h2, cat2 = await _registrar(client, "b@exemplo.com")
    bid = str(uuid4())
    await _batch(client, h1, _mut("bloco", "criar", bid, _bloco_payload(cat1)))
    [res] = await _batch(client, h2, _mut("bloco", "criar", bid, _bloco_payload(cat2)))
    assert res["status"] == "erro"


async def test_conflito_por_versao_base(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    bid = str(uuid4())
    await _batch(client, headers, _mut("bloco", "criar", bid, _bloco_payload(cat)))
    [ok] = await _batch(
        client, headers, _mut("bloco", "atualizar", bid, {"titulo": "A"}, versao_base=1)
    )
    assert ok["status"] == "aplicado"

    [conf] = await _batch(
        client, headers, _mut("bloco", "atualizar", bid, {"titulo": "B"}, versao_base=1)
    )
    assert conf["status"] == "conflito"
    assert conf["versao_servidor"] == 2
    assert conf["entidade_servidor"]["titulo"] == "A"
    assert conf["entidade_servidor"]["versao"] == 2

    corpo = (await client.get(f"/blocos/{bid}", headers=headers)).json()
    assert corpo["titulo"] == "A"


async def test_atualizar_inexistente_e_ignorado(client: AsyncClient) -> None:
    headers, _ = await _registrar(client, "a@exemplo.com")
    [res] = await _batch(
        client, headers, _mut("bloco", "atualizar", str(uuid4()), {"titulo": "x"}, versao_base=1)
    )
    assert res["status"] == "ignorado"


async def test_excluir_idempotente(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    bid = str(uuid4())
    await _batch(client, headers, _mut("bloco", "criar", bid, _bloco_payload(cat)))
    [r1] = await _batch(client, headers, _mut("bloco", "excluir", bid))
    [r2] = await _batch(client, headers, _mut("bloco", "excluir", bid))
    assert r1["status"] == r2["status"] == "aplicado"
    assert r1["versao_servidor"] == r2["versao_servidor"] == 2
    [r3] = await _batch(client, headers, _mut("bloco", "excluir", str(uuid4())))
    assert r3["status"] == "ignorado"


async def test_atualizar_inicio_recalcula_data_local(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    bid = str(uuid4())
    await _batch(client, headers, _mut("bloco", "criar", bid, _bloco_payload(cat)))
    await _batch(
        client,
        headers,
        _mut(
            "bloco",
            "atualizar",
            bid,
            {"inicio": "2026-11-06T12:00:00Z", "fim": "2026-11-06T13:00:00Z"},
            versao_base=1,
        ),
    )
    corpo = (await client.get(f"/blocos/{bid}", headers=headers)).json()
    assert corpo["data_local"] == "2026-11-06"


async def test_execucao_atualizar_pausas_recalcula_liquido(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    eid = str(uuid4())
    payload = {
        "categoria_id": cat,
        "inicio": "2026-11-05T10:00:00Z",
        "fim": "2026-11-05T12:00:00Z",
        "segundos_liquidos": 999999,
    }
    [res] = await _batch(client, headers, _mut("execucao", "criar", eid, payload))
    assert res["status"] == "aplicado"
    assert (await client.get(f"/execucoes/{eid}", headers=headers)).json()[
        "segundos_liquidos"
    ] == 7200

    await _batch(
        client,
        headers,
        _mut(
            "execucao",
            "atualizar",
            eid,
            {"pausas": [{"inicio": "2026-11-05T10:30:00Z", "fim": "2026-11-05T11:00:00Z"}]},
            versao_base=1,
        ),
    )
    assert (await client.get(f"/execucoes/{eid}", headers=headers)).json()[
        "segundos_liquidos"
    ] == 5400


async def test_batch_acima_do_limite_422(client: AsyncClient) -> None:
    headers, _ = await _registrar(client, "a@exemplo.com")
    muts = [_mut("bloco", "excluir", str(uuid4())) for _ in range(201)]
    r = await client.post("/sync/batch", headers=headers, json={"mutacoes": muts})
    assert r.status_code == 422


async def test_mudancas_com_e_sem_desde_e_excluidos(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    b1, b2 = str(uuid4()), str(uuid4())
    await _batch(
        client,
        headers,
        _mut("bloco", "criar", b1, _bloco_payload(cat)),
        _mut("bloco", "criar", b2, _bloco_payload(cat)),
    )
    await _batch(client, headers, _mut("bloco", "excluir", b2))

    r = await client.get("/sync/mudancas", headers=headers)
    assert r.status_code == 200
    corpo = r.json()
    assert [b["id"] for b in corpo["blocos"]] == [b1]
    assert len(corpo["categorias"]) == 6
    assert corpo["excluidos"] == [{"entidade": "bloco", "id": b2}]
    assert corpo["tem_mais"] is False
    assert corpo["cursor"]

    # `desde` no futuro não traz nada
    vazio = await client.get(
        "/sync/mudancas", headers=headers, params={"desde": "2999-01-01T00:00:00Z"}
    )
    assert vazio.status_code == 200
    assert vazio.json()["blocos"] == []
    assert vazio.json()["excluidos"] == []

    # o cursor devolvido é aceito e mudanças posteriores aparecem
    cursor = corpo["cursor"]
    b3 = str(uuid4())
    await _batch(client, headers, _mut("bloco", "criar", b3, _bloco_payload(cat)))
    r3 = await client.get("/sync/mudancas", headers=headers, params={"desde": cursor})
    assert b3 in [b["id"] for b in r3.json()["blocos"]]

    invalido = await client.get("/sync/mudancas", headers=headers, params={"desde": "ontem"})
    assert invalido.status_code == 422


async def test_mudancas_isolamento_entre_usuarios(client: AsyncClient) -> None:
    h1, cat1 = await _registrar(client, "a@exemplo.com")
    h2, _ = await _registrar(client, "b@exemplo.com")
    bid = str(uuid4())
    await _batch(client, h1, _mut("bloco", "criar", bid, _bloco_payload(cat1)))
    await _batch(client, h1, _mut("bloco", "excluir", bid))

    corpo = (await client.get("/sync/mudancas", headers=h2)).json()
    assert corpo["blocos"] == []
    assert corpo["excluidos"] == []
    assert all(c["id"] != cat1 for c in corpo["categorias"])

    # usuário 2 não consegue excluir/atualizar entidade do usuário 1
    [res] = await _batch(client, h2, _mut("bloco", "excluir", bid))
    assert res["status"] == "ignorado"


async def test_modelo_bloco_criar_atualizar_excluir(client: AsyncClient) -> None:
    headers, cat = await _registrar(client, "a@exemplo.com")
    mid = str(uuid4())
    payload = {
        "categoria_id": cat,
        "titulo": "Treino",
        "dia_semana": 1,
        "hora_inicio": "07:00",
        "hora_fim": "08:00",
        "pausas": [{"offset_min": 10, "duracao_min": 5}],
        "versao": 99,
    }
    [criado] = await _batch(client, headers, _mut("modelo_bloco", "criar", mid, payload))
    assert criado["status"] == "aplicado"
    assert criado["versao_servidor"] == 1

    [pausa_ruim] = await _batch(
        client,
        headers,
        _mut(
            "modelo_bloco",
            "atualizar",
            mid,
            {"pausas": [{"offset_min": 50, "duracao_min": 30}]},
            versao_base=1,
        ),
    )
    assert pausa_ruim["status"] == "erro"

    [ok] = await _batch(
        client, headers, _mut("modelo_bloco", "atualizar", mid, {"titulo": "Corrida"}, 1)
    )
    assert ok["status"] == "aplicado"
    [conf] = await _batch(
        client, headers, _mut("modelo_bloco", "atualizar", mid, {"titulo": "X"}, 1)
    )
    assert conf["status"] == "conflito"
    assert conf["entidade_servidor"]["titulo"] == "Corrida"

    modelos = (await client.get("/modelos-bloco", headers=headers)).json()
    assert [m["titulo"] for m in modelos] == ["Corrida"]

    [exc] = await _batch(client, headers, _mut("modelo_bloco", "excluir", mid))
    assert exc["status"] == "aplicado"
    assert (await client.get("/modelos-bloco", headers=headers)).json() == []
