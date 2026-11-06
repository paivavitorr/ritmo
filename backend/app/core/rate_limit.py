import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.config import get_settings
from app.core.errors import AppError


class LimiteExcedidoError(AppError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            status=429,
            detail="Muitas requisições. Tente novamente em instantes.",
            codigo="limite_excedido",
        )
        self.headers = {"Retry-After": str(retry_after)}


class LimitadorJanelaDeslizante:
    """Janela deslizante em memória (por processo). Suficiente para uma única réplica."""

    def __init__(self) -> None:
        self._eventos: dict[str, deque[float]] = defaultdict(deque)
        self._ultima_limpeza = 0.0

    def verificar(
        self, chave: str, maximo: int, janela_seg: float, agora: float | None = None
    ) -> int:
        """Registra o acesso; retorna 0 se permitido ou os segundos até liberar."""
        agora = time.monotonic() if agora is None else agora
        self._limpar(agora, janela_seg)
        eventos = self._eventos[chave]
        while eventos and eventos[0] <= agora - janela_seg:
            eventos.popleft()
        if len(eventos) >= maximo:
            return max(1, int(eventos[0] + janela_seg - agora) + 1)
        eventos.append(agora)
        return 0

    def _limpar(self, agora: float, janela_seg: float) -> None:
        if agora - self._ultima_limpeza < janela_seg:
            return
        self._ultima_limpeza = agora
        vazias = [k for k, ev in self._eventos.items() if not ev or ev[-1] <= agora - janela_seg]
        for chave in vazias:
            del self._eventos[chave]


def limitar(rota: str, maximo: int, janela_seg: int = 60) -> Callable[[Request], Awaitable[None]]:
    """Cria uma dependência FastAPI que limita `maximo` req/`janela_seg` por IP+rota.

    O estado fica em `app.state`, então cada instância da aplicação tem seu limitador.
    """

    async def dependencia(request: Request) -> None:
        if not get_settings().rate_limit_efetivo:
            return
        limitador: LimitadorJanelaDeslizante | None = getattr(request.app.state, "limitador", None)
        if limitador is None:
            limitador = LimitadorJanelaDeslizante()
            request.app.state.limitador = limitador
        ip = request.client.host if request.client else "desconhecido"
        espera = limitador.verificar(f"{rota}:{ip}", maximo, janela_seg)
        if espera:
            raise LimiteExcedidoError(espera)

    return dependencia
