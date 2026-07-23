"""The Recalculate-All freeze was in the Sheets write path, not the fetch path.

googleapiclient is built on httplib2, which is NOT thread-safe. The batch runs many
_run_one tasks concurrently, each doing ~10 Sheets API calls (2 upserts/ticker)
through ONE shared service on the default multi-thread executor. That concurrent use
of the single httplib2 connection wedged the whole run after ~6 tickers. These tests
pin the fix: (1) all Sheets I/O is serialized onto one dedicated thread, and (2)
requests retry with backoff on quota (429) / transient (503) errors so a full recalc
self-throttles instead of erroring or hanging.
"""
import asyncio
import threading
from unittest.mock import MagicMock

import pytest

import services.sheets as sheets


def test_sheets_executor_is_single_threaded():
    """One worker thread => the shared, non-thread-safe googleapiclient service is
    only ever touched by one thread at a time."""
    from concurrent.futures import ThreadPoolExecutor
    assert isinstance(sheets._SHEETS_EXECUTOR, ThreadPoolExecutor)
    assert sheets._SHEETS_EXECUTOR._max_workers == 1


@pytest.mark.asyncio
async def test_run_sheets_serializes_calls():
    """Concurrent _run_sheets calls never overlap — max one in flight at a time."""
    current = 0
    max_seen = 0
    lock = threading.Lock()

    def work():
        nonlocal current, max_seen
        with lock:
            current += 1
            max_seen = max(max_seen, current)
        import time
        time.sleep(0.02)
        with lock:
            current -= 1
        return "ok"

    await asyncio.gather(*[sheets._run_sheets(work) for _ in range(6)])
    assert max_seen == 1


def _http_error(status: int) -> Exception:
    from googleapiclient.errors import HttpError
    resp = MagicMock()
    resp.status = status
    return HttpError(resp, b"quota", uri="https://sheets")


def test_execute_retries_on_429_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(sheets._time, "sleep", lambda s: sleeps.append(s))
    req = MagicMock()
    req.execute.side_effect = [_http_error(429), _http_error(429), {"ok": True}]
    assert sheets._execute(req) == {"ok": True}
    assert req.execute.call_count == 3
    assert len(sleeps) == 2                      # backed off before each retry
    assert sleeps == sorted(sleeps)              # non-decreasing backoff


def test_execute_does_not_retry_non_quota_errors(monkeypatch):
    monkeypatch.setattr(sheets._time, "sleep", lambda s: (_ for _ in ()).throw(
        AssertionError("must not sleep on a non-quota error")))
    req = MagicMock()
    req.execute.side_effect = _http_error(403)   # permission denied, not quota
    with pytest.raises(Exception):
        sheets._execute(req)
    assert req.execute.call_count == 1           # no retry


def test_execute_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(sheets._time, "sleep", lambda s: None)
    monkeypatch.setattr(sheets, "_SHEETS_MAX_RETRIES", 3)
    req = MagicMock()
    req.execute.side_effect = _http_error(429)
    with pytest.raises(Exception):
        sheets._execute(req)
    assert req.execute.call_count == 3
