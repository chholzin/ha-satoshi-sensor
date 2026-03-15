"""Address derivation from extended public keys (xpub/ypub/zpub)."""
from __future__ import annotations

import hashlib
import logging

from bip_utils import Bip32KeyNetVersions, Bip32Slip10Secp256k1

from .const import XPUB_PREFIXES

_LOGGER = logging.getLogger(__name__)

# BIP32 serialization version bytes for each key type (mainnet public / private)
_KEY_NET_VERSIONS: dict[str, Bip32KeyNetVersions] = {
    "xpub": Bip32KeyNetVersions(b"\x04\x88\xb2\x1e", b"\x04\x88\xad\xe4"),  # BIP44
    "ypub": Bip32KeyNetVersions(b"\x04\x9d\x7c\xb2", b"\x04\x9d\x78\x78"),  # BIP49
    "zpub": Bip32KeyNetVersions(b"\x04\xb2\x47\x46", b"\x04\xb2\x43\x0c"),  # BIP84
}

# Bech32 charset for P2WPKH address encoding
_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def is_xpub(value: str) -> bool:
    return value[:4].lower() in _KEY_NET_VERSIONS


def derive_addresses(xpub: str, start: int, count: int) -> list[str]:
    """Derive `count` external-chain addresses starting at index `start`."""
    prefix = xpub[:4].lower()
    if prefix not in _KEY_NET_VERSIONS:
        raise ValueError(f"Unsupported prefix: {prefix!r}. Expected one of {XPUB_PREFIXES}.")

    ctx = Bip32Slip10Secp256k1.FromExtendedKey(xpub, _KEY_NET_VERSIONS[prefix])

    addresses = []
    for i in range(start, start + count):
        child = ctx.ChildKey(0).ChildKey(i)
        pub_bytes = child.PublicKey().RawCompressed().ToBytes()

        if prefix == "xpub":
            addr = _p2pkh(pub_bytes)
        elif prefix == "ypub":
            addr = _p2sh_p2wpkh(pub_bytes)
        else:  # zpub
            addr = _p2wpkh(pub_bytes)

        addresses.append(addr)

    return addresses


# ── Address encoding (pure Python, no bip_utils dependency) ─────────────────

def _hash160(data: bytes) -> bytes:
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def _b58check(payload: bytes) -> str:
    data = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(data, "big")
    result = []
    while n:
        n, r = divmod(n, 58)
        result.append(_B58_ALPHABET[r])
    leading = len(data) - len(data.lstrip(b"\x00"))
    result += [_B58_ALPHABET[0]] * leading
    return "".join(reversed(result))


def _p2pkh(pub: bytes) -> str:
    """Legacy address (1...) for xpub."""
    return _b58check(b"\x00" + _hash160(pub))


def _p2sh_p2wpkh(pub: bytes) -> str:
    """P2SH-wrapped SegWit address (3...) for ypub."""
    redeem = b"\x00\x14" + _hash160(pub)  # OP_0 PUSH20 <keyhash>
    return _b58check(b"\x05" + _hash160(redeem))


def _p2wpkh(pub: bytes) -> str:
    """Native SegWit address (bc1...) for zpub."""
    witprog = _hash160(pub)
    data = [0] + _convertbits(list(witprog), 8, 5)
    checksum = _bech32_checksum("bc", data)
    return "bc1" + "".join(_BECH32_CHARSET[d] for d in data + checksum)


def _convertbits(data: list[int], frombits: int, tobits: int) -> list[int]:
    acc = bits = 0
    result = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = ((acc << frombits) | value) & 0x3FFFFFFF
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            result.append((acc >> bits) & maxv)
    if bits:
        result.append((acc << (tobits - bits)) & maxv)
    return result


def _bech32_polymod(values: list[int]) -> int:
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if (b >> i) & 1 else 0
    return chk


def _bech32_checksum(hrp: str, data: list[int]) -> list[int]:
    expand = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]
    polymod = _bech32_polymod(expand + data + [0] * 6) ^ 1
    return [(polymod >> (5 * (5 - i))) & 31 for i in range(6)]
