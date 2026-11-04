from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.tempo import garantir_utc
from app.models.bloco import TipoBloco


class PausaPlanejadaInput(BaseModel):
    id: UUID | None = None
    inicio: datetime
    fim: datetime

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime) -> datetime:
        return garantir_utc(valor)

    @model_validator(mode="after")
    def validar_ordem(self) -> "PausaPlanejadaInput":
        if self.fim <= self.inicio:
            raise ValueError("O fim da pausa deve ser posterior ao início")
        return self


class PausaPlanejadaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bloco_id: UUID
    inicio: datetime
    fim: datetime


class BlocoCreate(BaseModel):
    id: UUID | None = None
    categoria_id: UUID
    tipo: TipoBloco = "rotina"
    titulo: str = Field(..., min_length=1, max_length=120)
    notas: str | None = None
    data_local: date | None = None
    inicio: datetime
    fim: datetime
    pausas: list[PausaPlanejadaInput] = Field(default_factory=list)

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime) -> datetime:
        return garantir_utc(valor)

    @model_validator(mode="after")
    def validar_intervalo_e_pausas(self) -> "BlocoCreate":
        if self.fim <= self.inicio:
            raise ValueError("O fim do bloco deve ser posterior ao início")
        for p in self.pausas:
            if p.inicio < self.inicio or p.fim > self.fim:
                raise ValueError("As pausas planejadas devem ficar contidas dentro do bloco")
        return self


class BlocoUpdate(BaseModel):
    categoria_id: UUID | None = None
    tipo: TipoBloco | None = None
    titulo: str | None = Field(default=None, min_length=1, max_length=120)
    notas: str | None = None
    data_local: date | None = None
    inicio: datetime | None = None
    fim: datetime | None = None
    pausas: list[PausaPlanejadaInput] | None = None

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime | None) -> datetime | None:
        if valor is not None:
            return garantir_utc(valor)
        return None

    @model_validator(mode="after")
    def rejeitar_nulos_em_obrigatorios(self) -> "BlocoUpdate":
        obrigatorios = {"categoria_id", "tipo", "titulo", "data_local", "inicio", "fim", "pausas"}
        for campo in self.model_fields_set & obrigatorios:
            if getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo")
        return self


class BlocoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    categoria_id: UUID
    modelo_bloco_id: UUID | None
    tipo: TipoBloco
    titulo: str
    notas: str | None
    data_local: date
    inicio: datetime
    fim: datetime
    desvinculado: bool
    pausas_planejadas: list[PausaPlanejadaRead]
    segundos_liquidos_planejados: int
    versao: int
    criado_em: datetime
    atualizado_em: datetime
