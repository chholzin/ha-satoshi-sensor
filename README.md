# Satoshi Sensor

[🇩🇪 Deutsch](#deutsch) | [🇬🇧 English](#english)

---

## Deutsch

Home Assistant Custom Integration zur Überwachung von Bitcoin-Wallet-Guthaben — unterstützt sowohl Einzeladressen als auch Hardware Wallets (HD Wallets via xpub).

### Funktionen

- **Einzelne Adressen** oder ganze **HD Wallets via xpub/ypub/zpub** hinzufügen
- Ein Config Entry pro Wallet (einzeln hinzufügen/entfernen)
- **Portfolio Total** — wird automatisch als eigener Eintrag angelegt und zeigt die **Gesamtsumme aller Wallets**:
  - **Total Balance (Satoshi)** — Summe aller Satoshi-Guthaben
  - **Total Balance (BTC)** — Summe aller BTC-Guthaben
  - **Total Value** — Gesamtwert in Fiat (nur wenn alle Wallets dieselbe Währung nutzen)
- **7 Sensoren pro Eintrag** (Einzeladresse und HD Wallet):
  - **Balance (Satoshi)** — bestätigtes Guthaben in Satoshi
  - **Balance (BTC)** — bestätigtes Guthaben in BTC
  - **Value** — Fiat-Wert in der konfigurierten Währung (EUR, USD, CHF, GBP)
  - **BTC Price Change 24h** — Preisänderung in % über 24 Stunden
  - **Unconfirmed Balance** — ausstehende unbestätigte Transaktionen in Satoshi
  - **Transactions** — Gesamtzahl der Transaktionen
  - **Address** *(Einzeladresse)* — die Bitcoin-Adresse als Sensorwert
  - **Active Addresses** *(HD Wallet)* — Anzahl Adressen mit Transaktionshistorie
- Gerätename enthält automatisch den Adresstyp (Legacy / SegWit / Native SegWit / Taproot)
- HD-Wallet: alle verwendeten Adressen mit Guthaben als Sensor-Attribute abrufbar
- HD-Wallet: scannt **externe und Change-Chain** (m/.../0 und m/.../1) für vollständige Salden
- HD-Wallet: **Adress-Cache** über HA-Storage — schnellerer Neustart ohne vollständigen Rescan
- Konfigurierbares Aktualisierungsintervall (Standard: 5 min, Minimum: 1 min)
- **Eigene Mempool-API-URL** konfigurierbar (z. B. Umbrel, RaspiBlitz oder eigene Instanz)
- **Schneller Neustart** — zuletzt abgerufene Werte werden sofort aus dem HA-Storage wiederhergestellt, API-Abruf läuft im Hintergrund
- **Exponential Backoff** bei API-Fehlern (Rate Limits, Server-Fehler) — verdoppelt das Intervall bis max. 4×
- **Diagnostik** über Home Assistant → Geräte & Dienste → Satoshi Sensor → Diagnostik herunterladen
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

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Nach **Satoshi Sensor** suchen
3. Bitcoin-Adresse **oder** Extended Public Key eingeben — die Integration erkennt den Typ automatisch
4. Optional ein Label vergeben
5. Fiat-Währung wählen (Standard: EUR)

Die Integration leitet bei xpub/ypub/zpub automatisch alle Adressen ab — sowohl auf der **externen Chain** (Empfangsadressen, m/.../0) als auch auf der **Change-Chain** (Wechselgeld, m/.../1) — und scannt sie mit Gap Limit 20 (BIP44-Standard). Bis zu 5 parallele API-Anfragen. Bereits gescannte Adressen werden gecacht und beim nächsten Neustart sofort abgefragt.

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

> **Hinweis:** xpub, ypub und zpub repräsentieren verschiedene BIP32-Accounts mit unterschiedlichen Schlüsseln (m/44'/0'/0', m/49'/0'/0', m/84'/0'/0'). Sie lassen sich kryptographisch **nicht** ineinander umrechnen. Wer mehrere Adresstypen überwachen möchte, muss den jeweiligen Key separat aus der Hardware-Wallet exportieren und als eigenen Eintrag hinzufügen.

> **Taproot (BIP86) xpub noch nicht unterstützt.**
> Für Taproot-HD-Wallets existiert kein standardisierter Key-Präfix — die meisten Wallets exportieren BIP86-Account-Keys als normales `xpub`, was von BIP44 nicht unterscheidbar ist. Taproot-**Einzeladressen** (`bc1p...`) funktionieren dagegen problemlos.

### Benennung von Geräten und Entitäten

Der Adresstyp wird automatisch aus der Eingabe erkannt und in den Gerätenamen aufgenommen:

| Eingabe | Gerätename |
|---------|-----------|
| `1...` | `BTC Wallet [Label] · Legacy` |
| `3...` | `BTC Wallet [Label] · SegWit` |
| `bc1q...` | `BTC Wallet [Label] · Native SegWit` |
| `bc1p...` | `BTC Wallet [Label] · Taproot` |
| `xpub...` | `BTC Wallet [Label] · Legacy` |
| `ypub...` | `BTC Wallet [Label] · SegWit` |
| `zpub...` | `BTC Wallet [Label] · Native SegWit` |

Alle Entitäten erben den Gerätenamen als Präfix, z. B.:
`BTC Wallet Cold Wallet · Native SegWit Balance (Satoshi)`

### Unterstützte Adressformate (Einzeladress-Modus)

- Legacy (`1...`)
- Pay-to-Script-Hash (`3...`)
- Native SegWit / Bech32 (`bc1q...`)
- Taproot / Bech32m (`bc1p...`)

### Verwendete Adressen abrufen (HD Wallet)

Der **Balance (Satoshi)**-Sensor eines HD-Wallet-Eintrags enthält als Attribut `addresses` ein Dictionary aller verwendeten Adressen mit ihrem Guthaben in Satoshi — also alle Adressen, die mindestens eine Transaktion hatten.

In den **Entwicklerwerkzeugen → Zustände** sieht das z. B. so aus:

```yaml
# sensor.btc_wallet_mein_wallet_satoshi
addresses:
  bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu: 150000
  bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g: 320000
```

In Templates und Automationen:

```yaml
{{ state_attr('sensor.btc_wallet_mein_wallet_satoshi', 'addresses') }}
```

Einzelnes Guthaben einer bestimmten Adresse abfragen:

```yaml
{{ state_attr('sensor.btc_wallet_mein_wallet_satoshi', 'addresses')
   .get('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu', 0) }}
```

### Einstellungen

Über den **Konfigurieren**-Button der Integration änderbar:

- **Fiat-Währung** — EUR, USD, CHF, GBP
- **Aktualisierungsintervall** — in Sekunden (Minimum: 60)
- **Mempool-API-URL** — eigene Mempool-Instanz verwenden (Standard: `https://mempool.space/api`)

Änderungen werden sofort übernommen (die Integration lädt automatisch neu).

### Portfolio Total

Sobald mindestens eine Wallet hinzugefügt wird, erscheint automatisch der Eintrag **„Portfolio Total"** unter Geräte & Dienste. Dieser Eintrag enthält drei Aggregations-Sensoren:

| Sensor | Beschreibung |
|--------|-------------|
| **Total Balance (Satoshi)** | Summe aller Satoshi-Guthaben über alle Wallets |
| **Total Balance (BTC)** | Summe aller BTC-Guthaben über alle Wallets |
| **Total Value** | Gesamtwert in Fiat — nur wenn alle Wallets dieselbe Währung nutzen |

> Wenn verschiedene Währungen konfiguriert sind, zeigt **Total Value** `Unavailable` und ein `warning`-Attribut listet die gemischten Währungen auf.

Die Sensoren aktualisieren sich automatisch bei jeder Wallet-Aktualisierung. Der Eintrag muss nicht manuell angelegt werden und kann nicht manuell gelöscht werden (er wird bei der nächsten Wallet-Aktivität neu erstellt).

### Beispiel-Dashboard

Im Repo liegt [`example_dashboard.yaml`](example_dashboard.yaml) — ein fertiges Lovelace-Dashboard mit Portfolio-Gesamt-Übersicht, Preis-Gauge und Wallet-Karten.

Einfügen unter: **Einstellungen → Dashboards → Drei-Punkte-Menü → YAML-Roheditor**

Die Entity-IDs in der Datei sind Platzhalter. Die eigenen IDs findest du unter **Entwicklerwerkzeuge → Zustände** (nach `satoshi` filtern).

### Diagnostik

Unter **Einstellungen → Geräte & Dienste → Satoshi Sensor → Diagnostik herunterladen** können Diagnosedaten exportiert werden. Enthalten sind:

- Eintragtyp und redaktierter Identifier
- Aktuelles Guthaben, Preis, Transaktionsanzahl
- Update-Intervall und Fehleranzahl
- Mempool-API-URL
- Bei HD-Wallets: Anzahl aktiver/gescannter Adressen

---

## English

Home Assistant custom integration to monitor Bitcoin wallet balances — supports both single addresses and hardware wallets (HD wallets via xpub).

### Features

- Add **single addresses** or entire **HD wallets via xpub/ypub/zpub**
- One config entry per wallet (easy to add/remove individually)
- **Portfolio Total** — automatically created as its own entry, showing the **aggregate across all wallets**:
  - **Total Balance (Satoshi)** — sum of all satoshi balances
  - **Total Balance (BTC)** — sum of all BTC balances
  - **Total Value** — total fiat value (only when all wallets use the same currency)
- **7 sensors per entry** (single address and HD wallet):
  - **Balance (Satoshi)** — confirmed balance in satoshis
  - **Balance (BTC)** — confirmed balance in BTC
  - **Value** — fiat value in your configured currency (EUR, USD, CHF, GBP)
  - **BTC Price Change 24h** — 24-hour BTC price change in %
  - **Unconfirmed Balance** — pending unconfirmed balance in satoshis
  - **Transactions** — total number of transactions
  - **Address** *(single address)* — the Bitcoin address as a sensor value
  - **Active Addresses** *(HD wallet)* — number of addresses with transaction history
- Device name automatically includes the address type (Legacy / SegWit / Native SegWit / Taproot)
- HD wallet: all used addresses with balances accessible as sensor attributes
- HD wallet: scans **external and change chain** (m/.../0 and m/.../1) for complete balances
- HD wallet: **address cache** via HA storage — faster restarts without full rescan
- Configurable update interval (default: 5 min, minimum: 1 min)
- **Custom Mempool API URL** configurable (e.g. Umbrel, RaspiBlitz or self-hosted instance)
- **Fast restart** — last fetched values are restored immediately from HA storage, API refresh runs in the background
- **Exponential backoff** on API errors (rate limits, server errors) — doubles the interval up to 4×
- **Diagnostics** via Home Assistant → Devices & Services → Satoshi Sensor → Download diagnostics
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

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Satoshi Sensor**
3. Enter a Bitcoin address **or** an Extended Public Key — the integration detects the type automatically
4. Optionally enter a label
5. Select your preferred fiat currency (default: EUR)

The integration will automatically derive all addresses for xpub/ypub/zpub entries — both on the **external chain** (receive addresses, m/.../0) and the **change chain** (change addresses, m/.../1) — and scan them with a gap limit of 20 (BIP44 standard). Up to 5 parallel API requests are used. Previously scanned addresses are cached and fetched immediately on the next restart.

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

> **Note:** xpub, ypub and zpub represent different BIP32 accounts with different key material (m/44'/0'/0', m/49'/0'/0', m/84'/0'/0'). They are cryptographically **independent** and cannot be derived from each other. To monitor multiple address types, export each key separately from your hardware wallet and add it as its own entry.

> **Taproot (BIP86) xpub not yet supported.**
> There is no standardized key prefix for Taproot HD wallets — most wallets export BIP86 account keys as a regular `xpub`, which is indistinguishable from BIP44. Taproot **single addresses** (`bc1p...`) work fine however.

### Device and entity naming

The address type is automatically detected from the input and included in the device name:

| Input | Device name |
|-------|-------------|
| `1...` | `BTC Wallet [Label] · Legacy` |
| `3...` | `BTC Wallet [Label] · SegWit` |
| `bc1q...` | `BTC Wallet [Label] · Native SegWit` |
| `bc1p...` | `BTC Wallet [Label] · Taproot` |
| `xpub...` | `BTC Wallet [Label] · Legacy` |
| `ypub...` | `BTC Wallet [Label] · SegWit` |
| `zpub...` | `BTC Wallet [Label] · Native SegWit` |

All entities inherit the device name as a prefix, e.g.:
`BTC Wallet Cold Wallet · Native SegWit Balance (Satoshi)`

### Supported address formats (single address mode)

- Legacy (`1...`)
- Pay-to-Script-Hash (`3...`)
- Native SegWit / Bech32 (`bc1q...`)
- Taproot / Bech32m (`bc1p...`)

### Accessing used addresses (HD wallet)

The **Balance (Satoshi)** sensor of an HD wallet entry exposes an `addresses` attribute — a dictionary of all used addresses (those with at least one transaction) and their balance in satoshis.

In **Developer Tools → States** it looks like this:

```yaml
# sensor.btc_wallet_my_wallet_satoshi
addresses:
  bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu: 150000
  bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g: 320000
```

In templates and automations:

```yaml
{{ state_attr('sensor.btc_wallet_my_wallet_satoshi', 'addresses') }}
```

Query the balance of a specific address:

```yaml
{{ state_attr('sensor.btc_wallet_my_wallet_satoshi', 'addresses')
   .get('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu', 0) }}
```

### Options

Go to the integration's **Configure** button to change:

- **Fiat currency** — EUR, USD, CHF, GBP
- **Update interval** — in seconds (minimum: 60)
- **Mempool API URL** — use your own Mempool instance (default: `https://mempool.space/api`)

Changes take effect immediately after saving (the integration reloads automatically).

### Portfolio Total

As soon as the first wallet is added, a **"Portfolio Total"** entry appears automatically under Devices & Services. It contains three aggregate sensors:

| Sensor | Description |
|--------|-------------|
| **Total Balance (Satoshi)** | Sum of all satoshi balances across all wallets |
| **Total Balance (BTC)** | Sum of all BTC balances across all wallets |
| **Total Value** | Total fiat value — only when all wallets use the same currency |

> If different currencies are configured, **Total Value** shows `Unavailable` and a `warning` attribute lists the mixed currencies.

The sensors update automatically whenever any wallet refreshes. The entry is created automatically and does not need to be added manually — if deleted, it will be re-created the next time a wallet entry is activated.

### Example Dashboard

The repository includes [`example_dashboard.yaml`](example_dashboard.yaml) — a ready-to-use Lovelace dashboard with a portfolio overview, price gauge, and individual wallet cards.

To use it: **Settings → Dashboards → three-dot menu → Edit in YAML**

The entity IDs in the file are placeholders. Find your own IDs under **Developer Tools → States** (filter by `satoshi`).

### Diagnostics

Under **Settings → Devices & Services → Satoshi Sensor → Download diagnostics** you can export diagnostic data including:

- Entry type and redacted identifier
- Current balance, price, transaction count
- Update interval and error count
- Mempool API URL
- For HD wallets: number of active/scanned addresses
