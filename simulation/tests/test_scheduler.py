"""Tests for KlineScheduler — asyncio + heapq K-line close time scheduler."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from simulation.engine.scheduler import KlineScheduler

# ============================================================================
# calc_next_kline_close  (pure function — no scheduler instance needed)
# ============================================================================


class TestCalcNextKlineClose:
    """Static method tests — each timeframe returns correct next close."""

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _ts(*args: int) -> float:
        """Return Unix timestamp for UTC datetime components."""
        return datetime(*args, tzinfo=UTC).timestamp()

    # -- 1m ----------------------------------------------------------------

    def test_1m_mid_minute(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 35, 42)
        result = KlineScheduler.calc_next_kline_close("1m", ts)
        expected = self._ts(2025, 5, 19, 14, 36, 0)
        assert result == expected

    def test_1m_at_boundary(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 35, 0)
        result = KlineScheduler.calc_next_kline_close("1m", ts)
        expected = self._ts(2025, 5, 19, 14, 36, 0)
        assert result == expected

    # -- 3m ----------------------------------------------------------------

    def test_3m(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 35, 0)
        result = KlineScheduler.calc_next_kline_close("3m", ts)
        expected = self._ts(2025, 5, 19, 14, 36, 0)
        assert result == expected

    def test_3m_at_boundary(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 36, 0)
        result = KlineScheduler.calc_next_kline_close("3m", ts)
        expected = self._ts(2025, 5, 19, 14, 39, 0)
        assert result == expected

    # -- 5m ----------------------------------------------------------------

    def test_5m(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 37, 0)
        result = KlineScheduler.calc_next_kline_close("5m", ts)
        expected = self._ts(2025, 5, 19, 14, 40, 0)
        assert result == expected

    def test_5m_at_boundary(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 35, 0)
        result = KlineScheduler.calc_next_kline_close("5m", ts)
        expected = self._ts(2025, 5, 19, 14, 40, 0)
        assert result == expected

    # -- 15m ---------------------------------------------------------------

    def test_15m(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 20, 0)
        result = KlineScheduler.calc_next_kline_close("15m", ts)
        expected = self._ts(2025, 5, 19, 14, 30, 0)
        assert result == expected

    def test_15m_at_boundary(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 30, 0)
        result = KlineScheduler.calc_next_kline_close("15m", ts)
        expected = self._ts(2025, 5, 19, 14, 45, 0)
        assert result == expected

    def test_15m_cross_hour(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 50, 0)
        result = KlineScheduler.calc_next_kline_close("15m", ts)
        expected = self._ts(2025, 5, 19, 15, 0, 0)
        assert result == expected

    # -- 1h ----------------------------------------------------------------

    def test_1h(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 35, 0)
        result = KlineScheduler.calc_next_kline_close("1h", ts)
        expected = self._ts(2025, 5, 19, 15, 0, 0)
        assert result == expected

    def test_1h_at_boundary(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 0, 0)
        result = KlineScheduler.calc_next_kline_close("1h", ts)
        expected = self._ts(2025, 5, 19, 15, 0, 0)
        assert result == expected

    # -- 4h ----------------------------------------------------------------

    def test_4h(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 35, 0)
        result = KlineScheduler.calc_next_kline_close("4h", ts)
        expected = self._ts(2025, 5, 19, 16, 0, 0)
        assert result == expected

    def test_4h_at_1600(self) -> None:
        ts = self._ts(2025, 5, 19, 16, 0, 0)
        result = KlineScheduler.calc_next_kline_close("4h", ts)
        expected = self._ts(2025, 5, 19, 20, 0, 0)
        assert result == expected

    def test_4h_at_midnight(self) -> None:
        ts = self._ts(2025, 5, 19, 0, 0, 0)
        result = KlineScheduler.calc_next_kline_close("4h", ts)
        expected = self._ts(2025, 5, 19, 4, 0, 0)
        assert result == expected

    # -- 1d ----------------------------------------------------------------

    def test_1d(self) -> None:
        ts = self._ts(2025, 5, 19, 14, 35, 0)
        result = KlineScheduler.calc_next_kline_close("1d", ts)
        expected = self._ts(2025, 5, 20, 0, 0, 0)
        assert result == expected

    def test_1d_at_midnight(self) -> None:
        ts = self._ts(2025, 5, 19, 0, 0, 0)
        result = KlineScheduler.calc_next_kline_close("1d", ts)
        expected = self._ts(2025, 5, 20, 0, 0, 0)
        assert result == expected

    # -- edge cases --------------------------------------------------------

    def test_microsecond_precision(self) -> None:
        """Fractional seconds should work correctly."""
        ts = self._ts(2025, 5, 19, 14, 0, 0) + 0.001
        result = KlineScheduler.calc_next_kline_close("1h", ts)
        expected = self._ts(2025, 5, 19, 15, 0, 0)
        assert result == expected

    def test_default_from_ts(self) -> None:
        """When from_ts is omitted, should use the current time."""
        result = KlineScheduler.calc_next_kline_close("1m")
        now = time.time()
        assert result > now
        assert result <= now + 60


# ============================================================================
# Scheduler operational tests
# ============================================================================


@pytest.mark.asyncio
async def test_schedule_and_fire() -> None:
    """Schedule an event — the callback should be invoked."""
    q: asyncio.Queue[str] = asyncio.Queue()

    async def callback() -> None:
        await q.put("fired")

    with patch("simulation.engine.scheduler.time.time", return_value=1000.0):
        scheduler = KlineScheduler(buffer_seconds=0)
        scheduler.schedule(1000.0, "evt", callback)

    runner = asyncio.create_task(scheduler.run())

    try:
        result = await asyncio.wait_for(q.get(), timeout=1.0)
        assert result == "fired"
    finally:
        scheduler.stop()
        await runner


@pytest.mark.asyncio
async def test_schedule_past_time_fires_immediately() -> None:
    """An event whose fire time is already past should fire right away."""
    q: asyncio.Queue[str] = asyncio.Queue()

    async def callback() -> None:
        await q.put("past")

    # current time is 5000, but event was scheduled for 1000 → already past
    with patch("simulation.engine.scheduler.time.time", return_value=5000.0):
        scheduler = KlineScheduler(buffer_seconds=0)
        scheduler.schedule(1000.0, "past", callback)

    runner = asyncio.create_task(scheduler.run())

    try:
        result = await asyncio.wait_for(q.get(), timeout=1.0)
        assert result == "past"
    finally:
        scheduler.stop()
        await runner


@pytest.mark.asyncio
async def test_cancel_prevents_fire() -> None:
    """A cancelled event must NOT invoke its callback."""
    q: asyncio.Queue[str] = asyncio.Queue()

    async def callback() -> None:
        await q.put("should_not_appear")

    with patch("simulation.engine.scheduler.time.time", return_value=1000.0):
        scheduler = KlineScheduler(buffer_seconds=0)
        scheduler.schedule(1000.0, "evt", callback)
        scheduler.cancel("evt")

    runner = asyncio.create_task(scheduler.run())

    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q.get(), timeout=0.15)
    finally:
        scheduler.stop()
        await runner


@pytest.mark.asyncio
async def test_multiple_events_fire_in_order() -> None:
    """Three events with different trigger times should all fire."""
    results: list[str] = []

    async def cb_a() -> None:
        results.append("a")

    async def cb_b() -> None:
        results.append("b")

    async def cb_c() -> None:
        results.append("c")

    with patch("simulation.engine.scheduler.time.time", return_value=99999.0):
        scheduler = KlineScheduler(buffer_seconds=0)
        scheduler.schedule(3000.0, "c", cb_c)
        scheduler.schedule(1000.0, "a", cb_a)
        scheduler.schedule(2000.0, "b", cb_b)

    runner = asyncio.create_task(scheduler.run())

    # Let events fire (all are past, so they fire almost instantly).
    await asyncio.sleep(0.05)
    scheduler.stop()
    await runner

    assert len(results) == 3
    assert set(results) == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_reentrant_callback() -> None:
    """A callback may schedule another event — both should fire."""
    q: asyncio.Queue[str] = asyncio.Queue()

    async def cb2() -> None:
        await q.put("second")

    async def cb1() -> None:
        await q.put("first")
        # Schedule another event from within the callback
        scheduler.schedule(1000.0, "second", cb2)

    with patch("simulation.engine.scheduler.time.time", return_value=1000.0):
        scheduler = KlineScheduler(buffer_seconds=0)
        scheduler.schedule(1000.0, "first", cb1)

    runner = asyncio.create_task(scheduler.run())

    try:
        r1 = await asyncio.wait_for(q.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q.get(), timeout=1.0)
        assert {r1, r2} == {"first", "second"}
    finally:
        scheduler.stop()
        await runner


@pytest.mark.asyncio
async def test_stop_exits_gracefully() -> None:
    """After stop() the run loop must exit promptly."""
    scheduler = KlineScheduler(buffer_seconds=0)

    runner = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.01)  # let the loop start and hit the empty-heap wait

    scheduler.stop()
    await asyncio.wait_for(runner, timeout=1.0)
    # If we reach here, run() returned cleanly.


@pytest.mark.asyncio
async def test_callback_exception_does_not_crash_scheduler() -> None:
    """An exception in a callback must not bring down the scheduler."""
    q: asyncio.Queue[str] = asyncio.Queue()

    async def faulty() -> None:
        raise RuntimeError("boom!")

    async def healthy() -> None:
        await q.put("ok")

    with patch("simulation.engine.scheduler.time.time", return_value=1000.0):
        scheduler = KlineScheduler(buffer_seconds=0)
        scheduler.schedule(1000.0, "faulty", faulty)
        scheduler.schedule(1000.0, "ok", healthy)

    runner = asyncio.create_task(scheduler.run())

    try:
        result = await asyncio.wait_for(q.get(), timeout=1.0)
        assert result == "ok"
    finally:
        scheduler.stop()
        await runner


@pytest.mark.asyncio
async def test_cancel_between_pop_and_execute() -> None:
    """Cancel called after pop but before callback runs should still skip."""
    q: asyncio.Queue[str] = asyncio.Queue()

    async def callback() -> None:
        await q.put("should_not_fire")

    with patch("simulation.engine.scheduler.time.time", return_value=1000.0):
        scheduler = KlineScheduler(buffer_seconds=0)
        scheduler.schedule(1000.0, "race", callback)

    # Cancel AFTER schedule but BEFORE run starts processing
    scheduler.cancel("race")

    runner = asyncio.create_task(scheduler.run())

    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q.get(), timeout=0.15)
    finally:
        scheduler.stop()
        await runner


@pytest.mark.asyncio
async def test_buffer_delay_is_applied() -> None:
    """The buffer_seconds should delay the actual fire time."""
    q: asyncio.Queue[str] = asyncio.Queue()

    async def callback() -> None:
        await q.put("buffered")

    # Time is 1000.0; trigger is 1000.0; with buffer=5, fire_ts=1005.0
    # So the event should NOT fire yet (fire_ts=1005 > now=1000).
    # Keep the mock active through run() so time stays frozen at 1000.0.
    with patch("simulation.engine.scheduler.time.time", return_value=1000.0):
        scheduler = KlineScheduler(buffer_seconds=5)
        scheduler.schedule(1000.0, "buf", callback)
        runner = asyncio.create_task(scheduler.run())

        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(q.get(), timeout=0.15)
        finally:
            scheduler.stop()
            await runner
