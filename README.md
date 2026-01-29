# PM Trace - Polymarket Account Forensics Tool

Comprehensive forensics tool for analyzing Polymarket accounts. Track funding sources, identify coordinated accounts, decode cross-chain bridges, and get complete portfolio analysis.

## Features

### 🔍 Funding Analysis
- **Trace funding sources** - Identify all wallets that sent USDC to an account
- **Multi-hop origin tracing** - Follow the money back through multiple hops to find the ultimate source
- **Source classification** - Automatically identify CEX, DEX, bridge, and known entity addresses

### 🌉 Cross-Chain Detection
- **Relay bridge decoding** - Automatically decode Relay.link transactions to find original sender
- **Cross-chain origin identification** - See which chain and address initiated the funding

### 🔗 Account Linking
- **Sibling detection** - Find other Polymarket accounts funded by the same source
- **Outbound analysis** - Discover accounts that the target has funded
- **Coordination detection** - Flag potential multi-account operations

### 📊 Portfolio Analysis
- **Current positions** - View all open positions with P&L
- **Portfolio summary** - Total value, win rate, volume traded
- **Trading behavior** - Markets traded, account age, activity level

### 🏷️ Classification System
Accounts are automatically classified based on detected signals:

| Classification | Meaning |
|---------------|---------|
| 🚨 Likely Coordinated | Multiple linked PM accounts detected |
| ⚠️ Likely Sophisticated | Relay + concentrated + large size |
| ⚠️ Cross-chain Funder | Bridge funding, needs investigation |
| ⚠️ Fresh + Large | New account with significant capital |
| ℹ️ Some Linked Accounts | 1-2 siblings, worth checking |
| ✅ Likely Retail | No siblings, no bridge, diversified |

## Quick Start

```bash
# Install
cd pm-trace
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Configure API key (free at https://polygonscan.com/apis)
pm-trace config --api-key YOUR_KEY

# Full analysis
pm-trace analyze 0x1234567890abcdef...

# Quick check (faster, less detail)
pm-trace quick 0x1234567890abcdef...

# JSON output for programmatic use
pm-trace analyze 0x1234... --json-output
```

## Commands

### `pm-trace analyze ADDRESS`

Full comprehensive analysis of a Polymarket account.

```bash
# Full analysis with all features
pm-trace analyze 0x1234...

# With Polymarket profile URL
pm-trace analyze https://polymarket.com/profile/0x1234...

# Skip sibling detection (faster)
pm-trace analyze 0x1234... --shallow

# Skip origin tracing
pm-trace analyze 0x1234... --no-origin

# Skip outbound funding check
pm-trace analyze 0x1234... --no-outbound

# Skip positions (faster)
pm-trace analyze 0x1234... --no-positions

# JSON output
pm-trace analyze 0x1234... --json-output

# Adjust sibling check limit
pm-trace analyze 0x1234... --max-siblings 50

# Adjust origin tracing depth
pm-trace analyze 0x1234... --max-hops 5
```

### `pm-trace quick ADDRESS`

Quick check - just funding sources and classification. Faster than full analyze.

```bash
pm-trace quick 0x1234...
```

### `pm-trace config`

Save your API key for future use.

```bash
pm-trace config --api-key YOUR_KEY
```

### `pm-trace links ADDRESS`

Generate investigation links for an address.

```bash
pm-trace links 0x1234...
# Outputs links to Polymarket, Arkham, Polygonscan, Relay, etc.
```

## Example Output

```
╔══════════════════════════════════════════════════════════════════════════════╗
║ PM Trace Report - ✅ Polymarket Account                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Address: 0x1234567890abcdef1234567890abcdef12345678
Username: whale_trader

Quick Links:
  • Polymarket: https://polymarket.com/profile/0x1234...
  • Arkham: https://platform.arkhamintelligence.com/explorer/address/0x1234...
  • Polygonscan: https://polygonscan.com/address/0x1234...

╭─────────────────────────── Classification ────────────────────────────────────╮
│ ⚠️  Cross-chain Funder - Review Needed                                        │
╰───────────────────────────────────────────────────────────────────────────────╯

Signals:
  🌉 Relay bridge funding: $200,000 (40%)
  🔍 Decoded 2 cross-chain origin(s)
  📤 Funded 2 other PM account(s)
  📈 High activity: 150+ trades
  💰 Whale funding: $500,000
  🔀 Multiple funding sources: 4 wallets

────────────────────────── Portfolio Summary ───────────────────────────────────

  Portfolio Value    $125,432.00    Positions      8
  Unrealized P&L     +$12,345.00    Realized P&L   +$45,678.00
  Win Rate           67.5%          Total Trades   150
  Markets Traded     12             Volume         $890,000

─────────────────────── Current Positions (8) ──────────────────────────────────

  Market                                Side   Size     Avg     Current  Value      P&L
  Will Trump win 2024?                  Yes    50,000   $0.52   $0.58    $29,000    +$3,000
  Fed rate cut by March?                No     30,000   $0.35   $0.28    $8,400     +$2,100
  ...

─────────────────────────── Funding Analysis ───────────────────────────────────

Total Funded: $500,000.00
First funded: 2024-06-15

  Source          Amount         Type           Label              Txs   First Date
  0x4d97dc...     $200,000.00    🌉 Relay       Relay.link         2     2024-06-15
  0xf89d7b...     $150,000.00    🏦 CEX         Binance Hot        5     2024-07-01
  0x123456...     $100,000.00    💼 Wallet      -                  3     2024-08-15
  0xabcdef...     $50,000.00     💼 Wallet      -                  1     2024-09-01

🌉 Cross-Chain Funding (Relay Bridge):
  • $100,000 from Ethereum
    Origin: 0xabcd...1234
    Arkham: https://platform.arkhamintelligence.com/explorer/address/0xabcd...

──────────────── Accounts Funded By This Wallet - 2 PM accounts ────────────────

Total Sent to Others: $25,000.00

  Recipient       Amount Sent    First Transfer   Polymarket Link
  0x9876ef...     $15,000.00     2024-08-20       https://polymarket.com/profile/0x9876...
  0x5432ab...     $10,000.00     2024-09-05       https://polymarket.com/profile/0x5432...

╭───────────────────────── Investigation Tips ──────────────────────────────────╮
│ 1. Decode Relay transactions to find original sender on source chain         │
│ 2. Investigate funded PM accounts for sybil behavior                         │
│ 3. Check which specific markets they're concentrated in                      │
╰───────────────────────────────────────────────────────────────────────────────╯
```

## Known Address Database

PM Trace includes a database of known addresses:

### CEX Addresses
- Binance, Coinbase, Kraken, OKX, Bybit, KuCoin, Crypto.com, Gemini, Huobi, Gate.io, Bitfinex

### Bridge Addresses
- Relay.link, Across Protocol, Stargate, Hop Protocol, Synapse, Celer cBridge

### DEX Addresses
- Uniswap, 1inch, 0x Protocol, ParaSwap, SushiSwap, QuickSwap, Balancer, Curve, AAVE, Compound

## API Keys Required

| API | Required | How to Get |
|-----|----------|------------|
| Etherscan V2 | ✅ Yes | Free at [polygonscan.com/apis](https://polygonscan.com/apis) |
| Polymarket | ❌ No | Public API, no key needed |
| Relay.link | ❌ No | Public API, no key needed |
| Arkham | ❌ No | Use web interface for labels |

The Etherscan V2 API key works for Polygon and 60+ other EVM chains.

## Programmatic Usage

```python
import asyncio
from pm_trace import trace_account, export_to_dict

async def main():
    api_key = "your_polygonscan_api_key"
    address = "0x1234567890abcdef..."
    
    result = await trace_account(
        api_key,
        address,
        deep=True,
        trace_origin=True,
        check_outbound=True,
        include_positions=True,
    )
    
    print(f"Classification: {result.classification}")
    print(f"Total Funded: ${result.total_funded:,.2f}")
    print(f"Sibling PM Accounts: {result.sibling_count}")
    print(f"Funded PM Accounts: {result.funded_pm_count}")
    
    # Export to JSON
    data = export_to_dict(result)
    
asyncio.run(main())
```

## Investigation Workflow

1. **Run full analysis** on the target account
2. **Check classification** and signals for red flags
3. **Review funding sources** - any from bridges or unknown wallets?
4. **Check Arkham** for labels on funding wallets
5. **Decode Relay transactions** using provided links
6. **Review sibling accounts** - do they trade similarly?
7. **Check outbound funding** - is this account funding others?
8. **Examine positions** - concentrated in one market?

## Contributing

Contributions welcome! Please submit issues and pull requests.

## License

MIT
