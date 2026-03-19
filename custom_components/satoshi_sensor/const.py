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
ENTRY_TYPE_STATS = "stats"

STATS_UNIQUE_ID = f"{DOMAIN}_stats"

GAP_LIMIT = 20
XPUB_BATCH_SIZE = 20
XPUB_PREFIXES = ("xpub", "ypub", "zpub")

XPUB_SCAN_TIMEOUT = 600          # seconds — default scan timeout (public mempool)
XPUB_SCAN_TIMEOUT_CUSTOM = 1800  # seconds — extended timeout for self-hosted instances
XPUB_CONCURRENCY = 3             # parallel requests — public mempool
XPUB_CONCURRENCY_CUSTOM = 1      # parallel requests — self-hosted (serialized to spare RPi)

CONF_XPUB_CONCURRENCY = "xpub_concurrency"
REQUEST_DELAY_PUBLIC = 0.1       # seconds between requests for public mempool
REQUEST_DELAY_CUSTOM = 0.3       # seconds between requests for self-hosted instances

DEFAULT_CURRENCY = "eur"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_UPDATE_INTERVAL = 300  # seconds
MIN_UPDATE_INTERVAL = 60  # seconds

SUPPORTED_CURRENCIES = ["eur", "usd", "chf", "gbp"]

CONF_INCLUDE_IN_TOTAL = "include_in_total"
CONF_MEMPOOL_URL = "mempool_url"
DEFAULT_MEMPOOL_URL = "https://mempool.space/api"
MEMPOOL_API_URL = "https://mempool.space/api/address/{address}"
MEMPOOL_FEES_PATH = "/v1/fees/recommended"
MEMPOOL_BLOCKS_PATH = "/v1/blocks"
COINGECKO_API_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies={currency}&include_24hr_change=true"
)

SATOSHIS_PER_BTC = 100_000_000
