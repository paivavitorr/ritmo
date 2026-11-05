from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PushChavePublicaResponse(BaseModel):
    public_key: str


class PushAssinaturaCreate(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None


class PushDesassinarRequest(BaseModel):
    endpoint: str


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
