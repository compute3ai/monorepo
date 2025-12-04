"""Job monitor TUI - async log streaming with metrics display"""
import asyncio
import time
from collections import deque
from typing import Optional
from queue import Queue, Empty
from dataclasses import dataclass, field

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich import box

from c3 import C3, LogStream, fetch_logs

console = Console()

# Buffer limits
MAX_LOG_LINES = 1000


@dataclass
class JobStatus:
    """Status updates for job execution (e.g., ComfyUI workflow progress)"""
    stage: str = "initializing"
    message: str = ""
    progress: float = 0
    history: list[str] = field(default_factory=list)
    error: str | None = None
    complete: bool = False
    result: dict | None = None


def format_time(seconds: int) -> str:
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s" if m else f"{s}s"


def bar(pct: float, width: int = 30, color: str = "blue") -> str:
    filled = int(pct / 100 * width)
    return f"[{color}]{'█' * filled}[/][dim]{'░' * (width - filled)}[/]"


def build_header(job, elapsed: int, metrics) -> Panel:
    """Combined job info + metrics header"""
    parts = []

    # Job info line
    colors = {"queued": "yellow", "assigned": "blue", "running": "green",
              "succeeded": "bright_green", "failed": "red", "terminated": "red"}
    state_color = colors.get(job.state, "white")

    info = f"[bold {state_color}]{job.state.upper()}[/]  {job.gpu_type} x{job.gpu_count}  {job.region}  ${job.price_per_hour:.2f}/hr"
    if job.hostname:
        info += f"  [dim]{job.hostname}[/]"
    if job.runtime and elapsed > 0:
        left = max(0, job.runtime - elapsed)
        pct = min(elapsed / job.runtime * 100, 100)
        c = "red" if left < 300 else "yellow" if left < 900 else "green"
        info += f"  {bar(pct, 10, c)} [{c}]{format_time(left)}[/]"
    parts.append(info)

    # System metrics (CPU + RAM) - show first
    if metrics and metrics.system:
        parts.append("")
        s = metrics.system
        cpu_pct = min(s.cpu_percent, 100)  # Clamp at 100% for display
        cpu_c = "green" if cpu_pct < 70 else "yellow" if cpu_pct < 90 else "red"
        mem_pct = (s.memory_used / s.memory_limit * 100) if s.memory_limit else 0
        mem_c = "red" if mem_pct >= 90 else "yellow" if mem_pct >= 70 else "green"

        line = f"[bold]CPU[/]  {bar(cpu_pct, 20, cpu_c)} {cpu_pct:4.0f}%  "
        line += f"RAM  {bar(mem_pct, 15, mem_c)} {s.memory_used/1024:.1f}/{s.memory_limit/1024:.1f}GB"
        parts.append(line)

    # GPU metrics
    if metrics and metrics.gpus:
        if not metrics.system:
            parts.append("")
        for g in metrics.gpus:
            uc = "green" if g.utilization >= 50 else "yellow" if g.utilization >= 20 else "dim"
            mp = (g.memory_used / g.memory_total * 100) if g.memory_total else 0
            mc = "red" if mp >= 90 else "yellow" if mp >= 70 else "green"
            tc = "red" if g.temperature >= 85 else "yellow" if g.temperature >= 70 else "green"
            pc = "green" if g.power_draw < 100 else "yellow" if g.power_draw < 250 else "bright_red" if g.power_draw < 350 else "red"

            line = f"[bold]GPU {g.index}[/]  {bar(g.utilization, 20, uc)} {g.utilization:4.0f}%  "
            line += f"VRAM {bar(mp, 15, mc)} {g.memory_used/1024:.1f}/{g.memory_total/1024:.1f}GB  "
            line += f"[{tc}]{g.temperature}°C[/]  [{pc}]{g.power_draw:.0f}W[/]"
            parts.append(line)

    return Panel("\n".join(parts), title=f"[bold]{job.job_id[:24]}[/]", border_style="blue", box=box.ROUNDED)


def build_status_panel(status: JobStatus, height: int = 10) -> Panel:
    """Build the job status panel showing workflow progress"""
    parts = []

    if status.progress > 0:
        prog_bar = bar(status.progress, 30, "cyan")
        parts.append(f"[bold]{status.stage}[/]  {prog_bar} {status.progress:.0f}%")
    else:
        parts.append(f"[bold cyan]{status.stage}[/]")

    if status.message:
        parts.append(f"  {status.message}")

    if status.error:
        parts.append(f"\n[bold red]Error:[/] {status.error}")

    if status.history:
        parts.append("")
        visible_history = status.history[-(height - 4):]
        for msg in visible_history:
            parts.append(f"[dim]  {msg}[/]")

    border = "green" if status.complete else "red" if status.error else "magenta"
    title = "[bold]Status[/]"
    if status.complete:
        title = "[bold green]Complete[/]"
    elif status.error:
        title = "[bold red]Failed[/]"

    return Panel("\n".join(parts), title=title, border_style=border, box=box.ROUNDED)


def build_layout(job, elapsed, metrics, logs, ws_status, job_status, content_height) -> Layout:
    """Build the full layout"""
    layout = Layout()
    header = build_header(job, elapsed, metrics)
    header_height = 3 + (len(metrics.gpus) if metrics and metrics.gpus else 0) + (1 if metrics and metrics.system else 0)

    if job_status:
        log_lines = int(content_height * 0.7)
        log_content = "\n".join(list(logs)[-log_lines:]) if logs else "[dim]Waiting for logs...[/]"
        log_panel = Panel(log_content, title=f"[bold]Logs[/] ({ws_status})", border_style="yellow", box=box.ROUNDED, height=content_height + 2)

        status_panel = build_status_panel(job_status, content_height)
        content_layout = Layout()
        content_layout.split_row(
            Layout(log_panel, name="logs", ratio=2),
            Layout(status_panel, name="status", ratio=1),
        )
        layout.split_column(
            Layout(header, name="header", size=header_height + 2),
            content_layout,
        )
    else:
        log_content = "\n".join(list(logs)[-content_height:]) if logs else "[dim]Waiting for logs...[/]"
        log_panel = Panel(log_content, title=f"[bold]Logs[/] ({ws_status})", border_style="yellow", box=box.ROUNDED, height=content_height + 2)

        layout.split_column(
            Layout(header, name="header", size=header_height + 2),
            Layout(log_panel, name="logs"),
        )

    return layout


async def _run_job_monitor_async(
    job_id: str,
    status_q: Queue = None,
    stop_on_status_complete: bool = False,
):
    """Async job monitor - uses SDK LogStream for logs"""
    c3 = C3()
    logs: deque[str] = deque(maxlen=MAX_LOG_LINES)
    log_stream: Optional[LogStream] = None
    log_task: Optional[asyncio.Task] = None
    metrics = None
    job_status: Optional[JobStatus] = None
    ws_status = "[dim]● waiting[/]"
    stop_event = asyncio.Event()

    console.print(f"[dim]Ctrl+C to exit[/]\n")

    # Wait for job
    job = None
    with console.status("[cyan]Connecting..."):
        while not job:
            try:
                job = c3.jobs.get(job_id)
            except Exception:
                await asyncio.sleep(1)

    async def stream_logs_task(stream: LogStream):
        """Background task that streams logs continuously with batching"""
        nonlocal ws_status
        log_batch = []
        last_flush = asyncio.get_event_loop().time()
        FLUSH_INTERVAL = 0.05  # Flush every 50ms

        try:
            async for line in stream:
                if stop_event.is_set():
                    break
                log_batch.append(line)

                # Flush batch periodically
                now = asyncio.get_event_loop().time()
                if now - last_flush >= FLUSH_INTERVAL:
                    logs.extend(log_batch)
                    log_batch.clear()
                    last_flush = now

            # Flush remaining
            if log_batch:
                logs.extend(log_batch)
        except Exception:
            pass
        finally:
            ws_status = "[dim]● ended[/]"

    async def fetch_metrics_task():
        """Background task that fetches metrics periodically"""
        nonlocal metrics
        while not stop_event.is_set():
            try:
                if job and job.state in ("assigned", "running"):
                    metrics = await asyncio.to_thread(c3.jobs.metrics, job_id)
            except Exception:
                pass
            await asyncio.sleep(2)

    async def fetch_job_task():
        """Background task that fetches job state periodically"""
        nonlocal job, log_stream, log_task, ws_status
        while not stop_event.is_set():
            try:
                job = await asyncio.to_thread(c3.jobs.get, job_id)

                # Start log stream when job is ready
                if job.state in ("assigned", "running") and log_stream is None and job.job_key:
                    # Fetch initial logs ONCE
                    if job.state == "running":
                        initial = await asyncio.to_thread(fetch_logs, c3, job_id, MAX_LOG_LINES)
                        for line in initial:
                            logs.append(line)

                    # Connect websocket and start streaming task
                    log_stream = LogStream(
                        c3, job_id,
                        job_key=job.job_key,
                        fetch_initial=False,
                        max_buffer=MAX_LOG_LINES,
                    )
                    await log_stream.connect()
                    log_task = asyncio.create_task(stream_logs_task(log_stream))
                    ws_status = "[green]● live[/]"
            except Exception:
                pass
            await asyncio.sleep(1)

    try:
        # Start background tasks
        metrics_task = asyncio.create_task(fetch_metrics_task())
        job_task = asyncio.create_task(fetch_job_task())

        with Live(console=console, refresh_per_second=10, screen=True) as live:
            while True:
                try:
                    elapsed = int(time.time() - job.started_at) if job and job.started_at else 0

                    # Drain status queue if provided
                    if status_q:
                        while True:
                            try:
                                job_status = status_q.get_nowait()
                            except Empty:
                                break

                    # Calculate layout
                    term_height = console.size.height
                    header_height = 3 + (len(metrics.gpus) if metrics and metrics.gpus else 0) + (1 if metrics and metrics.system else 0)
                    content_height = max(10, term_height - header_height - 4)

                    # Update display
                    if job:
                        layout = build_layout(job, elapsed, metrics, logs, ws_status, job_status, content_height)
                        live.update(layout)

                    # Check completion
                    if stop_on_status_complete and job_status and job_status.complete:
                        await asyncio.sleep(3)
                        break

                    # Job terminated
                    if job and job.state in ("succeeded", "failed", "canceled", "terminated"):
                        # Fetch final logs ONCE
                        final = await asyncio.to_thread(fetch_logs, c3, job_id, MAX_LOG_LINES)
                        logs.clear()
                        for line in final:
                            logs.append(line)
                        ws_status = "[dim]● ended[/]"

                        layout = build_layout(job, elapsed, metrics, logs, ws_status, job_status, content_height)
                        live.update(layout)
                        await asyncio.sleep(1)
                        break

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    console.print(f"[red]{e}[/]")

                await asyncio.sleep(0.05)  # 20fps render loop

        console.print(f"\n[bold]Job {job.state}[/]")

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped[/]")
    finally:
        stop_event.set()
        if log_task:
            log_task.cancel()
        if log_stream:
            await log_stream.close()
        metrics_task.cancel()
        job_task.cancel()


def run_job_monitor(
    job_id: str,
    status_q: Queue = None,
    stop_on_status_complete: bool = False,
):
    """Run the job monitor TUI (sync wrapper).

    Args:
        job_id: The job ID to monitor
        status_q: Optional queue receiving JobStatus updates for status pane
        stop_on_status_complete: If True, exit when JobStatus.complete is True
    """
    asyncio.run(_run_job_monitor_async(job_id, status_q, stop_on_status_complete))
