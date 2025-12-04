"""c3 comfyui commands - Run ComfyUI workflows on GPU"""
import random
import threading
from pathlib import Path
from queue import Queue
from typing import Optional

import typer

from c3 import C3, ComfyUIJob, APIError, apply_params, load_template, graph_to_api
from .output import console, error, success, spinner
from .tui import JobStatus, run_job_monitor

app = typer.Typer(help="Run ComfyUI workflows on GPU")


def get_client() -> C3:
    return C3()


def _run_workflow(
    job: ComfyUIJob,
    template: str,
    params: dict,
    timeout: int,
    output_dir: Path,
    status_q: Queue,
):
    """Execute workflow and push status updates to queue"""
    try:
        # Refresh and check current state
        job.refresh()
        status_q.put(JobStatus(
            stage="Initializing",
            message=f"Job state: {job.job.state}, checking {job.base_url}..."
        ))

        if not job.wait_ready(timeout=timeout):
            job.refresh()
            status_q.put(JobStatus(
                stage="Failed",
                error=f"Health check failed. State: {job.job.state}, URL: {job.base_url}",
                complete=True
            ))
            return

        status_q.put(JobStatus(
            stage="Loading",
            message=f"Loading template: {template}",
            history=["ComfyUI ready"],
        ))

        # Load and convert workflow
        try:
            graph = job.load_template(template)
        except ImportError as e:
            status_q.put(JobStatus(
                stage="Failed",
                error=str(e),
                history=["ComfyUI ready", "Failed to load template"],
                complete=True,
            ))
            return

        status_q.put(JobStatus(
            stage="Converting",
            message="Converting workflow to API format...",
            history=["ComfyUI ready", f"Loaded template: {template}"],
        ))

        workflow = job.convert_workflow(graph)

        # Apply params using type-based node lookup
        apply_params(workflow, **params)

        status_q.put(JobStatus(
            stage="Queuing",
            message="Submitting workflow to ComfyUI...",
            history=["ComfyUI ready", f"Loaded: {template}", "Workflow converted"],
        ))

        # Submit
        prompt_id = job.queue_prompt(workflow)

        status_q.put(JobStatus(
            stage="Generating",
            message=f"Prompt ID: {prompt_id[:16]}...",
            progress=10,
            history=["ComfyUI ready", f"Loaded: {template}", "Workflow converted", "Queued"],
        ))

        # Poll for completion
        import time
        start = time.time()
        last_progress = 10
        while time.time() - start < timeout:
            history_entry = job.get_history(prompt_id)
            if history_entry:
                status = history_entry.get("status", {})
                if status.get("completed"):
                    break
                if status.get("status_str") == "error":
                    status_q.put(JobStatus(
                        stage="Failed",
                        error=f"Workflow error: {status}",
                        history=["ComfyUI ready", f"Loaded: {template}", "Workflow converted", "Queued", "Execution failed"],
                        complete=True,
                    ))
                    return

            # Update progress (fake progress since we don't know actual)
            elapsed = time.time() - start
            # Assume ~60s typical, cap at 90%
            fake_progress = min(10 + (elapsed / 60) * 80, 90)
            if fake_progress > last_progress + 5:
                last_progress = fake_progress
                status_q.put(JobStatus(
                    stage="Generating",
                    message=f"Processing... ({int(elapsed)}s)",
                    progress=fake_progress,
                    history=["ComfyUI ready", f"Loaded: {template}", "Workflow converted", "Queued"],
                ))

            time.sleep(2)
        else:
            status_q.put(JobStatus(
                stage="Failed",
                error=f"Timeout after {timeout}s",
                complete=True,
            ))
            return

        status_q.put(JobStatus(
            stage="Downloading",
            message="Fetching output images...",
            progress=95,
            history=["ComfyUI ready", f"Loaded: {template}", "Workflow converted", "Queued", "Generated"],
        ))

        # Get outputs
        images = job.get_output_images(history_entry)
        if not images:
            status_q.put(JobStatus(
                stage="Failed",
                error="No output images found",
                complete=True,
            ))
            return

        # Download
        downloaded = []
        for img in images:
            filename = img["filename"]
            subfolder = img.get("subfolder", "")
            saved_path = job.download_output(filename, output_dir, subfolder)
            downloaded.append(str(saved_path))

        status_q.put(JobStatus(
            stage="Complete",
            message=f"Saved {len(downloaded)} image(s)",
            progress=100,
            history=[
                "ComfyUI ready",
                f"Loaded: {template}",
                "Workflow converted",
                "Queued",
                "Generated",
                *[f"Saved: {p}" for p in downloaded],
            ],
            complete=True,
            result={"images": downloaded},
        ))

    except Exception as e:
        status_q.put(JobStatus(
            stage="Failed",
            error=str(e),
            complete=True,
        ))


@app.command("run")
def run(
    template: str = typer.Argument(..., help="Template ID (e.g., image_qwen_image)"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Positive prompt"),
    negative: str = typer.Option("", "--negative", "-n", help="Negative prompt"),
    output: str = typer.Option(..., "--output", "-o", help="Output filename prefix"),
    width: int = typer.Option(1328, "--width", "-W", help="Image width"),
    height: int = typer.Option(1328, "--height", "-H", help="Image height"),
    seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed (increments with --num)"),
    random_seed: bool = typer.Option(False, "--random", "-r", help="Use random seed for each image"),
    steps: int = typer.Option(20, "--steps", help="Sampling steps"),
    cfg: float = typer.Option(2.5, "--cfg", help="CFG scale"),
    gpu_type: str = typer.Option("l40s", "--gpu", help="GPU type (e.g., l40s, a100, h100)"),
    gpu_count: int = typer.Option(1, "--count", help="Number of GPUs"),
    interruptible: bool = typer.Option(True, "--interruptible/--on-demand", help="Use interruptible instances"),
    region: Optional[str] = typer.Option(None, "--region", help="Region (e.g., us-east, eu-west, asia-east)"),
    output_dir: str = typer.Option(".", "--output-dir", "-d", help="Output directory"),
    timeout: int = typer.Option(600, "--timeout", "-t", help="Timeout in seconds"),
    num: int = typer.Option(1, "--num", "-N", help="Number of images to generate"),
    new: bool = typer.Option(False, "--new", help="Always launch new instance"),
    instance: Optional[str] = typer.Option(None, "--instance", "-i", help="Connect to job by ID, hostname, or IP"),
    lb: Optional[int] = typer.Option(None, "--lb", help="Enable HTTPS load balancer on port (e.g., 8188)"),
    auth: bool = typer.Option(False, "--auth", help="Enable Bearer token auth on load balancer"),
    stdout: bool = typer.Option(False, "--stdout", help="Output to stdout instead of TUI"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode: stdout + verbose errors"),
    workflow_json: bool = typer.Option(False, "--workflow-json", help="Output generated workflow JSON and exit (don't run)"),
):
    """Run a ComfyUI workflow template"""

    # --workflow-json: generate JSON offline and exit (no instance needed)
    if workflow_json:
        import json as json_module

        # Build params
        if seed is not None:
            iteration_seed = seed
        elif random_seed or num > 1:
            iteration_seed = random.randint(0, 2**32 - 1)
        else:
            iteration_seed = None

        params = {
            "prompt": prompt,
            "negative": negative,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "filename_prefix": output,
        }
        if iteration_seed is not None:
            params["seed"] = iteration_seed

        try:
            graph = load_template(template)
            workflow = graph_to_api(graph, debug=debug)
            apply_params(workflow, **params)

            # Output JSON to stdout
            print(json_module.dumps(workflow, indent=2))
        except ImportError as e:
            error(str(e))
            raise typer.Exit(1)
        except Exception as e:
            error(f"Failed to generate workflow: {e}")
            if debug:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
            raise typer.Exit(1)
        raise typer.Exit(0)

    c3 = get_client()

    # Get or create job
    try:
        if instance:
            # Connect to specific instance by ID, hostname, or IP
            with spinner(f"Connecting to instance {instance}..."):
                job = ComfyUIJob.get_by_instance(c3, instance)
                job.template = template
                job.use_lb = lb is not None
                job.use_auth = auth
        else:
            # Get or create job with template env var
            with spinner(f"Getting ComfyUI instance for {template}..."):
                job = ComfyUIJob.get_or_create_for_template(
                    c3,
                    template=template,
                    gpu_type=gpu_type,
                    gpu_count=gpu_count,
                    region=region,
                    reuse=not new,
                    lb=lb,
                    auth=auth,
                    interruptible=interruptible,
                )
    except APIError as e:
        error(f"API Error ({e.status_code}): {e.detail}")
        if debug:
            console.print(f"[dim]Request: gpu_type={gpu_type}, gpu_count={gpu_count}, region={region}, interruptible={interruptible}, lb={lb}, auth={auth}[/dim]")
        raise typer.Exit(1)

    console.print(f"Job: [cyan]{job.job_id}[/cyan]")
    if job.use_lb:
        console.print(f"URL: [cyan]{job.base_url}[/cyan] (HTTPS + {'auth' if job.use_auth else 'no auth'})")

    # Run workflow(s)
    for i in range(num):
        # Build params for this iteration
        # Seed logic:
        # - --seed X: use X, increment for each image (X, X+1, X+2...)
        # - --random: random seed per image
        # - --num > 1 (no seed): assume random (different images wanted)
        # - nothing: don't pass seed (use workflow default = reference image)
        if seed is not None:
            iteration_seed = seed + i
        elif random_seed or num > 1:
            iteration_seed = random.randint(0, 2**32 - 1)
        else:
            iteration_seed = None  # Use workflow default

        iteration_prefix = f"{output}_{i+1}" if num > 1 else output

        params = {
            "prompt": prompt,
            "negative": negative,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "filename_prefix": iteration_prefix,
        }
        if iteration_seed is not None:
            params["seed"] = iteration_seed

        if num > 1:
            seed_info = f"seed: {iteration_seed}" if iteration_seed else "default seed"
            console.print(f"\n[bold]Image {i+1}/{num}[/bold] ({seed_info})")

        if stdout or debug:
            # Simple mode without TUI
            _run_simple(job, template, params, timeout, Path(output_dir), debug=debug)
        else:
            # TUI mode with status pane
            status_q: Queue = Queue()

            # Start workflow in background thread
            workflow_thread = threading.Thread(
                target=_run_workflow,
                args=(job, template, params, timeout, Path(output_dir), status_q),
                daemon=True,
            )
            workflow_thread.start()

            # Run TUI in main thread
            run_job_monitor(job.job_id, status_q=status_q, stop_on_status_complete=True)

            # Wait for workflow thread to finish
            workflow_thread.join(timeout=5)


def _run_simple(job: ComfyUIJob, template: str, params: dict, timeout: int, output_dir: Path, debug: bool = False):
    """Simple mode without TUI"""
    if debug:
        console.print(f"[dim]Debug: base_url={job.base_url}[/dim]")
        console.print(f"[dim]Debug: params={params}[/dim]")

    if not job.hostname:
        with spinner("Waiting for instance to start..."):
            if not job.wait_for_hostname(timeout=timeout):
                error("Instance failed to start")
                raise typer.Exit(1)

    console.print(f"Host: [cyan]{job.hostname}[/cyan]")

    with spinner("Waiting for ComfyUI to be ready..."):
        if not job.wait_ready(timeout=timeout):
            error("ComfyUI failed to become ready")
            raise typer.Exit(1)

    success("ComfyUI ready")

    try:
        if debug:
            console.print(f"[dim]Debug: Loading template {template}...[/dim]")
        graph = job.load_template(template)

        if debug:
            console.print(f"[dim]Debug: Converting workflow...[/dim]")
        workflow = job.convert_workflow(graph, debug=debug)

        # Apply params using type-based node lookup
        apply_params(workflow, **params)

        if debug:
            import json
            console.print(f"[dim]Debug: Workflow nodes: {list(workflow.keys())}[/dim]")
            console.print(f"[dim]Debug: Submitting to {job.base_url}/prompt[/dim]")

        with spinner("Running workflow..."):
            history = job.run(workflow, timeout=timeout, convert=False)

    except ImportError as e:
        error(str(e))
        console.print("\n[dim]pip install comfyui-workflow-templates comfyui-workflow-templates-media-image[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        error(f"Workflow failed: {e}")
        if debug:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            # Try to get response body for HTTP errors
            if hasattr(e, 'response'):
                try:
                    console.print(f"[red]Response body: {e.response.text}[/red]")
                except:
                    pass
        raise typer.Exit(1)

    success("Workflow completed")

    images = job.get_output_images(history)
    if not images:
        error("No output images found")
        raise typer.Exit(1)

    for img in images:
        filename = img["filename"]
        subfolder = img.get("subfolder", "")
        with spinner(f"Downloading {filename}..."):
            saved_path = job.download_output(filename, output_dir, subfolder)
        console.print(f"  [green]✓[/green] {saved_path}")

    success("Done!")


@app.command("templates")
def templates():
    """List available workflow templates"""
    try:
        from comfyui_workflow_templates import iter_templates
    except ImportError:
        error("comfyui-workflow-templates not installed")
        console.print("\n[dim]pip install comfyui-workflow-templates[/dim]")
        raise typer.Exit(1)

    console.print("[bold]Available templates:[/bold]\n")

    by_bundle: dict[str, list] = {}
    for entry in iter_templates():
        bundle = entry.bundle
        if bundle not in by_bundle:
            by_bundle[bundle] = []
        by_bundle[bundle].append(entry.template_id)

    for bundle, ids in sorted(by_bundle.items()):
        console.print(f"[bold cyan]{bundle}[/bold cyan]")
        for tid in sorted(ids):
            console.print(f"  {tid}")
        console.print()


@app.command("status")
def status():
    """Show running ComfyUI job status"""
    c3 = get_client()

    with spinner("Checking for running jobs..."):
        job = ComfyUIJob.get_running(c3)

    if not job:
        console.print("[dim]No running ComfyUI job[/dim]")
        return

    console.print(f"[bold]Job ID:[/bold] {job.job_id}")
    console.print(f"[bold]State:[/bold] {job.job.state}")
    console.print(f"[bold]GPU:[/bold] {job.job.gpu_type} x{job.job.gpu_count}")
    console.print(f"[bold]Region:[/bold] {job.job.region}")

    if job.hostname:
        console.print(f"[bold]Hostname:[/bold] {job.hostname}")
        console.print(f"[bold]URL:[/bold] {job.base_url}")

        with spinner("Checking health..."):
            healthy = job.check_health()

        if healthy:
            success("ComfyUI is healthy")
        else:
            console.print("[yellow]ComfyUI not responding[/yellow]")


@app.command("download")
def download(
    instance: str = typer.Option(None, "--instance", "-i", help="Job ID, hostname, or IP"),
    output_dir: str = typer.Option(".", "--output-dir", "-d", help="Output directory"),
    lb: Optional[int] = typer.Option(None, "--lb", help="Use HTTPS load balancer on port"),
    auth: bool = typer.Option(False, "--auth", help="Use Bearer token auth"),
):
    """Download outputs from a running ComfyUI instance"""
    c3 = get_client()

    # Get job
    if instance:
        with spinner(f"Connecting to {instance}..."):
            job = ComfyUIJob.get_by_instance(c3, instance)
    else:
        with spinner("Finding running job..."):
            job = ComfyUIJob.get_running(c3)
        if not job:
            error("No running ComfyUI job found. Use --instance to specify one.")
            raise typer.Exit(1)

    # Set LB/auth mode - applies regardless of how we got the job
    job.use_lb = lb is not None
    job.use_auth = auth

    console.print(f"Job: [cyan]{job.job_id}[/cyan]")
    console.print(f"URL: [cyan]{job.base_url}[/cyan]")

    # Check health
    with spinner("Checking ComfyUI..."):
        if not job.check_health():
            error("ComfyUI not responding")
            raise typer.Exit(1)

    success("Connected")

    # Get history - list all prompts
    try:
        import httpx
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{job.base_url}/history", headers=job.auth_headers)
            resp.raise_for_status()
            all_history = resp.json()
    except Exception as e:
        error(f"Failed to get history: {e}")
        raise typer.Exit(1)

    if not all_history:
        console.print("[dim]No outputs found[/dim]")
        return

    console.print(f"\n[bold]Found {len(all_history)} prompt(s)[/bold]\n")

    # Collect all outputs
    all_outputs = []
    for prompt_id, history in all_history.items():
        status = history.get("status", {})
        completed = status.get("completed", False)
        status_str = "completed" if completed else status.get("status_str", "unknown")

        outputs = history.get("outputs", {})
        for node_id, node_output in outputs.items():
            for key in ["images", "gifs", "videos"]:
                if key in node_output:
                    for item in node_output[key]:
                        all_outputs.append({
                            "prompt_id": prompt_id[:8],
                            "status": status_str,
                            "type": key[:-1],  # image, gif, video
                            **item,
                        })

    if not all_outputs:
        console.print("[dim]No output files found[/dim]")
        return

    console.print(f"[bold]Found {len(all_outputs)} output file(s):[/bold]")
    for out in all_outputs:
        subfolder = out.get("subfolder", "")
        path = f"{subfolder}/{out['filename']}" if subfolder else out["filename"]
        console.print(f"  [{out['status']}] {out['type']}: {path}")

    console.print()

    # Download all
    output_path = Path(output_dir)
    for out in all_outputs:
        filename = out["filename"]
        subfolder = out.get("subfolder", "")
        with spinner(f"Downloading {filename}..."):
            try:
                saved = job.download_output(filename, output_path, subfolder)
                console.print(f"  [green]✓[/green] {saved}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {filename}: {e}")

    success("Done!")


@app.command("stop")
def stop():
    """Stop running ComfyUI job"""
    c3 = get_client()

    with spinner("Finding running job..."):
        job = ComfyUIJob.get_running(c3)

    if not job:
        console.print("[dim]No running ComfyUI job[/dim]")
        return

    console.print(f"Stopping job [cyan]{job.job_id}[/cyan]...")

    with spinner("Cancelling..."):
        job.shutdown()

    success("Job stopped")
