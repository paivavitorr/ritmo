from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.tempo import garantir_utc
from app.db import SessionLocal
from app.models.lembrete import Lembrete, PushAssinatura
from app.services import lembrete as servico
from app.services.lembrete import ResultadoEnvio, processar_lembretes_pendentes

ENDPOINT = "https://push.exemplo.com/abc"


class Cenario:
    def __init__(self, headers: dict[str, str], usuario_id: UUID, bloco_id: UUID, cat: str) -> None:
        self.headers = headers
        self.usuario_id = usuario_id
        self.bloco_id = bloco_id
        self.cat = cat
        self.bloco_inicio = (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0)

    @property
    def disparar_em(self) -> datetime:
        return self.bloco_inicio - timedelta(minutes=10)


async def _cenario(client: AsyncClient, com_assinatura: bool = True) -> Cenario:
    r = await client.post(
        "/auth/registrar",
        json={
            "email": "push@exemplo.com",
            "senha": "senha-segura-123",
            "nome": "Push",
            "fuso": "America/Manaus",
        },
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    usuario_id = UUID(r.json()["usuario"]["id"])
    cat = (await client.get("/categorias", headers=headers)).json()[0]["id"]

    inicio = (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0)
    b = await client.post(
        "/blocos",
        headers=headers,
        json={
            "categoria_id": cat,
            "titulo": "Leitura",
            "inicio": inicio.isoformat(),
            "fim": (inicio + timedelta(hours=1)).isoformat(),
        },
    )
    assert b.status_code == 201
    cenario = Cenario(headers, usuario_id, UUID(b.json()["id"]), cat)
    cenario.bloco_inicio = inicio

    if com_assinatura:
        async with SessionLocal() as session:
            session.add(
                PushAssinatura(usuario_id=usuario_id, endpoint=ENDPOINT, p256dh="k", auth="a")
            )
            await session.commit()
    return cenario


async def _lembretes(bloco_id: UUID) -> list[Lembrete]:
    async with SessionLocal() as session:
        resultado = await session.execute(
            select(Lembrete).where(Lembrete.bloco_id == bloco_id).order_by(Lembrete.criado_em)
        )
        return list(resultado.scalars().all())


async def _processar(agora: datetime) -> int:
    async with SessionLocal() as session:
        return await processar_lembretes_pendentes(session, agora=agora)


def _simular(
    monkeypatch: pytest.MonkeyPatch, resposta: Callable[[], ResultadoEnvio]
) -> list[Mapping[str, object]]:
    chamadas: list[Mapping[str, object]] = []

    def falso(
        endpoint: str, p256dh: str, auth: str, payload: Mapping[str, object], timeout: int = 5
    ) -> ResultadoEnvio:
        chamadas.append(payload)
        return resposta()

    monkeypatch.setattr(servico, "disparar_notificacao_push", falso)
    return chamadas


async def test_envio_com_sucesso_marca_disparado(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    estados_durante_envio: list[str] = []

    def resposta() -> ResultadoEnvio:
        # Em outra thread/sessão: o lock já foi liberado e o estado está commitado
        estados_durante_envio.append("chamado")
        return ResultadoEnvio("ok")

    chamadas = _simular(monkeypatch, resposta)
    assert await _processar(c.disparar_em + timedelta(seconds=5)) == 1

    assert len(chamadas) == 1
    assert chamadas[0]["bloco_id"] == str(c.bloco_id)
    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "disparado"
    assert lemb.tentativas == 1


async def test_status_enviando_e_commitado_antes_do_envio(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    c = await _cenario(client)
    visto: list[str] = []
    loop = asyncio.get_running_loop()

    def resposta() -> ResultadoEnvio:
        futuro = asyncio.run_coroutine_threadsafe(_lembretes(c.bloco_id), loop)
        visto.append(futuro.result(timeout=5)[0].status)
        return ResultadoEnvio("ok")

    _simular(monkeypatch, resposta)
    await _processar(c.disparar_em + timedelta(seconds=5))
    assert visto == ["enviando"]


async def test_assinatura_gone_410_e_removida(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    _simular(monkeypatch, lambda: ResultadoEnvio("expirada", erro="410 Gone"))
    await _processar(c.disparar_em + timedelta(seconds=5))

    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "sem_dispositivo"
    async with SessionLocal() as session:
        assert (await session.execute(select(PushAssinatura))).scalars().all() == []


async def test_429_respeita_retry_after_e_backoff_ate_erro(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    resposta = {"valor": ResultadoEnvio("limitada", retry_after_s=90, erro="429")}
    _simular(monkeypatch, lambda: resposta["valor"])

    t0 = c.disparar_em + timedelta(seconds=5)
    await _processar(t0)
    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "pendente"
    assert garantir_utc(lemb.disparar_em) == t0 + timedelta(seconds=90)
    assert lemb.tentativas == 1

    # Antes do horário de retry nada é enviado
    assert await _processar(t0 + timedelta(seconds=30)) == 0

    # Falha transitória: backoff de 2 min na 2ª tentativa
    resposta["valor"] = ResultadoEnvio("erro", erro="boom")
    t1 = t0 + timedelta(seconds=90)
    await _processar(t1)
    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "pendente"
    assert garantir_utc(lemb.disparar_em) == t1 + timedelta(minutes=2)

    # 3ª tentativa falha: esgotou -> erro
    t2 = t1 + timedelta(minutes=2)
    await _processar(t2)
    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "erro"
    assert lemb.tentativas == 3
    assert lemb.ultimo_erro == "boom"


async def test_primeiro_backoff_e_de_30_segundos(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    _simular(monkeypatch, lambda: ResultadoEnvio("erro", erro="rede"))
    t0 = c.disparar_em + timedelta(seconds=5)
    await _processar(t0)
    [lemb] = await _lembretes(c.bloco_id)
    assert garantir_utc(lemb.disparar_em) == t0 + timedelta(seconds=30)


async def test_lembrete_expira_se_o_bloco_ja_comecou(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    chamadas = _simular(monkeypatch, lambda: ResultadoEnvio("ok"))
    await _processar(c.bloco_inicio + timedelta(minutes=1))

    assert chamadas == []
    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "expirado"


async def test_sem_assinaturas_marca_sem_dispositivo(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client, com_assinatura=False)
    chamadas = _simular(monkeypatch, lambda: ResultadoEnvio("ok"))
    await _processar(c.disparar_em + timedelta(seconds=5))
    assert chamadas == []
    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "sem_dispositivo"


async def test_lembrete_preso_em_enviando_volta_e_e_enviado(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    agora = c.disparar_em + timedelta(minutes=1)
    async with SessionLocal() as session:
        lemb = (await session.execute(select(Lembrete))).scalars().one()
        lemb.status = "enviando"
        lemb.tentativas = 1
        lemb.tentativa_em = agora - timedelta(minutes=6)
        await session.commit()

    chamadas = _simular(monkeypatch, lambda: ResultadoEnvio("ok"))
    await _processar(agora)
    assert len(chamadas) == 1
    [lemb] = await _lembretes(c.bloco_id)
    assert lemb.status == "disparado"
    assert lemb.tentativas == 2


async def test_enviando_recente_nao_e_reprocessado(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    agora = c.disparar_em + timedelta(minutes=1)
    async with SessionLocal() as session:
        lemb = (await session.execute(select(Lembrete))).scalars().one()
        lemb.status = "enviando"
        lemb.tentativa_em = agora - timedelta(minutes=1)
        await session.commit()

    chamadas = _simular(monkeypatch, lambda: ResultadoEnvio("ok"))
    assert await _processar(agora) == 0
    assert chamadas == []


async def test_reagendar_nao_duplica_lembrete_ja_enviado(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = await _cenario(client)
    _simular(monkeypatch, lambda: ResultadoEnvio("ok"))
    await _processar(c.disparar_em + timedelta(seconds=5))

    # Editar só o título reagenda; o horário é o mesmo e o aviso já foi enviado
    r = await client.patch(f"/blocos/{c.bloco_id}", headers=c.headers, json={"titulo": "Novo"})
    assert r.status_code == 200
    lembretes = await _lembretes(c.bloco_id)
    assert [x.status for x in lembretes] == ["disparado"]

    # Mover o bloco muda o horário de disparo: novo lembrete pendente
    novo_inicio = c.bloco_inicio + timedelta(hours=3)
    r = await client.patch(
        f"/blocos/{c.bloco_id}",
        headers=c.headers,
        json={
            "inicio": novo_inicio.isoformat(),
            "fim": (novo_inicio + timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 200
    assert sorted(x.status for x in await _lembretes(c.bloco_id)) == ["disparado", "pendente"]
