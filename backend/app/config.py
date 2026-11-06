from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de desenvolvimento commitados no repositório: são PÚBLICOS e nunca devem
# ser usados em produção (o boot falha em `producao` se continuarem assim).
JWT_SEGREDO_DEV = "segredo-dev-inseguro-trocar-em-producao-32b"
VAPID_PUBLIC_KEY_DEV = (
    "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U"
)
VAPID_PRIVATE_KEY_DEV = "UU2x74o7OHF8F5HnI2q8g9-dEeqT4H-96Qk9_qUjXm0"

_HOSTS_LOCAIS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")


class Settings(BaseSettings):
    """Configuração da API, carregada de variáveis de ambiente / `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ambiente: Literal["dev", "teste", "producao"] = "dev"
    database_url: str = "postgresql+asyncpg://ritmo:ritmo@localhost:5432/ritmo"
    cors_origens: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    sql_echo: bool = False
    # Desliga /docs, /redoc e /openapi.json quando False.
    docs_habilitado: bool = True

    # Autenticação e JWT
    jwt_segredo: str = JWT_SEGREDO_DEV  # default público: só para dev
    jwt_algoritmo: str = "HS256"
    access_token_expira_min: int = 15
    refresh_token_expira_dias: int = 30
    refresh_cookie_nome: str = "ritmo_refresh"
    cookie_seguro: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    registro_aberto: bool = True

    # Rate limit em memória. None = automático (desligado apenas em `teste`).
    rate_limit_ativo: bool | None = None

    # Web Push / VAPID (defaults públicos: só para dev)
    vapid_public_key: str = VAPID_PUBLIC_KEY_DEV
    vapid_private_key: str = VAPID_PRIVATE_KEY_DEV
    vapid_claim_email: str = "mailto:suporte@ritmo.local"
    # Loop de lembretes embutido na API. Em produção, rode `python -m app.worker`
    # e defina DESPACHADOR_ATIVO=false na API.
    despachador_ativo: bool = True

    @property
    def rate_limit_efetivo(self) -> bool:
        if self.rate_limit_ativo is not None:
            return self.rate_limit_ativo
        return self.ambiente != "teste"

    @model_validator(mode="after")
    def _validar_producao(self) -> Self:
        if self.cookie_samesite == "none" and not self.cookie_seguro:
            raise ValueError("COOKIE_SAMESITE=none exige COOKIE_SEGURO=true")
        if self.ambiente != "producao":
            return self

        problemas: list[str] = []
        if self.jwt_segredo == JWT_SEGREDO_DEV or len(self.jwt_segredo) < 32:
            problemas.append("JWT_SEGREDO deve ser próprio e ter ao menos 32 caracteres")
        if (
            self.vapid_public_key == VAPID_PUBLIC_KEY_DEV
            or self.vapid_private_key == VAPID_PRIVATE_KEY_DEV
        ):
            problemas.append("VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY não podem ser os defaults de dev")
        if not self.cookie_seguro:
            problemas.append("COOKIE_SEGURO deve ser true")
        if any(host in origem for origem in self.cors_origens for host in _HOSTS_LOCAIS):
            problemas.append("CORS_ORIGENS não pode conter localhost em produção")
        if problemas:
            raise ValueError("Configuração insegura para produção: " + "; ".join(problemas))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
