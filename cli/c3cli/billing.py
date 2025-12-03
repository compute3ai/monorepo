"""c3 billing commands"""
import typer
from c3 import C3
from .output import output, console, spinner

app = typer.Typer(help="Billing and balance commands")


def get_client() -> C3:
    return C3()


@app.command("balance")
def balance(
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """Get account balance"""
    c3 = get_client()
    with spinner("Fetching balance..."):
        bal = c3.billing.balance()

    if fmt == "table":
        console.print()
        console.print("[bold]Account Balance[/bold]")
        console.print()
        console.print(f"  Balance:   [bold green]${bal.total}[/bold green]")
        console.print(f"  Available: ${bal.available}")
        if bal.rewards != "0.000000" and bal.rewards != "0":
            console.print(f"  [dim](Rewards: ${bal.rewards})[/dim]")
        console.print()
    else:
        output(bal, fmt)


@app.command("transactions")
def transactions(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of transactions"),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List transactions"""
    c3 = get_client()
    with spinner("Fetching transactions..."):
        txs = c3.billing.transactions(limit=limit, page=page)

    if fmt == "json":
        output(txs, fmt)
    else:
        output(txs, "table", ["id", "transaction_type", "amount_usd", "status", "created_at"])


@app.command("invoices")
def invoices(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of invoices"),
    fmt: str = typer.Option("table", "--output", "-o", help="Output format: table|json"),
):
    """List invoices"""
    c3 = get_client()
    # TODO: Add invoices to SDK
    console.print("[dim]Invoices endpoint not yet implemented in SDK[/dim]")
