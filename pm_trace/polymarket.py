"""Polymarket API interactions"""

import httpx
import asyncio
from typing import Optional
from .config import PM_DATA_API, PM_GAMMA_API


# Shared client for connection pooling
_client: Optional[httpx.AsyncClient] = None


async def get_client() -> httpx.AsyncClient:
    """Get or create shared async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


async def is_polymarket_account(address: str) -> bool:
    """
    Check if an address is a Polymarket account by querying the Data API.
    Returns True if the address has any activity on Polymarket.
    """
    address = address.lower()
    client = await get_client()
    
    try:
        response = await client.get(
            f"{PM_DATA_API}/activity",
            params={"user": address, "limit": 1}
        )
        if response.status_code == 200:
            data = response.json()
            return isinstance(data, list) and len(data) > 0
    except Exception:
        pass
    
    return False


async def batch_check_polymarket_accounts(addresses: list[str], max_concurrent: int = 5) -> dict[str, bool]:
    """
    Check multiple addresses in parallel with rate limiting.
    
    Args:
        addresses: List of addresses to check
        max_concurrent: Max concurrent requests (rate limiting)
    
    Returns:
        Dict mapping address -> is_polymarket
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_one(addr: str) -> tuple[str, bool]:
        async with semaphore:
            result = await is_polymarket_account(addr)
            await asyncio.sleep(0.1)  # Small delay to avoid rate limits
            return (addr, result)
    
    tasks = [check_one(addr) for addr in addresses]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        addr: is_pm 
        for addr, is_pm in results 
        if isinstance((addr, is_pm), tuple)
    }


async def get_account_positions(address: str) -> list:
    """Get current positions for a Polymarket account."""
    address = address.lower()
    client = await get_client()
    
    try:
        response = await client.get(
            f"{PM_DATA_API}/positions",
            params={"user": address}
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []


async def get_account_activity(address: str, limit: int = 100) -> list:
    """Get recent trading activity for a Polymarket account."""
    address = address.lower()
    client = await get_client()
    
    try:
        response = await client.get(
            f"{PM_DATA_API}/activity",
            params={"user": address, "limit": limit}
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []


async def get_account_profile(address: str) -> Optional[dict]:
    """Get profile info for a Polymarket account."""
    address = address.lower()
    client = await get_client()
    
    try:
        response = await client.get(
            f"{PM_GAMMA_API}/profiles",
            params={"address": address}
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0] if isinstance(data, list) else data
    except Exception:
        pass
    return None


async def get_account_pnl(address: str) -> Optional[dict]:
    """Get P&L summary for a Polymarket account."""
    address = address.lower()
    client = await get_client()
    
    try:
        # Try the profit-loss endpoint
        response = await client.get(
            f"{PM_DATA_API}/profit-loss",
            params={"user": address}
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


async def close_client():
    """Close the shared client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
