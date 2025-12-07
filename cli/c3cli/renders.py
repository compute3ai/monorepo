"""c3 renders commands"""
import time
import typer
from typing import Optional
from c3 import C3
from .output import output, console, success, spinner

app = typer.Typer(help="Manage renders")


def get_client() -> C3:
    return C3()


@app.command("list")
def list_renders(
    state: Optional[str] = typer.Option(None, "--state", "-s", help="Filter by state"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Filter by template"),
    type: Optional[str] = typer.Option(None, "--type", help="Filter by render type"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List all renders"""
    c3 = get_client()
    with spinner("Fetching renders..."):
        renders = c3.renders.list(state=state, template=template, type=type)

    if fmt == "json":
        output(renders, "json")
    else:
        if not renders:
            console.print("[dim]No renders found[/dim]")
            return
        output(renders, "table", ["render_id", "state", "template", "render_type", "created_at"])


@app.command("get")
def get_render(
    render_id: str = typer.Argument(..., help="Render ID"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Get render details"""
    c3 = get_client()
    with spinner("Fetching render..."):
        render = c3.renders.get(render_id)
    output(render, fmt)


@app.command("create")
def create_render(
    template: str = typer.Argument(..., help="Template name"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Text prompt"),
    gpu: str = typer.Option("L40S", "--gpu", "-g", help="GPU type"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Region"),
    render_type: str = typer.Option("comfyui", "--type", "-t", help="Render type"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for completion"),
    notify_url: Optional[str] = typer.Option(None, "--notify", help="Webhook URL for completion"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Create a new render"""
    c3 = get_client()

    params = {
        "template": template,
        "prompt": prompt,
        "gpu_type": gpu,
    }
    if region:
        params["region"] = region

    with spinner("Creating render..."):
        render = c3.renders.create(params=params, render_type=render_type, notify_url=notify_url)

    if fmt == "json" and not wait:
        output(render, "json")
    else:
        console.print(f"[bold green]✓[/bold green] Render created: [cyan]{render.render_id}[/cyan]")
        console.print(f"  State: {render.state}")

    if wait:
        _wait_for_render(c3, render.render_id, fmt)


@app.command("status")
def status(
    render_id: str = typer.Argument(..., help="Render ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch status live"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Get render status"""
    c3 = get_client()

    if watch:
        _watch_status(c3, render_id)
    else:
        with spinner("Fetching status..."):
            s = c3.renders.status(render_id)
        output(s, fmt)


@app.command("cancel")
def cancel(
    render_id: str = typer.Argument(..., help="Render ID"),
):
    """Cancel a render"""
    c3 = get_client()
    with spinner("Cancelling render..."):
        c3.renders.cancel(render_id)
    success(f"Render {render_id} cancelled")


def _wait_for_render(c3: C3, render_id: str, fmt: str, poll_interval: float = 2.0):
    """Wait for render to complete"""
    console.print("Waiting for completion...")

    while True:
        status = c3.renders.status(render_id)
        progress_str = f" ({status.progress:.0%})" if status.progress is not None else ""
        console.print(f"  State: {status.state}{progress_str}")

        if status.state in ("completed", "failed", "cancelled"):
            break
        time.sleep(poll_interval)

    # Get final render details
    render = c3.renders.get(render_id)

    if fmt == "json":
        output(render, "json")
    else:
        console.print()
        if render.state == "completed":
            success(f"Render completed!")
            if render.result_url:
                console.print(f"  Result: [link={render.result_url}]{render.result_url}[/link]")
        else:
            console.print(f"[bold red]Render {render.state}[/bold red]")
            if render.error:
                console.print(f"  Error: {render.error}")


def _watch_status(c3: C3, render_id: str, poll_interval: float = 2.0):
    """Watch render status live"""
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    def render_status_panel(status, render=None):
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        table.add_row("ID", status.render_id)
        table.add_row("State", _state_style(status.state))
        if status.progress is not None:
            table.add_row("Progress", f"{status.progress:.0%}")
        if render and render.result_url:
            table.add_row("Result", render.result_url)
        if render and render.error:
            table.add_row("Error", f"[red]{render.error}[/red]")

        return Panel(table, title="[bold]Render Status[/bold]")

    with Live(console=console, refresh_per_second=2) as live:
        while True:
            try:
                status = c3.renders.status(render_id)
                render = None

                if status.state in ("completed", "failed", "cancelled"):
                    render = c3.renders.get(render_id)
                    live.update(render_status_panel(status, render))
                    break

                live.update(render_status_panel(status))
                time.sleep(poll_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                break


def _state_style(state: str) -> str:
    """Style state for display"""
    styles = {
        "pending": "[yellow]pending[/yellow]",
        "running": "[blue]running[/blue]",
        "completed": "[green]completed[/green]",
        "failed": "[red]failed[/red]",
        "cancelled": "[dim]cancelled[/dim]",
    }
    return styles.get(state, state)
