from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoriaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    categoria_id: UUID | None  # None representa execuções avulsas / espontâneas
    nome: str
    cor: str
    conta_como_produtiva: bool
    segundos_planejados: int
    segundos_executados: int
    segundos_liquidos_aderentes: int
    aderencia_volume: float  # [0.0, 1.0]
    aderencia_temporal: float  # [0.0, 1.0]
    eh_espontaneo: bool = False


class FaixaIntervalo(BaseModel):
    inicio_iso: str
    fim_iso: str
    tipo: Literal["planejado", "executado"]
    categoria_id: UUID | None
    categoria_nome: str
    categoria_cor: str
    titulo: str
    status: str | None = None


class FaixaDia(BaseModel):
    data: date
    segundos_planejados: int
    segundos_executados: int
    aderencia_volume: float
    aderencia_temporal: float
    planejados: list[FaixaIntervalo]
    executados: list[FaixaIntervalo]


class ResumoPeriodoResponse(BaseModel):
    de: date
    ate: date
    agrupamento: Literal["dia", "semana"]
    total_segundos_planejados: int
    total_segundos_executados: int
    aderencia_volume_geral: float
    aderencia_temporal_geral: float
    categorias: list[CategoriaResumo]
    faixas_dias: list[FaixaDia]
