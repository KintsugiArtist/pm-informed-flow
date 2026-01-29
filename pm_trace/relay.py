"""Relay.link bridge transaction decoding"""

import httpx
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


RELAY_API = "https://api.relay.link"


@dataclass
class RelayOrigin:
    """Decoded origin information from a Relay bridge transaction."""
    origin_chain_id: int
    origin_chain_name: str
    origin_address: str
    origin_tx_hash: Optional[str]
    amount: float
    token_symbol: str
    timestamp: Optional[datetime]
    
    # Destination info
    dest_chain_id: int
    dest_chain_name: str
    dest_address: str
    dest_tx_hash: str
    
    # Status
    status: str  # "completed", "pending", etc.


# Chain ID to name mapping
CHAIN_NAMES = {
    1: "Ethereum",
    10: "Optimism",
    137: "Polygon",
    8453: "Base",
    42161: "Arbitrum",
    43114: "Avalanche",
    56: "BNB Chain",
    250: "Fantom",
    324: "zkSync Era",
    59144: "Linea",
    534352: "Scroll",
    81457: "Blast",
}


def get_chain_name(chain_id: int) -> str:
    """Get chain name from chain ID."""
    return CHAIN_NAMES.get(chain_id, f"Chain {chain_id}")


def _is_valid_eth_address(addr: str) -> bool:
    """Check if string is a valid Ethereum address."""
    if not addr:
        return False
    addr = addr.strip()
    if not addr.startswith("0x"):
        return False
    if len(addr) != 42:
        return False
    try:
        int(addr, 16)
        return True
    except ValueError:
        return False


async def decode_relay_transaction(tx_hash: str, client: Optional[httpx.AsyncClient] = None) -> Optional[RelayOrigin]:
    """
    Decode a Relay.link bridge transaction to find the origin.
    
    Args:
        tx_hash: The transaction hash on the destination chain (Polygon)
        client: Optional async client for connection reuse
    
    Returns:
        RelayOrigin with decoded information, or None if not found/invalid
    """
    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
    
    try:
        # Try the requests endpoint
        response = await client.get(
            f"{RELAY_API}/requests/v2",
            params={"hash": tx_hash}
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        # Handle different response formats
        requests = data.get("requests", [])
        if not requests:
            # Try direct data
            if "originChainId" in data:
                requests = [data]
            else:
                return None
        
        req = requests[0]
        
        # Extract origin info
        origin_chain_id = req.get("originChainId", 0)
        dest_chain_id = req.get("destinationChainId", 137)
        
        # Validate chain ID - must be a known EVM chain
        if origin_chain_id == 0 or origin_chain_id not in CHAIN_NAMES:
            return None  # Invalid or unsupported chain
        
        # Get amount (in human readable units)
        amount_raw = req.get("data", {}).get("inAmount") or req.get("inAmount", "0")
        try:
            # Assume 6 decimals for USDC
            amount = int(amount_raw) / 1_000_000 if amount_raw else 0
        except (ValueError, TypeError):
            amount = 0
        
        # Get addresses
        origin_address = req.get("data", {}).get("user") or req.get("user", "")
        dest_address = req.get("data", {}).get("recipient") or req.get("recipient", "")
        
        # Validate origin address is a proper Ethereum address
        if not _is_valid_eth_address(origin_address):
            return None  # Invalid origin address (could be Solana or other non-EVM)
        
        # Get hashes
        origin_tx = req.get("inTxHashes", [None])[0] if req.get("inTxHashes") else None
        dest_tx = tx_hash
        
        # Get timestamp
        timestamp = None
        if req.get("createdAt"):
            try:
                timestamp = datetime.fromisoformat(req["createdAt"].replace("Z", "+00:00"))
            except:
                pass
        
        return RelayOrigin(
            origin_chain_id=origin_chain_id,
            origin_chain_name=get_chain_name(origin_chain_id),
            origin_address=origin_address.lower(),
            origin_tx_hash=origin_tx,
            amount=amount,
            token_symbol="USDC",
            timestamp=timestamp,
            dest_chain_id=dest_chain_id,
            dest_chain_name=get_chain_name(dest_chain_id),
            dest_address=dest_address.lower() if dest_address else "",
            dest_tx_hash=dest_tx,
            status=req.get("status", "unknown")
        )
        
    except Exception:
        # Failed to decode - return None
        pass
    finally:
        if should_close:
            await client.aclose()
    
    return None


async def batch_decode_relay_transactions(
    tx_hashes: list[str],
    max_concurrent: int = 3
) -> dict[str, Optional[RelayOrigin]]:
    """
    Decode multiple Relay transactions in parallel.
    
    Args:
        tx_hashes: List of transaction hashes to decode
        max_concurrent: Max concurrent requests
    
    Returns:
        Dict mapping tx_hash -> RelayOrigin (or None if failed)
    """
    import asyncio
    
    results = {}
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        async def decode_one(tx_hash: str) -> tuple[str, Optional[RelayOrigin]]:
            async with semaphore:
                result = await decode_relay_transaction(tx_hash, client)
                await asyncio.sleep(0.2)  # Rate limiting
                return (tx_hash, result)
        
        tasks = [decode_one(h) for h in tx_hashes]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        for item in completed:
            if isinstance(item, tuple):
                tx_hash, origin = item
                results[tx_hash] = origin
    
    return results


def generate_relay_link(tx_hash: str) -> str:
    """Generate Relay.link URL to view a bridge transaction."""
    return f"https://relay.link/transaction/{tx_hash}"


def generate_origin_explorer_link(origin: RelayOrigin) -> str:
    """Generate block explorer link for the origin transaction."""
    explorers = {
        1: "https://etherscan.io/tx/",
        10: "https://optimistic.etherscan.io/tx/",
        137: "https://polygonscan.com/tx/",
        8453: "https://basescan.org/tx/",
        42161: "https://arbiscan.io/tx/",
        43114: "https://snowtrace.io/tx/",
        56: "https://bscscan.com/tx/",
    }
    
    base_url = explorers.get(origin.origin_chain_id, "")
    if base_url and origin.origin_tx_hash:
        return f"{base_url}{origin.origin_tx_hash}"
    return ""


def generate_origin_address_link(origin: RelayOrigin) -> str:
    """Generate block explorer link for the origin address."""
    explorers = {
        1: "https://etherscan.io/address/",
        10: "https://optimistic.etherscan.io/address/",
        137: "https://polygonscan.com/address/",
        8453: "https://basescan.org/address/",
        42161: "https://arbiscan.io/address/",
        43114: "https://snowtrace.io/address/",
        56: "https://bscscan.com/address/",
    }
    
    base_url = explorers.get(origin.origin_chain_id, "")
    if base_url and origin.origin_address:
        return f"{base_url}{origin.origin_address}"
    return ""
