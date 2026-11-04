from httpx import AsyncClient


async def test_vivo(client: AsyncClient) -> None:
    resposta = await client.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


async def test_banco(client: AsyncClient) -> None:
    resposta = await client.get("/saude/banco")
    assert resposta.status_code == 200
