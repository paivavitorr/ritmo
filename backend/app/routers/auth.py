from fastapi import APIRouter, Depends, Request, Response, status

from app.config import get_settings
from app.core.rate_limit import limitar
from app.dependencies import CurrentUserDep, SessionDep
from app.schemas.usuario import (
    LoginRequest,
    TokenResponse,
    UsuarioCreate,
    UsuarioRead,
    UsuarioUpdate,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _definir_cookie_refresh(response: Response, token_bruto: str) -> None:
    settings = get_settings()
    max_age = settings.refresh_token_expira_dias * 24 * 60 * 60
    response.set_cookie(
        key=settings.refresh_cookie_nome,
        value=token_bruto,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_seguro,
        samesite=settings.cookie_samesite,
        path="/auth",
    )


def _limpar_cookie_refresh(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_nome,
        httponly=True,
        secure=settings.cookie_seguro,
        samesite=settings.cookie_samesite,
        path="/auth",
    )


@router.post(
    "/registrar",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limitar("registrar", 5))],
)
async def registrar(
    dados: UsuarioCreate,
    request: Request,
    response: Response,
    session: SessionDep,
) -> TokenResponse:
    service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    token_resp, refresh_bruto = await service.registrar(dados, user_agent=user_agent)
    _definir_cookie_refresh(response, refresh_bruto)
    return token_resp


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limitar("login", 10))])
async def login(
    credenciais: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> TokenResponse:
    service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    token_resp, refresh_bruto = await service.login(credenciais, user_agent=user_agent)
    _definir_cookie_refresh(response, refresh_bruto)
    return token_resp


@router.post(
    "/refresh", response_model=TokenResponse, dependencies=[Depends(limitar("refresh", 30))]
)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
) -> TokenResponse:
    settings = get_settings()
    refresh_bruto = request.cookies.get(settings.refresh_cookie_nome)
    service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    token_resp, novo_refresh = await service.rotacionar_refresh(
        refresh_bruto, user_agent=user_agent
    )
    _definir_cookie_refresh(response, novo_refresh)
    return token_resp


@router.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
async def sair(
    request: Request,
    response: Response,
    session: SessionDep,
) -> None:
    settings = get_settings()
    refresh_bruto = request.cookies.get(settings.refresh_cookie_nome)
    service = AuthService(session)
    await service.sair(refresh_bruto)
    _limpar_cookie_refresh(response)


@router.get("/eu", response_model=UsuarioRead)
async def eu(usuario: CurrentUserDep) -> UsuarioRead:
    return UsuarioRead.model_validate(usuario)


@router.patch("/eu", response_model=UsuarioRead)
async def atualizar_eu(
    dados: UsuarioUpdate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> UsuarioRead:
    campos = dados.model_dump(exclude_unset=True)
    if campos:
        for campo, valor in campos.items():
            setattr(usuario, campo, valor)
        usuario.versao += 1
        await session.commit()
        await session.refresh(usuario)
    return UsuarioRead.model_validate(usuario)
