from datetime import UTC, datetime, timedelta

import jwt
from httpx import AsyncClient

from app.config import get_settings


async def _registrar_padrao(client: AsyncClient) -> dict[str, object]:
    resposta = await client.post(
        "/auth/registrar",
        json={
            "email": " Vitor@Exemplo.com ",
            "senha": "senha-segura-123",
            "nome": "Vitor Paiva",
            "fuso": "America/Manaus",
        },
    )
    assert resposta.status_code == 201
    return resposta.json()  # type: ignore[no-any-return]


async def test_registrar_e_obter_eu(client: AsyncClient) -> None:
    dados = await _registrar_padrao(client)
    assert "access_token" in dados
    usuario = dados["usuario"]
    assert isinstance(usuario, dict)
    assert usuario["email"] == "vitor@exemplo.com"
    assert usuario["nome"] == "Vitor Paiva"
    assert usuario["fuso"] == "America/Manaus"

    token = dados["access_token"]
    eu = await client.get("/auth/eu", headers={"Authorization": f"Bearer {token}"})
    assert eu.status_code == 200
    assert eu.json()["id"] == usuario["id"]


async def test_registrar_email_duplicado_retorna_409(client: AsyncClient) -> None:
    await _registrar_padrao(client)
    duplicado = await client.post(
        "/auth/registrar",
        json={
            "email": "vitor@exemplo.com",
            "senha": "outra-senha-123",
            "nome": "Outro Nome",
        },
    )
    assert duplicado.status_code == 409
    assert duplicado.json()["codigo"] == "conflito"


async def test_registrar_fuso_invalido_retorna_422(client: AsyncClient) -> None:
    resposta = await client.post(
        "/auth/registrar",
        json={
            "email": "teste@exemplo.com",
            "senha": "senha-segura-123",
            "nome": "Teste",
            "fuso": "Fuso/Inexistente",
        },
    )
    assert resposta.status_code == 422


async def test_registrar_bloqueado_quando_flag_desativada(client: AsyncClient) -> None:
    settings = get_settings()
    original = settings.registro_aberto
    settings.registro_aberto = False
    try:
        resposta = await client.post(
            "/auth/registrar",
            json={
                "email": "bloqueado@exemplo.com",
                "senha": "senha-segura-123",
                "nome": "Bloqueado",
            },
        )
        assert resposta.status_code == 403
        assert resposta.json()["codigo"] == "permissao_negada"
    finally:
        settings.registro_aberto = original


async def test_login_sucesso_e_falha(client: AsyncClient) -> None:
    await _registrar_padrao(client)

    errado = await client.post(
        "/auth/login",
        json={"email": "vitor@exemplo.com", "senha": "errada"},
    )
    assert errado.status_code == 401
    assert errado.json()["codigo"] == "nao_autenticado"

    certo = await client.post(
        "/auth/login",
        json={"email": "vitor@exemplo.com", "senha": "senha-segura-123"},
    )
    assert certo.status_code == 200
    assert "access_token" in certo.json()
    assert get_settings().refresh_cookie_nome in certo.cookies


async def test_rotacao_refresh_e_deteccao_de_reuso(client: AsyncClient) -> None:
    await _registrar_padrao(client)
    cookie_nome = get_settings().refresh_cookie_nome
    primeiro_refresh = client.cookies.get(cookie_nome)
    assert primeiro_refresh is not None

    # 1ª rotação: funciona e entrega um novo cookie
    r1 = await client.post("/auth/refresh")
    assert r1.status_code == 200
    segundo_refresh = client.cookies.get(cookie_nome)
    assert segundo_refresh is not None
    assert segundo_refresh != primeiro_refresh

    # Reuso malicioso do primeiro refresh token (já rotacionado):
    # deve falhar com 401 e revogar toda a família (incluindo o segundo_refresh).
    client.cookies.set(cookie_nome, primeiro_refresh, path="/auth")
    reuso = await client.post("/auth/refresh")
    assert reuso.status_code == 401
    assert "reuso" in reuso.json()["detail"].lower()

    # Tentar usar o segundo_refresh agora também deve falhar pois a família foi revogada.
    client.cookies.set(cookie_nome, segundo_refresh, path="/auth")
    apos_revogacao = await client.post("/auth/refresh")
    assert apos_revogacao.status_code == 401


async def test_sair_revoga_sessao(client: AsyncClient) -> None:
    await _registrar_padrao(client)
    saida = await client.post("/auth/sair")
    assert saida.status_code == 204

    tentativa = await client.post("/auth/refresh")
    assert tentativa.status_code == 401


async def test_access_token_expirado_e_invalido(client: AsyncClient) -> None:
    dados = await _registrar_padrao(client)
    usuario = dados["usuario"]
    assert isinstance(usuario, dict)

    settings = get_settings()
    agora = datetime.now(UTC)
    expirado = jwt.encode(
        {
            "sub": usuario["id"],
            "type": "access",
            "iat": agora - timedelta(minutes=30),
            "exp": agora - timedelta(minutes=1),
        },
        settings.jwt_segredo,
        algorithm=settings.jwt_algoritmo,
    )

    r_exp = await client.get("/auth/eu", headers={"Authorization": f"Bearer {expirado}"})
    assert r_exp.status_code == 401
    assert "expirado" in r_exp.json()["detail"].lower()

    r_sem = await client.get("/auth/eu")
    assert r_sem.status_code == 401


async def test_atualizar_eu(client: AsyncClient) -> None:
    dados = await _registrar_padrao(client)
    token = dados["access_token"]

    patch = await client.patch(
        "/auth/eu",
        headers={"Authorization": f"Bearer {token}"},
        json={"nome": "Vitor Atualizado", "antecedencia_padrao_min": 15},
    )
    assert patch.status_code == 200
    corpo = patch.json()
    assert corpo["nome"] == "Vitor Atualizado"
    assert corpo["antecedencia_padrao_min"] == 15
    assert corpo["versao"] == 2

    # Enviar null explícito em campo NOT NULL deve ser rejeitado com 422
    nulo = await client.patch(
        "/auth/eu",
        headers={"Authorization": f"Bearer {token}"},
        json={"nome": None},
    )
    assert nulo.status_code == 422
