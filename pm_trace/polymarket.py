"""Polymarket API interactions"""

import httpx
import asyncio
import sys
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from .config import PM_DATA_API, PM_GAMMA_API, PM_CLOB_API


def _warn(msg: str) -> None:
    """Print warning to stderr for debugging."""
    if sys.stderr.isatty():
        print(f"[pm-trace warning] {msg}", file=sys.stderr)


# Shared client for connection pooling
_client: Optional[httpx.AsyncClient] = None


async def get_client() -> httpx.AsyncClient:
    """Get or create shared async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


async def close_client():
    """Close the shared client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Position:
    """A position in a Polymarket market."""
    market_id: str
    condition_id: str
    outcome: str  # "Yes" or "No"
    size: float  # Number of shares
    avg_price: float  # Average entry price
    current_price: float
    market_question: str
    market_slug: Optional[str] = None
    unrealized_pnl: float = 0.0
    value: float = 0.0  # Current value = size * current_price
    
    @property
    def pnl_percent(self) -> float:
        """P&L as percentage."""
        if self.avg_price > 0:
            return ((self.current_price - self.avg_price) / self.avg_price) * 100
        return 0.0


@dataclass
class PortfolioSummary:
    """Summary of account portfolio."""
    total_value: float
    total_invested: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    win_rate: float
    total_trades: int
    markets_traded: int
    volume_traded: float
    positions_count: int


@dataclass
class MarketInfo:
    """Information about a Polymarket market."""
    condition_id: str
    question: str
    slug: str
    outcome_yes_price: float
    outcome_no_price: float
    volume: float
    liquidity: float
    end_date: Optional[datetime]
    resolved: bool
    resolution: Optional[str]  # "Yes", "No", or None


# ============================================================================
# Account Verification
# ============================================================================

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


async def batch_check_polymarket_accounts(
    addresses: list[str], 
    max_concurrent: int = 5
) -> dict[str, bool]:
    """
    Check multiple addresses in parallel with rate limiting.
    
    Args:
        addresses: List of addresses to check
        max_concurrent: Max concurrent requests (rate limiting)
    
    Returns:
        Dict mapping address -> is_polymarket
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}
    
    async def check_one(addr: str) -> tuple[str, bool]:
        async with semaphore:
            result = await is_polymarket_account(addr)
            await asyncio.sleep(0.1)  # Small delay to avoid rate limits
            return (addr, result)
    
    tasks = [check_one(addr) for addr in addresses]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    
    for item in completed:
        if isinstance(item, tuple):
            addr, is_pm = item
            results[addr] = is_pm
    
    return results


# ============================================================================
# Account Data
# ============================================================================

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


async def get_all_account_activity(address: str, max_pages: int = 10) -> list:
    """Get all trading activity by paginating through results."""
    address = address.lower()
    client = await get_client()
    all_activity = []
    
    try:
        offset = 0
        limit = 100
        
        for _ in range(max_pages):
            response = await client.get(
                f"{PM_DATA_API}/activity",
                params={"user": address, "limit": limit, "offset": offset}
            )
            if response.status_code != 200:
                break
            
            data = response.json()
            if not data:
                break
            
            all_activity.extend(data)
            
            if len(data) < limit:
                break
            
            offset += limit
            await asyncio.sleep(0.1)  # Rate limiting
            
    except Exception:
        pass
    
    return all_activity


async def get_account_positions_raw(address: str) -> list:
    """Get raw positions data for a Polymarket account."""
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


async def get_account_pnl(address: str) -> Optional[dict]:
    """Get P&L summary for a Polymarket account."""
    address = address.lower()
    client = await get_client()
    
    try:
        response = await client.get(
            f"{PM_DATA_API}/profit-loss",
            params={"user": address}
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


# ============================================================================
# Market Data
# ============================================================================

async def get_market_info(condition_id: str) -> Optional[MarketInfo]:
    """Get market information by condition ID."""
    client = await get_client()
    
    try:
        response = await client.get(
            f"{PM_GAMMA_API}/markets",
            params={"condition_id": condition_id}
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                market = data[0] if isinstance(data, list) else data
                
                # Parse end date
                end_date = None
                if market.get("end_date_iso"):
                    try:
                        end_date = datetime.fromisoformat(
                            market["end_date_iso"].replace("Z", "+00:00")
                        )
                    except:
                        pass
                
                return MarketInfo(
                    condition_id=condition_id,
                    question=market.get("question", ""),
                    slug=market.get("slug", ""),
                    outcome_yes_price=float(market.get("outcomePrices", [0.5, 0.5])[0]),
                    outcome_no_price=float(market.get("outcomePrices", [0.5, 0.5])[1]),
                    volume=float(market.get("volume", 0)),
                    liquidity=float(market.get("liquidity", 0)),
                    end_date=end_date,
                    resolved=market.get("resolved", False),
                    resolution=market.get("resolution")
                )
    except Exception:
        pass
    return None


async def batch_get_market_info(
    condition_ids: list[str],
    max_concurrent: int = 5
) -> dict[str, Optional[MarketInfo]]:
    """Get market info for multiple markets in parallel."""
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}
    
    async def get_one(cid: str) -> tuple[str, Optional[MarketInfo]]:
        async with semaphore:
            result = await get_market_info(cid)
            await asyncio.sleep(0.1)
            return (cid, result)
    
    tasks = [get_one(cid) for cid in condition_ids]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    
    for item in completed:
        if isinstance(item, tuple):
            cid, info = item
            results[cid] = info
    
    return results


# ============================================================================
# Enhanced Position Fetching
# ============================================================================

async def get_account_positions(address: str) -> list[Position]:
    """
    Get positions for a Polymarket account.
    The raw API response already includes all necessary data.
    """
    address = address.lower()
    
    # Get raw positions - the API already returns enriched data
    raw_positions = await get_account_positions_raw(address)
    if not raw_positions:
        return []
    
    # Build positions from raw data
    # API response includes: title, slug, curPrice, avgPrice, size, currentValue, cashPnl, outcome, etc.
    positions = []
    for p in raw_positions:
        try:
            # Extract fields using actual API field names
            condition_id = p.get("conditionId", "")
            outcome = p.get("outcome", "Yes")
            size = float(p.get("size", 0) or 0)
            avg_price = float(p.get("avgPrice", 0) or 0)
            current_price = float(p.get("curPrice", 0) or avg_price)
            current_value = float(p.get("currentValue", 0) or 0)
            cash_pnl = float(p.get("cashPnl", 0) or 0)
            
            # Use value from API or calculate
            value = current_value if current_value > 0 else (size * current_price)
            
            positions.append(Position(
                market_id=p.get("eventId", "") or p.get("marketId", ""),
                condition_id=condition_id,
                outcome=outcome,
                size=size,
                avg_price=avg_price,
                current_price=current_price,
                market_question=p.get("title", ""),  # API provides title directly
                market_slug=p.get("slug"),  # API provides slug directly
                unrealized_pnl=cash_pnl,  # API provides cashPnl directly
                value=value
            ))
        except (ValueError, TypeError, KeyError):
            # Skip malformed position data
            continue
    
    return positions


async def get_portfolio_summary(address: str) -> Optional[PortfolioSummary]:
    """
    Get a comprehensive portfolio summary for an account.
    """
    address = address.lower()
    
    try:
        # Fetch all data in parallel
        positions_task = get_account_positions(address)
        pnl_task = get_account_pnl(address)
        activity_task = get_all_account_activity(address, max_pages=5)
        
        positions, pnl_data, activity = await asyncio.gather(
            positions_task, pnl_task, activity_task
        )
        
        # Calculate portfolio metrics from positions
        total_value = sum(p.value for p in positions) if positions else 0.0
        total_invested = sum(p.size * p.avg_price for p in positions) if positions else 0.0
        unrealized_pnl = sum(p.unrealized_pnl for p in positions) if positions else 0.0
        
        # From P&L data
        realized_pnl = 0.0
        if pnl_data:
            try:
                if isinstance(pnl_data, list):
                    realized_pnl = sum(float(p.get("realized", 0) or 0) for p in pnl_data)
                elif isinstance(pnl_data, dict):
                    realized_pnl = float(pnl_data.get("realized", 0) or 0)
            except (ValueError, TypeError):
                pass
        
        total_pnl = realized_pnl + unrealized_pnl
        
        # Calculate win rate from activity
        wins = 0
        losses = 0
        volume = 0.0
        markets_traded = set()
        
        for a in activity:
            try:
                trade_type = a.get("type", "")
                if trade_type in ["sell", "redeem"]:
                    # Check if profitable
                    pnl = float(a.get("pnl", 0) or 0)
                    if pnl > 0:
                        wins += 1
                    elif pnl < 0:
                        losses += 1
                
                # Track volume
                amount = float(a.get("amount", 0) or a.get("value", 0) or 0)
                volume += amount
                
                # Track markets
                cid = a.get("conditionId") or a.get("condition_id", "")
                if cid:
                    markets_traded.add(cid)
            except (ValueError, TypeError):
                continue
        
        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0
        
        return PortfolioSummary(
            total_value=total_value,
            total_invested=total_invested,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            win_rate=win_rate,
            total_trades=len(activity),
            markets_traded=len(markets_traded),
            volume_traded=volume,
            positions_count=len(positions)
        )
    except Exception:
        return None


# ============================================================================
# Utility Functions
# ============================================================================

def generate_market_link(condition_id: str = "", slug: str = "") -> str:
    """Generate a Polymarket market link."""
    if slug:
        return f"https://polymarket.com/event/{slug}"
    elif condition_id:
        return f"https://polymarket.com/markets/{condition_id}"
    return "https://polymarket.com"


def generate_profile_link(address: str) -> str:
    """Generate a Polymarket profile link."""
    return f"https://polymarket.com/profile/{address.lower()}"
