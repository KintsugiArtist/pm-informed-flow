"""CLI interface for PM Trace"""

import asyncio
import re
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .config import get_polygonscan_api_key, save_api_key
from .tracer import trace_account, TraceResult


console = Console()


def extract_address(input_str: str) -> str:
    """Extract Ethereum address from input (URL or raw address)."""
    # Match 0x followed by 40 hex characters
    match = re.search(r'0x[a-fA-F0-9]{40}', input_str)
    if match:
        return match.group(0).lower()
    raise ValueError(f"Could not extract valid address from: {input_str}")


def generate_links(address: str) -> dict[str, str]:
    """Generate useful links for an address."""
    return {
        "Polymarket": f"https://polymarket.com/profile/{address}",
        "Arkham": f"https://platform.arkhamintelligence.com/explorer/address/{address}",
        "Polygonscan": f"https://polygonscan.com/address/{address}",
    }


def generate_relay_link(tx_hash: str) -> str:
    """Generate Relay.link URL to decode a bridge transaction."""
    return f"https://relay.link/transaction/{tx_hash}"


def format_address(address: str) -> str:
    """Format address as shortened version."""
    return f"{address[:8]}...{address[-6:]}"


def print_result(result: TraceResult) -> None:
    """Print the trace result with rich formatting."""
    
    # Header
    status = "✅ Polymarket Account" if result.is_polymarket else "❌ Not a Polymarket Account"
    title = f"[bold cyan]PM Trace Report[/bold cyan] - {status}"
    
    console.print()
    console.print(Panel(title, box=box.DOUBLE))
    console.print()
    
    # Address info
    console.print(f"[bold]Address:[/bold] {result.address}")
    if result.profile:
        username = result.profile.get("username") or result.profile.get("name")
        if username:
            console.print(f"[bold]Username:[/bold] {username}")
    console.print()
    
    # Quick links
    links = generate_links(result.address)
    console.print("[dim]Quick Links:[/dim]")
    for name, url in links.items():
        console.print(f"  • {name}: {url}")
    console.print()
    
    # Classification
    console.print(Panel(
        f"[bold]{result.classification}[/bold]",
        title="Classification",
        box=box.ROUNDED
    ))
    console.print()
    
    # Signals
    if result.signals:
        console.print("[bold]Signals:[/bold]")
        for signal in result.signals:
            console.print(f"  {signal}")
        console.print()
    
    # Funding Summary
    if result.funding_sources:
        console.print(f"[bold]Funding Summary:[/bold] ${result.total_funded:,.2f} total")
        if result.first_funding_date:
            console.print(f"[dim]First funded: {result.first_funding_date.strftime('%Y-%m-%d')}[/dim]")
        console.print()
        
        # Funding Sources Table
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Source", style="cyan")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Txs", justify="right")
        table.add_column("First Date")
        
        # Sort by amount descending
        sorted_sources = sorted(result.funding_sources, key=lambda x: x.total_amount, reverse=True)
        
        for source in sorted_sources:
            source_type = source.label if source.label else ("🌉 Relay" if source.is_relay else "Wallet")
            first_date = source.first_tx_date.strftime("%Y-%m-%d") if source.first_tx_date else "-"
            
            table.add_row(
                format_address(source.address),
                f"${source.total_amount:,.2f}",
                source_type,
                str(len(source.transfers)),
                first_date
            )
        
        console.print(table)
        console.print()
        
        # Relay transaction decode links
        relay_txs = [
            t for source in result.funding_sources 
            for t in source.transfers 
            if source.is_relay
        ]
        if relay_txs:
            console.print("[bold yellow]🌉 Relay Transactions (decode to find original sender):[/bold yellow]")
            for tx in relay_txs[:5]:  # Limit to 5
                link = generate_relay_link(tx.tx_hash)
                console.print(f"  • {tx.value_formatted} on {tx.timestamp.strftime('%Y-%m-%d')}")
                console.print(f"    [dim]{link}[/dim]")
            if len(relay_txs) > 5:
                console.print(f"  [dim]... and {len(relay_txs) - 5} more[/dim]")
            console.print()
    
    # Sibling Accounts
    pm_siblings = [s for s in result.all_siblings if s.is_polymarket]
    if pm_siblings:
        console.print(f"[bold red]🔗 Connected Polymarket Accounts ({len(pm_siblings)} found):[/bold red]")
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Address", style="cyan")
        table.add_column("Funded", justify="right", style="green")
        table.add_column("Polymarket Link")
        
        # Sort by funding amount
        sorted_siblings = sorted(pm_siblings, key=lambda x: x.total_funded, reverse=True)
        
        for sibling in sorted_siblings[:10]:  # Limit to 10
            pm_link = f"https://polymarket.com/profile/{sibling.address}"
            
            table.add_row(
                format_address(sibling.address),
                f"${sibling.total_funded:,.2f}",
                pm_link
            )
        
        console.print(table)
        
        if len(pm_siblings) > 10:
            console.print(f"  [dim]... and {len(pm_siblings) - 10} more[/dim]")
        console.print()
    
    # Trading behavior
    if result.trading:
        console.print("[bold]Trading Activity:[/bold]")
        console.print(f"  Total Trades: {result.trading.total_trades}")
        console.print(f"  Markets Traded: {result.trading.markets_traded}")
        if result.trading.account_age_days is not None:
            console.print(f"  Account Age: {result.trading.account_age_days} days")
        if result.trading.first_trade_date:
            console.print(f"  First Trade: {result.trading.first_trade_date.strftime('%Y-%m-%d')}")
        if result.trading.last_trade_date:
            console.print(f"  Last Trade: {result.trading.last_trade_date.strftime('%Y-%m-%d')}")
        console.print()
    
    # Next steps
    console.print(Panel(
        "[dim]Next Steps:\n"
        "1. Check funding sources on Arkham for labels (CEX, Fund, etc.)\n"
        "2. Decode Relay transactions to find original sender\n"
        "3. Check sibling accounts for coordinated trading patterns[/dim]",
        title="Investigation Tips",
        box=box.ROUNDED
    ))


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """PM Trace - Polymarket Account Forensics Tool
    
    Track funding sources and identify coordinated accounts.
    """
    pass


@cli.command()
@click.argument("address_or_url")
@click.option("--deep/--shallow", default=True, help="Deep trace to find sibling accounts")
@click.option("--max-siblings", default=20, help="Max sibling addresses to check (for speed)")
@click.option("--api-key", envvar="POLYGONSCAN_API_KEY", help="Etherscan V2 API key")
def analyze(address_or_url: str, deep: bool, max_siblings: int, api_key: str):
    """Analyze a Polymarket account.
    
    ADDRESS_OR_URL can be a wallet address or a Polymarket profile URL.
    
    Examples:
    
        pm-trace analyze 0x1234...
        
        pm-trace analyze https://polymarket.com/profile/0x1234...
        
        pm-trace analyze 0x1234... --shallow  # Skip sibling detection (faster)
    """
    # Get API key
    if not api_key:
        api_key = get_polygonscan_api_key()
    
    if not api_key:
        console.print("[red]Error:[/red] No API key found.")
        console.print()
        console.print("Get a free API key from: https://polygonscan.com/apis")
        console.print("(Works with Etherscan V2 API for Polygon)")
        console.print()
        console.print("Then either:")
        console.print("  1. Run: pm-trace config --api-key YOUR_KEY")
        console.print("  2. Set env: export POLYGONSCAN_API_KEY=YOUR_KEY")
        console.print("  3. Pass directly: pm-trace analyze ADDRESS --api-key YOUR_KEY")
        return
    
    # Extract address
    try:
        address = extract_address(address_or_url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        return
    
    console.print(f"[dim]Analyzing {format_address(address)}...[/dim]")
    console.print(f"[dim]Mode: {'Deep trace (checking siblings)' if deep else 'Shallow (funding only)'}[/dim]")
    
    # Run trace
    with console.status("[bold green]Fetching data from Polygon & Polymarket..."):
        result = asyncio.run(trace_account(
            api_key, 
            address, 
            deep=deep,
            max_siblings_to_check=max_siblings
        ))
    
    # Print results
    print_result(result)


@cli.command()
@click.option("--api-key", prompt="Etherscan V2 API Key", help="Your Etherscan V2 API key (works for Polygon)")
def config(api_key: str):
    """Configure PM Trace with your API key.
    
    Get a free key from https://polygonscan.com/apis
    """
    save_api_key(api_key)
    console.print("[green]✓[/green] API key saved to ~/.pm_trace/.env")


@cli.command()
@click.argument("address")
def links(address: str):
    """Generate investigation links for an address."""
    try:
        address = extract_address(address)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        return
    
    console.print()
    console.print(f"[bold]Links for {format_address(address)}[/bold]")
    console.print()
    
    all_links = {
        "Polymarket Profile": f"https://polymarket.com/profile/{address}",
        "Arkham Intelligence": f"https://platform.arkhamintelligence.com/explorer/address/{address}",
        "Polygonscan": f"https://polygonscan.com/address/{address}",
        "Relay.link Search": f"https://relay.link/transactions?search={address}",
    }
    
    for name, url in all_links.items():
        console.print(f"  {name}:")
        console.print(f"    {url}")
    console.print()


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
