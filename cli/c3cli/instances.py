"""c3 instances commands"""
import typer
from typing import Optional
from c3 import C3
from .output import output, console, success, spinner

app = typer.Typer(help="GPU instances - browse and launch")


def get_client() -> C3:
    return C3()


@app.command("list")
def list_instances(
    gpu: Optional[str] = typer.Option(None, "--gpu", "-g", help="Filter by GPU type"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Filter by region"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List available GPU instances with pricing"""
    c3 = get_client()
    with spinner("Fetching instances..."):
        available = c3.instances.list_available(gpu_type=gpu, region=region)

    if fmt == "json":
        output(available, "json")
    else:
        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("GPU")
        table.add_column("Count", justify="right")
        table.add_column("Region")
        table.add_column("Spot $/hr", justify="right")
        table.add_column("On-Demand $/hr", justify="right")
        table.add_column("vCPUs", justify="right")
        table.add_column("RAM GB", justify="right")

        for item in sorted(available, key=lambda x: (x["gpu_type"], x["gpu_count"], x.get("price_spot") or 999)):
            spot_price = f"${item['price_spot']:.2f}" if item['price_spot'] else "-"
            od_price = f"${item['price_on_demand']:.2f}" if item['price_on_demand'] else "-"

            table.add_row(
                f"[green]{item['gpu_type']}[/]",
                str(item['gpu_count']),
                f"{item['region']} ({item['region_name']})",
                f"[cyan]{spot_price}[/]",
                od_price,
                str(int(item['cpu_cores'])),
                str(int(item['memory_gb'])),
            )

        console.print(table)


@app.command("gpus")
def list_gpus(
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Filter by region"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List available GPU types"""
    c3 = get_client()
    with spinner("Fetching GPU types..."):
        types = c3.instances.types()

    if fmt == "json":
        output({k: {"name": v.name, "description": v.description, "configs": [
            {"gpu_count": c.gpu_count, "cpu_cores": c.cpu_cores, "memory_gb": c.memory_gb, "regions": c.regions}
            for c in v.configs
        ]} for k, v in types.items()}, "json")
    else:
        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("GPU Type")
        table.add_column("Name")
        table.add_column("Description")
        table.add_column("Counts")
        table.add_column("Regions")

        for gpu_id, gpu in types.items():
            available_counts = []
            available_regions = set()
            for config in gpu.configs:
                if config.regions:
                    if region and region not in config.regions:
                        continue
                    available_counts.append(str(config.gpu_count))
                    available_regions.update(config.regions)

            if not available_counts:
                continue

            table.add_row(
                f"[green]{gpu_id}[/]",
                gpu.name,
                gpu.description,
                ", ".join(available_counts),
                ", ".join(sorted(available_regions)),
            )

        console.print(table)


@app.command("regions")
def list_regions(
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List available regions"""
    c3 = get_client()
    with spinner("Fetching regions..."):
        regions = c3.instances.regions()

    if fmt == "json":
        output({k: {"description": v.description, "country": v.country} for k, v in regions.items()}, "json")
    else:
        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Code")
        table.add_column("Location")
        table.add_column("Country")

        for region_id, region in regions.items():
            table.add_row(
                f"[green]{region_id}[/]",
                region.description,
                region.country,
            )

        console.print(table)


@app.command("launch")
def launch(
    image: str = typer.Argument(..., help="Docker image"),
    command: Optional[str] = typer.Option(None, "--command", "-c", help="Command to run"),
    gpu: str = typer.Option("l40s", "--gpu", "-g", help="GPU type"),
    count: int = typer.Option(1, "--count", "-n", help="Number of GPUs"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Region code"),
    runtime: Optional[int] = typer.Option(None, "--runtime", "-t", help="Runtime in seconds"),
    interruptible: bool = typer.Option(True, "--interruptible/--on-demand", help="Use interruptible instances"),
    env: Optional[list[str]] = typer.Option(None, "--env", "-e", help="Env vars (KEY=VALUE)"),
    port: Optional[list[str]] = typer.Option(None, "--port", "-p", help="Ports (name:port)"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs after creation"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Launch a new GPU instance"""
    c3 = get_client()

    # Parse env vars
    env_dict = None
    if env:
        env_dict = {}
        for e in env:
            if "=" in e:
                k, v = e.split("=", 1)
                env_dict[k] = v

    # Parse ports
    ports_dict = None
    if port:
        ports_dict = {}
        for p in port:
            if ":" in p:
                name, port_num = p.split(":", 1)
                ports_dict[name] = int(port_num)

    with spinner("Launching instance..."):
        job = c3.jobs.create(
            image=image,
            command=command,
            gpu_type=gpu,
            gpu_count=count,
            region=region,
            runtime=runtime,
            interruptible=interruptible,
            env=env_dict,
            ports=ports_dict,
        )

    if fmt == "json":
        output(job, "json")
    else:
        success(f"Instance launched: {job.job_id}")
        console.print(f"  State:    {job.state}")
        console.print(f"  GPU:      {job.gpu_type} x{job.gpu_count}")
        console.print(f"  Region:   {job.region}")
        console.print(f"  Price:    ${job.price_per_hour:.2f}/hr")
        if job.hostname:
            console.print(f"  Hostname: {job.hostname}")

    if follow:
        console.print()
        from .tui.job_monitor import run_job_monitor
        run_job_monitor(job.job_id)
