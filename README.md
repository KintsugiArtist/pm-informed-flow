# PM Trace - Polymarket Account Forensics Tool

Track funding sources and identify coordinated/sophisticated accounts on Polymarket.

## What it does

Given a Polymarket account address, PM Trace will:

1. **Find Funding Sources** - Identify all wallets that sent USDC to this account
2. **Detect Relay Bridges** - Flag cross-chain deposits and provide links to decode original sender
3. **Find Sibling Accounts** - Check if the same funder sent money to other Polymarket accounts
4. **Classify the Account** - Estimate if it's retail, sophisticated, or part of a coordinated group

## Quick Start

```bash
# Install
cd pm-informed-flow
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Configure your API key (free at https://polygonscan.com/apis)
pm-trace config --api-key YOUR_KEY

# Analyze an account
pm-trace analyze 0x1234567890abcdef...

# Or use a Polymarket profile URL
pm-trace analyze https://polymarket.com/profile/0x1234...
```

## Commands

### `pm-trace analyze ADDRESS`

Analyze a Polymarket account and trace its funding.

```bash
# Full deep trace (checks sibling accounts)
pm-trace analyze 0x1234...

# Shallow trace (just funding sources, faster)
pm-trace analyze 0x1234... --shallow

# Limit sibling checks for speed
pm-trace analyze 0x1234... --max-siblings 10
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
# Outputs links to Polymarket, Arkham, Polygonscan, Relay
```

## Classification System

### Signals Detected

| Signal | Meaning |
|--------|---------|
| 🌉 Relay Bridge | Funded via cross-chain bridge (harder to trace origin) |
| 🔗 Multiple Siblings | Same funder sent to multiple PM accounts |
| 🆕 Fresh Account | Account is < 7 days old |
| 🎯 Single Market | Only trades in one market (high conviction) |
| 💰 Whale Funding | $100k+ total funding |
| 📈 High Activity | 100+ trades |
| 🔀 Multiple Sources | Funded by 3+ different wallets |

### Classifications

| Classification | Meaning |
|---------------|---------|
| 🚨 Likely Coordinated | 3+ sibling PM accounts from same funder |
| ⚠️ Likely Sophisticated/Punt | Relay funding + concentrated markets + large size |
| ⚠️ Cross-chain Funder | Relay funding detected, needs manual decode |
| ⚠️ Fresh + Large Funding | New account with significant capital |
| ℹ️ Some Linked Accounts | 1-2 siblings, worth investigating |
| ✅ Likely Retail | No siblings, no relay, diversified trading |

## How It Works

### Polymarket Account Detection

PM Trace identifies Polymarket accounts by querying the Polymarket Data API. If an address has trading activity, it's flagged as a PM account.

### The Sibling Detection Strategy

```
┌─────────────────────────────────────────────────────────────┐
│  1. Get USDC inflows to target account                      │
│  2. For each funder (non-Relay):                            │
│     - Get all their outgoing USDC transfers                 │
│     - Check each recipient against PM Data API              │
│     - Flag any that are PM accounts as "siblings"           │
│  3. Aggregate and classify                                  │
└─────────────────────────────────────────────────────────────┘
```

### Relay Bridge Handling

When funding comes from Relay.link (cross-chain bridge):
1. The tool flags it as obfuscated funding
2. Provides direct links to decode the original sender
3. You can then trace that original address on Arkham

## Required API Keys

| API | Required | How to Get |
|-----|----------|------------|
| Etherscan V2 | ✅ Yes | Free at [polygonscan.com/apis](https://polygonscan.com/apis) |
| Polymarket | ❌ No | Public API, no key needed |
| Arkham | ❌ No | Use web interface for labels |

The Etherscan V2 API key works for Polygon and 60+ other EVM chains.

## Investigation Workflow

After running `pm-trace analyze`:

1. **Check Arkham** for the funding wallet - see if it's labeled (CEX, Fund, etc.)
2. **Decode Relay transactions** using the provided links to find the original sender
3. **Check sibling account activity** - do they all bet on the same markets?
4. **Review timing** - did all siblings enter the same position around the same time?

## Example Output

```
╔════════════════════════════════════════════════════════════════════════════╗
║ PM Trace Report - ✅ Polymarket Account                                    ║
╚════════════════════════════════════════════════════════════════════════════╝

Address: 0x6a72f61820b26b1fe4d956e17b6dc2a1ea3033ee

╭─────────────────────────── Classification ───────────────────────────────╮
│ ⚠️  Cross-chain Funder - Review Needed                                    │
╰──────────────────────────────────────────────────────────────────────────╯

Signals:
  🌉 Relay bridge funding: $199,950 (33%)
  ℹ️  1 other PM account from same funder
  📈 High activity: 200+ trades
  💰 Whale funding: $600,467
  🔀 Multiple funding sources: 4 wallets

Funding Summary: $600,466.64 total
First funded: 2025-06-23

  Source                   Amount   Type                  Txs   First Date  
 ──────────────────────────────────────────────────────────────────────────
  0x4d97dc...476045   $301,061.16   Wallet                 35   2025-06-26  
  0xf70da9...a3dbef   $199,950.03   Relay.link Executor     2   2025-09-04  

🌉 Relay Transactions (decode to find original sender):
  • $100,000.00 on 2025-09-04
    https://relay.link/transaction/0xb8e676dab9bdb4...

🔗 Connected Polymarket Accounts (1 found):
  Address              Funded   Polymarket Link                                 
 ──────────────────────────────────────────────────────────────────────────────
  0x4ec4a2...b079da   $234.00   https://polymarket.com/profile/0x4ec4a2...
```

## License

MIT
