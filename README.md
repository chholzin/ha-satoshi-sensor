# Satoshi Sensor

A Home Assistant custom integration to monitor Bitcoin wallet balances — supports both single addresses and hardware wallets (HD wallets via xpub).

## Features

- Add **single addresses** or entire **HD wallets via xpub/ypub/zpub**
- One config entry per wallet (easy to add/remove individually)
- **5 sensors per single address**, **6 sensors per HD wallet**:
  - **Balance (Satoshi)** — confirmed balance in satoshis
  - **Balance (BTC)** — confirmed balance in BTC
  - **Wert** — fiat value in your configured currency (EUR, USD, CHF, GBP)
  - **BTC Preisänderung 24h** — 24-hour BTC price change in %
  - **Unbestätigtes Guthaben** — pending unconfirmed balance in satoshis
  - **Aktive Adressen** *(HD wallet only)* — number of addresses with transaction history
- HD wallet sensor shows all individual address balances as state attributes
- Configurable update interval (default: 5 min, minimum: 1 min)
- Data sourced from [mempool.space](https://mempool.space) (balance) and [CoinGecko](https://coingecko.com) (price)
- No API key required
- Available in English and German

## Installation

### Via HACS (recommended)

1. Add this repository as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) in HACS:
   - Category: **Integration**
   - URL: `https://github.com/chholzin/ha-satoshi-sensor`
2. Install **Satoshi Sensor** from HACS
3. Restart Home Assistant

### Manual

1. Copy `custom_components/satoshi_sensor/` into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

### Single Address

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Satoshi Sensor**
3. Select type: **address**
4. Enter your Bitcoin address and an optional label
5. Select your preferred fiat currency (default: EUR)

### HD Wallet (Hardware Wallet via xpub)

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Satoshi Sensor**
3. Select type: **xpub**
4. Enter your Extended Public Key (`xpub`, `ypub`, or `zpub`) and an optional label
5. Select your preferred fiat currency

The integration will automatically derive all addresses and scan them with a gap limit of 20 (BIP44 standard). All addresses are scanned with up to 5 parallel requests.

#### Where to find your xpub

| Hardware Wallet | Path |
|-----------------|------|
| **Ledger** | Ledger Live → Account → Settings → Advanced → Account key |
| **Trezor** | Trezor Suite → Account → Details → Public key |
| **Coldcard** | Advanced → View XPub |

#### Supported key types

| Prefix | Standard | Address format |
|--------|----------|----------------|
| `xpub` | BIP44 | Legacy (`1...`) |
| `ypub` | BIP49 | P2SH-SegWit (`3...`) |
| `zpub` | BIP84 | Native SegWit (`bc1...`) |

## Supported address formats (single address mode)

- Legacy (`1...`)
- Pay-to-Script-Hash (`3...`)
- Native SegWit / Bech32 (`bc1...`)

## Options

Go to the integration's **Configure** button to change:

- **Fiat currency** — EUR, USD, CHF, GBP
- **Update interval** — in seconds (minimum: 60)

Changes take effect immediately after saving (the integration reloads automatically).
