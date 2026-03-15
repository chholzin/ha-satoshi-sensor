"""Address derivation from extended public keys — pure Python, no external dependencies."""
from __future__ import annotations

import hashlib
import hmac
import struct

from .const import XPUB_PREFIXES

# ── secp256k1 curve parameters ───────────────────────────────────────────────

_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
_G = (_Gx, _Gy)

# ── secp256k1 point arithmetic ───────────────────────────────────────────────

def _point_add(p1: tuple | None, p2: tuple | None) -> tuple | None:
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if y1 != y2:
            return None
        m = (3 * x1 * x1 * pow(2 * y1, _P - 2, _P)) % _P
    else:
        m = ((y2 - y1) * pow(x2 - x1, _P - 2, _P)) % _P
    x3 = (m * m - x1 - x2) % _P
    y3 = (m * (x1 - x3) - y1) % _P
    return (x3, y3)


def _point_mul(k: int, point: tuple) -> tuple | None:
    result = None
    addend = point
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result


def _compress(x: int, y: int) -> bytes:
    return (b"\x02" if y % 2 == 0 else b"\x03") + x.to_bytes(32, "big")


def _decompress(data: bytes) -> tuple[int, int]:
    x = int.from_bytes(data[1:], "big")
    y_sq = (pow(x, 3, _P) + 7) % _P
    y = pow(y_sq, (_P + 1) // 4, _P)
    if y % 2 != data[0] % 2:
        y = _P - y
    return (x, y)


# ── Base58Check ───────────────────────────────────────────────────────────────

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + _B58.index(c)
    result = []
    while n:
        n, r = divmod(n, 256)
        result.append(r)
    leading = len(s) - len(s.lstrip("1"))
    return bytes(leading) + bytes(reversed(result))


def _b58check_decode(s: str) -> bytes:
    raw = _b58decode(s)
    payload, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected:
        raise ValueError("Invalid base58check checksum")
    return payload


def _b58check_encode(payload: bytes) -> str:
    data = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(data, "big")
    result = []
    while n:
        n, r = divmod(n, 58)
        result.append(_B58[r])
    leading = len(data) - len(data.lstrip(b"\x00"))
    return _B58[0] * leading + "".join(reversed(result))


# ── BIP32 extended key parsing ────────────────────────────────────────────────

def _parse_xpub(xpub: str) -> tuple[bytes, bytes]:
    """Return (pubkey_bytes_33, chaincode_bytes_32) from an xpub/ypub/zpub string."""
    payload = _b58check_decode(xpub)
    if len(payload) != 78:
        raise ValueError(f"Expected 78 bytes, got {len(payload)}")
    # 4 version | 1 depth | 4 fingerprint | 4 index | 32 chaincode | 33 pubkey
    chaincode = payload[13:45]
    pubkey = payload[45:78]
    return pubkey, chaincode


# ── BIP32 child key derivation (public → public, non-hardened) ────────────────

def _derive_child_pubkey(pubkey: bytes, chaincode: bytes, index: int) -> tuple[bytes, bytes]:
    data = pubkey + struct.pack(">I", index)
    I = hmac.new(chaincode, data, hashlib.sha512).digest()
    IL, IR = I[:32], I[32:]

    il_int = int.from_bytes(IL, "big")
    if il_int >= _N:
        raise ValueError("Invalid derived key — try next index")

    parent_point = _decompress(pubkey)
    tweak_point = _point_mul(il_int, _G)
    child_point = _point_add(tweak_point, parent_point)
    if child_point is None:
        raise ValueError("Derived point at infinity — try next index")

    child_pubkey = _compress(*child_point)
    return child_pubkey, IR  # child chaincode = IR


# ── Address encoding (pure Python) ───────────────────────────────────────────

def _hash160(data: bytes) -> bytes:
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def _p2pkh(pub: bytes) -> str:
    return _b58check_encode(b"\x00" + _hash160(pub))


def _p2sh_p2wpkh(pub: bytes) -> str:
    redeem = b"\x00\x14" + _hash160(pub)
    return _b58check_encode(b"\x05" + _hash160(redeem))


_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _convertbits(data: list[int], frombits: int, tobits: int) -> list[int]:
    acc = bits = 0
    result = []
    maxv = (1 << tobits) - 1
    for v in data:
        acc = ((acc << frombits) | v) & 0x3FFFFFFF
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
    poly = _bech32_polymod(expand + data + [0] * 6) ^ 1
    return [(poly >> (5 * (5 - i))) & 31 for i in range(6)]


def _p2wpkh(pub: bytes) -> str:
    witprog = list(_hash160(pub))
    data = [0] + _convertbits(witprog, 8, 5)
    return "bc1" + "".join(_BECH32[d] for d in data + _bech32_checksum("bc", data))


_ADDR_FN = {"xpub": _p2pkh, "ypub": _p2sh_p2wpkh, "zpub": _p2wpkh}

# ── Public API ────────────────────────────────────────────────────────────────

def is_xpub(value: str) -> bool:
    return value[:4].lower() in _ADDR_FN


def derive_addresses(xpub: str, start: int, count: int) -> list[str]:
    """Derive `count` external-chain addresses starting at index `start`."""
    prefix = xpub[:4].lower()
    if prefix not in _ADDR_FN:
        raise ValueError(f"Unsupported prefix: {prefix!r}. Expected one of {XPUB_PREFIXES}.")

    addr_fn = _ADDR_FN[prefix]
    account_pub, account_chain = _parse_xpub(xpub)

    # Derive external chain key (m/.../0)
    ext_pub, ext_chain = _derive_child_pubkey(account_pub, account_chain, 0)

    addresses = []
    for i in range(start, start + count):
        child_pub, _ = _derive_child_pubkey(ext_pub, ext_chain, i)
        addresses.append(addr_fn(child_pub))

    return addresses
