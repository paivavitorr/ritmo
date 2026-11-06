from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.bloco import Bloco
from app.models.lembrete import Lembrete
from app.services import modelo_semana as servico

# 2030-01-06 é domingo; a quarta-feira da semana é 2030-01-09 (dia_semana = 3)
SEMANA = "2030-01-06"


async def _usuario(client: AsyncClient) -> tuple[dict[str, str], str]:
    r = await client.post(
        "/auth/registrar",
        json={
            "email": "modelo@exemplo.com",
            "senha": "senha-segura-123",
            "nome": "Modelo",
            "fuso": "America/Manaus",
        },
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cat = (await client.get("/categorias", headers=headers)).json()[0]["id"]
    return headers, cat


async def _modelo(
    client: AsyncClient, headers: dict[str, str], cat: str, lembretes: list[int]
) -> str:
    r = await client.post(
        "/modelos-bloco",
        headers=headers,
        json={
            "categoria_id": cat,
            "titulo": "Leitura",
            "dia_semana": 3,
            "hora_inicio": "08:00:00",
            "hora_fim": "09:00:00",
            "lembretes": lembretes,
        },
    )
    assert r.status_code == 201
    return str(r.json()["id"])


async def _contar(modelo: type[Bloco] | type[Lembrete]) -> int:
    async with SessionLocal() as session:
        return int((await session.execute(select(func.count()).select_from(modelo))).scalar_one())


async def test_aplicar_usa_lembretes_do_modelo(client: AsyncClient) -> None:
    headers, cat = await _usuario(client)
    await _modelo(client, headers, cat, [10, 30])

    r = await client.post(f"/semanas/{SEMANA}/aplicar-modelo", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    async with SessionLocal() as session:
        lembretes = (await session.execute(select(Lembrete))).scalars().all()
    assert sorted((x.antecedencia_min, x.status) for x in lembretes) == [
        (10, "pendente"),
        (30, "pendente"),
    ]

    # Reaplicar sem mudanças não recria lembretes
    await client.post(f"/semanas/{SEMANA}/aplicar-modelo", headers=headers)
    assert await _contar(Lembrete) == 2


async def test_modelo_sem_lembretes_usa_padrao_do_usuario(client: AsyncClient) -> None:
    headers, cat = await _usuario(client)
    await _modelo(client, headers, cat, [])
    padrao = (await client.get("/auth/eu", headers=headers)).json()["antecedencia_padrao_min"]

    await client.post(f"/semanas/{SEMANA}/aplicar-modelo", headers=headers)
    async with SessionLocal() as session:
        lembretes = (await session.execute(select(Lembrete))).scalars().all()
    assert [x.antecedencia_min for x in lembretes] == [padrao]


async def test_modelos_inativos_e_excluidos_sao_ignorados(client: AsyncClient) -> None:
    headers, cat = await _usuario(client)
    inativo = await _modelo(client, headers, cat, [])
    excluido = await _modelo(client, headers, cat, [])
    await client.patch(f"/modelos-bloco/{inativo}", headers=headers, json={"ativo": False})
    assert (await client.delete(f"/modelos-bloco/{excluido}", headers=headers)).status_code == 204

    r = await client.post(f"/semanas/{SEMANA}/aplicar-modelo", headers=headers)
    assert r.status_code == 200
    assert r.json() == []
    assert await _contar(Bloco) == 0


async def test_aplicacao_e_atomica_quando_falha_no_meio(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, cat = await _usuario(client)
    await _modelo(client, headers, cat, [10])

    async def quebrado(*_args: object, **_kwargs: object) -> None:
        raise IntegrityError("insert", {}, Exception("aplicação concorrente"))

    monkeypatch.setattr(servico, "agendar_lembrete_para_bloco", quebrado)
    r = await client.post(f"/semanas/{SEMANA}/aplicar-modelo", headers=headers)
    assert r.status_code == 409

    # Nenhum bloco ficou gravado pela metade
    assert await _contar(Bloco) == 0
    assert await _contar(Lembrete) == 0


async def test_servico_nao_faz_commit(client: AsyncClient) -> None:
    from datetime import date

    from app.models.usuario import Usuario

    headers, cat = await _usuario(client)
    await _modelo(client, headers, cat, [])
    usuario_id = UUID((await client.get("/auth/eu", headers=headers)).json()["id"])

    async with SessionLocal() as session:
        usuario = await session.get(Usuario, usuario_id)
        assert usuario is not None
        blocos = await servico.MaterializadorSemanaService(session).aplicar_modelo_na_semana(
            usuario, date(2030, 1, 6)
        )
        assert len(blocos) == 1
        await session.rollback()

    assert await _contar(Bloco) == 0
