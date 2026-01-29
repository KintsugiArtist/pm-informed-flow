"""Blockchain interaction via Etherscan V2 API (supports multiple chains)"""

import httpx
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .config import (
    USDC_POLYGON, USDC_E_POLYGON, 
    ETHERSCAN_V2_API, CHAIN_IDS,
    is_relay_address, is_bridge_address, is_cex_address,
    get_address_label, get_address_type,
    PROTOCOL_CONTRACTS,
)


def _warn(msg: str) -> None:
    """Print warning to stderr for debugging."""
    if sys.stderr.isatty():
        print(f"[pm-trace warning] {msg}", file=sys.stderr)


@dataclass
class TokenTransfer:
    """Represents a token transfer event."""
    tx_hash: str
    from_address: str
    to_address: str
    value: float  # In human-readable units (e.g., USDC with decimals)
    token_symbol: str
    timestamp: datetime
    block_number: int = 0
    is_relay: bool = False
    
    @property
    def value_formatted(self) -> str:
        """Format value with commas and 2 decimal places."""
        return f"${self.value:,.2f}"


@dataclass
class WalletInfo:
    """Information about a wallet."""
    address: str
    first_tx_date: Optional[datetime] = None
    last_tx_date: Optional[datetime] = None
    tx_count: int = 0
    age_days: Optional[int] = None
    label: Optional[str] = None
    source_type: str = "unknown"  # cex, bridge, dex, entity, protocol, unknown
    
    @property
    def is_fresh(self) -> bool:
        """Is this a fresh wallet (< 7 days old)?"""
        return self.age_days is not None and self.age_days < 7
    
    @property
    def is_new(self) -> bool:
        """Is this a new wallet (< 30 days old)?"""
        return self.age_days is not None and self.age_days < 30


@dataclass
class FundingChain:
    """A chain of funding from origin to target."""
    hops: list["FundingHop"] = field(default_factory=list)
    
    @property
    def origin(self) -> Optional["FundingHop"]:
        """Get the ultimate origin (first hop)."""
        return self.hops[0] if self.hops else None
    
    @property
    def depth(self) -> int:
        """Number of hops in the chain."""
        return len(self.hops)
    
    @property
    def total_amount(self) -> float:
        """Amount at the final hop."""
        return self.hops[-1].amount if self.hops else 0.0


@dataclass
class FundingHop:
    """One hop in a funding chain."""
    from_address: str
    to_address: str
    amount: float
    timestamp: datetime
    tx_hash: str
    from_label: Optional[str] = None
    from_type: str = "unknown"


# ============================================================================
# Core API Functions
# ============================================================================

def _fetch_token_transfers(
    api_key: str,
    address: str,
    contract_address: str,
    symbol: str,
    chain_id: int = 137
) -> list[TokenTransfer]:
    """
    Fetch ERC-20 token transfers using Etherscan V2 API.
    """
    transfers = []
    
    params = {
        "chainid": chain_id,
        "module": "account",
        "action": "tokentx",
        "contractaddress": contract_address,
        "address": address,
        "page": 1,
        "offset": 1000,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
        "apikey": api_key
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(ETHERSCAN_V2_API, params=params)
            data = response.json()
            
            if data.get("status") != "1" or not data.get("result"):
                return transfers
            
            for event in data["result"]:
                from_addr = event.get("from", "").lower()
                to_addr = event.get("to", "").lower()
                
                # Parse value (USDC has 6 decimals)
                raw_value = int(event.get("value", 0))
                decimals = int(event.get("tokenDecimal", 6))
                value = raw_value / (10 ** decimals)
                
                # Check if this is from a Relay address
                is_relay = is_relay_address(from_addr)
                
                timestamp_val = int(event.get("timeStamp", 0))
                block_num = int(event.get("blockNumber", 0))
                
                transfers.append(TokenTransfer(
                    tx_hash=event.get("hash", ""),
                    from_address=from_addr,
                    to_address=to_addr,
                    value=value,
                    token_symbol=symbol,
                    timestamp=datetime.fromtimestamp(timestamp_val) if timestamp_val else datetime.now(),
                    block_number=block_num,
                    is_relay=is_relay
                ))
    except Exception as e:
        pass
    
    return transfers


def get_usdc_transfers(
    api_key: str,
    address: str,
    direction: str = "both",  # "in", "out", or "both"
    chain_id: int = 137
) -> list[TokenTransfer]:
    """
    Get all USDC transfers for an address.
    
    Args:
        api_key: Etherscan V2 API key
        address: Wallet address to query
        direction: "in" for incoming, "out" for outgoing, "both" for all
        chain_id: Chain ID (default: Polygon)
    
    Returns:
        List of TokenTransfer objects sorted by timestamp (oldest first)
    """
    address = address.lower()
    transfers = []
    
    # Token addresses depend on chain
    if chain_id == 137:  # Polygon
        tokens = [
            (USDC_POLYGON, "USDC"),
            (USDC_E_POLYGON, "USDC.e")
        ]
    elif chain_id == 1:  # Ethereum
        tokens = [
            ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USDC"),
        ]
    elif chain_id == 42161:  # Arbitrum
        tokens = [
            ("0xaf88d065e77c8cc2239327c5edb3a432268e5831", "USDC"),
            ("0xff970a61a04b1ca14834a43f5de4533ebddb5cc8", "USDC.e"),
        ]
    elif chain_id == 8453:  # Base
        tokens = [
            ("0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", "USDC"),
        ]
    else:
        tokens = [(USDC_POLYGON, "USDC")]
    
    for token_address, symbol in tokens:
        token_transfers = _fetch_token_transfers(
            api_key, address, token_address, symbol, chain_id
        )
        
        for transfer in token_transfers:
            is_incoming = transfer.to_address == address
            is_outgoing = transfer.from_address == address
            
            if direction == "in" and not is_incoming:
                continue
            if direction == "out" and not is_outgoing:
                continue
            
            transfers.append(transfer)
    
    transfers.sort(key=lambda x: x.timestamp)
    return transfers


def get_funding_sources(api_key: str, address: str) -> list[TokenTransfer]:
    """Get all incoming USDC transfers (funding sources) for an address."""
    return get_usdc_transfers(api_key, address, direction="in")


def get_funded_addresses(api_key: str, funder_address: str) -> list[TokenTransfer]:
    """Get all outgoing USDC transfers from a funder address."""
    return get_usdc_transfers(api_key, funder_address, direction="out")


def get_unique_recipients(transfers: list[TokenTransfer]) -> list[str]:
    """Get unique recipient addresses from a list of transfers."""
    return list(set(t.to_address for t in transfers))


def get_unique_senders(transfers: list[TokenTransfer]) -> list[str]:
    """Get unique sender addresses from a list of transfers."""
    return list(set(t.from_address for t in transfers))


# ============================================================================
# Wallet Analysis
# ============================================================================

def get_wallet_info(api_key: str, address: str, chain_id: int = 137) -> WalletInfo:
    """
    Get information about a wallet including age and activity.
    """
    address = address.lower()
    
    # Check if it's a known address first
    label = get_address_label(address)
    source_type = get_address_type(address)
    
    info = WalletInfo(
        address=address,
        label=label,
        source_type=source_type
    )
    
    # Get transaction history to determine age
    try:
        params = {
            "chainid": chain_id,
            "module": "account",
            "action": "txlist",
            "address": address,
            "page": 1,
            "offset": 1,  # Just get first tx
            "startblock": 0,
            "endblock": 99999999,
            "sort": "asc",
            "apikey": api_key
        }
        
        with httpx.Client(timeout=15.0) as client:
            response = client.get(ETHERSCAN_V2_API, params=params)
            data = response.json()
            
            if data.get("status") == "1" and data.get("result"):
                first_tx = data["result"][0]
                first_ts = int(first_tx.get("timeStamp", 0))
                if first_ts:
                    info.first_tx_date = datetime.fromtimestamp(first_ts)
                    info.age_days = (datetime.now() - info.first_tx_date).days
        
        # Get total tx count
        params["action"] = "txlist"
        params["offset"] = 10000
        
        with httpx.Client(timeout=15.0) as client:
            response = client.get(ETHERSCAN_V2_API, params=params)
            data = response.json()
            if data.get("status") == "1" and data.get("result"):
                info.tx_count = len(data["result"])
                
                # Get last tx date
                if data["result"]:
                    last_tx = data["result"][-1]
                    last_ts = int(last_tx.get("timeStamp", 0))
                    if last_ts:
                        info.last_tx_date = datetime.fromtimestamp(last_ts)
                        
    except Exception:
        pass
    
    return info


# ============================================================================
# Multi-Hop Tracing
# ============================================================================

def trace_funding_origin(
    api_key: str,
    address: str,
    max_hops: int = 3,
    min_amount: float = 100.0,
    chain_id: int = 137
) -> list[FundingChain]:
    """
    Trace back through funding hops to find origin wallets.
    
    Args:
        api_key: Etherscan API key
        address: Starting address to trace from
        max_hops: Maximum number of hops to trace back
        min_amount: Minimum transfer amount to follow
        chain_id: Chain ID
    
    Returns:
        List of FundingChain objects representing different origin paths
    """
    address = address.lower()
    chains = []
    
    # Get incoming transfers
    incoming = get_funding_sources(api_key, address)
    
    # Group by sender
    by_sender: dict[str, list[TokenTransfer]] = {}
    for t in incoming:
        if t.value < min_amount:
            continue
        sender = t.from_address
        if sender not in by_sender:
            by_sender[sender] = []
        by_sender[sender].append(t)
    
    # Trace each significant sender
    for sender, transfers in by_sender.items():
        total = sum(t.value for t in transfers)
        first_tx = min(transfers, key=lambda x: x.timestamp)
        
        # Get sender info
        sender_label = get_address_label(sender)
        sender_type = get_address_type(sender)
        
        # Create initial hop
        first_hop = FundingHop(
            from_address=sender,
            to_address=address,
            amount=total,
            timestamp=first_tx.timestamp,
            tx_hash=first_tx.tx_hash,
            from_label=sender_label,
            from_type=sender_type
        )
        
        chain = FundingChain(hops=[first_hop])
        
        # If it's a known source (CEX, bridge), stop here
        if sender_type in ("cex", "bridge", "dex", "protocol"):
            chains.append(chain)
            continue
        
        # Otherwise, trace back further
        if max_hops > 1:
            _trace_back(api_key, sender, chain, max_hops - 1, min_amount, chain_id)
        
        chains.append(chain)
    
    return chains


def _trace_back(
    api_key: str,
    address: str,
    chain: FundingChain,
    remaining_hops: int,
    min_amount: float,
    chain_id: int
) -> None:
    """Recursively trace back funding sources."""
    if remaining_hops <= 0:
        return
    
    # Skip known protocol contracts
    if address.lower() in {k.lower() for k in PROTOCOL_CONTRACTS}:
        return
    
    # Get incoming transfers to this address
    incoming = get_funding_sources(api_key, address)
    
    if not incoming:
        return
    
    # Find the largest funder
    by_sender: dict[str, float] = {}
    tx_by_sender: dict[str, TokenTransfer] = {}
    
    for t in incoming:
        if t.value < min_amount:
            continue
        sender = t.from_address
        by_sender[sender] = by_sender.get(sender, 0) + t.value
        if sender not in tx_by_sender:
            tx_by_sender[sender] = t
    
    if not by_sender:
        return
    
    # Get the largest funder
    largest_sender = max(by_sender, key=lambda x: by_sender[x])
    largest_amount = by_sender[largest_sender]
    largest_tx = tx_by_sender[largest_sender]
    
    # Get sender info
    sender_label = get_address_label(largest_sender)
    sender_type = get_address_type(largest_sender)
    
    # Add hop to chain
    hop = FundingHop(
        from_address=largest_sender,
        to_address=address,
        amount=largest_amount,
        timestamp=largest_tx.timestamp,
        tx_hash=largest_tx.tx_hash,
        from_label=sender_label,
        from_type=sender_type
    )
    
    # Insert at beginning (we're tracing backwards)
    chain.hops.insert(0, hop)
    
    # If it's a known source, stop
    if sender_type in ("cex", "bridge", "dex", "protocol"):
        return
    
    # Continue tracing
    _trace_back(api_key, largest_sender, chain, remaining_hops - 1, min_amount, chain_id)


# ============================================================================
# Outbound Analysis
# ============================================================================

def get_accounts_funded_by(
    api_key: str,
    address: str,
    min_amount: float = 10.0
) -> list[tuple[str, float, list[TokenTransfer]]]:
    """
    Get all addresses that this account has funded.
    
    Returns:
        List of (recipient_address, total_amount, transfers)
    """
    address = address.lower()
    outgoing = get_funded_addresses(api_key, address)
    
    # Filter out protocol contracts and dust
    by_recipient: dict[str, list[TokenTransfer]] = {}
    
    for t in outgoing:
        recipient = t.to_address
        
        # Skip protocol contracts
        if recipient.lower() in {k.lower() for k in PROTOCOL_CONTRACTS}:
            continue
        
        # Skip small amounts
        if t.value < min_amount:
            continue
        
        if recipient not in by_recipient:
            by_recipient[recipient] = []
        by_recipient[recipient].append(t)
    
    # Build results
    results = []
    for recipient, transfers in by_recipient.items():
        total = sum(t.value for t in transfers)
        results.append((recipient, total, transfers))
    
    # Sort by amount descending
    results.sort(key=lambda x: x[1], reverse=True)
    
    return results


# ============================================================================
# Utility Functions
# ============================================================================

def generate_explorer_link(
    address: str,
    chain_id: int = 137,
    link_type: str = "address"
) -> str:
    """Generate block explorer link for an address or transaction."""
    explorers = {
        1: "https://etherscan.io",
        10: "https://optimistic.etherscan.io",
        137: "https://polygonscan.com",
        8453: "https://basescan.org",
        42161: "https://arbiscan.io",
    }
    
    base = explorers.get(chain_id, "https://polygonscan.com")
    return f"{base}/{link_type}/{address}"
