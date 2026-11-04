from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PausaModeloSchema(BaseModel):
    offset_min: int = Field(..., ge=0, le=1440)
    duracao_min: int = Field(..., ge=1, le=1440)


def _duracao_minutos_modelo(hora_inicio: time, hora_fim: time) -> int:
    ini_min = hora_inicio.hour * 60 + hora_inicio.minute
    fim_min = hora_fim.hour * 60 + hora_fim.minute
    if fim_min <= ini_min:
        fim_min += 24 * 60
    return fim_min - ini_min


class ModeloBlocoCreate(BaseModel):
    id: UUID | None = None
    categoria_id: UUID
    titulo: str = Field(..., min_length=1, max_length=120)
    dia_semana: int = Field(..., ge=0, le=6)
    hora_inicio: time
    hora_fim: time
    pausas: list[PausaModeloSchema] = Field(default_factory=list)
    lembretes: list[int] = Field(default_factory=list)
    ativo: bool = True

    @model_validator(mode="after")
    def validar_pausas_e_lembretes(self) -> "ModeloBlocoCreate":
        duracao_total = _duracao_minutos_modelo(self.hora_inicio, self.hora_fim)
        for p in self.pausas:
            if p.offset_min + p.duracao_min > duracao_total:
                raise ValueError("A pausa do modelo excede a duração total do bloco")
        for lemb in self.lembretes:
            if lemb < 0 or lemb > 1440:
                raise ValueError("Antecedência de lembrete deve estar entre 0 e 1440 minutos")
        return self


class ModeloBlocoUpdate(BaseModel):
    categoria_id: UUID | None = None
    titulo: str | None = Field(default=None, min_length=1, max_length=120)
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    hora_inicio: time | None = None
    hora_fim: time | None = None
    pausas: list[PausaModeloSchema] | None = None
    lembretes: list[int] | None = None
    ativo: bool | None = None

    @model_validator(mode="after")
    def rejeitar_nulos_explicitos(self) -> "ModeloBlocoUpdate":
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo")
        return self


class ModeloBlocoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    categoria_id: UUID
    titulo: str
    dia_semana: int
    hora_inicio: time
    hora_fim: time
    pausas: list[PausaModeloSchema]
    lembretes: list[int]
    ativo: bool
    versao: int
    criado_em: datetime
    atualizado_em: datetime
