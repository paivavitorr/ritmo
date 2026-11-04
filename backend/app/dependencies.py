from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NaoAutenticadoError
from app.core.security import decodificar_access_token
from app.db import get_session
from app.models.usuario import Usuario
from app.repositories.usuario import UsuarioRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer_scheme = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


async def get_current_user(
    session: SessionDep,
    credenciais: BearerDep,
) -> Usuario:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise NaoAutenticadoError("Credenciais de autenticação ausentes")

    usuario_id = decodificar_access_token(credenciais.credentials)
    repo = UsuarioRepository(session)
    usuario = await repo.obter_por_id(usuario_id)
    if usuario is None:
        raise NaoAutenticadoError("Usuário não encontrado ou inativo")
    return usuario


CurrentUserDep = Annotated[Usuario, Depends(get_current_user)]
