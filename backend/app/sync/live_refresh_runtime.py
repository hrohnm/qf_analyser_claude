import asyncio
from dataclasses import dataclass

from app.config import settings


MIN_INTERVAL_SECONDS = 60


@dataclass
class LiveRefreshState:
    enabled: bool
    interval_seconds: int


class LiveRefreshController:
    def __init__(self, enabled: bool, interval_seconds: int) -> None:
        self._enabled = enabled
        self._interval_seconds = max(interval_seconds, MIN_INTERVAL_SECONDS)
        self._change_event = asyncio.Event()

    def get_state(self) -> LiveRefreshState:
        return LiveRefreshState(
            enabled=self._enabled,
            interval_seconds=self._interval_seconds,
        )

    def update(self, enabled: bool | None = None, interval_seconds: int | None = None) -> LiveRefreshState:
        changed = False

        if enabled is not None and enabled != self._enabled:
            self._enabled = enabled
            changed = True

        if interval_seconds is not None:
            normalized_interval = max(interval_seconds, MIN_INTERVAL_SECONDS)
            if normalized_interval != self._interval_seconds:
                self._interval_seconds = normalized_interval
                changed = True

        if changed:
            self._change_event.set()

        return self.get_state()

    async def wait_until_next_run(self) -> LiveRefreshState:
        while True:
            state = self.get_state()
            if not state.enabled:
                await self._wait_for_change()
                continue

            timeout = self._seconds_until_next_interval(state.interval_seconds)
            changed = await self._wait_for_change(timeout=timeout)
            if changed:
                continue

            return self.get_state()

    async def _wait_for_change(self, timeout: float | None = None) -> bool:
        self._change_event.clear()
        try:
            if timeout is None:
                await self._change_event.wait()
                return True
            await asyncio.wait_for(self._change_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    @staticmethod
    def _seconds_until_next_interval(interval_seconds: int) -> float:
        now = asyncio.get_running_loop().time()
        remainder = now % interval_seconds
        return interval_seconds - remainder if remainder else interval_seconds


live_refresh_controller = LiveRefreshController(
    enabled=settings.live_fixture_refresh_enabled,
    interval_seconds=settings.live_fixture_refresh_interval_seconds,
)
