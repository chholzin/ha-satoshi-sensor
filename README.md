# Satoshi Sensor

A Home Assistant custom integration to monitor Bitcoin wallet balances.

## Features

- Add any number of Bitcoin wallet addresses via the UI
- One config entry per address (easy to add/remove individually)
- Three sensors per address:
  - **Balance (Satoshi)** — raw satoshi amount
  - **Balance (BTC)** — amount in BTC
  - **Wert** — fiat value in your configured currency (EUR, USD, CHF, GBP)
- Data sourced from [mempool.space](https://mempool.space) (balance) and [CoinGecko](https://coingecko.com) (price)
- Updates every 5 minutes, no API key required

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

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Satoshi Sensor**
3. Enter your Bitcoin address and an optional label
4. Select your preferred fiat currency (default: EUR)

Repeat for each wallet address you want to monitor.

## Supported address formats

- Legacy (`1...`)
- Pay-to-Script-Hash (`3...`)
- Native SegWit / Bech32 (`bc1...`)

## Changing the currency

Go to the integration's **Configure** option and select a different currency. The integration will reload automatically.
