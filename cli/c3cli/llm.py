"""c3 llm commands - uses OpenAI SDK"""
import typer
from typing import Optional
from openai import OpenAI
from c3.config import get_api_key, get_api_url
from .output import output, console, spinner

app = typer.Typer(help="LLM API commands")


def get_openai_client() -> OpenAI:
    """Get OpenAI client configured for C3"""
    api_key = get_api_key()
    if not api_key:
        raise typer.Exit("C3_API_KEY not set. Run: c3 configure")

    base_url = get_api_url()
    return OpenAI(api_key=api_key, base_url=f"{base_url}/v1")


@app.command("models")
def models(
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List available models"""
    client = get_openai_client()
    with spinner("Fetching models..."):
        models_list = list(client.models.list())

    if fmt == "json":
        output([{"id": m.id, "owned_by": m.owned_by} for m in models_list], "json")
    else:
        data = [{"id": m.id, "owned_by": m.owned_by} for m in models_list]
        output(data, "table", ["id", "owned_by"])


@app.command("chat")
def chat(
    model: Optional[str] = typer.Argument(None, help="Model name (optional for interactive)"),
    prompt: Optional[str] = typer.Argument(None, help="Prompt (omit for interactive)"),
    system: Optional[str] = typer.Option(None, "--system", "-s", help="System message"),
    max_tokens: int = typer.Option(4096, "--max-tokens", "-m", help="Max tokens"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", help="Temperature"),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
    fmt: str = typer.Option("text", "--output", "-o", help="Output format: text|json"),
):
    """Chat completion"""
    client = get_openai_client()

    # Interactive mode if -i flag or no model provided
    if interactive or model is None:
        _interactive_chat(client, model, system, max_tokens, temperature)
        return

    if prompt is None:
        _interactive_chat(client, model, system, max_tokens, temperature)
        return

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if no_stream or fmt == "json":
        with spinner("Generating response..."):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        if fmt == "json":
            output(response.model_dump(), "json")
        else:
            console.print(response.choices[0].message.content)
    else:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                console.print(content, end="")
        console.print()


def _interactive_chat(client: OpenAI, model: Optional[str], system: Optional[str], max_tokens: int, temperature: float):
    """Interactive chat mode with slash commands"""
    from rich.table import Table

    # Default model if none provided
    current_model = model or "meta-llama/llama-3.3-70b-instruct"
    current_system = system
    current_temp = temperature
    current_max_tokens = max_tokens
    messages: list[dict] = []

    if current_system:
        messages.append({"role": "system", "content": current_system})

    def show_help():
        console.print("\n[bold cyan]Commands:[/bold cyan]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Command", style="green")
        table.add_column("Description")
        table.add_row("/model <name>", "Switch to a different model")
        table.add_row("/models", "List available models")
        table.add_row("/system <prompt>", "Set system prompt")
        table.add_row("/temp <value>", "Set temperature (0.0-2.0)")
        table.add_row("/tokens <value>", "Set max tokens")
        table.add_row("/clear", "Clear conversation history")
        table.add_row("/history", "Show conversation history")
        table.add_row("/help", "Show this help")
        table.add_row("/quit", "Exit chat")
        console.print(table)
        console.print()

    def show_status():
        console.print(f"[dim]Model: [green]{current_model}[/] | Temp: {current_temp} | Max tokens: {current_max_tokens}[/]")
        if current_system:
            sys_preview = current_system[:50] + "..." if len(current_system) > 50 else current_system
            console.print(f"[dim]System: {sys_preview}[/]")

    console.print("\n[bold cyan]C3 Chat[/bold cyan]")
    show_status()
    console.print("[dim]Type /help for commands, /quit to exit[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold blue]> [/bold blue]").strip()

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                parts = user_input[1:].split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else None

                if cmd in ("quit", "exit", "q"):
                    console.print("[dim]Goodbye![/dim]")
                    break

                elif cmd == "help":
                    show_help()

                elif cmd == "models":
                    with spinner("Fetching models..."):
                        models_list = list(client.models.list())
                    console.print("\n[bold]Available models:[/bold]")
                    for m in models_list:
                        marker = "[green]●[/]" if m.id == current_model else "[dim]○[/]"
                        console.print(f"  {marker} {m.id}")
                    console.print()

                elif cmd == "model":
                    if not arg:
                        console.print(f"[dim]Current model: [green]{current_model}[/][/]")
                    else:
                        current_model = arg
                        console.print(f"[green]✓[/] Switched to model: [bold]{current_model}[/]")

                elif cmd == "system":
                    if not arg:
                        if current_system:
                            console.print(f"[dim]System prompt: {current_system}[/]")
                        else:
                            console.print("[dim]No system prompt set[/]")
                    else:
                        current_system = arg
                        # Update or add system message
                        if messages and messages[0]["role"] == "system":
                            messages[0]["content"] = current_system
                        else:
                            messages.insert(0, {"role": "system", "content": current_system})
                        console.print(f"[green]✓[/] System prompt updated")

                elif cmd == "temp":
                    if not arg:
                        console.print(f"[dim]Temperature: {current_temp}[/]")
                    else:
                        try:
                            current_temp = float(arg)
                            console.print(f"[green]✓[/] Temperature set to {current_temp}")
                        except ValueError:
                            console.print("[red]Invalid temperature value[/]")

                elif cmd == "tokens":
                    if not arg:
                        console.print(f"[dim]Max tokens: {current_max_tokens}[/]")
                    else:
                        try:
                            current_max_tokens = int(arg)
                            console.print(f"[green]✓[/] Max tokens set to {current_max_tokens}")
                        except ValueError:
                            console.print("[red]Invalid token value[/]")

                elif cmd == "clear":
                    messages.clear()
                    if current_system:
                        messages.append({"role": "system", "content": current_system})
                    console.print("[green]✓[/] Conversation cleared")

                elif cmd == "history":
                    if not messages or (len(messages) == 1 and messages[0]["role"] == "system"):
                        console.print("[dim]No conversation history[/]")
                    else:
                        console.print("\n[bold]Conversation history:[/bold]")
                        for msg in messages:
                            if msg["role"] == "system":
                                console.print(f"[dim]System: {msg['content'][:100]}...[/]")
                            elif msg["role"] == "user":
                                console.print(f"[blue]You:[/] {msg['content'][:100]}...")
                            else:
                                console.print(f"[green]Assistant:[/] {msg['content'][:100]}...")
                        console.print()

                else:
                    console.print(f"[red]Unknown command: /{cmd}[/] - type /help for commands")

                continue

            # Regular message - send to model
            messages.append({"role": "user", "content": user_input})

            console.print("[bold green]Assistant:[/bold green] ", end="")

            try:
                full_response = []
                stream = client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                    max_tokens=current_max_tokens,
                    temperature=current_temp,
                    stream=True,
                )

                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        console.print(content, end="")
                        full_response.append(content)

                console.print("\n")
                messages.append({"role": "assistant", "content": "".join(full_response)})

            except Exception as e:
                console.print(f"\n[red]Error: {e}[/]\n")
                # Remove the failed user message
                messages.pop()

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break
