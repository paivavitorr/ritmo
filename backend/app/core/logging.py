import contextvars
import json
import logging
import sys
import uuid
from datetime import UTC, datetime

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

CABECALHO_REQUEST_ID = "X-Request-ID"
_TAMANHO_MAX_REQUEST_ID = 100


class _FiltroRequestId(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


class _FormatadorJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            dados["excecao"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False)


def configurar_logging(ambiente: str) -> None:
    """Configura o logging da raiz: JSON em produção, texto legível no restante."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_FiltroRequestId())
    if ambiente == "producao":
        handler.setFormatter(_FormatadorJson())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
        )
    raiz = logging.getLogger()
    raiz.handlers = [handler]
    raiz.setLevel(logging.INFO)


def _request_id_valido(valor: str | None) -> str | None:
    if valor and len(valor) <= _TAMANHO_MAX_REQUEST_ID and valor.isprintable():
        return valor
    return None


class RequestIdMiddleware:
    """Aceita ou gera `X-Request-ID`, o expõe nos logs e o devolve na resposta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        recebido = _request_id_valido(Headers(scope=scope).get(CABECALHO_REQUEST_ID))
        request_id = recebido or uuid.uuid4().hex
        # Sem reset: cada requisição roda em seu próprio contexto e o handler de 500
        # (fora deste middleware) ainda precisa enxergar o id.
        request_id_ctx.set(request_id)

        async def send_com_id(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                MutableHeaders(scope=mensagem)[CABECALHO_REQUEST_ID] = request_id
            await send(mensagem)

        await self.app(scope, receive, send_com_id)
