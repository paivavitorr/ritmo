from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.execucao import Execucao


async def _usuario(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    r = await client.post(
        "/auth/registrar",
        json={
            "email": "exec@exemplo.com",
            "senha": "senha-segura-123",
            "nome": "Exec",
            "fuso": "America/Manaus",
        },
    )
    assert r.status_code == 201
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cats = (await client.get("/categorias", headers=headers)).json()
    return headers, cats[0]["id"], r.json()["usuario"]["id"]


async def _bloco(client: AsyncClient, headers: dict[str, str], cat: str) -> str:
    r = await client.post(
        "/blocos",
        headers=headers,
        json={
            "categoria_id": cat,
            "titulo": "Foco",
            "inicio": "2026-11-06T12:00:00Z",
            "fim": "2026-11-06T14:00:00Z",
            "pausas": [{"inicio": "2026-11-06T13:00:00Z", "fim": "2026-11-06T13:10:00Z"}],
        },
    )
    assert r.status_code == 201
    return str(r.json()["id"])


@pytest.mark.parametrize("rota", ["blocos", "execucoes"])
async def test_confirmar_idempotente(client: AsyncClient, rota: str) -> None:
    headers, cat, _ = await _usuario(client)
    bloco_id = await _bloco(client, headers, cat)

    def chamar() -> object:
        if rota == "blocos":
            return client.post(f"/blocos/{bloco_id}/confirmar", headers=headers)
        return client.post(
            "/execucoes/confirmar-bloco", headers=headers, json={"bloco_id": bloco_id}
        )

    primeira = await chamar()  # type: ignore[misc]
    segunda = await chamar()  # type: ignore[misc]
    assert primeira.json()["id"] == segunda.json()["id"]
    assert segunda.json()["status"] == "concluida"
    assert segunda.json()["segundos_liquidos"] == 6600  # 2h - 10min de pausa
    assert segunda.json()["versao"] == primeira.json()["versao"]

    lista = await client.get("/execucoes?de=2026-11-06&ate=2026-11-06", headers=headers)
    assert len(lista.json()) == 1


async def test_confirmar_nao_sobrescreve_tempo_medido(client: AsyncClient) -> None:
    headers, cat, _ = await _usuario(client)
    bloco_id = await _bloco(client, headers, cat)
    medida = await client.post(
        "/execucoes",
        headers=headers,
        json={
            "categoria_id": cat,
            "bloco_id": bloco_id,
            "inicio": "2026-11-06T12:05:00Z",
            "fim": "2026-11-06T12:35:00Z",
            "status": "parcial",
            "origem": "cronometro",
        },
    )
    assert medida.status_code == 201

    r = await client.post(f"/blocos/{bloco_id}/confirmar", headers=headers)
    assert r.json()["id"] == medida.json()["id"]
    assert r.json()["inicio"].startswith("2026-11-06T12:05:00")
    assert r.json()["fim"].startswith("2026-11-06T12:35:00")
    assert r.json()["segundos_liquidos"] == 1800
    assert r.json()["origem"] == "cronometro"

    lista = await client.get("/execucoes?de=2026-11-06&ate=2026-11-06", headers=headers)
    assert len(lista.json()) == 1


async def test_confirmar_encerra_cronometro_em_andamento(client: AsyncClient) -> None:
    headers, cat, _ = await _usuario(client)
    bloco_id = await _bloco(client, headers, cat)
    iniciada = await client.post(
        "/execucoes/iniciar",
        headers=headers,
        json={"bloco_id": bloco_id, "instante": "2026-11-06T12:00:00Z"},
    )
    assert iniciada.status_code == 201

    r = await client.post(f"/blocos/{bloco_id}/confirmar", headers=headers)
    assert r.json()["id"] == iniciada.json()["id"]
    assert r.json()["status"] == "concluida"
    assert r.json()["fim"] is not None
    assert r.json()["inicio"].startswith("2026-11-06T12:00:00")
    assert (await client.get("/execucoes/ativa", headers=headers)).json() is None


async def test_dois_iniciar_encerra_a_primeira_e_mantem_um_cronometro(
    client: AsyncClient,
) -> None:
    headers, cat, _ = await _usuario(client)
    a = await client.post(
        "/execucoes/iniciar",
        headers=headers,
        json={"categoria_id": cat, "instante": "2026-11-06T10:00:00Z"},
    )
    b = await client.post(
        "/execucoes/iniciar",
        headers=headers,
        json={"categoria_id": cat, "instante": "2026-11-06T11:00:00Z"},
    )
    assert a.status_code == b.status_code == 201
    assert (await client.get("/execucoes/ativa", headers=headers)).json()["id"] == b.json()["id"]
    antiga = await client.get(f"/execucoes/{a.json()['id']}", headers=headers)
    assert antiga.json()["status"] == "concluida"


async def test_iniciar_com_instante_anterior_ao_cronometro_aberto_da_409(
    client: AsyncClient,
) -> None:
    headers, cat, _ = await _usuario(client)
    aberta = await client.post(
        "/execucoes/iniciar",
        headers=headers,
        json={"categoria_id": cat, "instante": "2026-11-06T11:00:00Z"},
    )
    r = await client.post(
        "/execucoes/iniciar",
        headers=headers,
        json={"categoria_id": cat, "instante": "2026-11-06T10:00:00Z"},
    )
    assert r.status_code == 409
    ativa = (await client.get("/execucoes/ativa", headers=headers)).json()
    assert ativa["id"] == aberta.json()["id"]
    assert ativa["fim"] is None


async def test_indice_unico_impede_dois_cronometros_no_banco(client: AsyncClient) -> None:
    from uuid import UUID

    _, cat, usuario_id = await _usuario(client)
    async with SessionLocal() as session:
        for _ in range(2):
            session.add(
                Execucao(
                    usuario_id=UUID(usuario_id),
                    categoria_id=UUID(cat),
                    inicio=datetime(2026, 11, 6, 10, tzinfo=UTC),
                    status="em_andamento",
                )
            )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_criar_com_id_existente_da_409(client: AsyncClient) -> None:
    headers, cat, _ = await _usuario(client)
    ident = str(uuid4())
    corpo = {
        "id": ident,
        "categoria_id": cat,
        "inicio": "2026-11-06T12:00:00Z",
        "fim": "2026-11-06T13:00:00Z",
    }
    assert (await client.post("/execucoes", headers=headers, json=corpo)).status_code == 201
    assert (await client.post("/execucoes", headers=headers, json=corpo)).status_code == 409

    bloco = {
        "id": str(uuid4()),
        "categoria_id": cat,
        "titulo": "X",
        "inicio": "2026-11-06T12:00:00Z",
        "fim": "2026-11-06T13:00:00Z",
    }
    assert (await client.post("/blocos", headers=headers, json=bloco)).status_code == 201
    assert (await client.post("/blocos", headers=headers, json=bloco)).status_code == 409


async def test_patch_incoerente_da_422(client: AsyncClient) -> None:
    headers, cat, _ = await _usuario(client)
    aberta = (
        await client.post(
            "/execucoes/iniciar",
            headers=headers,
            json={"categoria_id": cat, "instante": "2026-11-06T10:00:00Z"},
        )
    ).json()
    url_aberta = f"/execucoes/{aberta['id']}"

    # em_andamento não pode ter fim
    r = await client.patch(url_aberta, headers=headers, json={"fim": "2026-11-06T11:00:00Z"})
    assert r.status_code == 422
    # concluida exige fim
    r = await client.patch(url_aberta, headers=headers, json={"status": "concluida"})
    assert r.status_code == 422

    # concluida com fim válido: ok
    r = await client.patch(
        url_aberta,
        headers=headers,
        json={"status": "concluida", "fim": "2026-11-06T11:00:00Z"},
    )
    assert r.status_code == 200
    assert r.json()["segundos_liquidos"] == 3600

    # fim <= inicio
    r = await client.patch(url_aberta, headers=headers, json={"fim": "2026-11-06T09:00:00Z"})
    assert r.status_code == 422
    # pausa fora do intervalo
    r = await client.patch(
        url_aberta,
        headers=headers,
        json={"pausas": [{"inicio": "2026-11-06T10:50:00Z", "fim": "2026-11-06T11:10:00Z"}]},
    )
    assert r.status_code == 422
    # pausas sobrepostas
    r = await client.patch(
        url_aberta,
        headers=headers,
        json={
            "pausas": [
                {"inicio": "2026-11-06T10:10:00Z", "fim": "2026-11-06T10:30:00Z"},
                {"inicio": "2026-11-06T10:20:00Z", "fim": "2026-11-06T10:40:00Z"},
            ]
        },
    )
    assert r.status_code == 422
    # pausas válidas
    r = await client.patch(
        url_aberta,
        headers=headers,
        json={
            "pausas": [
                {"inicio": "2026-11-06T10:10:00Z", "fim": "2026-11-06T10:20:00Z"},
                {"inicio": "2026-11-06T10:30:00Z", "fim": "2026-11-06T10:40:00Z"},
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["segundos_liquidos"] == 2400


async def test_patch_pausa_aberta_em_execucao_concluida_da_422(client: AsyncClient) -> None:
    headers, cat, _ = await _usuario(client)
    aberta = (
        await client.post(
            "/execucoes/iniciar",
            headers=headers,
            json={"categoria_id": cat, "instante": "2026-11-06T10:00:00Z"},
        )
    ).json()
    await client.post(
        f"/execucoes/{aberta['id']}/pausar",
        headers=headers,
        json={"instante": "2026-11-06T10:30:00Z"},
    )
    # Concluir via PATCH deixando a pausa aberta é incoerente
    r = await client.patch(
        f"/execucoes/{aberta['id']}",
        headers=headers,
        json={"status": "concluida", "fim": "2026-11-06T11:00:00Z"},
    )
    assert r.status_code == 422
