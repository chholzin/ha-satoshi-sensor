"""Constants for Satoshi Sensor."""

DOMAIN = "satoshi_sensor"
SIGNAL_TOTALS_UPDATE = f"{DOMAIN}_totals_update"
TOTALS_UNIQUE_ID = f"{DOMAIN}_totals"

CONF_ADDRESS = "address"
CONF_LABEL = "label"
CONF_CURRENCY = "currency"
CONF_XPUB = "xpub"
CONF_ENTRY_TYPE = "entry_type"

ENTRY_TYPE_ADDRESS = "address"
ENTRY_TYPE_XPUB = "xpub"
ENTRY_TYPE_TOTALS = "totals"

GAP_LIMIT = 20
XPUB_BATCH_SIZE = 20
XPUB_PREFIXES = ("xpub", "ypub", "zpub")

DEFAULT_CURRENCY = "eur"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_UPDATE_INTERVAL = 300  # seconds
MIN_UPDATE_INTERVAL = 60  # seconds

SUPPORTED_CURRENCIES = ["eur", "usd", "chf", "gbp"]

CONF_MEMPOOL_URL = "mempool_url"
DEFAULT_MEMPOOL_URL = "https://mempool.space/api"
MEMPOOL_API_URL = "https://mempool.space/api/address/{address}"
COINGECKO_API_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies={currency}&include_24hr_change=true"
)

SATOSHIS_PER_BTC = 100_000_000
