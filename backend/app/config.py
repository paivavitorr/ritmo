from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da API, carregada de variáveis de ambiente / `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ambiente: str = "dev"
    database_url: str = "postgresql+asyncpg://ritmo:ritmo@localhost:5432/ritmo"
    cors_origens: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    sql_echo: bool = False

    # Autenticação e JWT
    jwt_segredo: str = "segredo-dev-inseguro-trocar-em-producao-32b"
    jwt_algoritmo: str = "HS256"
    access_token_expira_min: int = 15
    refresh_token_expira_dias: int = 30
    refresh_cookie_nome: str = "ritmo_refresh"
    cookie_seguro: bool = False
    registro_aberto: bool = True

    # Web Push / VAPID
    vapid_public_key: str = (
        "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U"
    )
    vapid_private_key: str = "UU2x74o7OHF8F5HnI2q8g9-dEeqT4H-96Qk9_qUjXm0"
    vapid_claim_email: str = "mailto:suporte@ritmo.local"
    despachador_ativo: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
