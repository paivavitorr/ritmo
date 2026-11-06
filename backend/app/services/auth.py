from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.config import get_settings
from app.core.errors import (
    ConflitoError,
    NaoAutenticadoError,
    PermissaoNegadaError,
)
from app.core.security import (
    criar_access_token,
    gerar_hash_senha,
    gerar_refresh_token,
    hash_refresh_token,
    verificar_senha,
    verificar_senha_fantasma,
)
from app.models.usuario import SessaoRefresh, Usuario
from app.repositories.categoria import CategoriaRepository
from app.repositories.usuario import SessaoRefreshRepository, UsuarioRepository
from app.schemas.usuario import LoginRequest, TokenResponse, UsuarioCreate, UsuarioRead

JANELA_GRACA_REFRESH = timedelta(seconds=30)


def _garantir_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _truncar_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return user_agent[:255]


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.usuarios = UsuarioRepository(session)
        self.sessoes = SessaoRefreshRepository(session)
        self.categorias = CategoriaRepository(session)
        self.settings = get_settings()

    async def registrar(
        self, dados: UsuarioCreate, user_agent: str | None = None
    ) -> tuple[TokenResponse, str]:
        if not self.settings.registro_aberto:
            raise PermissaoNegadaError("O registro de novos usuários está desativado")

        # Decisão de produto: e-mail já cadastrado devolve 409 explícito (melhor UX), o que
        # permite enumerar contas. A mitigação é o rate limit de /auth/registrar; para
        # eliminar o vetor seria preciso confirmação por e-mail (fora do escopo do MVP).
        existente = await self.usuarios.obter_por_email(dados.email, incluir_excluidos=True)
        if existente is not None:
            raise ConflitoError("Já existe uma conta cadastrada com este e-mail")

        usuario = Usuario(
            email=dados.email,
            senha_hash=gerar_hash_senha(dados.senha),
            nome=dados.nome,
            fuso=dados.fuso,
            inicio_semana=dados.inicio_semana,
            antecedencia_padrao_min=dados.antecedencia_padrao_min,
        )
        try:
            await self.usuarios.criar(usuario)
            await self.categorias.criar_padroes_do_usuario(usuario.id)
            resposta, refresh_bruto = await self._emitir_par_tokens(usuario, user_agent=user_agent)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflitoError("Já existe uma conta cadastrada com este e-mail") from exc

        return resposta, refresh_bruto

    async def login(
        self, credenciais: LoginRequest, user_agent: str | None = None
    ) -> tuple[TokenResponse, str]:
        usuario = await self.usuarios.obter_por_email(credenciais.email)
        if usuario is None:
            # Mitiga enumeração por tempo: gasta o mesmo custo de Argon2 de um login real.
            verificar_senha_fantasma(credenciais.senha)
            raise NaoAutenticadoError("E-mail ou senha inválidos")
        if not verificar_senha(credenciais.senha, usuario.senha_hash):
            raise NaoAutenticadoError("E-mail ou senha inválidos")

        resposta, refresh_bruto = await self._emitir_par_tokens(usuario, user_agent=user_agent)
        await self.session.commit()
        return resposta, refresh_bruto

    async def rotacionar_refresh(
        self, refresh_bruto: str | None, user_agent: str | None = None
    ) -> tuple[TokenResponse, str]:
        if not refresh_bruto:
            raise NaoAutenticadoError("Refresh token ausente")

        token_hash = hash_refresh_token(refresh_bruto)
        # FOR UPDATE: requisições concorrentes com o mesmo token são serializadas.
        sessao_atual = await self.sessoes.obter_por_hash(token_hash, para_atualizar=True)
        if sessao_atual is None:
            raise NaoAutenticadoError("Sessão inválida")

        agora = datetime.now(UTC)
        em_graca = False

        if sessao_atual.revogado_em is not None:
            em_graca = await self._dentro_da_graca(sessao_atual, agora)
            if not em_graca:
                # Reuso fora da janela de graça: possível roubo, revoga a família inteira.
                await self.sessoes.revogar_familia(sessao_atual.familia_id, agora)
                await self.session.commit()
                raise NaoAutenticadoError("Sessão revogada por detecção de reuso")

        if _garantir_utc(sessao_atual.expira_em) <= agora:
            if not em_graca:
                sessao_atual.revogado_em = agora
                await self.session.commit()
            raise NaoAutenticadoError("Sessão expirada")

        usuario = await self.usuarios.obter_por_id(sessao_atual.usuario_id)
        if usuario is None:
            raise NaoAutenticadoError("Usuário inativo ou inexistente")

        novo_bruto = gerar_refresh_token()
        nova_sessao = SessaoRefresh(
            id=uuid7(),
            usuario_id=usuario.id,
            familia_id=sessao_atual.familia_id,
            token_hash=hash_refresh_token(novo_bruto),
            user_agent=_truncar_user_agent(user_agent),
            expira_em=agora + timedelta(days=self.settings.refresh_token_expira_dias),
        )
        await self.sessoes.criar(nova_sessao)

        # Na graça o token já foi rotacionado: não sobrescreve o sucessor original,
        # que continua válido (o cliente concorrente pode ter recebido o cookie dele).
        if not em_graca:
            sessao_atual.revogado_em = agora
            sessao_atual.substituido_por_id = nova_sessao.id

        access_token, expira_seg = criar_access_token(usuario.id)
        await self.session.commit()

        return (
            TokenResponse(
                access_token=access_token,
                expira_em=expira_seg,
                usuario=UsuarioRead.model_validate(usuario),
            ),
            novo_bruto,
        )

    async def _dentro_da_graca(self, sessao: SessaoRefresh, agora: datetime) -> bool:
        """True se o token foi rotacionado há pouco e o sucessor segue ativo.

        Cobre abas/requisições concorrentes que apresentam o mesmo refresh quase ao mesmo
        tempo; logout ou revogação da família (sucessor revogado) não entram na graça.
        """
        if sessao.revogado_em is None or sessao.substituido_por_id is None:
            return False
        if agora - _garantir_utc(sessao.revogado_em) >= JANELA_GRACA_REFRESH:
            return False
        sucessora = await self.sessoes.obter_por_id(sessao.substituido_por_id)
        return sucessora is not None and sucessora.revogado_em is None

    async def sair(self, refresh_bruto: str | None) -> None:
        if not refresh_bruto:
            return
        sessao = await self.sessoes.obter_por_hash(hash_refresh_token(refresh_bruto))
        if sessao is not None and sessao.revogado_em is None:
            await self.sessoes.revogar_familia(sessao.familia_id, datetime.now(UTC))
            await self.session.commit()

    async def _emitir_par_tokens(
        self, usuario: Usuario, user_agent: str | None = None
    ) -> tuple[TokenResponse, str]:
        agora = datetime.now(UTC)
        refresh_bruto = gerar_refresh_token()
        sessao = SessaoRefresh(
            usuario_id=usuario.id,
            token_hash=hash_refresh_token(refresh_bruto),
            user_agent=_truncar_user_agent(user_agent),
            expira_em=agora + timedelta(days=self.settings.refresh_token_expira_dias),
        )
        await self.sessoes.criar(sessao)
        access_token, expira_seg = criar_access_token(usuario.id)
        return (
            TokenResponse(
                access_token=access_token,
                expira_em=expira_seg,
                usuario=UsuarioRead.model_validate(usuario),
            ),
            refresh_bruto,
        )
