import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import CABECALHO_REQUEST_ID, request_id_ctx

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Exceção de domínio com código HTTP e identificador semântico."""

    headers: dict[str, str] | None = None

    def __init__(self, status: int, detail: str, codigo: str = "erro_aplicacao") -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.codigo = codigo


class NaoAutenticadoError(AppError):
    def __init__(self, detail: str = "Não autenticado") -> None:
        super().__init__(status=401, detail=detail, codigo="nao_autenticado")


class PermissaoNegadaError(AppError):
    def __init__(self, detail: str = "Permissão negada") -> None:
        super().__init__(status=403, detail=detail, codigo="permissao_negada")


class NaoEncontradoError(AppError):
    def __init__(self, detail: str = "Recurso não encontrado") -> None:
        super().__init__(status=404, detail=detail, codigo="nao_encontrado")


class ConflitoError(AppError):
    def __init__(self, detail: str = "Conflito de estado") -> None:
        super().__init__(status=409, detail=detail, codigo="conflito")


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"detail": exc.detail, "codigo": exc.codigo},
        headers=exc.headers,
    )


async def erro_inesperado_handler(_: Request, exc: Exception) -> JSONResponse:
    """Último recurso: loga com stack trace, mas não vaza detalhes ao cliente."""
    logger.exception("Erro não tratado", exc_info=exc)
    headers = {}
    request_id = request_id_ctx.get()
    if request_id:
        headers[CABECALHO_REQUEST_ID] = request_id
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor", "codigo": "erro_interno"},
        headers=headers,
    )


def registrar_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, erro_inesperado_handler)
