from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ItemMutacaoSync(BaseModel):
    id: UUID
    entidade: Literal["bloco", "categoria", "execucao", "modelo_bloco"]
    acao: Literal["criar", "atualizar", "excluir"]
    entidade_id: UUID
    payload: dict[str, object] = Field(default_factory=dict)
    criado_em: datetime


class SyncBatchRequest(BaseModel):
    mutacoes: list[ItemMutacaoSync] = Field(default_factory=list)


class ItemResultadoSync(BaseModel):
    mutacao_id: UUID
    status: Literal["aplicado", "ignorado", "erro"]
    mensagem: str | None = None
    versao_servidor: int | None = None


class SyncBatchResponse(BaseModel):
    processadas: int
    resultados: list[ItemResultadoSync]
