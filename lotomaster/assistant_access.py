"""Controles de acesso para chamadas pagas ao Gemini no servidor.

A limitação em memória é defesa adicional por processo; não substitui controles
por usuário no gateway nem quotas/budgets no provedor em produção distribuída.
"""
from collections import defaultdict, deque
import hmac
import os
import re
import threading
import time

from fastapi import HTTPException, Request

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{32,256}$")
_WINDOW_SECONDS = 60.0
_PER_CLIENT_LIMIT = 10
_GLOBAL_LIMIT = 30
_MAX_CLIENTS = 4096


class SlidingWindowRateLimiter:
    """Limiter em janela móvel, limitado em memória e seguro entre threads."""

    def __init__(
        self,
        per_client_limit: int = _PER_CLIENT_LIMIT,
        global_limit: int = _GLOBAL_LIMIT,
        window_seconds: float = _WINDOW_SECONDS,
        max_clients: int = _MAX_CLIENTS,
    ):
        self.per_client_limit = per_client_limit
        self.global_limit = global_limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._global_events = deque()
        self._client_events = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(self, client_key: str, now: float | None = None) -> int | None:
        """Retorna segundos para retry se excedido; caso contrário consome cota."""
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            while self._global_events and self._global_events[0] <= cutoff:
                self._global_events.popleft()
            for key in tuple(self._client_events):
                events = self._client_events[key]
                while events and events[0] <= cutoff:
                    events.popleft()
                if not events:
                    del self._client_events[key]

            client_events = self._client_events.get(client_key)
            if client_events is None:
                if len(self._client_events) >= self.max_clients:
                    return max(1, int(self.window_seconds))
                client_events = self._client_events[client_key]

            if len(self._global_events) >= self.global_limit:
                retry_at = self._global_events[0] + self.window_seconds
                return max(1, int(retry_at - current + 0.999))
            if len(client_events) >= self.per_client_limit:
                retry_at = client_events[0] + self.window_seconds
                return max(1, int(retry_at - current + 0.999))

            self._global_events.append(current)
            client_events.append(current)
            return None


server_gemini_rate_limiter = SlidingWindowRateLimiter()


def server_gemini_configuration_ready() -> bool:
    """True only when the feature, provider key, and separate strong token exist."""
    if os.getenv("LOTOMASTER_ENABLE_SERVER_GEMINI", "").strip().lower() != "true":
        return False
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    access_token = os.getenv("LOTOMASTER_SERVER_GEMINI_TOKEN", "")
    if not api_key or not _TOKEN_PATTERN.fullmatch(access_token):
        return False
    return not hmac.compare_digest(api_key.encode("utf-8"), access_token.encode("utf-8"))


def authorize_server_gemini_request(request: Request) -> None:
    """Reject server-Gemini requests unless enabled, authenticated, and rate-limited."""
    if not server_gemini_configuration_ready():
        raise HTTPException(
            status_code=503,
            detail="Gemini no servidor desabilitado ou com configuração de segurança incompleta.",
        )

    expected = os.environ["LOTOMASTER_SERVER_GEMINI_TOKEN"].encode("utf-8")
    authorization = request.headers.get("authorization", "")
    scheme, separator, supplied = authorization.partition(" ")
    valid_scheme = scheme.lower() == "bearer" and bool(separator) and bool(supplied)
    try:
        valid_token = valid_scheme and hmac.compare_digest(supplied.encode("utf-8"), expected)
    except UnicodeEncodeError:
        valid_token = False
    if not valid_token:
        raise HTTPException(
            status_code=401,
            detail="Credencial necessária para usar o Gemini no servidor.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Do not parse X-Forwarded-For ourselves. If proxy middleware rewrites this
    # address, the server must trust only explicitly configured proxy ranges.
    client_key = request.client.host if request.client else "unknown"
    retry_after = server_gemini_rate_limiter.consume(client_key)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Limite temporário de chamadas Gemini excedido.",
            headers={"Retry-After": str(retry_after)},
        )
