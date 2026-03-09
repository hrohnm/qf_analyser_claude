import asyncio
import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.sync.budget_manager import budget_manager

BASE_URL = "https://v3.football.api-sports.io"

# api-football.com Pro plan: max 300 requests/minute
# Keep a small reserve to avoid burst-triggered throttling.
MAX_REQUESTS_PER_MINUTE = 280


class RateLimitError(Exception):
    pass


class MinuteRateLimiter:
    """Token-bucket limiter: allows at most `rate` calls per 60-second window."""

    def __init__(self, rate: int = MAX_REQUESTS_PER_MINUTE):
        self._rate = rate
        self._lock = asyncio.Lock()
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Remove timestamps older than 60 seconds
            self._timestamps = [t for t in self._timestamps if now - t < 60.0]

            if len(self._timestamps) >= self._rate:
                # Wait until the oldest call is 60s old
                wait_for = 60.0 - (now - self._timestamps[0]) + 0.1
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
                # Re-clean after sleep
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < 60.0]

            self._timestamps.append(time.monotonic())


class ApiFootballClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"x-apisports-key": settings.api_football_key},
            timeout=30.0,
        )
        self._rate_limiter = MinuteRateLimiter(MAX_REQUESTS_PER_MINUTE)

    async def close(self):
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=5, max=65),
        reraise=True,
    )
    async def get(self, endpoint: str, params: dict | None = None, job_name: str = "") -> dict:
        # Respect per-minute rate limit
        await self._rate_limiter.acquire()

        async with AsyncSessionLocal() as db:
            await budget_manager.check_and_raise(db, calls=1, job_name=job_name)

        full_params = params or {}
        error_msg = None
        response = None

        try:
            response = await self._client.get(endpoint, params=full_params)

            if response.status_code == 429:
                raise RateLimitError("HTTP 429 – rate limit reached")

            response.raise_for_status()
            data = response.json()

            # api-football also signals rate limits in the JSON body
            errors = data.get("errors")
            if errors:
                error_str = str(errors)
                error_msg = error_str
                if "rateLimit" in error_str or "rate" in error_str.lower():
                    raise RateLimitError(f"JSON rate limit: {error_str}")

            return data

        except RateLimitError:
            raise  # let tenacity retry
        except Exception as exc:
            error_msg = str(exc)
            raise
        finally:
            async with AsyncSessionLocal() as db:
                await budget_manager.record_call(
                    db=db,
                    endpoint=endpoint,
                    params=full_params,
                    http_status=response.status_code if response else None,
                    headers=dict(response.headers) if response else None,
                    job_name=job_name or None,
                    error=error_msg,
                )


# Singleton used across all sync jobs
api_client = ApiFootballClient()
