from datetime import UTC, datetime
from uuid import uuid4

from httpx import AsyncClient


async def _criar_usuario_com_token(
    client: AsyncClient, email: str = "ana@exemplo.com"
) -> tuple[str, dict[str, str]]:
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
    token = r.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def test_categorias_padrao_criadas_no_registro_e_protecao_em_uso(
    client: AsyncClient,
) -> None:
    _, headers = await _criar_usuario_com_token(client)

    lista = await client.get("/categorias", headers=headers)
    assert lista.status_code == 200
    cats = lista.json()
    assert len(cats) == 6
    nomes = [c["nome"] for c in cats]
    assert nomes == ["Trabalho", "Estudo", "Treino", "Descanso", "Pessoal", "Compromissos"]
    descanso = next(c for c in cats if c["nome"] == "Descanso")
    assert descanso["conta_como_produtiva"] is False

    # Criar um bloco usando a categoria Trabalho e tentar excluir a categoria -> 409
    cat_trabalho_id = cats[0]["id"]
    b = await client.post(
        "/blocos",
        headers=headers,
        json={
            "categoria_id": cat_trabalho_id,
            "titulo": "Foco profundo",
            "inicio": "2026-11-04T12:00:00Z",
            "fim": "2026-11-04T14:00:00Z",
        },
    )
    assert b.status_code == 201

    del_em_uso = await client.delete(f"/categorias/{cat_trabalho_id}", headers=headers)
    assert del_em_uso.status_code == 409

    # Categoria livre pode ser excluída normalmente
    del_livre = await client.delete(f"/categorias/{descanso['id']}", headers=headers)
    assert del_livre.status_code == 204


async def test_isolamento_multi_usuario(client: AsyncClient) -> None:
    _, headers_a = await _criar_usuario_com_token(client, "user_a@exemplo.com")
    _, headers_b = await _criar_usuario_com_token(client, "user_b@exemplo.com")

    cats_a = (await client.get("/categorias", headers=headers_a)).json()
    cat_a_id = cats_a[0]["id"]

    # Usuário B não consegue ver nem usar a categoria do usuário A
    get_b = await client.get(f"/categorias/{cat_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    bloco_b = await client.post(
        "/blocos",
        headers=headers_b,
        json={
            "categoria_id": cat_a_id,
            "titulo": "Invasão",
            "inicio": "2026-11-04T12:00:00Z",
            "fim": "2026-11-04T13:00:00Z",
        },
    )
    assert bloco_b.status_code == 404


async def test_bloco_pausas_if_match_e_confirmacao(client: AsyncClient) -> None:
    _, headers = await _criar_usuario_com_token(client)
    cat_id = (await client.get("/categorias", headers=headers)).json()[0]["id"]

    # Bloco de 2h (7200s) com 1 pausa de 15min (900s) -> 6300s líquidos
    criado = await client.post(
        "/blocos",
        headers=headers,
        json={
            "categoria_id": cat_id,
            "titulo": "Manhã de código",
            "inicio": "2026-11-04T12:00:00Z",
            "fim": "2026-11-04T14:00:00Z",
            "pausas": [
                {
                    "inicio": "2026-11-04T13:00:00Z",
                    "fim": "2026-11-04T13:15:00Z",
                }
            ],
        },
    )
    assert criado.status_code == 201
    corpo = criado.json()
    bloco_id = corpo["id"]
    assert corpo["segundos_liquidos_planejados"] == 6300
    assert corpo["versao"] == 1

    # PATCH com If-Match incorreto -> 409
    conflito = await client.patch(
        f"/blocos/{bloco_id}",
        headers={**headers, "If-Match": "99"},
        json={"titulo": "Conflito"},
    )
    assert conflito.status_code == 409

    # PATCH com If-Match correto -> 200 e versao=2
    ok = await client.patch(
        f"/blocos/{bloco_id}",
        headers={**headers, "If-Match": "1"},
        json={"titulo": "Manhã atualizada"},
    )
    assert ok.status_code == 200
    assert ok.json()["versao"] == 2

    # Confirmar bloco ("Fiz como planejado") cria execução com os mesmos 6300s líquidos
    conf = await client.post(f"/blocos/{bloco_id}/confirmar", headers=headers)
    assert conf.status_code == 201
    exec_json = conf.json()
    assert exec_json["origem"] == "confirmacao"
    assert exec_json["status"] == "concluida"
    assert exec_json["segundos_liquidos"] == 6300
    assert len(exec_json["pausas"]) == 1


async def test_materializacao_semana_idempotente_e_desvinculacao(
    client: AsyncClient,
) -> None:
    _, headers = await _criar_usuario_com_token(client)
    cats = (await client.get("/categorias", headers=headers)).json()
    cat_estudo = next(c for c in cats if c["nome"] == "Estudo")["id"]

    # 2026-11-04 é quarta-feira -> na convenção Ritmo (0=dom..6=sáb), quarta = 3
    m = await client.post(
        "/modelos-bloco",
        headers=headers,
        json={
            "categoria_id": cat_estudo,
            "titulo": "Leitura técnica",
            "dia_semana": 3,
            "hora_inicio": "08:00:00",
            "hora_fim": "09:30:00",
            "pausas": [{"offset_min": 45, "duracao_min": 10}],
            "lembretes": [10],
        },
    )
    assert m.status_code == 201
    modelo_id = m.json()["id"]

    # Aplicar na semana iniciando em domingo 2026-11-01
    r1 = await client.post("/semanas/2026-11-01/aplicar-modelo", headers=headers)
    assert r1.status_code == 200
    blocos_1 = r1.json()
    assert len(blocos_1) == 1
    b_quarta = blocos_1[0]
    assert b_quarta["data_local"] == "2026-11-04"
    # 90min - 10min = 80min = 4800s
    assert b_quarta["segundos_liquidos_planejados"] == 4800
    assert b_quarta["desvinculado"] is False

    # Reaplicar sem mudanças é idempotente (mesmo ID, mesma versao e mesmos IDs de pausa)
    pausa_id_original = b_quarta["pausas_planejadas"][0]["id"]
    r2 = await client.post("/semanas/2026-11-01/aplicar-modelo", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["id"] == b_quarta["id"]
    assert r2.json()[0]["versao"] == 1
    assert r2.json()[0]["pausas_planejadas"][0]["id"] == pausa_id_original

    # Atualizar o modelo enquanto o bloco ainda está vinculado -> incrementa versao do bloco
    await client.patch(
        f"/modelos-bloco/{modelo_id}",
        headers=headers,
        json={"titulo": "Leitura atualizada pelo modelo"},
    )
    r2b = await client.post("/semanas/2026-11-01/aplicar-modelo", headers=headers)
    assert r2b.status_code == 200
    assert r2b.json()[0]["titulo"] == "Leitura atualizada pelo modelo"
    assert r2b.json()[0]["versao"] == 2

    # Editar a instância de quarta a marca como `desvinculado=True`
    edit = await client.patch(
        f"/blocos/{b_quarta['id']}",
        headers=headers,
        json={"titulo": "Leitura customizada na quarta"},
    )
    assert edit.status_code == 200
    assert edit.json()["desvinculado"] is True

    # Atualizar o modelo e reaplicar NÃO sobrescreve a instância desvinculada
    await client.patch(
        f"/modelos-bloco/{modelo_id}",
        headers=headers,
        json={"titulo": "Novo título do modelo"},
    )
    r3 = await client.post("/semanas/2026-11-01/aplicar-modelo", headers=headers)
    assert r3.status_code == 200
    assert r3.json()[0]["titulo"] == "Leitura customizada na quarta"

    # Materializar a próxima semana (2026-11-08 -> quarta 2026-11-11) e mover o bloco de
    # 2026-11-04 para 2026-11-11 não deve violar `uq_bloco_modelo_data_local`
    r_prox = await client.post("/semanas/2026-11-08/aplicar-modelo", headers=headers)
    assert r_prox.status_code == 200
    mover = await client.patch(
        f"/blocos/{b_quarta['id']}",
        headers=headers,
        json={
            "inicio": "2026-11-11T15:00:00Z",
            "fim": "2026-11-11T16:30:00Z",
            "pausas": [],
        },
    )
    assert mover.status_code == 200
    assert mover.json()["data_local"] == "2026-11-11"
    assert mover.json()["modelo_bloco_id"] is None


async def test_execucao_manual_recalcula_segundos_liquidos(client: AsyncClient) -> None:
    _, headers = await _criar_usuario_com_token(client)
    cat_id = (await client.get("/categorias", headers=headers)).json()[0]["id"]

    id_cliente = str(uuid4())
    criada = await client.post(
        "/execucoes",
        headers=headers,
        json={
            "id": id_cliente,
            "categoria_id": cat_id,
            "inicio": datetime(2026, 11, 4, 18, 0, tzinfo=UTC).isoformat(),
            "fim": datetime(2026, 11, 4, 19, 0, tzinfo=UTC).isoformat(),
            "pausas": [
                {
                    "inicio": datetime(2026, 11, 4, 18, 20, tzinfo=UTC).isoformat(),
                    "fim": datetime(2026, 11, 4, 18, 30, tzinfo=UTC).isoformat(),
                }
            ],
        },
    )
    assert criada.status_code == 201
    assert criada.json()["id"] == id_cliente
    assert criada.json()["segundos_liquidos"] == 3000  # 60min - 10min = 50min

    # Atualizar fim para 19:30 -> 90min - 10min = 80min = 4800s
    atualizada = await client.patch(
        f"/execucoes/{id_cliente}",
        headers=headers,
        json={"fim": datetime(2026, 11, 4, 19, 30, tzinfo=UTC).isoformat()},
    )
    assert atualizada.status_code == 200
    assert atualizada.json()["segundos_liquidos"] == 4800

    listagem = await client.get("/execucoes?de=2026-11-04&ate=2026-11-04", headers=headers)
    assert listagem.status_code == 200
    assert len(listagem.json()) == 1
