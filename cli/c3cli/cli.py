"""C3 CLI - Main entry point"""
import sys
import typer
from rich.console import Console
from rich.prompt import Prompt

from c3 import C3, APIError, configure
from c3.config import CONFIG_FILE

from . import billing, comfyui, instances, jobs, llm, renders, user

console = Console()


def fuzzy_match(input_str: str, options: list[str], threshold: float = 0.5) -> list[str]:
    """Find similar strings using multiple heuristics"""
    def similarity(a: str, b: str) -> float:
        a, b = a.lower(), b.lower()
        if a == b:
            return 1.0

        # Exact substring match
        if a in b or b in a:
            return 0.9

        # Same characters (handles transpositions like rtx6000pro vs rtxpro6000)
        if sorted(a) == sorted(b):
            return 0.95

        # Character set overlap
        set_a, set_b = set(a), set(b)
        common = set_a & set_b
        jaccard = len(common) / len(set_a | set_b) if set_a | set_b else 0

        # Prefix match bonus
        prefix_len = 0
        for ca, cb in zip(a, b):
            if ca == cb:
                prefix_len += 1
            else:
                break
        prefix_bonus = prefix_len / max(len(a), len(b)) * 0.3

        return jaccard + prefix_bonus

    matches = [(opt, similarity(input_str, opt)) for opt in options]
    matches = [(opt, score) for opt, score in matches if score >= threshold]
    matches.sort(key=lambda x: x[1], reverse=True)
    return [opt for opt, _ in matches[:3]]

app = typer.Typer(
    name="c3",
    help="Compute3 CLI - GPU orchestration and LLM API",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register subcommands
app.add_typer(billing.app, name="billing")
app.add_typer(comfyui.app, name="comfyui")
app.add_typer(instances.app, name="instances")
app.add_typer(jobs.app, name="jobs")
app.add_typer(llm.app, name="llm")
app.add_typer(renders.app, name="renders")
app.add_typer(user.app, name="user")


@app.command("configure")
def configure_cmd():
    """Configure C3 CLI with your API key and API URL"""
    import getpass
    from c3.config import get_api_key, get_api_url, DEFAULT_API_URL

    console.print("\n[bold cyan]C3 CLI Configuration[/bold cyan]\n")

    # Show current config
    current_key = get_api_key()
    current_url = get_api_url()

    if current_key:
        key_preview = current_key[:4] + "..." + current_key[-4:] if len(current_key) > 8 else "****"
        console.print(f"Current API key: [dim]{key_preview}[/dim]")
    if current_url and current_url != DEFAULT_API_URL:
        console.print(f"Current API URL: [dim]{current_url}[/dim]")

    console.print()
    console.print("Get your API key at [link=https://compute3.ai/dashboard]compute3.ai/dashboard[/link]\n")

    # API Key
    api_key = getpass.getpass("API key (enter to keep current): ") if current_key else getpass.getpass("API key: ")
    api_key = api_key.strip() if api_key else None

    if not api_key and not current_key:
        console.print("[red]No API key provided[/red]")
        raise typer.Exit(1)

    # API URL
    url_prompt = f"API URL (enter for default, current: {current_url}): " if current_url != DEFAULT_API_URL else "API URL (enter for default): "
    api_url = Prompt.ask(url_prompt, default="")
    api_url = api_url.strip() if api_url else None

    # Only update what changed
    final_key = api_key or current_key
    final_url = api_url if api_url else (current_url if current_url != DEFAULT_API_URL else None)

    configure(final_key, final_url)

    console.print(f"\n[green]✓[/green] Config saved to {CONFIG_FILE}")
    if api_key:
        preview = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "****"
        console.print(f"  API key: {preview}")
    if final_url:
        console.print(f"  API URL: {final_url}")
    console.print("\nTest your setup with: [cyan]c3 billing balance[/cyan]\n")


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """
    [bold cyan]C3 CLI[/bold cyan] - Compute3 GPU orchestration and LLM API

    Set your API key: [green]c3 configure[/green]

    Get started:
        c3 instances list      Browse available GPUs
        c3 instances launch    Launch a GPU instance
        c3 jobs list           View your running jobs
        c3 llm chat -i         Start a chat
    """
    if version:
        from . import __version__
        console.print(f"c3 version {__version__}")
        raise typer.Exit()


def cli():
    """Entry point with error handling"""
    try:
        app()
    except APIError as e:
        detail = e.detail or str(e)

        # Check for GPU type errors and suggest corrections
        if "GPU type" in detail and "not found" in detail and "Available:" in detail:
            # Extract the invalid GPU type and available options
            import re
            match = re.search(r"GPU type '([^']+)' not found\. Available: \[([^\]]+)\]", detail)
            if match:
                invalid_type = match.group(1)
                available_str = match.group(2)
                available = [s.strip().strip("'") for s in available_str.split(",")]

                console.print(f"[bold red]Error:[/bold red] Unknown GPU type '[yellow]{invalid_type}[/yellow]'")

                # Find similar GPU types
                suggestions = fuzzy_match(invalid_type, available)
                if suggestions:
                    console.print(f"\n[dim]Did you mean:[/dim]")
                    for s in suggestions:
                        console.print(f"  [green]{s}[/green]")

                console.print(f"\n[dim]Available GPU types:[/dim] {', '.join(available)}")
                sys.exit(1)

        # Check for region errors
        if "region" in detail.lower() and "not found" in detail.lower():
            console.print(f"[bold red]Error:[/bold red] {detail}")
            console.print("\n[dim]Tip: Use 'c3 jobs regions' to see available regions[/dim]")
            sys.exit(1)

        # Generic API error
        console.print(f"[bold red]API Error ({e.status_code}):[/bold red] {detail}")
        sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
        sys.exit(130)


if __name__ == "__main__":
    cli()
