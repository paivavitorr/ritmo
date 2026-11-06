import hmac

from fastapi import APIRouter, status

from app.config import get_settings
from app.core.errors import ConflitoError
from app.dependencies import CurrentUserDep, SessionDep
from app.models.lembrete import PushAssinatura
from app.repositories.lembrete import LembreteRepository
from app.schemas.lembrete import (
    PushAssinaturaCreate,
    PushAssinaturaRead,
    PushChavePublicaResponse,
    PushDesassinarRequest,
)

router = APIRouter(prefix="/push", tags=["push"])


def _mesmas_chaves(existente: PushAssinatura, dados: PushAssinaturaCreate) -> bool:
    return hmac.compare_digest(
        existente.p256dh.encode(), dados.p256dh.encode()
    ) and hmac.compare_digest(existente.auth.encode(), dados.auth.encode())


@router.get("/chave-publica", response_model=PushChavePublicaResponse)
async def obter_chave_publica() -> PushChavePublicaResponse:
    settings = get_settings()
    return PushChavePublicaResponse(public_key=settings.vapid_public_key)


@router.post("/assinar", response_model=PushAssinaturaRead, status_code=status.HTTP_201_CREATED)
async def salvar_assinatura_push(
    dados: PushAssinaturaCreate,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> PushAssinaturaRead:
    repo = LembreteRepository(session)
    existente = await repo.obter_assinatura_por_endpoint(dados.endpoint)

    if existente is not None and existente.usuario_id == usuario.id:
        existente.p256dh = dados.p256dh
        existente.auth = dados.auth
        existente.user_agent = dados.user_agent
        await session.commit()
        return PushAssinaturaRead.model_validate(existente)

    if existente is not None:
        # Endpoint de outro usuário (ex.: troca de conta no mesmo navegador): só transfere
        # se a requisição provar posse apresentando as mesmas chaves da assinatura.
        if not _mesmas_chaves(existente, dados):
            raise ConflitoError("Endpoint já vinculado a outra conta")
        await session.delete(existente)
        await session.flush()

    nova = PushAssinatura(
        usuario_id=usuario.id,
        endpoint=dados.endpoint,
        p256dh=dados.p256dh,
        auth=dados.auth,
        user_agent=dados.user_agent,
    )
    salva = await repo.salvar_assinatura(nova)
    await session.commit()
    return PushAssinaturaRead.model_validate(salva)


@router.post("/desassinar", status_code=status.HTTP_204_NO_CONTENT)
async def remover_assinatura_push(
    dados: PushDesassinarRequest,
    usuario: CurrentUserDep,
    session: SessionDep,
) -> None:
    repo = LembreteRepository(session)
    ass = await repo.obter_assinatura_por_endpoint(dados.endpoint)
    if ass is not None and ass.usuario_id == usuario.id:
        await session.delete(ass)
        await session.commit()
