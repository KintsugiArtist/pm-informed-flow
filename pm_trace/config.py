"""Configuration management for PM Trace"""

import os
from pathlib import Path

# Known contract addresses
USDC_POLYGON = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC on Polygon
USDC_E_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # Bridged USDC.e on Polygon

# Known Relay.link depositor addresses (these are bridge contracts)
RELAY_ADDRESSES = {
    "0x0000000000A39bb272e79075ade125fd351887Ac".lower(): "Relay.link",
    "0xf70da97812cb96acdf810712aa562db8dfa3dbef".lower(): "Relay.link Executor",
}

# Polymarket API endpoints
PM_DATA_API = "https://data-api.polymarket.com"
PM_GAMMA_API = "https://gamma-api.polymarket.com"


def get_polygonscan_api_key() -> str:
    """Get Polygonscan API key from environment or prompt user."""
    key = os.environ.get("POLYGONSCAN_API_KEY")
    if not key:
        # Try loading from .env file in project root
        env_path = Path.home() / ".pm_trace" / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith("POLYGONSCAN_API_KEY="):
                        key = line.strip().split("=", 1)[1]
                        break
    return key or ""


def save_api_key(key: str) -> None:
    """Save API key to user's home directory."""
    config_dir = Path.home() / ".pm_trace"
    config_dir.mkdir(exist_ok=True)
    env_path = config_dir / ".env"
    with open(env_path, "w") as f:
        f.write(f"POLYGONSCAN_API_KEY={key}\n")

