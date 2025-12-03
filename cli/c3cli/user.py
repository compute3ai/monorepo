"""c3 user commands"""
import typer
from c3 import C3
from .output import output, spinner

app = typer.Typer(help="User account commands")


@app.callback(invoke_without_command=True)
def user_info(
    ctx: typer.Context,
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Get current user info"""
    if ctx.invoked_subcommand is None:
        c3 = C3()
        with spinner("Fetching user info..."):
            user = c3.user.get()
        output(user, fmt)
