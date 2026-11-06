from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.tempo import garantir_utc
from app.models.execucao import OrigemExecucao, StatusExecucao
from app.schemas.bloco import BlocoRead
from app.schemas.categoria import CategoriaRead
from app.schemas.execucao import ExecucaoRead
from app.schemas.modelo_semana import ModeloBlocoRead

EntidadeSync = Literal["bloco", "categoria", "execucao", "modelo_bloco"]

LIMITE_MUTACOES_POR_LOTE = 200


class ItemMutacaoSync(BaseModel):
    id: UUID
    entidade: EntidadeSync
    acao: Literal["criar", "atualizar", "excluir"]
    entidade_id: UUID
    payload: dict[str, object] = Field(default_factory=dict)
    criado_em: datetime
    # Versão da entidade que o cliente conhecia ao editar (None em `criar`).
    versao_base: int | None = None


class SyncBatchRequest(BaseModel):
    mutacoes: list[ItemMutacaoSync] = Field(
        default_factory=list, max_length=LIMITE_MUTACOES_POR_LOTE
    )


class ItemResultadoSync(BaseModel):
    mutacao_id: UUID
    status: Literal["aplicado", "ignorado", "conflito", "erro"]
    mensagem: str | None = None
    versao_servidor: int | None = None
    # Estado atual no servidor (schema Read da entidade), preenchido em `conflito`.
    entidade_servidor: dict[str, object] | None = None


class SyncBatchResponse(BaseModel):
    processadas: int
    resultados: list[ItemResultadoSync]


class ExcluidoSync(BaseModel):
    entidade: EntidadeSync
    id: UUID


class SyncMudancasResponse(BaseModel):
    blocos: list[BlocoRead]
    categorias: list[CategoriaRead]
    execucoes: list[ExecucaoRead]
    modelos_bloco: list[ModeloBlocoRead]
    excluidos: list[ExcluidoSync]
    cursor: str
    tem_mais: bool


# --- Payloads de execução aceitos pelo sync -------------------------------------------------
# Diferem do REST por permitirem execução em andamento (cronômetro offline): `fim` opcional
# e pausa ainda aberta (`fim` nulo).


class PausaExecucaoSync(BaseModel):
    id: UUID | None = None
    inicio: datetime
    fim: datetime | None = None

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime | None) -> datetime | None:
        return garantir_utc(valor) if valor is not None else None

    @model_validator(mode="after")
    def validar_ordem(self) -> "PausaExecucaoSync":
        if self.fim is not None and self.fim <= self.inicio:
            raise ValueError("O fim da pausa deve ser posterior ao início")
        return self


def validar_pausas_no_intervalo(
    inicio: datetime, fim: datetime | None, pausas: list[PausaExecucaoSync]
) -> None:
    for p in pausas:
        if p.inicio < inicio or (fim is not None and p.fim is not None and p.fim > fim):
            raise ValueError("As pausas devem ficar dentro do intervalo da execução")


class ExecucaoSyncCreate(BaseModel):
    categoria_id: UUID
    bloco_id: UUID | None = None
    inicio: datetime
    fim: datetime | None = None
    status: StatusExecucao = "concluida"
    origem: OrigemExecucao = "manual"
    pausas: list[PausaExecucaoSync] = Field(default_factory=list)

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime | None) -> datetime | None:
        return garantir_utc(valor) if valor is not None else None

    @model_validator(mode="after")
    def validar_intervalo(self) -> "ExecucaoSyncCreate":
        if self.fim is not None and self.fim <= self.inicio:
            raise ValueError("O fim da execução deve ser posterior ao início")
        if self.fim is None and self.status != "em_andamento":
            raise ValueError("Execução sem fim deve estar em andamento")
        validar_pausas_no_intervalo(self.inicio, self.fim, self.pausas)
        return self


class ExecucaoSyncUpdate(BaseModel):
    categoria_id: UUID | None = None
    bloco_id: UUID | None = None
    inicio: datetime | None = None
    fim: datetime | None = None
    status: StatusExecucao | None = None
    pausas: list[PausaExecucaoSync] | None = None

    @field_validator("inicio", "fim", mode="after")
    @classmethod
    def normalizar_utc(cls, valor: datetime | None) -> datetime | None:
        return garantir_utc(valor) if valor is not None else None

    @model_validator(mode="after")
    def rejeitar_nulos_em_obrigatorios(self) -> "ExecucaoSyncUpdate":
        obrigatorios = {"categoria_id", "inicio", "fim", "status", "pausas"}
        for campo in self.model_fields_set & obrigatorios:
            if getattr(self, campo) is None:
                raise ValueError(f"O campo '{campo}' não pode ser nulo")
        return self
