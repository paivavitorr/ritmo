from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def _validar_fuso(valor: str) -> str:
    try:
        ZoneInfo(valor)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise ValueError(f"Fuso horário IANA inválido: {valor}") from exc
    return valor


class UsuarioCreate(BaseModel):
    email: EmailStr
    senha: str = Field(..., min_length=8, max_length=128)
    nome: str = Field(..., min_length=2, max_length=100)
    fuso: str = Field(default="America/Manaus", max_length=64)
    inicio_semana: int = Field(default=1, ge=0, le=6)
    antecedencia_padrao_min: int = Field(default=10, ge=0, le=1440)

    @field_validator("email", mode="after")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        return valor.strip().lower()

    @field_validator("fuso", mode="after")
    @classmethod
    def validar_fuso_iana(cls, valor: str) -> str:
        return _validar_fuso(valor)


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    fuso: str | None = Field(default=None, max_length=64)
    inicio_semana: int | None = Field(default=None, ge=0, le=6)
    antecedencia_padrao_min: int | None = Field(default=None, ge=0, le=1440)

    @field_validator("fuso", mode="after")
    @classmethod
    def validar_fuso_iana(cls, valor: str | None) -> str | None:
        if valor is not None:
            return _validar_fuso(valor)
        return None

    @model_validator(mode="after")
    def rejeitar_nulos_explicitos(self) -> "UsuarioUpdate":
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo")
        return self


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    nome: str
    fuso: str
    inicio_semana: int
    antecedencia_padrao_min: int
    versao: int
    criado_em: datetime
    atualizado_em: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str = Field(..., min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        return valor.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expira_em: int
    usuario: UsuarioRead
