"""Blockchain interaction via Etherscan V2 API (supports Polygon)"""

import httpx
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .config import USDC_POLYGON, USDC_E_POLYGON, RELAY_ADDRESSES


# Etherscan V2 API base URL (supports multiple chains including Polygon)
ETHERSCAN_V2_API = "https://api.etherscan.io/v2/api"
POLYGON_CHAIN_ID = 137


@dataclass
class TokenTransfer:
    """Represents a token transfer event."""
    tx_hash: str
    from_address: str
    to_address: str
    value: float  # In human-readable units (e.g., USDC with decimals)
    token_symbol: str
    timestamp: datetime
    is_relay: bool = False
    
    @property
    def value_formatted(self) -> str:
        """Format value with commas and 2 decimal places."""
        return f"${self.value:,.2f}"


def _fetch_token_transfers(
    api_key: str,
    address: str,
    contract_address: str,
    symbol: str
) -> list[TokenTransfer]:
    """
    Fetch ERC-20 token transfers using Etherscan V2 API.
    """
    transfers = []
    
    params = {
        "chainid": POLYGON_CHAIN_ID,
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
                is_relay = from_addr in RELAY_ADDRESSES
                
                timestamp_val = int(event.get("timeStamp", 0))
                
                transfers.append(TokenTransfer(
                    tx_hash=event.get("hash", ""),
                    from_address=from_addr,
                    to_address=to_addr,
                    value=value,
                    token_symbol=symbol,
                    timestamp=datetime.fromtimestamp(timestamp_val) if timestamp_val else datetime.now(),
                    is_relay=is_relay
                ))
    except Exception as e:
        # Log error but don't fail
        print(f"Error fetching transfers for {contract_address}: {e}")
    
    return transfers


def get_usdc_transfers(
    api_key: str,
    address: str,
    direction: str = "both"  # "in", "out", or "both"
) -> list[TokenTransfer]:
    """
    Get all USDC transfers for an address.
    
    Args:
        api_key: Etherscan V2 API key
        address: Wallet address to query
        direction: "in" for incoming, "out" for outgoing, "both" for all
    
    Returns:
        List of TokenTransfer objects sorted by timestamp (oldest first)
    """
    address = address.lower()
    transfers = []
    
    # Check both USDC and USDC.e
    for token_address, symbol in [
        (USDC_POLYGON, "USDC"),
        (USDC_E_POLYGON, "USDC.e")
    ]:
        token_transfers = _fetch_token_transfers(api_key, address, token_address, symbol)
        
        for transfer in token_transfers:
            # Filter by direction
            is_incoming = transfer.to_address == address
            is_outgoing = transfer.from_address == address
            
            if direction == "in" and not is_incoming:
                continue
            if direction == "out" and not is_outgoing:
                continue
            
            transfers.append(transfer)
    
    # Sort by timestamp
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
