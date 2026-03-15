# Satoshi Sensor

[🇩🇪 Deutsch](#deutsch) | [🇬🇧 English](#english)

---

## Deutsch

Home Assistant Custom Integration zur Überwachung von Bitcoin-Wallet-Guthaben — unterstützt sowohl Einzeladressen als auch Hardware Wallets (HD Wallets via xpub).

### Funktionen

- **Einzelne Adressen** oder ganze **HD Wallets via xpub/ypub/zpub** hinzufügen
- Ein Config Entry pro Wallet (einzeln hinzufügen/entfernen)
- **5 Sensoren pro Einzeladresse**, **6 Sensoren pro HD Wallet**:
  - **Balance (Satoshi)** — bestätigtes Guthaben in Satoshi
  - **Balance (BTC)** — bestätigtes Guthaben in BTC
  - **Wert** — Fiat-Wert in der konfigurierten Währung (EUR, USD, CHF, GBP)
  - **BTC Preisänderung 24h** — Preisänderung in % über 24 Stunden
  - **Unbestätigtes Guthaben** — ausstehende unbestätigte Transaktionen in Satoshi
  - **Aktive Adressen** *(nur HD Wallet)* — Anzahl Adressen mit Transaktionshistorie
- HD-Wallet-Sensor zeigt alle Einzeladressen mit Guthaben als Sensor-Attribute
- Konfigurierbares Aktualisierungsintervall (Standard: 5 min, Minimum: 1 min)
- Datenquellen: [mempool.space](https://mempool.space) (Guthaben) und [CoinGecko](https://coingecko.com) (Preis)
- Kein API-Key erforderlich
- Verfügbar in Deutsch und Englisch

### Installation

#### Via HACS (empfohlen)

1. Dieses Repository als [Custom Repository](https://hacs.xyz/docs/faq/custom_repositories/) in HACS hinzufügen:
   - Kategorie: **Integration**
   - URL: `https://github.com/chholzin/ha-satoshi-sensor`
2. **Satoshi Sensor** in HACS installieren
3. Home Assistant neu starten

#### Manuell

1. `custom_components/satoshi_sensor/` in das HA-Verzeichnis `config/custom_components/` kopieren
2. Home Assistant neu starten

### Konfiguration

#### Einzelne Adresse

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Nach **Satoshi Sensor** suchen
3. Typ **address** auswählen
4. Bitcoin-Adresse und optional ein Label eingeben
5. Fiat-Währung wählen (Standard: EUR)

#### HD Wallet (Hardware Wallet via xpub)

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Nach **Satoshi Sensor** suchen
3. Typ **xpub** auswählen
4. Extended Public Key (`xpub`, `ypub` oder `zpub`) und optional ein Label eingeben
5. Fiat-Währung wählen

Die Integration leitet automatisch alle Adressen ab und scannt sie mit Gap Limit 20 (BIP44-Standard). Bis zu 5 parallele API-Anfragen.

#### Wo findet man den xpub?

| Hardware Wallet | Pfad |
|-----------------|------|
| **Ledger** | Ledger Live → Konto → Einstellungen → Erweiterter Modus → Kontoschlüssel |
| **Trezor** | Trezor Suite → Konto → Details → Öffentlicher Schlüssel |
| **Coldcard** | Advanced → View XPub |
| **BitBox02** | BitBoxApp → Konto → Konto-Info → Extended Public Key |

#### Unterstützte Key-Typen

| Präfix | Standard | Adressformat |
|--------|----------|--------------|
| `xpub` | BIP44 | Legacy (`1...`) |
| `ypub` | BIP49 | P2SH-SegWit (`3...`) |
| `zpub` | BIP84 | Native SegWit (`bc1q...`) |

> **Taproot (BIP86) xpub noch nicht unterstützt.**
> Für Taproot-HD-Wallets existiert kein standardisierter Key-Präfix — die meisten Wallets exportieren BIP86-Account-Keys als normales `xpub`, was von BIP44 nicht unterscheidbar ist. Taproot-**Einzeladressen** (`bc1p...`) funktionieren dagegen problemlos.

### Unterstützte Adressformate (Einzeladress-Modus)

- Legacy (`1...`)
- Pay-to-Script-Hash (`3...`)
- Native SegWit / Bech32 (`bc1q...`)
- Taproot / Bech32m (`bc1p...`)

### Einstellungen

Über den **Konfigurieren**-Button der Integration änderbar:

- **Fiat-Währung** — EUR, USD, CHF, GBP
- **Aktualisierungsintervall** — in Sekunden (Minimum: 60)

Änderungen werden sofort übernommen (die Integration lädt automatisch neu).

---

## English

Home Assistant custom integration to monitor Bitcoin wallet balances — supports both single addresses and hardware wallets (HD wallets via xpub).

### Features

- Add **single addresses** or entire **HD wallets via xpub/ypub/zpub**
- One config entry per wallet (easy to add/remove individually)
- **5 sensors per single address**, **6 sensors per HD wallet**:
  - **Balance (Satoshi)** — confirmed balance in satoshis
  - **Balance (BTC)** — confirmed balance in BTC
  - **Value** — fiat value in your configured currency (EUR, USD, CHF, GBP)
  - **BTC Price Change 24h** — 24-hour BTC price change in %
  - **Unconfirmed Balance** — pending unconfirmed balance in satoshis
  - **Active Addresses** *(HD wallet only)* — number of addresses with transaction history
- HD wallet sensor shows all individual address balances as state attributes
- Configurable update interval (default: 5 min, minimum: 1 min)
- Data sourced from [mempool.space](https://mempool.space) (balance) and [CoinGecko](https://coingecko.com) (price)
- No API key required
- Available in English and German

### Installation

#### Via HACS (recommended)

1. Add this repository as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) in HACS:
   - Category: **Integration**
   - URL: `https://github.com/chholzin/ha-satoshi-sensor`
2. Install **Satoshi Sensor** from HACS
3. Restart Home Assistant

#### Manual

1. Copy `custom_components/satoshi_sensor/` into your HA `config/custom_components/` directory
2. Restart Home Assistant

### Configuration

#### Single Address

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Satoshi Sensor**
3. Select type: **address**
4. Enter your Bitcoin address and an optional label
5. Select your preferred fiat currency (default: EUR)

#### HD Wallet (Hardware Wallet via xpub)

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Satoshi Sensor**
3. Select type: **xpub**
4. Enter your Extended Public Key (`xpub`, `ypub`, or `zpub`) and an optional label
5. Select your preferred fiat currency

The integration will automatically derive all addresses and scan them with a gap limit of 20 (BIP44 standard). Up to 5 parallel API requests are used.

#### Where to find your xpub

| Hardware Wallet | Path |
|-----------------|------|
| **Ledger** | Ledger Live → Account → Settings → Advanced → Account key |
| **Trezor** | Trezor Suite → Account → Details → Public key |
| **Coldcard** | Advanced → View XPub |
| **BitBox02** | BitBoxApp → Account → Account Info → Extended Public Key |

#### Supported key types

| Prefix | Standard | Address format |
|--------|----------|----------------|
| `xpub` | BIP44 | Legacy (`1...`) |
| `ypub` | BIP49 | P2SH-SegWit (`3...`) |
| `zpub` | BIP84 | Native SegWit (`bc1q...`) |

> **Taproot (BIP86) xpub not yet supported.**
> There is no standardized key prefix for Taproot HD wallets — most wallets export BIP86 account keys as a regular `xpub`, which is indistinguishable from BIP44. Taproot **single addresses** (`bc1p...`) work fine however.

### Supported address formats (single address mode)

- Legacy (`1...`)
- Pay-to-Script-Hash (`3...`)
- Native SegWit / Bech32 (`bc1q...`)
- Taproot / Bech32m (`bc1p...`)

### Options

Go to the integration's **Configure** button to change:

- **Fiat currency** — EUR, USD, CHF, GBP
- **Update interval** — in seconds (minimum: 60)

Changes take effect immediately after saving (the integration reloads automatically).
