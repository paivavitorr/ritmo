from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import SessionDep

router = APIRouter(prefix="/saude", tags=["saude"])


class SaudeResponse(BaseModel):
    status: Literal["ok"]


@router.get("", response_model=SaudeResponse)
async def vivo() -> SaudeResponse:
    """Liveness: o processo está de pé (não toca no banco)."""
    return SaudeResponse(status="ok")


@router.get("/banco", response_model=SaudeResponse)
async def banco(session: SessionDep) -> SaudeResponse:
    """Readiness: o banco responde."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Banco de dados indisponível") from exc
    return SaudeResponse(status="ok")
