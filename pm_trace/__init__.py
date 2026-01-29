"""PM Trace - Polymarket Account Forensics Tool

A comprehensive tool for analyzing Polymarket accounts including:
- Funding source tracing
- Cross-chain bridge decoding
- Sibling account detection
- Outbound funding analysis
- Portfolio and position tracking
- Source classification
"""

__version__ = "0.2.0"

from .tracer import (
    trace_account,
    TraceResult,
    FundingSource,
    SiblingAccount,
    FundedAccount,
    TradingBehavior,
    export_to_dict,
)

from .polymarket import (
    is_polymarket_account,
    get_account_profile,
    get_account_positions,
    get_portfolio_summary,
    Position,
    PortfolioSummary,
    MarketInfo,
)

from .blockchain import (
    get_funding_sources,
    get_funded_addresses,
    get_wallet_info,
    trace_funding_origin,
    TokenTransfer,
    WalletInfo,
    FundingChain,
)

from .relay import (
    decode_relay_transaction,
    RelayOrigin,
)

from .config import (
    get_polygonscan_api_key,
    save_api_key,
    get_address_label,
    get_address_type,
)

__all__ = [
    # Main
    "trace_account",
    "TraceResult",
    
    # Data classes
    "FundingSource",
    "SiblingAccount", 
    "FundedAccount",
    "TradingBehavior",
    "Position",
    "PortfolioSummary",
    "MarketInfo",
    "TokenTransfer",
    "WalletInfo",
    "FundingChain",
    "RelayOrigin",
    
    # Functions
    "is_polymarket_account",
    "get_account_profile",
    "get_account_positions",
    "get_portfolio_summary",
    "get_funding_sources",
    "get_funded_addresses",
    "get_wallet_info",
    "trace_funding_origin",
    "decode_relay_transaction",
    "get_polygonscan_api_key",
    "save_api_key",
    "get_address_label",
    "get_address_type",
    "export_to_dict",
]
