import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from app.core.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Ограничивает частоту запросов с одного IP; при злоупотреблении — временная блокировка."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._request_times: dict[str, deque[float]] = defaultdict(deque)
        self._post_times: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _prune(self, bucket: deque[float], window: float, now: float) -> None:
        while bucket and now - bucket[0] > window:
            bucket.popleft()

    def _is_blocked(self, ip: str, now: float) -> bool:
        blocked_until = self._blocked_until.get(ip)
        if blocked_until is None:
            return False
        if now >= blocked_until:
            self._blocked_until.pop(ip, None)
            return False
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.monotonic()

        if self._is_blocked(ip, now):
            return HTMLResponse(
                "<h1>Слишком много запросов</h1><p>Подождите несколько минут и обновите страницу.</p>",
                status_code=429,
            )

        general_bucket = self._request_times[ip]
        self._prune(general_bucket, settings.rate_limit_window_seconds, now)
        general_bucket.append(now)
        if len(general_bucket) > settings.rate_limit_max_requests:
            self._blocked_until[ip] = now + settings.rate_limit_block_seconds
            return HTMLResponse(
                "<h1>Слишком много запросов</h1><p>Доступ временно ограничен. Попробуйте позже.</p>",
                status_code=429,
            )

        if request.method == "POST":
            post_bucket = self._post_times[ip]
            self._prune(post_bucket, settings.rate_limit_post_window_seconds, now)
            post_bucket.append(now)
            if len(post_bucket) > settings.rate_limit_max_post_requests:
                self._blocked_until[ip] = now + settings.rate_limit_block_seconds
                return HTMLResponse(
                    "<h1>Слишком много действий</h1><p>Вы слишком часто нажимали кнопки. Подождите несколько минут.</p>",
                    status_code=429,
                )

        return await call_next(request)
