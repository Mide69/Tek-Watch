"""Usage metering middleware — increments per-customer API call counter after each successful response."""
import asyncio
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_ADMIN_PREFIX = "/api/v1/admin/"
_HEALTH_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class UsageMeterMiddleware(BaseHTTPMiddleware):
    """Fire-and-forget usage metering after every successful authenticated customer request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        path = request.url.path
        if (
            response.status_code < 400
            and path not in _HEALTH_PATHS
            and not path.startswith(_ADMIN_PREFIX)
            and hasattr(request.state, "customer_id")
        ):
            customer_id: str = request.state.customer_id
            endpoint = path.lstrip("/").split("/")[2] if path.count("/") >= 3 else "unknown"
            asyncio.ensure_future(_meter(customer_id, endpoint))

        return response


async def _meter(customer_id: str, endpoint: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _meter_sync, customer_id, endpoint)


def _meter_sync(customer_id: str, endpoint: str) -> None:
    try:
        from services.usage_meter import increment_api_call
        increment_api_call(customer_id, endpoint)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Usage meter background error: %s", exc)
