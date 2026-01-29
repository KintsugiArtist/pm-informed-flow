"""Configuration management for PM Trace"""

import os
from pathlib import Path
from typing import Optional

# ============================================================================
# Token Addresses (Polygon)
# ============================================================================
USDC_POLYGON = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC on Polygon
USDC_E_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # Bridged USDC.e on Polygon

# ============================================================================
# Known Bridge Addresses
# ============================================================================
RELAY_ADDRESSES = {
    "0x0000000000a39bb272e79075ade125fd351887ac": "Relay.link",
    "0xf70da97812cb96acdf810712aa562db8dfa3dbef": "Relay.link Executor",
}

BRIDGE_ADDRESSES = {
    # Relay
    **RELAY_ADDRESSES,
    # Across Protocol
    "0x9295ee1d8c5b022be115a2ad3c30c72e34e7f096": "Across Bridge",
    "0x69b5c72837769ef1e7c164abc6515dcff217f920": "Across Spoke Pool",
    # Stargate
    "0x45a01e4e04f14f7a4a6880e7d2d2f80ee0f0e3e9": "Stargate Router",
    "0x2f6f07cdcf3588944bf4c42ac74ff24bf56e7590": "Stargate USDC Pool",
    # Hop Protocol
    "0x58c61ae7293a2967f5f858d0bf5e4e6e75e17cb9": "Hop USDC Bridge",
    # Synapse
    "0x1c6ae197ff4bf7ba96c66c5fd64cb22450af9cc8": "Synapse Bridge",
    # Celer
    "0x88dcdc47d2f83a99cf0000fdf667a468bb958a78": "Celer cBridge",
    # Multichain (defunct but historical)
    "0x2ef4a574b72e1f555f5f5ca5ef1e3e3e4a6d2a9e": "Multichain Router",
}

# ============================================================================
# Known CEX Addresses (Polygon)
# ============================================================================
CEX_ADDRESSES = {
    # Binance
    "0xe7804c37c13166ff0b37f5ae0bb07a3aebb6e245": "Binance Hot Wallet",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance Cold Wallet",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance Hot Wallet 2",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance Deposit",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance Deposit 2",
    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase Hot Wallet",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase Cold Wallet",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase Deposit",
    "0x3cd751e6b0078be393132286c442345e5dc49699": "Coinbase Deposit 2",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase Commerce",
    # Kraken
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken Hot Wallet",
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": "Kraken Hot Wallet 2",
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX Hot Wallet",
    "0x98ec059dc3adfbdd63429454aeb0c990fba4a128": "OKX Hot Wallet 2",
    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit Hot Wallet",
    # KuCoin
    "0xf16e9b0d03470827a95cdfd0cb8a8a3b46969b91": "KuCoin Hot Wallet",
    # Crypto.com
    "0x6262998ced04146fa42253a5c0af90ca02dfd2a3": "Crypto.com Hot Wallet",
    "0x46340b20830761efd32be78e2bc4da185f90bd98": "Crypto.com Hot Wallet 2",
    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": "Gemini Hot Wallet",
    # Huobi/HTX
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": "Huobi Hot Wallet",
    "0x18709e89bd403f470088abdacebe86cc60dda12e": "Huobi Hot Wallet 2",
    # Gate.io
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io Hot Wallet",
    # Bitfinex
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": "Bitfinex Hot Wallet",
    # FTX (historical)
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2": "FTX Hot Wallet (defunct)",
}

# ============================================================================
# Known DEX / DeFi Addresses (Polygon)
# ============================================================================
DEX_ADDRESSES = {
    # Uniswap
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router 2",
    "0x4c60051384bd2d3c01bfc845cf5f4b44bcbe9de5": "Uniswap Universal Router",
    # 1inch
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router V5",
    "0x1111111254fb6c44bac0bed2854e76f90643097d": "1inch Router V4",
    # 0x Protocol
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange Proxy",
    # ParaSwap
    "0xdef171fe48cf0115b1d80b88dc8eab59176fee57": "ParaSwap Router",
    # SushiSwap
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506": "SushiSwap Router",
    # QuickSwap
    "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff": "QuickSwap Router",
    "0xf5b509bb0909a69b1c207e495f687a596c168e12": "QuickSwap Router V3",
    # Balancer
    "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault",
    # Curve
    "0x094d12e5b541784701fd8d65f11fc0598fbc6332": "Curve Registry",
    # AAVE
    "0x794a61358d6845594f94dc1db02a252b5b4814ad": "AAVE V3 Pool",
    "0x8dff5e27ea6b7ac08ebfdf9eb090f32ee9a30fcf": "AAVE V2 Pool",
    # Compound
    "0xf25212e676d1f7f89cd72ffee66158f541246445": "Compound III",
}

# ============================================================================
# Known Funds / Whales / Market Makers
# ============================================================================
KNOWN_ENTITIES = {
    # Polymarket-related
    "0x4b87b7b0c5a48b0e8f9e2c88f3cb93f4e2a8d1e3": "Polymarket: Treasury",
    # Known market makers (examples - update with real addresses)
    "0x9e927c02c9eadab63939b5762ce8e5e3c3c3bb74": "Wintermute Trading",
    "0x00000000000a9e8c4f4ec4e4e4e4e4e4e4e4e4e4": "Jump Trading",
    # Other prediction markets
    "0x4bd2a30435e6624ccc7b69e31b8f4a5f5f5f5f5f": "Kalshi",
}

# ============================================================================
# Protocol Contracts (should be excluded from sibling checks)
# ============================================================================
PROTOCOL_CONTRACTS = {
    # Polymarket CTF Exchange
    "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e": "Polymarket CTF Exchange",
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC.e Token",
    "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": "USDC Token",
    # Add more protocol addresses to exclude
}

# ============================================================================
# API Endpoints
# ============================================================================
PM_DATA_API = "https://data-api.polymarket.com"
PM_GAMMA_API = "https://gamma-api.polymarket.com"
PM_CLOB_API = "https://clob.polymarket.com"

# Relay.link API
RELAY_API = "https://api.relay.link"

# Etherscan V2 (multi-chain)
ETHERSCAN_V2_API = "https://api.etherscan.io/v2/api"

# Chain IDs
CHAIN_IDS = {
    "ethereum": 1,
    "polygon": 137,
    "arbitrum": 42161,
    "optimism": 10,
    "base": 8453,
}


# ============================================================================
# Helper Functions
# ============================================================================

def get_all_known_addresses() -> dict[str, str]:
    """Get all known addresses with their labels."""
    all_known = {}
    all_known.update({k.lower(): v for k, v in BRIDGE_ADDRESSES.items()})
    all_known.update({k.lower(): v for k, v in CEX_ADDRESSES.items()})
    all_known.update({k.lower(): v for k, v in DEX_ADDRESSES.items()})
    all_known.update({k.lower(): v for k, v in KNOWN_ENTITIES.items()})
    all_known.update({k.lower(): v for k, v in PROTOCOL_CONTRACTS.items()})
    return all_known


def get_address_label(address: str) -> Optional[str]:
    """Get label for a known address, or None if unknown."""
    address = address.lower()
    all_known = get_all_known_addresses()
    return all_known.get(address)


def get_address_type(address: str) -> str:
    """Get the type of a known address."""
    address = address.lower()
    
    if address in {k.lower() for k in BRIDGE_ADDRESSES}:
        return "bridge"
    if address in {k.lower() for k in CEX_ADDRESSES}:
        return "cex"
    if address in {k.lower() for k in DEX_ADDRESSES}:
        return "dex"
    if address in {k.lower() for k in KNOWN_ENTITIES}:
        return "entity"
    if address in {k.lower() for k in PROTOCOL_CONTRACTS}:
        return "protocol"
    return "unknown"


def is_relay_address(address: str) -> bool:
    """Check if address is a Relay.link address."""
    return address.lower() in {k.lower() for k in RELAY_ADDRESSES}


def is_bridge_address(address: str) -> bool:
    """Check if address is any bridge address."""
    return address.lower() in {k.lower() for k in BRIDGE_ADDRESSES}


def is_cex_address(address: str) -> bool:
    """Check if address is a known CEX address."""
    return address.lower() in {k.lower() for k in CEX_ADDRESSES}


def is_protocol_contract(address: str) -> bool:
    """Check if address is a known protocol contract."""
    return address.lower() in {k.lower() for k in PROTOCOL_CONTRACTS}


# ============================================================================
# API Key Management
# ============================================================================

def get_polygonscan_api_key() -> str:
    """Get Polygonscan API key from environment or config file."""
    key = os.environ.get("POLYGONSCAN_API_KEY")
    if not key:
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
