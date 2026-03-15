"""Address derivation from extended public keys (xpub/ypub/zpub)."""
from __future__ import annotations

from bip_utils import Bip44, Bip44Changes, Bip44Coins, Bip49, Bip49Coins, Bip84, Bip84Coins

from .const import XPUB_PREFIXES

_HANDLERS: dict[str, tuple] = {
    "xpub": (Bip44, Bip44Coins.BITCOIN),
    "ypub": (Bip49, Bip49Coins.BITCOIN),
    "zpub": (Bip84, Bip84Coins.BITCOIN),
}


def is_xpub(value: str) -> bool:
    return value[:4].lower() in _HANDLERS


def derive_addresses(xpub: str, start: int, count: int) -> list[str]:
    """Derive `count` external-chain addresses starting at index `start`."""
    prefix = xpub[:4].lower()
    if prefix not in _HANDLERS:
        raise ValueError(f"Unsupported key prefix: {prefix!r}. Expected one of {XPUB_PREFIXES}.")

    bip_class, coin = _HANDLERS[prefix]
    ctx = bip_class.FromExtendedKey(xpub, coin)

    return [
        ctx.Change(Bip44Changes.CHAIN_EXT).AddressIndex(i).PublicKey().ToAddress()
        for i in range(start, start + count)
    ]
