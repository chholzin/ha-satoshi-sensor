"""Constants for Satoshi Sensor."""

DOMAIN = "satoshi_sensor"

CONF_ADDRESS = "address"
CONF_LABEL = "label"
CONF_CURRENCY = "currency"

DEFAULT_CURRENCY = "eur"
DEFAULT_UPDATE_INTERVAL = 300  # seconds

SUPPORTED_CURRENCIES = ["eur", "usd", "chf", "gbp"]

MEMPOOL_API_URL = "https://mempool.space/api/address/{address}"
COINGECKO_API_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies={currency}"
)

SATOSHIS_PER_BTC = 100_000_000
