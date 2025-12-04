"""c3 jobs commands"""
import typer
from typing import Optional
from c3 import C3
from .output import output, console, success, spinner

app = typer.Typer(help="Manage running jobs")


def get_client() -> C3:
    return C3()


@app.command("list")
def list_jobs(
    state: Optional[str] = typer.Option(None, "--state", "-s", help="Filter by state"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List all jobs"""
    c3 = get_client()
    with spinner("Fetching jobs..."):
        jobs = c3.jobs.list(state=state)

    if fmt == "json":
        output(jobs, "json")
    else:
        if not jobs:
            console.print("[dim]No jobs found[/dim]")
            return
        output(jobs, "table", ["job_id", "state", "gpu_type", "gpu_count", "region", "hostname"])


@app.command("get")
def get_job(
    job_id: str = typer.Argument(..., help="Job ID"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Get job details"""
    c3 = get_client()
    with spinner("Fetching job..."):
        job = c3.jobs.get(job_id)
    output(job, fmt)


@app.command("logs")
def logs(
    job_id: str = typer.Argument(..., help="Job ID"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream logs"),
):
    """Get job logs"""
    c3 = get_client()

    if follow:
        _follow_job(job_id)
    else:
        with spinner("Fetching logs..."):
            logs_str = c3.jobs.logs(job_id)
        console.print(logs_str)


@app.command("metrics")
def metrics(
    job_id: str = typer.Argument(..., help="Job ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch metrics live"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Get job GPU metrics"""
    c3 = get_client()

    if watch:
        _watch_metrics(job_id)
    else:
        with spinner("Fetching metrics..."):
            m = c3.jobs.metrics(job_id)
        if fmt == "json":
            output(m, "json")
        else:
            _print_metrics(m)


@app.command("cancel")
def cancel(
    job_id: str = typer.Argument(..., help="Job ID"),
):
    """Cancel a running job"""
    c3 = get_client()
    with spinner("Cancelling job..."):
        c3.jobs.cancel(job_id)
    success(f"Job {job_id} cancelled")


@app.command("extend")
def extend(
    job_id: str = typer.Argument(..., help="Job ID"),
    runtime: int = typer.Argument(..., help="New runtime in seconds"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Extend job runtime"""
    c3 = get_client()
    with spinner("Extending runtime..."):
        job = c3.jobs.extend(job_id, runtime)
    if fmt == "json":
        output(job, "json")
    else:
        success(f"Job extended to {runtime}s runtime")


def _print_metrics(m):
    """Print GPU metrics"""
    from rich.panel import Panel
    from rich.table import Table

    # System metrics (CPU/RAM)
    if m.system:
        sys_table = Table(show_header=False, box=None, padding=(0, 2))
        sys_table.add_column("Metric", style="cyan")
        sys_table.add_column("Value")
        sys_table.add_column("Bar", width=30)

        cpu_bar = _make_bar(m.system.cpu_percent, 100)
        mem_pct = (m.system.memory_used / m.system.memory_limit * 100) if m.system.memory_limit else 0
        mem_bar = _make_bar(mem_pct, 100)

        sys_table.add_row("CPU", f"{m.system.cpu_percent:5.1f}%", cpu_bar)
        sys_table.add_row("RAM", f"{m.system.memory_used/1024:.1f}/{m.system.memory_limit/1024:.1f} GB", mem_bar)

        console.print(Panel(sys_table, title="[bold]System[/bold]"))

    if not m.gpus:
        console.print("[dim]No GPU metrics available[/dim]")
        return

    for gpu in m.gpus:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_column("Bar", width=30)

        util_bar = _make_bar(gpu.utilization, 100)
        mem_pct = (gpu.memory_used / gpu.memory_total * 100) if gpu.memory_total else 0
        mem_bar = _make_bar(mem_pct, 100)
        temp_bar = _make_bar(gpu.temperature, 100, warn=70, crit=85)

        table.add_row("GPU", f"{gpu.utilization:5.1f}%", util_bar)
        table.add_row("VRAM", f"{gpu.memory_used/1024:.1f}/{gpu.memory_total/1024:.1f} GB", mem_bar)
        table.add_row("Temp", f"{gpu.temperature}°C", temp_bar)
        table.add_row("Power", f"{gpu.power_draw:.0f}W", "")

        title = f"[bold]GPU {gpu.index}: {gpu.name}[/bold]" if gpu.name else f"[bold]GPU {gpu.index}[/bold]"
        console.print(Panel(table, title=title))


def _make_bar(value: float, max_val: float, warn: float = None, crit: float = None) -> str:
    """Create a colored progress bar"""
    pct = min(value / max_val, 1.0) if max_val else 0
    width = 25
    filled = int(pct * width)

    if crit and value >= crit:
        color = "red"
    elif warn and value >= warn:
        color = "yellow"
    else:
        color = "green"

    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}]"


def _follow_job(job_id: str):
    """Follow job with TUI"""
    from .tui.job_monitor import run_job_monitor
    run_job_monitor(job_id)


def _watch_metrics(job_id: str):
    """Watch metrics live"""
    import time
    from rich.live import Live

    c3 = get_client()

    with Live(console=console, refresh_per_second=2) as live:
        while True:
            try:
                m = c3.jobs.metrics(job_id)
                live.update(_render_metrics(m))
                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                break


def _render_metrics(m):
    """Render metrics as Rich panel"""
    from rich.panel import Panel
    from rich.table import Table
    from rich.console import Group

    panels = []

    # System metrics
    if m.system:
        sys_table = Table(show_header=False, box=None)
        sys_table.add_column("Metric", style="cyan")
        sys_table.add_column("Value")
        cpu_bar = _make_bar(m.system.cpu_percent, 100)
        mem_pct = (m.system.memory_used / m.system.memory_limit * 100) if m.system.memory_limit else 0
        mem_bar = _make_bar(mem_pct, 100)
        sys_table.add_row("CPU", f"{m.system.cpu_percent:5.1f}% {cpu_bar}")
        sys_table.add_row("RAM", f"{m.system.memory_used/1024:.1f}/{m.system.memory_limit/1024:.1f}GB {mem_bar}")
        panels.append(Panel(sys_table, title="[bold]System[/bold]", border_style="blue"))

    if not m.gpus:
        panels.append(Panel("[dim]No GPU metrics[/dim]"))
        return Group(*panels)

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("GPU")
    table.add_column("Util")
    table.add_column("VRAM")
    table.add_column("Temp")
    table.add_column("Power")

    for gpu in m.gpus:
        util_bar = _make_bar(gpu.utilization, 100)
        name = f"{gpu.index}: {gpu.name}" if gpu.name else str(gpu.index)
        table.add_row(
            f"[bold]{name}[/bold]",
            f"{gpu.utilization:5.1f}% {util_bar}",
            f"{gpu.memory_used/1024:.1f}/{gpu.memory_total/1024:.1f}GB",
            f"{gpu.temperature}°C",
            f"{gpu.power_draw:.0f}W"
        )

    panels.append(Panel(table, title="[bold]GPU Metrics[/bold]", border_style="green"))
    return Group(*panels)
