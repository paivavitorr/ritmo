import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.schemas.lembrete import PushAssinaturaCreate

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"


async def _registrar(client: AsyncClient, email: str) -> dict[str, str]:
    resposta = await client.post(
        "/auth/registrar",
        json={"email": email, "senha": "senha-segura-123", "nome": "Teste", "fuso": "UTC"},
    )
    assert resposta.status_code == 201
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


def _corpo(
    endpoint: str = ENDPOINT, p256dh: str = "chave-p", auth: str = "chave-a"
) -> dict[str, str]:
    return {"endpoint": endpoint, "p256dh": p256dh, "auth": auth}


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/x",
        "https://updates.push.services.mozilla.com/wpush/v2/x",
        "https://a.push.services.mozilla.com/x",
        "https://wns2-par02p.notify.windows.com/x",
        "https://web.push.apple.com/x",
        "https://api.push.apple.com/x",
    ],
)
def test_endpoints_permitidos(endpoint: str) -> None:
    assert PushAssinaturaCreate(endpoint=endpoint, p256dh="p", auth="a").endpoint == endpoint


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/x",
        "https://evil.example.com/x",
        "https://fcm.googleapis.com.evil.com/x",
        "https://evilpush.apple.com/x",
        "https://127.0.0.1/x",
        "ftp://fcm.googleapis.com/x",
        "nao-e-url",
    ],
)
def test_endpoints_rejeitados(endpoint: str) -> None:
    with pytest.raises(ValidationError):
        PushAssinaturaCreate(endpoint=endpoint, p256dh="p", auth="a")


def test_limites_de_tamanho() -> None:
    with pytest.raises(ValidationError):
        PushAssinaturaCreate(endpoint=ENDPOINT, p256dh="p" * 257, auth="a")
    with pytest.raises(ValidationError):
        PushAssinaturaCreate(endpoint=ENDPOINT, p256dh="p", auth="a" * 101)
    with pytest.raises(ValidationError):
        PushAssinaturaCreate(endpoint=ENDPOINT, p256dh="p", auth="a", user_agent="u" * 513)


async def test_assinar_endpoint_fora_da_allowlist_422(client: AsyncClient) -> None:
    headers = await _registrar(client, "a@exemplo.com")
    r = await client.post(
        "/push/assinar", json=_corpo("https://evil.example.com/x"), headers=headers
    )
    assert r.status_code == 422


async def test_mesmo_usuario_atualiza_chaves(client: AsyncClient) -> None:
    headers = await _registrar(client, "a@exemplo.com")
    assert (await client.post("/push/assinar", json=_corpo(), headers=headers)).status_code == 201
    r = await client.post("/push/assinar", json=_corpo(p256dh="nova"), headers=headers)
    assert r.status_code == 201
    assert r.json()["p256dh"] == "nova"


async def test_endpoint_de_outro_usuario_sem_posse_409(client: AsyncClient) -> None:
    dono = await _registrar(client, "dono@exemplo.com")
    intruso = await _registrar(client, "intruso@exemplo.com")
    assert (await client.post("/push/assinar", json=_corpo(), headers=dono)).status_code == 201

    r = await client.post(
        "/push/assinar", json=_corpo(p256dh="outra", auth="outra"), headers=intruso
    )
    assert r.status_code == 409


async def test_endpoint_de_outro_usuario_com_posse_transfere(client: AsyncClient) -> None:
    dono = await _registrar(client, "dono@exemplo.com")
    novo = await _registrar(client, "novo@exemplo.com")
    antigo = await client.post("/push/assinar", json=_corpo(), headers=dono)
    assert antigo.status_code == 201

    r = await client.post("/push/assinar", json=_corpo(), headers=novo)
    assert r.status_code == 201
    eu_id = (await client.get("/auth/eu", headers=novo)).json()["id"]
    assert r.json()["usuario_id"] == eu_id
    assert r.json()["id"] != antigo.json()["id"]
