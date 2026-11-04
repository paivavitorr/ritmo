from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.categoria import CorCategoria


class CategoriaCreate(BaseModel):
    id: UUID | None = None
    nome: str = Field(..., min_length=1, max_length=40)
    cor: CorCategoria
    icone: str | None = Field(default=None, max_length=40)
    conta_como_produtiva: bool = True
    meta_semanal_min: int | None = Field(default=None, ge=0, le=10080)
    ordem: int = Field(default=0, ge=0, le=1000)


class CategoriaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=40)
    cor: CorCategoria | None = None
    icone: str | None = Field(default=None, max_length=40)
    conta_como_produtiva: bool | None = None
    meta_semanal_min: int | None = Field(default=None, ge=0, le=10080)
    ordem: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def rejeitar_nulos_em_obrigatorios(self) -> "CategoriaUpdate":
        obrigatorios = {"nome", "cor", "conta_como_produtiva", "ordem"}
        for campo in self.model_fields_set & obrigatorios:
            if getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo")
        return self


class CategoriaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    nome: str
    cor: CorCategoria
    icone: str | None
    conta_como_produtiva: bool
    meta_semanal_min: int | None
    ordem: int
    versao: int
    criado_em: datetime
    atualizado_em: datetime
