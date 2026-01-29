"""Core tracing logic for Polymarket account forensics"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .blockchain import (
    TokenTransfer,
    WalletInfo,
    FundingChain,
    FundingHop,
    get_funding_sources,
    get_funded_addresses,
    get_unique_recipients,
    get_wallet_info,
    trace_funding_origin,
    get_accounts_funded_by,
)
from .polymarket import (
    is_polymarket_account,
    batch_check_polymarket_accounts,
    get_account_activity,
    get_account_profile,
    get_account_positions,
    get_portfolio_summary,
    close_client,
    Position,
    PortfolioSummary,
)
from .relay import (
    decode_relay_transaction,
    batch_decode_relay_transactions,
    RelayOrigin,
    generate_relay_link,
)
from .config import (
    RELAY_ADDRESSES,
    get_address_label,
    get_address_type,
    is_relay_address,
    is_bridge_address,
    is_cex_address,
    is_protocol_contract,
)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SiblingAccount:
    """A Polymarket account funded by the same source."""
    address: str
    total_funded: float
    is_polymarket: bool
    funding_txs: list[TokenTransfer] = field(default_factory=list)
    shared_funders: list[str] = field(default_factory=list)  # Addresses of shared funders


@dataclass
class FundedAccount:
    """An account that was funded by the target account."""
    address: str
    total_sent: float
    is_polymarket: bool
    transfers: list[TokenTransfer] = field(default_factory=list)
    first_tx_date: Optional[datetime] = None


@dataclass
class FundingSource:
    """A source that funded the target account."""
    address: str
    total_amount: float
    is_relay: bool
    transfers: list[TokenTransfer] = field(default_factory=list)
    label: Optional[str] = None
    source_type: str = "unknown"  # cex, bridge, dex, entity, protocol, wallet
    first_tx_date: Optional[datetime] = None
    
    # Decoded relay origin (if applicable)
    relay_origins: list[RelayOrigin] = field(default_factory=list)
    
    # Siblings funded by this same source
    siblings: list[SiblingAccount] = field(default_factory=list)
    
    # Full funding chain (multi-hop trace)
    funding_chain: Optional[FundingChain] = None
    
    # Wallet info
    wallet_info: Optional[WalletInfo] = None


@dataclass 
class TradingBehavior:
    """Analysis of trading patterns."""
    total_trades: int = 0
    markets_traded: int = 0
    unique_outcomes: int = 0
    first_trade_date: Optional[datetime] = None
    last_trade_date: Optional[datetime] = None
    
    @property
    def account_age_days(self) -> Optional[int]:
        """Days since first trade."""
        if self.first_trade_date:
            return (datetime.now() - self.first_trade_date).days
        return None


@dataclass
class TraceResult:
    """Complete trace result for a Polymarket account."""
    address: str
    is_polymarket: bool
    profile: Optional[dict] = None
    
    # Funding analysis
    funding_sources: list[FundingSource] = field(default_factory=list)
    total_funded: float = 0.0
    first_funding_date: Optional[datetime] = None
    
    # Sibling accounts (other PM accounts from same funders)
    all_siblings: list[SiblingAccount] = field(default_factory=list)
    
    # Accounts this address has funded
    funded_accounts: list[FundedAccount] = field(default_factory=list)
    funded_pm_accounts: list[FundedAccount] = field(default_factory=list)
    total_sent_to_others: float = 0.0
    
    # Trading behavior
    trading: Optional[TradingBehavior] = None
    
    # Portfolio
    portfolio: Optional[PortfolioSummary] = None
    positions: list[Position] = field(default_factory=list)
    
    # Classification signals
    signals: list[str] = field(default_factory=list)
    classification: str = "Unknown"
    
    # Origin tracing
    origin_chains: list[FundingChain] = field(default_factory=list)
    ultimate_origins: list[str] = field(default_factory=list)  # Final origin addresses
    
    @property
    def sibling_count(self) -> int:
        """Number of other PM accounts funded by same source(s)."""
        return len([s for s in self.all_siblings if s.is_polymarket])
    
    @property
    def funded_pm_count(self) -> int:
        """Number of PM accounts this address has funded."""
        return len(self.funded_pm_accounts)
    
    @property
    def has_relay_funding(self) -> bool:
        """Whether any funding came through Relay bridge."""
        return any(f.is_relay for f in self.funding_sources)
    
    @property
    def relay_amount(self) -> float:
        """Total amount funded via Relay."""
        return sum(f.total_amount for f in self.funding_sources if f.is_relay)
    
    @property
    def cex_funding(self) -> float:
        """Total amount from CEX sources."""
        return sum(f.total_amount for f in self.funding_sources if f.source_type == "cex")
    
    @property
    def has_cex_origin(self) -> bool:
        """Whether any origin was traced to a CEX."""
        for chain in self.origin_chains:
            if chain.origin and chain.origin.from_type == "cex":
                return True
        return False


# ============================================================================
# Main Tracing Function
# ============================================================================

async def trace_account(
    api_key: str, 
    address: str, 
    deep: bool = True,
    max_siblings_to_check: int = 20,
    trace_origin: bool = True,
    max_origin_hops: int = 3,
    check_outbound: bool = True,
    include_positions: bool = True,
) -> TraceResult:
    """
    Comprehensive trace of a Polymarket account.
    
    Args:
        api_key: Etherscan V2 API key
        address: The Polymarket account address to trace
        deep: If True, check for sibling accounts
        max_siblings_to_check: Limit on sibling addresses to check
        trace_origin: If True, trace back funding to find origins
        max_origin_hops: Maximum hops for origin tracing
        check_outbound: If True, check what addresses this account funded
        include_positions: If True, fetch current positions
    
    Returns:
        TraceResult with complete analysis
    """
    address = address.lower()
    result = TraceResult(address=address, is_polymarket=False)
    
    try:
        # ====================================================================
        # Step 1: Basic account info (parallel)
        # ====================================================================
        is_pm_task = is_polymarket_account(address)
        profile_task = get_account_profile(address)
        
        result.is_polymarket, result.profile = await asyncio.gather(
            is_pm_task, profile_task
        )
        
        # ====================================================================
        # Step 2: Get funding sources (incoming USDC)
        # ====================================================================
        incoming = get_funding_sources(api_key, address)
        
        if incoming:
            result.first_funding_date = min(t.timestamp for t in incoming)
        
        # Group by sender
        sender_transfers: dict[str, list[TokenTransfer]] = {}
        for transfer in incoming:
            sender = transfer.from_address
            if sender not in sender_transfers:
                sender_transfers[sender] = []
            sender_transfers[sender].append(transfer)
        
        # ====================================================================
        # Step 3: Analyze each funding source
        # ====================================================================
        # Track: recipient -> (total_amount, transfers, [funder_addresses])
        all_potential_siblings: dict[str, tuple[float, list[TokenTransfer], list[str]]] = {}
        relay_tx_hashes: list[str] = []
        
        for sender, transfers in sender_transfers.items():
            total = sum(t.value for t in transfers)
            is_relay = is_relay_address(sender)
            first_tx = min(t.timestamp for t in transfers)
            
            # Get label and type
            label = get_address_label(sender)
            source_type = get_address_type(sender)
            if source_type == "unknown" and is_relay:
                source_type = "bridge"
            
            # Skip protocol contracts as funding sources (they're not real funders)
            # e.g., CTF Exchange sends USDC when users sell shares
            if is_protocol_contract(sender):
                source_type = "protocol"
            
            source = FundingSource(
                address=sender,
                total_amount=total,
                is_relay=is_relay,
                transfers=transfers,
                label=label or (RELAY_ADDRESSES.get(sender) if is_relay else None),
                source_type=source_type,
                first_tx_date=first_tx
            )
            
            # Collect relay tx hashes for decoding
            if is_relay:
                for t in transfers:
                    relay_tx_hashes.append(t.tx_hash)
            
            # Get wallet info for non-bridge sources
            if not is_bridge_address(sender) and source_type == "unknown":
                source.wallet_info = get_wallet_info(api_key, sender)
                if source.wallet_info.is_fresh:
                    source_type = "fresh_wallet"
            
            result.funding_sources.append(source)
            result.total_funded += total
            
            # Deep: find other addresses this funder has sent to
            # Skip protocol contracts, bridges, and relay - they send to everyone
            if deep and not is_relay and not is_bridge_address(sender) and not is_protocol_contract(sender):
                outgoing = get_funded_addresses(api_key, sender)
                recipients = get_unique_recipients(outgoing)
                
                for recipient in recipients:
                    if recipient == address:
                        continue
                    if is_protocol_contract(recipient):
                        continue
                    
                    recipient_transfers = [t for t in outgoing if t.to_address == recipient]
                    recipient_total = sum(t.value for t in recipient_transfers)
                    
                    if recipient not in all_potential_siblings:
                        all_potential_siblings[recipient] = (recipient_total, recipient_transfers, [sender])
                    else:
                        existing_total, existing_txs, existing_funders = all_potential_siblings[recipient]
                        # Add this funder to the list if not already present
                        if sender not in existing_funders:
                            existing_funders.append(sender)
                        all_potential_siblings[recipient] = (
                            existing_total + recipient_total,
                            existing_txs + recipient_transfers,
                            existing_funders
                        )
        
        # ====================================================================
        # Step 4: Decode Relay transactions
        # ====================================================================
        if relay_tx_hashes:
            decoded = await batch_decode_relay_transactions(relay_tx_hashes[:10])
            
            # Attach decoded origins to funding sources
            for source in result.funding_sources:
                if source.is_relay:
                    for t in source.transfers:
                        if t.tx_hash in decoded and decoded[t.tx_hash]:
                            source.relay_origins.append(decoded[t.tx_hash])
        
        # ====================================================================
        # Step 5: Check which potential siblings are PM accounts
        # ====================================================================
        if deep and all_potential_siblings:
            addresses_to_check = list(all_potential_siblings.keys())[:max_siblings_to_check]
            pm_status = await batch_check_polymarket_accounts(addresses_to_check)
            
            for recipient, is_pm in pm_status.items():
                total_funded, txs, shared_funders = all_potential_siblings[recipient]
                sibling = SiblingAccount(
                    address=recipient,
                    total_funded=total_funded,
                    is_polymarket=is_pm,
                    funding_txs=txs,
                    shared_funders=shared_funders
                )
                
                if is_pm:
                    result.all_siblings.append(sibling)
        
        # ====================================================================
        # Step 6: Check outbound funding (who did this account fund?)
        # ====================================================================
        if check_outbound:
            outbound = get_accounts_funded_by(api_key, address, min_amount=10.0)
            
            if outbound:
                # Check which are PM accounts
                outbound_addresses = [addr for addr, _, _ in outbound][:max_siblings_to_check]
                pm_status = await batch_check_polymarket_accounts(outbound_addresses)
                
                for recipient, total, transfers in outbound:
                    is_pm = pm_status.get(recipient, False)
                    first_tx = min(t.timestamp for t in transfers) if transfers else None
                    
                    funded = FundedAccount(
                        address=recipient,
                        total_sent=total,
                        is_polymarket=is_pm,
                        transfers=transfers,
                        first_tx_date=first_tx
                    )
                    
                    result.funded_accounts.append(funded)
                    result.total_sent_to_others += total
                    
                    if is_pm:
                        result.funded_pm_accounts.append(funded)
        
        # ====================================================================
        # Step 7: Trace funding origins (multi-hop)
        # ====================================================================
        if trace_origin:
            # For each non-bridge funding source, trace back
            for source in result.funding_sources:
                if source.source_type in ("cex", "bridge", "dex", "protocol"):
                    # Already at a known origin
                    continue
                
                if source.total_amount >= 100:  # Only trace significant amounts
                    chains = trace_funding_origin(
                        api_key, 
                        source.address, 
                        max_hops=max_origin_hops,
                        min_amount=50.0
                    )
                    
                    if chains:
                        source.funding_chain = chains[0]
                        result.origin_chains.extend(chains)
            
            # Extract ultimate origins
            seen_origins = set()
            for chain in result.origin_chains:
                if chain.origin:
                    origin_addr = chain.origin.from_address
                    if origin_addr not in seen_origins:
                        seen_origins.add(origin_addr)
                        result.ultimate_origins.append(origin_addr)
        
        # ====================================================================
        # Step 8: Get trading behavior
        # ====================================================================
        activity = await get_account_activity(address, limit=200)
        if activity:
            markets = set()
            outcomes = set()
            timestamps = []
            
            for a in activity:
                if a.get("conditionId"):
                    markets.add(a.get("conditionId"))
                if a.get("outcome"):
                    outcomes.add(a.get("outcome"))
                if a.get("timestamp"):
                    try:
                        ts = datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00"))
                        timestamps.append(ts)
                    except:
                        pass
            
            result.trading = TradingBehavior(
                total_trades=len(activity),
                markets_traded=len(markets),
                unique_outcomes=len(outcomes),
                first_trade_date=min(timestamps) if timestamps else None,
                last_trade_date=max(timestamps) if timestamps else None
            )
        
        # ====================================================================
        # Step 9: Get positions and portfolio
        # ====================================================================
        if include_positions and result.is_polymarket:
            positions_task = get_account_positions(address)
            portfolio_task = get_portfolio_summary(address)
            
            result.positions, result.portfolio = await asyncio.gather(
                positions_task, portfolio_task
            )
        
        # ====================================================================
        # Step 10: Generate classification
        # ====================================================================
        result.signals = _generate_signals(result)
        result.classification = _classify(result)
        
    finally:
        await close_client()
    
    return result


# ============================================================================
# Classification Logic
# ============================================================================

def _generate_signals(result: TraceResult) -> list[str]:
    """Generate classification signals based on the trace."""
    signals = []
    
    # Account age signal
    if result.trading and result.trading.account_age_days is not None:
        age = result.trading.account_age_days
        if age < 7:
            signals.append(f"🆕 Very fresh account ({age} days old)")
        elif age < 30:
            signals.append(f"📅 New account ({age} days old)")
    
    # Relay funding signal
    if result.has_relay_funding:
        relay_pct = (result.relay_amount / result.total_funded * 100) if result.total_funded > 0 else 0
        signals.append(f"🌉 Relay bridge funding: ${result.relay_amount:,.0f} ({relay_pct:.0f}%)")
        
        # Check if we decoded the origin
        decoded_count = sum(len(s.relay_origins) for s in result.funding_sources)
        if decoded_count > 0:
            signals.append(f"🔍 Decoded {decoded_count} cross-chain origin(s)")
    
    # CEX origin signal
    if result.cex_funding > 0:
        signals.append(f"🏦 CEX funding: ${result.cex_funding:,.0f}")
    elif result.has_cex_origin:
        signals.append("🏦 Origin traced to CEX")
    
    # Sibling accounts signal
    sibling_count = result.sibling_count
    if sibling_count >= 5:
        signals.append(f"🚨 HIGH: {sibling_count} other PM accounts from same funder")
    elif sibling_count >= 2:
        signals.append(f"⚠️  MEDIUM: {sibling_count} other PM accounts from same funder")
    elif sibling_count == 1:
        signals.append(f"ℹ️  1 other PM account from same funder")
    
    # Outbound funding signal (accounts this address has funded)
    if result.funded_pm_count > 0:
        signals.append(f"📤 Funded {result.funded_pm_count} other PM account(s)")
    
    # Market diversity signal
    if result.trading:
        if result.trading.markets_traded == 1:
            signals.append("🎯 Single market focus")
        elif result.trading.markets_traded <= 3:
            signals.append(f"🎯 Concentrated: {result.trading.markets_traded} markets")
        
        if result.trading.total_trades >= 100:
            signals.append(f"📈 High activity: {result.trading.total_trades}+ trades")
        elif result.trading.total_trades < 10:
            signals.append(f"📉 Low activity: {result.trading.total_trades} trades")
    
    # Portfolio signals
    if result.portfolio:
        if result.portfolio.total_value >= 50000:
            signals.append(f"💎 Large portfolio: ${result.portfolio.total_value:,.0f}")
        if result.portfolio.win_rate >= 70:
            signals.append(f"🏆 High win rate: {result.portfolio.win_rate:.0f}%")
        elif result.portfolio.win_rate <= 30 and result.portfolio.total_trades >= 10:
            signals.append(f"📉 Low win rate: {result.portfolio.win_rate:.0f}%")
    
    # Funding size signal
    if result.total_funded >= 100000:
        signals.append(f"💰 Whale funding: ${result.total_funded:,.0f}")
    elif result.total_funded >= 50000:
        signals.append(f"💰 Large funding: ${result.total_funded:,.0f}")
    elif result.total_funded >= 10000:
        signals.append(f"💵 Significant funding: ${result.total_funded:,.0f}")
    
    # Multiple funding sources (exclude relay and protocol contracts)
    real_wallet_sources = len([
        f for f in result.funding_sources 
        if not f.is_relay and f.source_type not in ("protocol", "bridge", "dex")
    ])
    if real_wallet_sources >= 3:
        signals.append(f"🔀 Multiple funding sources: {real_wallet_sources} wallets")
    
    # Fresh funder wallets
    fresh_funders = [f for f in result.funding_sources 
                     if f.wallet_info and f.wallet_info.is_fresh]
    if fresh_funders:
        signals.append(f"🆕 Funded by {len(fresh_funders)} fresh wallet(s)")
    
    return signals


def _classify(result: TraceResult) -> str:
    """Classify the account based on signals."""
    sibling_count = result.sibling_count
    funded_pm_count = result.funded_pm_count
    
    # Coordinated if multiple siblings OR funds multiple PM accounts
    if sibling_count >= 3 or funded_pm_count >= 3:
        total_linked = sibling_count + funded_pm_count
        return f"🚨 Likely Coordinated (Multi-Account) - {total_linked} linked accounts"
    
    # Sophisticated if relay + concentrated + large funding
    if result.has_relay_funding:
        if result.trading and result.trading.markets_traded <= 3:
            if result.total_funded >= 10000:
                return "⚠️  Likely Sophisticated/Punt"
        return "⚠️  Cross-chain Funder - Review Needed"
    
    # Fresh account with big funding
    if result.trading:
        age = result.trading.account_age_days
        if age is not None and age < 14:
            if result.total_funded >= 5000:
                return "⚠️  Fresh + Large Funding - Worth Investigating"
    
    # Low activity with single market
    if result.trading and result.trading.total_trades < 10:
        if result.trading.markets_traded == 1 and result.total_funded >= 2000:
            return "⚠️  Single Bet Account - Check Market"
    
    # Funds other PM accounts
    if funded_pm_count > 0:
        return f"⚠️  Funds {funded_pm_count} Other PM Account(s) - Check for Coordination"
    
    # Some siblings but not many
    if sibling_count == 1 or sibling_count == 2:
        return "ℹ️  Some Linked Accounts - Manual Review"
    
    # Default retail indicators
    if sibling_count == 0 and not result.has_relay_funding:
        if result.trading and result.trading.markets_traded >= 5:
            return "✅ Likely Retail (Diversified)"
        return "✅ Likely Retail"
    
    return "❓ Inconclusive - Manual Review Needed"


# ============================================================================
# Export Functions
# ============================================================================

def export_to_dict(result: TraceResult) -> dict:
    """Export trace result to a dictionary for JSON serialization."""
    return {
        "address": result.address,
        "is_polymarket": result.is_polymarket,
        "classification": result.classification,
        "signals": result.signals,
        "funding": {
            "total_funded": result.total_funded,
            "first_funding_date": result.first_funding_date.isoformat() if result.first_funding_date else None,
            "sources": [
                {
                    "address": s.address,
                    "amount": s.total_amount,
                    "type": s.source_type,
                    "label": s.label,
                    "is_relay": s.is_relay,
                    "relay_origins": [
                        {
                            "chain": o.origin_chain_name,
                            "address": o.origin_address,
                            "amount": o.amount,
                        }
                        for o in s.relay_origins
                    ] if s.relay_origins else []
                }
                for s in result.funding_sources
            ]
        },
        "siblings": {
            "count": result.sibling_count,
            "accounts": [
                {"address": s.address, "funded": s.total_funded}
                for s in result.all_siblings if s.is_polymarket
            ]
        },
        "funded_accounts": {
            "count": result.funded_pm_count,
            "total_sent": result.total_sent_to_others,
            "pm_accounts": [
                {"address": f.address, "sent": f.total_sent}
                for f in result.funded_pm_accounts
            ]
        },
        "trading": {
            "total_trades": result.trading.total_trades if result.trading else 0,
            "markets_traded": result.trading.markets_traded if result.trading else 0,
            "account_age_days": result.trading.account_age_days if result.trading else None,
        } if result.trading else None,
        "portfolio": {
            "total_value": result.portfolio.total_value,
            "unrealized_pnl": result.portfolio.unrealized_pnl,
            "realized_pnl": result.portfolio.realized_pnl,
            "win_rate": result.portfolio.win_rate,
            "positions_count": result.portfolio.positions_count,
        } if result.portfolio else None,
        "positions": [
            {
                "market": p.market_question,
                "outcome": p.outcome,
                "size": p.size,
                "avg_price": p.avg_price,
                "current_price": p.current_price,
                "value": p.value,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in result.positions
        ],
        "origin_tracing": {
            "ultimate_origins": result.ultimate_origins,
            "chains": [
                {
                    "depth": chain.depth,
                    "origin": {
                        "address": chain.origin.from_address,
                        "type": chain.origin.from_type,
                        "label": chain.origin.from_label,
                    } if chain.origin else None
                }
                for chain in result.origin_chains
            ]
        }
    }
