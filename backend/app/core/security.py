import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.config import get_settings
from app.core.errors import NaoAutenticadoError

password_hasher = PasswordHash.recommended()


def gerar_hash_senha(senha: str) -> str:
    return password_hasher.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return password_hasher.verify(senha, senha_hash)


def criar_access_token(usuario_id: UUID) -> tuple[str, int]:
    """Cria um JWT de acesso curto e retorna `(token, expira_em_segundos)`."""
    settings = get_settings()
    agora = datetime.now(UTC)
    expira_seg = settings.access_token_expira_min * 60
    payload = {
        "sub": str(usuario_id),
        "type": "access",
        "iat": agora,
        "exp": agora + timedelta(seconds=expira_seg),
    }
    token = jwt.encode(payload, settings.jwt_segredo, algorithm=settings.jwt_algoritmo)
    return token, expira_seg


def decodificar_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_segredo,
            algorithms=[settings.jwt_algoritmo],
        )
    except jwt.ExpiredSignatureError as exc:
        raise NaoAutenticadoError("Token de acesso expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise NaoAutenticadoError("Token de acesso inválido") from exc

    if payload.get("type") != "access":
        raise NaoAutenticadoError("Tipo de token inválido")

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise NaoAutenticadoError("Token sem identificador de usuário")

    try:
        return UUID(sub)
    except ValueError as exc:
        raise NaoAutenticadoError("Identificador de usuário malformado") from exc


def gerar_refresh_token() -> str:
    """Gera token opaco criptograficamente seguro."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token_bruto: str) -> str:
    """Calcula SHA-256 determinístico para busca indexada na tabela de sessões."""
    return hashlib.sha256(token_bruto.encode("utf-8")).hexdigest()
