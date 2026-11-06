from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PushChavePublicaResponse(BaseModel):
    public_key: str


# Serviços de push dos navegadores (FCM, Mozilla, WNS, APNs web). "*." casa subdomínios.
HOSTS_PUSH_PERMITIDOS = (
    "fcm.googleapis.com",
    "*.push.services.mozilla.com",
    "updates.push.services.mozilla.com",
    "*.notify.windows.com",
    "web.push.apple.com",
    "*.push.apple.com",
)

ENDPOINT_MAX = 2048
P256DH_MAX = 256
AUTH_MAX = 100  # coluna String(100)
USER_AGENT_MAX = 512


def _host_permitido(host: str) -> bool:
    for padrao in HOSTS_PUSH_PERMITIDOS:
        if padrao.startswith("*."):
            if host.endswith(padrao[1:]):
                return True
        elif host == padrao:
            return True
    return False


def validar_endpoint_push(endpoint: str) -> str:
    partes = urlsplit(endpoint)
    host = (partes.hostname or "").lower()
    if partes.scheme != "https" or not host or not _host_permitido(host):
        raise ValueError("Endpoint de push não permitido")
    return endpoint


class PushAssinaturaCreate(BaseModel):
    endpoint: str = Field(max_length=ENDPOINT_MAX)
    p256dh: str = Field(min_length=1, max_length=P256DH_MAX)
    auth: str = Field(min_length=1, max_length=AUTH_MAX)
    user_agent: str | None = Field(default=None, max_length=USER_AGENT_MAX)

    @field_validator("endpoint")
    @classmethod
    def _endpoint_na_allowlist(cls, valor: str) -> str:
        return validar_endpoint_push(valor)


class PushDesassinarRequest(BaseModel):
    endpoint: str = Field(max_length=ENDPOINT_MAX)


class PushAssinaturaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None
    criado_em: datetime


class LembreteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    bloco_id: UUID
    disparar_em: datetime
    antecedencia_min: int
    status: str
    titulo: str
    corpo: str | None
    versao: int
    criado_em: datetime
