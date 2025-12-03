"""Job monitor with load bars - metrics hover above scrolling logs"""
import json
import time
import threading
from typing import Optional
from queue import Queue, Empty

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich import box

from c3 import C3
from c3.config import get_ws_url, WS_LOGS_PATH


console = Console()


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

    # GPU metrics
    if metrics and metrics.gpus:
        parts.append("")  # blank line
        for g in metrics.gpus:
            uc = "green" if g.utilization >= 50 else "yellow" if g.utilization >= 20 else "dim"
            mp = (g.memory_used / g.memory_total * 100) if g.memory_total else 0
            mc = "red" if mp >= 90 else "yellow" if mp >= 70 else "green"
            tc = "red" if g.temperature >= 85 else "yellow" if g.temperature >= 70 else "green"

            line = f"[bold]GPU {g.index}[/]  {bar(g.utilization, 20, uc)} {g.utilization:4.0f}%  "
            line += f"VRAM {bar(mp, 15, mc)} {g.memory_used/1024:.1f}/{g.memory_total/1024:.1f}GB  "
            line += f"[{tc}]{g.temperature}°C[/]  {g.power_draw:.0f}W"
            parts.append(line)

    return Panel("\n".join(parts), title=f"[bold]{job.job_id[:24]}[/]", border_style="blue", box=box.ROUNDED)


class WSLogs:
    def __init__(self, job_key: str, q: Queue):
        self.job_key = job_key
        self.q = q
        self.status = "disconnected"  # disconnected, connecting, connected
        self.running = True
        self.error = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

    def _run(self):
        import websocket

        ws_url = get_ws_url()
        full_url = f"{ws_url}{WS_LOGS_PATH}/{self.job_key}"

        while self.running:
            self.status = "connecting"
            try:
                ws = websocket.create_connection(full_url, timeout=10)
                self.status = "connected"
                self.error = None

                while self.running:
                    try:
                        ws.settimeout(0.05)  # 50ms for near-realtime
                        data = ws.recv()
                        if data:
                            msg = json.loads(data)
                            if msg.get("event") == "log" and msg.get("log"):
                                # Split by newlines and flush each line immediately
                                for line in msg["log"].splitlines():
                                    if line:
                                        self.q.put(line)
                    except websocket.WebSocketTimeoutException:
                        continue
                    except websocket.WebSocketConnectionClosedException:
                        break
                    except Exception as e:
                        self.error = str(e)
                        break

                ws.close()
            except Exception as e:
                self.error = str(e)
                self.status = "disconnected"

            # Retry after 1s if still running
            if self.running:
                time.sleep(1)


def run_job_monitor(job_id: str):
    c3 = C3()
    logs: list[str] = []
    log_q: Queue = Queue()
    ws: Optional[WSLogs] = None
    metrics = None
    last_metrics = 0
    fetched_initial_logs = False

    console.print(f"[dim]Ctrl+C to exit[/]\n")

    # Wait for job
    job = None
    with console.status("[cyan]Connecting..."):
        while not job:
            try:
                job = c3.jobs.get(job_id)
            except:
                time.sleep(1)

    try:
        with Live(console=console, refresh_per_second=10, screen=True) as live:
            while True:
                now = time.time()
                try:
                    job = c3.jobs.get(job_id)
                    elapsed = int(now - job.started_at) if job.started_at else 0

                    # Start websocket when we have job_key
                    if job.state in ("assigned", "running") and ws is None and job.job_key:
                        # Fetch existing logs first when running
                        if job.state == "running" and not fetched_initial_logs:
                            try:
                                r = c3.jobs.logs(job_id)
                                if r:
                                    logs = r.strip().split("\n")
                                fetched_initial_logs = True
                            except:
                                pass
                        # Then connect websocket
                        ws = WSLogs(job.job_key, log_q)
                        ws.start()

                    # Drain websocket queue immediately
                    while True:
                        try:
                            logs.append(log_q.get_nowait())
                        except Empty:
                            break

                    # Fetch metrics every 2s when running
                    if job.state == "running" and now - last_metrics >= 2:
                        try:
                            metrics = c3.jobs.metrics(job_id)
                            last_metrics = now
                        except:
                            pass

                    # Build layout
                    layout = Layout()
                    header = build_header(job, elapsed, metrics)
                    header_height = 3 + (len(metrics.gpus) if metrics and metrics.gpus else 0)

                    term_height = console.size.height
                    log_height = max(10, term_height - header_height - 4)

                    # Status indicator
                    if ws:
                        if ws.status == "connected":
                            status = "[green]● live[/]"
                        elif ws.status == "connecting":
                            status = "[yellow]● connecting[/]"
                        else:
                            status = f"[red]● {ws.error or 'disconnected'}[/]"
                    else:
                        status = "[dim]● waiting[/]"

                    log_content = "\n".join(logs[-log_height:]) if logs else "[dim]Waiting for logs...[/]"
                    log_panel = Panel(log_content, title=f"[bold]Logs[/] ({status})", border_style="yellow", box=box.ROUNDED)

                    layout.split_column(
                        Layout(header, name="header", size=header_height + 2),
                        Layout(log_panel, name="logs"),
                    )
                    live.update(layout)

                    # Job finished
                    if job.state in ("succeeded", "failed", "canceled", "terminated"):
                        if ws:
                            ws.stop()
                        # Final log fetch
                        try:
                            r = c3.jobs.logs(job_id)
                            if r:
                                logs = r.strip().split("\n")
                        except:
                            pass
                        log_content = "\n".join(logs[-log_height:])
                        log_panel = Panel(log_content, title="[bold]Logs[/]", border_style="yellow", box=box.ROUNDED)
                        layout.split_column(
                            Layout(header, name="header", size=header_height + 2),
                            Layout(log_panel, name="logs"),
                        )
                        live.update(layout)
                        time.sleep(1)
                        break

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    console.print(f"[red]{e}[/]")

                time.sleep(0.1)  # Fast loop for responsive websocket

        console.print(f"\n[bold]Job {job.state}[/]")

    except KeyboardInterrupt:
        if ws:
            ws.stop()
        console.print("\n[dim]Stopped[/]")
