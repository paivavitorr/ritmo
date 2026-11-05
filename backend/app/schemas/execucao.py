from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.tempo import garantir_utc
from app.models.execucao import OrigemExecucao, StatusExecucao


class PausaExecucaoInput(BaseModel):
    id: UUID | None = None
    inicio: datetime
    fim: datetime

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime) -> datetime:
        return garantir_utc(valor)

    @model_validator(mode="after")
    def validar_ordem(self) -> "PausaExecucaoInput":
        if self.fim <= self.inicio:
            raise ValueError("O fim da pausa deve ser posterior ao início")
        return self


class PausaExecucaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    execucao_id: UUID
    inicio: datetime
    fim: datetime | None


class ExecucaoCreate(BaseModel):
    id: UUID | None = None
    categoria_id: UUID
    bloco_id: UUID | None = None
    inicio: datetime
    fim: datetime
    status: StatusExecucao = "concluida"
    origem: OrigemExecucao = "manual"
    pausas: list[PausaExecucaoInput] = Field(default_factory=list)

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime) -> datetime:
        return garantir_utc(valor)

    @model_validator(mode="after")
    def validar_intervalo(self) -> "ExecucaoCreate":
        if self.fim <= self.inicio:
            raise ValueError("O fim da execução deve ser posterior ao início")
        if self.status == "em_andamento":
            raise ValueError("Use POST /execucoes/iniciar para criar execução em andamento")
        for p in self.pausas:
            if p.inicio < self.inicio or p.fim > self.fim:
                raise ValueError("As pausas devem ficar dentro do intervalo da execução")
        return self


class ExecucaoUpdate(BaseModel):
    categoria_id: UUID | None = None
    bloco_id: UUID | None = None
    inicio: datetime | None = None
    fim: datetime | None = None
    status: StatusExecucao | None = None
    pausas: list[PausaExecucaoInput] | None = None

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime | None) -> datetime | None:
        if valor is not None:
            return garantir_utc(valor)
        return None

    @model_validator(mode="after")
    def rejeitar_nulos_em_obrigatorios(self) -> "ExecucaoUpdate":
        obrigatorios = {"categoria_id", "inicio", "fim", "status", "pausas"}
        for campo in self.model_fields_set & obrigatorios:
            if getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo")
        return self


class ExecucaoIniciarRequest(BaseModel):
    id: UUID | None = None
    categoria_id: UUID | None = None
    bloco_id: UUID | None = None
    instante: datetime | None = None

    @field_validator("instante", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime | None) -> datetime | None:
        if valor is not None:
            return garantir_utc(valor)
        return None


class ExecucaoTransicaoRequest(BaseModel):
    instante: datetime | None = None
    status: Literal["concluida", "parcial"] = "concluida"

    @field_validator("instante", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime | None) -> datetime | None:
        if valor is not None:
            return garantir_utc(valor)
        return None


class ExecucaoConfirmarBlocoRequest(BaseModel):
    bloco_id: UUID
    status: Literal["concluida", "parcial", "pulada"] = "concluida"


class ExecucaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    categoria_id: UUID
    bloco_id: UUID | None
    inicio: datetime
    fim: datetime | None
    status: StatusExecucao
    origem: OrigemExecucao
    segundos_liquidos: int
    pausas: list[PausaExecucaoRead]
    versao: int
    criado_em: datetime
    atualizado_em: datetime
