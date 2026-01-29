"""CLI interface for PM Trace"""

import asyncio
import json
import re
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich import box

from .config import get_polygonscan_api_key, save_api_key
from .tracer import trace_account, TraceResult, export_to_dict
from .relay import generate_relay_link, generate_origin_address_link


console = Console()


# ============================================================================
# Helper Functions
# ============================================================================

def extract_address(input_str: str) -> str:
    """Extract Ethereum address from input (URL or raw address)."""
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


def format_address(address: str, length: int = 14) -> str:
    """Format address as shortened version."""
    if len(address) <= length:
        return address
    half = (length - 3) // 2
    return f"{address[:half+2]}...{address[-half:]}"


def format_pnl(value: float) -> str:
    """Format P&L with color indicator."""
    if value > 0:
        return f"[green]+${value:,.2f}[/green]"
    elif value < 0:
        return f"[red]-${abs(value):,.2f}[/red]"
    return f"${value:,.2f}"


# ============================================================================
# Report Printing
# ============================================================================

def print_result(result: TraceResult) -> None:
    """Print the comprehensive trace result with rich formatting."""
    
    # ========================================================================
    # Header
    # ========================================================================
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
    
    # ========================================================================
    # Classification
    # ========================================================================
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
    
    # ========================================================================
    # Portfolio Summary (if available)
    # ========================================================================
    if result.portfolio and result.is_polymarket:
        console.print(Panel("[bold]Portfolio Summary[/bold]", box=box.SIMPLE))
        
        port = result.portfolio
        
        # Portfolio stats table
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")
        
        table.add_row(
            "Portfolio Value", f"${port.total_value:,.2f}",
            "Positions", str(port.positions_count)
        )
        table.add_row(
            "Unrealized P&L", format_pnl(port.unrealized_pnl),
            "Realized P&L", format_pnl(port.realized_pnl)
        )
        table.add_row(
            "Win Rate", f"{port.win_rate:.1f}%",
            "Total Trades", str(port.total_trades)
        )
        table.add_row(
            "Markets Traded", str(port.markets_traded),
            "Volume", f"${port.volume_traded:,.0f}"
        )
        
        console.print(table)
        console.print()
    
    # ========================================================================
    # Current Positions
    # ========================================================================
    if result.positions:
        console.print(Panel(f"[bold]Current Positions ({len(result.positions)})[/bold]", box=box.SIMPLE))
        
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Market", max_width=40)
        table.add_column("Side", justify="center")
        table.add_column("Size", justify="right")
        table.add_column("Avg Price", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Value", justify="right", style="cyan")
        table.add_column("P&L", justify="right")
        
        # Sort by value descending
        sorted_positions = sorted(result.positions, key=lambda x: x.value, reverse=True)
        
        for pos in sorted_positions[:15]:  # Limit to 15
            question = pos.market_question[:38] + "..." if len(pos.market_question) > 40 else pos.market_question
            side_color = "green" if pos.outcome.lower() == "yes" else "red"
            
            table.add_row(
                question or "[dim]Unknown Market[/dim]",
                f"[{side_color}]{pos.outcome}[/{side_color}]",
                f"{pos.size:,.0f}",
                f"${pos.avg_price:.2f}",
                f"${pos.current_price:.2f}",
                f"${pos.value:,.2f}",
                format_pnl(pos.unrealized_pnl)
            )
        
        console.print(table)
        
        if len(result.positions) > 15:
            console.print(f"  [dim]... and {len(result.positions) - 15} more positions[/dim]")
        console.print()
    
    # ========================================================================
    # Funding Analysis
    # ========================================================================
    if result.funding_sources:
        console.print(Panel("[bold]Funding Analysis[/bold]", box=box.SIMPLE))
        
        console.print(f"[bold]Total Funded:[/bold] ${result.total_funded:,.2f}")
        if result.first_funding_date:
            console.print(f"[dim]First funded: {result.first_funding_date.strftime('%Y-%m-%d')}[/dim]")
        console.print()
        
        # Funding Sources Table
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Source", style="cyan")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Label")
        table.add_column("Txs", justify="right")
        table.add_column("First Date")
        
        sorted_sources = sorted(result.funding_sources, key=lambda x: x.total_amount, reverse=True)
        
        for source in sorted_sources:
            # Determine type display
            if source.label:
                type_display = source.label
            elif source.is_relay:
                type_display = "🌉 Relay Bridge"
            elif source.source_type == "cex":
                type_display = "🏦 CEX"
            elif source.source_type == "bridge":
                type_display = "🌉 Bridge"
            elif source.source_type == "dex":
                type_display = "🔄 DEX"
            else:
                type_display = "💼 Wallet"
            
            first_date = source.first_tx_date.strftime("%Y-%m-%d") if source.first_tx_date else "-"
            
            table.add_row(
                format_address(source.address),
                f"${source.total_amount:,.2f}",
                type_display,
                source.label or "-",
                str(len(source.transfers)),
                first_date
            )
        
        console.print(table)
        console.print()
        
        # ====================================================================
        # Relay Transaction Decoding
        # ====================================================================
        relay_sources = [s for s in result.funding_sources if s.is_relay]
        if relay_sources:
            console.print("[bold yellow]🌉 Cross-Chain Funding (Relay Bridge):[/bold yellow]")
            
            for source in relay_sources:
                decoded_origins = [o for o in source.relay_origins if o and o.origin_chain_id > 0]
                
                if decoded_origins:
                    for origin in decoded_origins:
                        # Use the transfer amount if decoded amount is 0
                        display_amount = origin.amount if origin.amount > 0 else 0
                        console.print(f"  • ${display_amount:,.2f} from [cyan]{origin.origin_chain_name}[/cyan]")
                        console.print(f"    Origin: {origin.origin_address}")
                        arkham_link = f"https://platform.arkhamintelligence.com/explorer/address/{origin.origin_address}"
                        console.print(f"    [dim]Arkham: {arkham_link}[/dim]")
                else:
                    # Provide manual decode links when decoding failed
                    console.print("  [dim]Could not auto-decode origin. Use links below to decode manually:[/dim]")
                    for tx in source.transfers[:5]:
                        link = generate_relay_link(tx.tx_hash)
                        console.print(f"  • {tx.value_formatted} on {tx.timestamp.strftime('%Y-%m-%d')}")
                        console.print(f"    [dim]{link}[/dim]")
            
            console.print()
    
    # ========================================================================
    # Origin Tracing
    # ========================================================================
    if result.origin_chains:
        console.print(Panel("[bold]Origin Tracing[/bold]", box=box.SIMPLE))
        
        for i, chain in enumerate(result.origin_chains[:5]):
            if chain.origin:
                origin = chain.origin
                
                # Build a visual chain
                tree = Tree(f"[bold cyan]Chain {i+1}[/bold cyan] ({chain.depth} hops)")
                
                current = tree
                for hop in chain.hops:
                    label = hop.from_label or format_address(hop.from_address)
                    type_icon = {
                        "cex": "🏦",
                        "bridge": "🌉",
                        "dex": "🔄",
                        "entity": "🏢",
                    }.get(hop.from_type, "💼")
                    
                    node_text = f"{type_icon} {label} → ${hop.amount:,.0f}"
                    current = current.add(node_text)
                
                # Add final destination
                current.add(f"🎯 Target: {format_address(result.address)}")
                
                console.print(tree)
        
        console.print()
    
    # ========================================================================
    # Sibling Accounts (funded by same sources)
    # ========================================================================
    pm_siblings = [s for s in result.all_siblings if s.is_polymarket]
    if pm_siblings:
        console.print(Panel(
            f"[bold red]🔗 Linked Accounts (Same Funder) - {len(pm_siblings)} found[/bold red]",
            box=box.SIMPLE
        ))
        
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Address", style="cyan", no_wrap=True)
        table.add_column("Funded", justify="right", style="green")
        table.add_column("Shared Funder(s)", style="yellow")
        
        sorted_siblings = sorted(pm_siblings, key=lambda x: x.total_funded, reverse=True)
        
        for sibling in sorted_siblings[:10]:
            # Show which funder(s) this sibling shares with target
            shared_display = ", ".join(format_address(f) for f in sibling.shared_funders[:2])
            if len(sibling.shared_funders) > 2:
                shared_display += f" +{len(sibling.shared_funders) - 2}"
            
            table.add_row(
                sibling.address,
                f"${sibling.total_funded:,.2f}",
                shared_display or "-",
            )
        
        console.print(table)
        
        # Print links separately for easy copying
        console.print()
        console.print("[dim]Polymarket Links:[/dim]")
        for sibling in sorted_siblings[:10]:
            console.print(f"  [link=https://polymarket.com/profile/{sibling.address}]https://polymarket.com/profile/{sibling.address}[/link]")
        
        if len(pm_siblings) > 10:
            console.print(f"  [dim]... and {len(pm_siblings) - 10} more[/dim]")
        console.print()
    
    # ========================================================================
    # Outbound Funding (accounts this address has funded)
    # ========================================================================
    if result.funded_pm_accounts:
        console.print(Panel(
            f"[bold magenta]📤 Accounts Funded By This Wallet - {len(result.funded_pm_accounts)} PM accounts[/bold magenta]",
            box=box.SIMPLE
        ))
        
        console.print(f"[bold]Total Sent to Others:[/bold] ${result.total_sent_to_others:,.2f}")
        console.print()
        
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Recipient Address", style="cyan", no_wrap=True)
        table.add_column("Amount Sent", justify="right", style="green")
        table.add_column("First Transfer")
        
        sorted_funded = sorted(result.funded_pm_accounts, key=lambda x: x.total_sent, reverse=True)
        
        for funded in sorted_funded[:10]:
            first_date = funded.first_tx_date.strftime("%Y-%m-%d") if funded.first_tx_date else "-"
            
            table.add_row(
                funded.address,  # Show full address
                f"${funded.total_sent:,.2f}",
                first_date,
            )
        
        console.print(table)
        
        # Print links separately for easy copying
        console.print()
        console.print("[dim]Polymarket Links:[/dim]")
        for funded in sorted_funded[:10]:
            console.print(f"  [link=https://polymarket.com/profile/{funded.address}]https://polymarket.com/profile/{funded.address}[/link]")
        
        if len(result.funded_pm_accounts) > 10:
            console.print(f"  [dim]... and {len(result.funded_pm_accounts) - 10} more[/dim]")
        console.print()
    
    # ========================================================================
    # Trading Activity
    # ========================================================================
    if result.trading:
        console.print(Panel("[bold]Trading Activity[/bold]", box=box.SIMPLE))
        
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")
        
        table.add_row(
            "Total Trades", str(result.trading.total_trades),
            "Markets Traded", str(result.trading.markets_traded)
        )
        
        age_str = f"{result.trading.account_age_days} days" if result.trading.account_age_days else "-"
        first_trade = result.trading.first_trade_date.strftime('%Y-%m-%d') if result.trading.first_trade_date else "-"
        last_trade = result.trading.last_trade_date.strftime('%Y-%m-%d') if result.trading.last_trade_date else "-"
        
        table.add_row(
            "Account Age", age_str,
            "First Trade", first_trade
        )
        table.add_row(
            "Last Trade", last_trade,
            "", ""
        )
        
        console.print(table)
        console.print()
    
    # ========================================================================
    # Investigation Tips
    # ========================================================================
    tips = []
    
    if result.has_relay_funding:
        tips.append("Decode Relay transactions to find original sender on source chain")
    
    if result.sibling_count > 0:
        tips.append("Check sibling accounts for coordinated trading patterns")
    
    if result.funded_pm_count > 0:
        tips.append("Investigate funded PM accounts for sybil behavior")
    
    if not result.has_cex_origin and result.total_funded > 10000:
        tips.append("Trace funding origins on Arkham Intelligence for entity labels")
    
    if result.trading and result.trading.markets_traded <= 2:
        tips.append("Check which specific markets they're concentrated in")
    
    if tips:
        tips_text = "\n".join(f"{i+1}. {tip}" for i, tip in enumerate(tips))
        console.print(Panel(
            f"[dim]{tips_text}[/dim]",
            title="Investigation Tips",
            box=box.ROUNDED
        ))
    
    console.print()


# ============================================================================
# CLI Commands
# ============================================================================

@click.group()
@click.version_option(version="0.2.0")
def cli():
    """PM Trace - Polymarket Account Forensics Tool
    
    Comprehensive analysis of Polymarket accounts including:
    
    • Funding source analysis and origin tracing
    • Cross-chain bridge decoding (Relay.link)
    • Sibling account detection
    • Outbound funding analysis
    • Portfolio and position tracking
    • Source classification (CEX/DEX/Bridge)
    """
    pass


@cli.command()
@click.argument("address_or_url")
@click.option("--deep/--shallow", default=True, help="Deep trace to find sibling accounts")
@click.option("--max-siblings", default=20, help="Max sibling addresses to check")
@click.option("--trace-origin/--no-origin", default=True, help="Trace back to find funding origins")
@click.option("--max-hops", default=3, help="Max hops for origin tracing")
@click.option("--check-outbound/--no-outbound", default=True, help="Check who this account funded")
@click.option("--positions/--no-positions", default=True, help="Include current positions")
@click.option("--json-output", is_flag=True, help="Output as JSON")
@click.option("--api-key", envvar="POLYGONSCAN_API_KEY", help="Etherscan V2 API key")
def analyze(
    address_or_url: str, 
    deep: bool, 
    max_siblings: int,
    trace_origin: bool,
    max_hops: int,
    check_outbound: bool,
    positions: bool,
    json_output: bool,
    api_key: str
):
    """Analyze a Polymarket account comprehensively.
    
    ADDRESS_OR_URL can be a wallet address or a Polymarket profile URL.
    
    \b
    Examples:
        pm-trace analyze 0x1234...
        pm-trace analyze https://polymarket.com/profile/0x1234...
        pm-trace analyze 0x1234... --shallow  # Skip sibling detection
        pm-trace analyze 0x1234... --no-origin  # Skip origin tracing
        pm-trace analyze 0x1234... --json-output  # Get JSON output
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
    
    if not json_output:
        console.print(f"[dim]Analyzing {format_address(address)}...[/dim]")
        mode_parts = []
        if deep:
            mode_parts.append("siblings")
        if trace_origin:
            mode_parts.append("origin tracing")
        if check_outbound:
            mode_parts.append("outbound")
        if positions:
            mode_parts.append("positions")
        console.print(f"[dim]Features: {', '.join(mode_parts)}[/dim]")
    
    # Run trace
    with console.status("[bold green]Fetching data from Polygon, Polymarket & Relay...") if not json_output else nullcontext():
        result = asyncio.run(trace_account(
            api_key, 
            address, 
            deep=deep,
            max_siblings_to_check=max_siblings,
            trace_origin=trace_origin,
            max_origin_hops=max_hops,
            check_outbound=check_outbound,
            include_positions=positions,
        ))
    
    # Output
    if json_output:
        print(json.dumps(export_to_dict(result), indent=2, default=str))
    else:
        print_result(result)


@cli.command()
@click.option("--api-key", prompt="Etherscan V2 API Key", help="Your Etherscan V2 API key")
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
    console.print(f"[bold]Investigation Links for {format_address(address)}[/bold]")
    console.print()
    
    all_links = {
        "Polymarket Profile": f"https://polymarket.com/profile/{address}",
        "Arkham Intelligence": f"https://platform.arkhamintelligence.com/explorer/address/{address}",
        "Polygonscan": f"https://polygonscan.com/address/{address}",
        "Relay.link Search": f"https://relay.link/transactions?search={address}",
        "Etherscan (if bridged from ETH)": f"https://etherscan.io/address/{address}",
        "Arbiscan (if bridged from Arb)": f"https://arbiscan.io/address/{address}",
        "Basescan (if bridged from Base)": f"https://basescan.org/address/{address}",
    }
    
    for name, url in all_links.items():
        console.print(f"  {name}:")
        console.print(f"    [cyan]{url}[/cyan]")
    console.print()


@cli.command()
@click.argument("address_or_url")
@click.option("--api-key", envvar="POLYGONSCAN_API_KEY", help="Etherscan V2 API key")
def quick(address_or_url: str, api_key: str):
    """Quick check - just funding sources and classification.
    
    Faster than full analyze, skips siblings/positions/origin tracing.
    """
    if not api_key:
        api_key = get_polygonscan_api_key()
    
    if not api_key:
        console.print("[red]Error:[/red] No API key. Run: pm-trace config --api-key YOUR_KEY")
        return
    
    try:
        address = extract_address(address_or_url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        return
    
    console.print(f"[dim]Quick check: {format_address(address)}...[/dim]")
    
    with console.status("[bold green]Fetching..."):
        result = asyncio.run(trace_account(
            api_key, 
            address, 
            deep=False,
            trace_origin=False,
            check_outbound=False,
            include_positions=False,
        ))
    
    # Quick summary output
    console.print()
    status = "✅ PM Account" if result.is_polymarket else "❌ Not PM"
    console.print(f"[bold]{status}[/bold] | {result.address}")
    console.print(f"Classification: [bold]{result.classification}[/bold]")
    console.print(f"Total Funded: [green]${result.total_funded:,.2f}[/green] from {len(result.funding_sources)} source(s)")
    
    if result.signals:
        console.print()
        console.print("Signals:")
        for sig in result.signals[:5]:
            console.print(f"  {sig}")
    
    console.print()
    console.print(f"[dim]Run 'pm-trace analyze {address}' for full analysis[/dim]")


# Context manager for non-status mode
class nullcontext:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
