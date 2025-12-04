"""Async log streaming for jobs"""
import asyncio
import json
from collections import deque
from typing import TYPE_CHECKING, AsyncIterator, Callable

import websockets

from .config import get_ws_url, WS_LOGS_PATH

if TYPE_CHECKING:
    from .client import C3


# Default limits to prevent memory blowup
DEFAULT_MAX_INITIAL_LINES = 1000  # Max lines to fetch on initial REST call
DEFAULT_MAX_BUFFER = 5000  # Max lines to keep in memory buffer


def fetch_logs(c3: "C3", job_id: str, tail: int = None) -> list[str]:
    """Fetch logs via REST API (one-time call).

    Args:
        c3: C3 client
        job_id: Job ID
        tail: Only return last N lines (default: all)

    Returns:
        List of log lines
    """
    try:
        logs = c3.jobs.logs(job_id)
        if not logs:
            return []
        lines = logs.strip().split("\n")
        if tail and len(lines) > tail:
            return lines[-tail:]
        return lines
    except Exception:
        return []


class LogStream:
    """Async log streamer - websocket streaming with optional initial fetch.

    Usage:
        stream = LogStream(c3, job)
        await stream.connect()
        async for line in stream:
            print(line)
        await stream.close()

    This class guarantees:
    - Initial logs fetched ONCE on connect (limited to max_initial_lines)
    - All subsequent logs via websocket (NO polling)
    - Bounded buffer to prevent memory blowup
    - Proper cleanup on close
    """

    def __init__(
        self,
        c3: "C3",
        job_id: str,
        job_key: str = None,
        fetch_initial: bool = True,
        max_initial_lines: int = DEFAULT_MAX_INITIAL_LINES,
        max_buffer: int = DEFAULT_MAX_BUFFER,
    ):
        """
        Args:
            c3: C3 client
            job_id: Job ID for REST log fetch
            job_key: Job key for websocket (if None, fetched from job)
            fetch_initial: Whether to fetch existing logs on connect
            max_initial_lines: Max lines to fetch initially (prevents huge fetch)
            max_buffer: Max lines to keep in buffer (oldest dropped)
        """
        self.c3 = c3
        self.job_id = job_id
        self.job_key = job_key
        self.fetch_initial = fetch_initial
        self.max_initial_lines = max_initial_lines
        self.max_buffer = max_buffer

        self._ws = None
        self._buffer: deque[str] = deque(maxlen=max_buffer)
        self._initial_fetched = False
        self._connected = False
        self._closed = False

    @property
    def status(self) -> str:
        """Connection status: disconnected, connecting, connected, closed"""
        if self._closed:
            return "closed"
        if self._connected:
            return "connected"
        if self._ws:
            return "connecting"
        return "disconnected"

    async def connect(self) -> list[str]:
        """Connect to log stream.

        Returns initial logs (if fetch_initial=True).
        After this, iterate with `async for line in stream`.
        """
        if self._closed:
            raise RuntimeError("LogStream is closed")

        initial_lines = []

        # Fetch initial logs ONCE (bounded)
        if self.fetch_initial and not self._initial_fetched:
            initial_lines = fetch_logs(self.c3, self.job_id, tail=self.max_initial_lines)
            for line in initial_lines:
                self._buffer.append(line)
            self._initial_fetched = True

        # Get job_key if not provided
        if not self.job_key:
            job = self.c3.jobs.get(self.job_id)
            self.job_key = job.job_key

        # Connect websocket
        if self.job_key and not self._ws:
            ws_url = get_ws_url()
            full_url = f"{ws_url}{WS_LOGS_PATH}/{self.job_key}"
            self._ws = await websockets.connect(full_url)
            self._connected = True

        return initial_lines

    async def close(self):
        """Close the websocket connection"""
        self._closed = True
        self._connected = False
        if self._ws:
            await self._ws.close()
            self._ws = None

    def get_buffer(self) -> list[str]:
        """Get current buffer contents (bounded, oldest may be dropped)"""
        return list(self._buffer)

    def clear_buffer(self):
        """Clear the buffer"""
        self._buffer.clear()

    async def __aiter__(self) -> AsyncIterator[str]:
        """Async iterate over NEW log lines from websocket.

        Note: This does NOT yield initial logs. Call connect() first
        and handle the returned initial lines separately.
        """
        if not self._ws:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            async for message in self._ws:
                if self._closed:
                    break
                try:
                    data = json.loads(message)
                    if data.get("event") == "log" and data.get("log"):
                        for line in data["log"].splitlines():
                            if line:
                                self._buffer.append(line)
                                yield line
                except json.JSONDecodeError:
                    continue
        except websockets.ConnectionClosed:
            self._connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def stream_logs(
    c3: "C3",
    job_id: str,
    on_line: Callable[[str], None],
    until_state: set[str] = None,
    poll_state_interval: float = 2.0,
    fetch_initial: bool = True,
    fetch_final: bool = True,
    max_initial_lines: int = DEFAULT_MAX_INITIAL_LINES,
) -> None:
    """Stream logs until job reaches a terminal state.

    Args:
        c3: C3 client
        job_id: Job ID to stream logs from
        on_line: Callback for each log line (called immediately, no buffering)
        until_state: States to stop on (default: terminal states)
        poll_state_interval: How often to check job STATE (NOT log polling!)
        fetch_initial: Fetch existing logs on start
        fetch_final: Fetch logs one more time after job terminates
        max_initial_lines: Max lines to fetch initially

    This function:
    - Fetches initial logs ONCE (bounded)
    - Streams via websocket (NO log polling)
    - Polls job STATE only (to detect termination)
    - Optionally fetches final logs ONCE when job terminates
    """
    if until_state is None:
        until_state = {"succeeded", "failed", "canceled", "terminated"}

    job = c3.jobs.get(job_id)
    initial_fetched = False
    ws = None

    try:
        # Wait for job to be assigned/running
        while job.state in ("pending", "queued"):
            await asyncio.sleep(poll_state_interval)
            job = c3.jobs.get(job_id)

        # Check for immediate terminal state
        if job.state in until_state:
            if fetch_final:
                for line in fetch_logs(c3, job_id, tail=max_initial_lines):
                    on_line(line)
            return

        # Fetch initial logs ONCE when running (bounded)
        if fetch_initial and job.state == "running" and not initial_fetched:
            for line in fetch_logs(c3, job_id, tail=max_initial_lines):
                on_line(line)
            initial_fetched = True

        # Connect websocket
        if job.job_key:
            ws_url = get_ws_url()
            full_url = f"{ws_url}{WS_LOGS_PATH}/{job.job_key}"
            ws = await websockets.connect(full_url)

            # Stream logs while checking job state periodically
            while True:
                try:
                    # Wait for message with timeout to allow state checks
                    message = await asyncio.wait_for(ws.recv(), timeout=poll_state_interval)
                    try:
                        data = json.loads(message)
                        if data.get("event") == "log" and data.get("log"):
                            for line in data["log"].splitlines():
                                if line:
                                    on_line(line)
                    except json.JSONDecodeError:
                        continue
                except asyncio.TimeoutError:
                    # Check job state (NOT polling logs!)
                    job = c3.jobs.get(job_id)
                    if job.state in until_state:
                        break
                except websockets.ConnectionClosed:
                    break

        # Fetch final logs ONCE (may have missed some during shutdown)
        if fetch_final:
            # Small delay to let final logs flush
            await asyncio.sleep(0.5)
            for line in fetch_logs(c3, job_id, tail=max_initial_lines):
                on_line(line)

    finally:
        if ws:
            await ws.close()
