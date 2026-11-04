from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Exceção de domínio com código HTTP e identificador semântico."""

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
    )


def registrar_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
