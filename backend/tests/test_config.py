import pytest
from pydantic import ValidationError

from app.config import (
    JWT_SEGREDO_DEV,
    VAPID_PRIVATE_KEY_DEV,
    VAPID_PUBLIC_KEY_DEV,
    Settings,
    get_settings,
)
from app.main import create_app

_PRODUCAO_OK: dict[str, object] = {
    "ambiente": "producao",
    "jwt_segredo": "x" * 40,
    "vapid_public_key": "chave-publica-propria",
    "vapid_private_key": "chave-privada-propria",
    "cookie_seguro": True,
    "cors_origens": ["https://ritmo.exemplo.com"],
}


def _settings(**sobrescritas: object) -> Settings:
    return Settings(_env_file=None, **{**_PRODUCAO_OK, **sobrescritas})  # type: ignore[arg-type]


def test_producao_valida_passa() -> None:
    assert _settings().ambiente == "producao"


def test_dev_aceita_defaults() -> None:
    assert Settings(_env_file=None).ambiente == "dev"


@pytest.mark.parametrize(
    "sobrescrita",
    [
        {"jwt_segredo": JWT_SEGREDO_DEV},
        {"jwt_segredo": "curto"},
        {"vapid_public_key": VAPID_PUBLIC_KEY_DEV},
        {"vapid_private_key": VAPID_PRIVATE_KEY_DEV},
        {"cookie_seguro": False},
        {"cors_origens": ["http://localhost:3000"]},
        {"cors_origens": ["https://ritmo.exemplo.com", "http://127.0.0.1:3000"]},
    ],
)
def test_producao_insegura_falha(sobrescrita: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _settings(**sobrescrita)


def test_samesite_none_exige_cookie_seguro() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cookie_samesite="none", cookie_seguro=False)


def test_ambiente_invalido() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ambiente="staging")  # type: ignore[arg-type]


def test_docs_desligados_removem_rotas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "docs_habilitado", False)
    caminhos = {getattr(rota, "path", "") for rota in create_app().routes}
    assert not {"/docs", "/redoc", "/openapi.json"} & caminhos
