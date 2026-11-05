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


async def test_ciclo_cronometro_iniciar_pausar_retomar_concluir_e_auto_encerrar(
    client: AsyncClient,
) -> None:
    _, headers = await _criar_usuario_com_token(client)
    cats = (await client.get("/categorias", headers=headers)).json()
    cat_trabalho = cats[0]["id"]
    cat_estudo = cats[1]["id"]

    # Iniciar cronômetro às 10:00:00Z
    ini1 = await client.post(
        "/execucoes/iniciar",
        headers=headers,
        json={
            "categoria_id": cat_trabalho,
            "instante": "2026-11-05T10:00:00Z",
        },
    )
    assert ini1.status_code == 201
    exec1 = ini1.json()
    exec1_id = exec1["id"]
    assert exec1["status"] == "em_andamento"
    assert exec1["fim"] is None

    # GET /execucoes/ativa retorna a execução em andamento
    ativa = await client.get("/execucoes/ativa", headers=headers)
    assert ativa.status_code == 200
    assert ativa.json()["id"] == exec1_id

    # Pausar às 10:30:00Z
    pausada = await client.post(
        f"/execucoes/{exec1_id}/pausar",
        headers=headers,
        json={"instante": "2026-11-05T10:30:00Z"},
    )
    assert pausada.status_code == 200
    assert len(pausada.json()["pausas"]) == 1
    assert pausada.json()["pausas"][0]["fim"] is None

    # Tentar pausar novamente retorna 409
    dup_pausa = await client.post(f"/execucoes/{exec1_id}/pausar", headers=headers)
    assert dup_pausa.status_code == 409

    # Retomar às 10:40:00Z (10 min de pausa = 600s)
    retomada = await client.post(
        f"/execucoes/{exec1_id}/retomar",
        headers=headers,
        json={"instante": "2026-11-05T10:40:00Z"},
    )
    assert retomada.status_code == 200
    assert retomada.json()["pausas"][0]["fim"] is not None

    # Iniciar segunda execução às 11:00:00Z encerra automaticamente a primeira
    ini2 = await client.post(
        "/execucoes/iniciar",
        headers=headers,
        json={
            "categoria_id": cat_estudo,
            "instante": "2026-11-05T11:00:00Z",
        },
    )
    assert ini2.status_code == 201
    exec2_id = ini2.json()["id"]

    # Verificar que a primeira foi concluída com 3600s - 600s = 3000s líquidos
    e1_final = await client.get(f"/execucoes/{exec1_id}", headers=headers)
    assert e1_final.status_code == 200
    assert e1_final.json()["status"] == "concluida"
    assert e1_final.json()["segundos_liquidos"] == 3000

    # Concluir a segunda às 11:25:00Z (1500s)
    conc2 = await client.post(
        f"/execucoes/{exec2_id}/concluir",
        headers=headers,
        json={"instante": "2026-11-05T11:25:00Z", "status": "concluida"},
    )
    assert conc2.status_code == 200
    assert conc2.json()["status"] == "concluida"
    assert conc2.json()["segundos_liquidos"] == 1500

    # Nenhuma ativa restante
    ativa_vazia = await client.get("/execucoes/ativa", headers=headers)
    assert ativa_vazia.status_code == 200
    assert ativa_vazia.json() is None


async def test_resumo_calcula_aderencia_e_separa_espontaneo(client: AsyncClient) -> None:
    _, headers = await _criar_usuario_com_token(client)
    cats = (await client.get("/categorias", headers=headers)).json()
    cat_estudo = next(c for c in cats if c["nome"] == "Estudo")["id"]

    # 1. Bloco de Estudo: 2h (10:00 às 12:00 = 7200s)
    b = await client.post(
        "/blocos",
        headers=headers,
        json={
            "categoria_id": cat_estudo,
            "titulo": "Algoritmos",
            "inicio": "2026-11-06T10:00:00Z",
            "fim": "2026-11-06T12:00:00Z",
        },
    )
    assert b.status_code == 201
    bloco_id = b.json()["id"]

    # Execução vinculada: executou 1h das 2h (10:00 às 11:00 = 3600s)
    ex_bloco = await client.post(
        "/execucoes",
        headers=headers,
        json={
            "categoria_id": cat_estudo,
            "bloco_id": bloco_id,
            "inicio": "2026-11-06T10:00:00Z",
            "fim": "2026-11-06T11:00:00Z",
            "status": "parcial",
            "origem": "cronometro",
        },
    )
    assert ex_bloco.status_code == 201

    # 2. Execução espontânea/avulsa (sem bloco_id): 30 min (1800s)
    ex_avulsa = await client.post(
        "/execucoes",
        headers=headers,
        json={
            "categoria_id": cat_estudo,
            "inicio": "2026-11-06T15:00:00Z",
            "fim": "2026-11-06T15:30:00Z",
            "status": "concluida",
            "origem": "cronometro",
        },
    )
    assert ex_avulsa.status_code == 201

    # Consulta resumo do dia
    r = await client.get("/resumo?de=2026-11-06&ate=2026-11-06", headers=headers)
    assert r.status_code == 200
    resumo_dados = r.json()

    # Categoria Estudo deve ter: planejado 7200s, executado 3600s (aderência volume 0.5)
    cat_resumo = next(c for c in resumo_dados["categorias"] if c["categoria_id"] == cat_estudo)
    assert cat_resumo["segundos_planejados"] == 7200
    assert cat_resumo["segundos_executados"] == 3600
    assert cat_resumo["aderencia_volume"] == 0.5
    assert cat_resumo["eh_espontaneo"] is False

    # Linha espontânea separada com 1800s
    linha_espontanea = next(c for c in resumo_dados["categorias"] if c["eh_espontaneo"] is True)
    assert linha_espontanea["segundos_executados"] == 1800
    assert linha_espontanea["segundos_planejados"] == 0

    assert len(resumo_dados["faixas_dias"]) == 1
    faixa = resumo_dados["faixas_dias"][0]
    assert len(faixa["planejados"]) == 1
    assert len(faixa["executados"]) == 2


async def test_confirmar_bloco_substitui_execucao_existente(client: AsyncClient) -> None:
    _, headers = await _criar_usuario_com_token(client)
    cat_id = (await client.get("/categorias", headers=headers)).json()[0]["id"]

    b = await client.post(
        "/blocos",
        headers=headers,
        json={
            "categoria_id": cat_id,
            "titulo": "Bloco único",
            "inicio": "2026-11-05T14:00:00Z",
            "fim": "2026-11-05T15:00:00Z",
        },
    )
    bloco_id = b.json()["id"]

    c1 = await client.post(
        "/execucoes/confirmar-bloco",
        headers=headers,
        json={"bloco_id": bloco_id, "status": "concluida"},
    )
    assert c1.status_code == 200
    exec_id = c1.json()["id"]
    assert c1.json()["segundos_liquidos"] == 3600

    # Segundo toque atualiza a mesma execução em vez de duplicar
    c2 = await client.post(
        "/execucoes/confirmar-bloco",
        headers=headers,
        json={"bloco_id": bloco_id, "status": "pulada"},
    )
    assert c2.status_code == 200
    assert c2.json()["id"] == exec_id
    assert c2.json()["status"] == "pulada"
    assert c2.json()["segundos_liquidos"] == 0
