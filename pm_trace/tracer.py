"""Core tracing logic for Polymarket account forensics"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .blockchain import (
    TokenTransfer,
    get_funding_sources,
    get_funded_addresses,
    get_unique_recipients,
)
from .polymarket import (
    is_polymarket_account,
    batch_check_polymarket_accounts,
    get_account_activity,
    get_account_profile,
    close_client,
)
from .config import RELAY_ADDRESSES


@dataclass
class SiblingAccount:
    """A Polymarket account funded by the same source."""
    address: str
    total_funded: float
    is_polymarket: bool
    funding_txs: list[TokenTransfer] = field(default_factory=list)


@dataclass
class FundingSource:
    """A source that funded the target account."""
    address: str
    total_amount: float
    is_relay: bool
    transfers: list[TokenTransfer] = field(default_factory=list)
    label: Optional[str] = None  # e.g., "Relay.link", "Binance", etc.
    first_tx_date: Optional[datetime] = None
    
    # Siblings funded by this same source
    siblings: list[SiblingAccount] = field(default_factory=list)


@dataclass 
class TradingBehavior:
    """Analysis of trading patterns."""
    total_trades: int = 0
    markets_traded: int = 0
    unique_outcomes: int = 0  # Number of unique outcome tokens traded
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
    
    # Trading behavior
    trading: Optional[TradingBehavior] = None
    
    # Classification signals
    signals: list[str] = field(default_factory=list)
    classification: str = "Unknown"  # "Retail", "Sophisticated", "Coordinated"
    
    @property
    def sibling_count(self) -> int:
        """Number of other PM accounts funded by same source(s)."""
        return len([s for s in self.all_siblings if s.is_polymarket])
    
    @property
    def has_relay_funding(self) -> bool:
        """Whether any funding came through Relay bridge."""
        return any(f.is_relay for f in self.funding_sources)
    
    @property
    def relay_amount(self) -> float:
        """Total amount funded via Relay."""
        return sum(f.total_amount for f in self.funding_sources if f.is_relay)


async def trace_account(
    api_key: str, 
    address: str, 
    deep: bool = True,
    max_siblings_to_check: int = 20
) -> TraceResult:
    """
    Trace a Polymarket account to find funding sources and sibling accounts.
    
    Args:
        api_key: Etherscan V2 API key
        address: The Polymarket account address to trace
        deep: If True, also check each funder's other recipients
        max_siblings_to_check: Limit on sibling addresses to check (for performance)
    
    Returns:
        TraceResult with complete analysis
    """
    address = address.lower()
    result = TraceResult(address=address, is_polymarket=False)
    
    try:
        # Step 1: Check if this is a Polymarket account and get profile
        result.is_polymarket, result.profile = await asyncio.gather(
            is_polymarket_account(address),
            get_account_profile(address)
        )
        
        # Step 2: Get funding sources (incoming USDC) - this is synchronous
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
        
        # Step 3: Analyze each funding source
        all_potential_siblings: dict[str, tuple[float, list[TokenTransfer]]] = {}
        
        for sender, transfers in sender_transfers.items():
            total = sum(t.value for t in transfers)
            is_relay = sender in RELAY_ADDRESSES
            first_tx = min(t.timestamp for t in transfers)
            
            source = FundingSource(
                address=sender,
                total_amount=total,
                is_relay=is_relay,
                transfers=transfers,
                label=RELAY_ADDRESSES.get(sender),
                first_tx_date=first_tx
            )
            
            result.funding_sources.append(source)
            result.total_funded += total
            
            # Step 4: If deep trace, find other addresses this funder has sent to
            if deep and not is_relay:  # Skip relay addresses (they send to everyone)
                outgoing = get_funded_addresses(api_key, sender)
                recipients = get_unique_recipients(outgoing)
                
                # Collect potential siblings (excluding target)
                for recipient in recipients:
                    if recipient == address:
                        continue
                    
                    recipient_transfers = [t for t in outgoing if t.to_address == recipient]
                    recipient_total = sum(t.value for t in recipient_transfers)
                    
                    # Track which funder this came from
                    if recipient not in all_potential_siblings:
                        all_potential_siblings[recipient] = (recipient_total, recipient_transfers)
                    else:
                        # Merge if same recipient from multiple funders
                        existing_total, existing_txs = all_potential_siblings[recipient]
                        all_potential_siblings[recipient] = (
                            existing_total + recipient_total,
                            existing_txs + recipient_transfers
                        )
        
        # Step 5: Batch check which potential siblings are PM accounts
        if deep and all_potential_siblings:
            # Limit the number we check to avoid long waits
            addresses_to_check = list(all_potential_siblings.keys())[:max_siblings_to_check]
            
            pm_status = await batch_check_polymarket_accounts(addresses_to_check)
            
            for recipient, is_pm in pm_status.items():
                total_funded, txs = all_potential_siblings[recipient]
                sibling = SiblingAccount(
                    address=recipient,
                    total_funded=total_funded,
                    is_polymarket=is_pm,
                    funding_txs=txs
                )
                
                if is_pm:
                    result.all_siblings.append(sibling)
        
        # Step 6: Get trading behavior
        activity = await get_account_activity(address, limit=200)
        if activity:
            # Extract market/condition IDs
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
        
        # Step 7: Generate classification signals
        result.signals = _generate_signals(result)
        result.classification = _classify(result)
        
    finally:
        await close_client()
    
    return result


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
    
    # Sibling accounts signal
    sibling_count = result.sibling_count
    if sibling_count >= 5:
        signals.append(f"🚨 HIGH: {sibling_count} other PM accounts from same funder")
    elif sibling_count >= 2:
        signals.append(f"⚠️  MEDIUM: {sibling_count} other PM accounts from same funder")
    elif sibling_count == 1:
        signals.append(f"ℹ️  1 other PM account from same funder")
    
    # Market diversity signal
    if result.trading:
        if result.trading.markets_traded == 1:
            signals.append("🎯 Single market focus")
        elif result.trading.markets_traded <= 3:
            signals.append(f"🎯 Concentrated: {result.trading.markets_traded} markets")
        
        # Activity level
        if result.trading.total_trades >= 100:
            signals.append(f"📈 High activity: {result.trading.total_trades}+ trades")
        elif result.trading.total_trades < 10:
            signals.append(f"📉 Low activity: {result.trading.total_trades} trades")
    
    # Funding size signal
    if result.total_funded >= 100000:
        signals.append(f"💰 Whale funding: ${result.total_funded:,.0f}")
    elif result.total_funded >= 50000:
        signals.append(f"💰 Large funding: ${result.total_funded:,.0f}")
    elif result.total_funded >= 10000:
        signals.append(f"💵 Significant funding: ${result.total_funded:,.0f}")
    
    # Multiple funding sources
    non_relay_sources = len([f for f in result.funding_sources if not f.is_relay])
    if non_relay_sources >= 3:
        signals.append(f"🔀 Multiple funding sources: {non_relay_sources} wallets")
    
    return signals


def _classify(result: TraceResult) -> str:
    """Classify the account based on signals."""
    sibling_count = result.sibling_count
    
    # Coordinated if multiple siblings
    if sibling_count >= 3:
        return "🚨 Likely Coordinated (Multi-Account)"
    
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
    
    # Some siblings but not many
    if sibling_count == 1 or sibling_count == 2:
        return "ℹ️  Some Linked Accounts - Manual Review"
    
    # Default retail indicators
    if sibling_count == 0 and not result.has_relay_funding:
        if result.trading and result.trading.markets_traded >= 5:
            return "✅ Likely Retail (Diversified)"
        return "✅ Likely Retail"
    
    return "❓ Inconclusive - Manual Review Needed"
