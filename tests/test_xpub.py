"""Tests for xpub address derivation."""
import importlib.util
import sys
import os
import types
import pytest

# Load xpub.py directly without triggering the HA-dependent package __init__
_XPUB_PATH = os.path.join(os.path.dirname(__file__), "..", "custom_components", "satoshi_sensor", "xpub.py")

# Register stub modules so relative imports inside xpub.py resolve correctly
_pkg_name = "custom_components.satoshi_sensor"
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules.setdefault(_pkg_name, types.ModuleType(_pkg_name))
_const = types.ModuleType(f"{_pkg_name}.const")
_const.XPUB_PREFIXES = ("xpub", "ypub", "zpub")
sys.modules[f"{_pkg_name}.const"] = _const

spec = importlib.util.spec_from_file_location(f"{_pkg_name}.xpub", _XPUB_PATH)
_xpub_mod = importlib.util.module_from_spec(spec)
_xpub_mod.__package__ = _pkg_name
sys.modules[f"{_pkg_name}.xpub"] = _xpub_mod
spec.loader.exec_module(_xpub_mod)

_b58check_decode = _xpub_mod._b58check_decode
_b58decode = _xpub_mod._b58decode
_b58check_encode = _xpub_mod._b58check_encode
_hash160 = _xpub_mod._hash160
_p2pkh = _xpub_mod._p2pkh
_p2sh_p2wpkh = _xpub_mod._p2sh_p2wpkh
_p2wpkh = _xpub_mod._p2wpkh
_p2tr = _xpub_mod._p2tr
derive_addresses = _xpub_mod.derive_addresses
is_xpub = _xpub_mod.is_xpub


# ── BIP84 standard test vector ────────────────────────────────────────────────
# Source: https://github.com/bitcoin/bips/blob/master/bip-0084.mediawiki
# Mnemonic: "abandon" x11 + "about", no passphrase, account m/84'/0'/0'

ZPUB_BIP84 = (
    "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1"
    "ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
)
BIP84_ADDRESSES = [
    "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
    "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g",
    "bc1qp59yckz4ae5c4efgw2s5wfyvrz0ala7rgvuz8z",
]

# zpub with '1' characters mid-string (regression: b58decode leading-zero bug)
ZPUB_WITH_ONES = (
    "zpub6rEFZmWBhx1AvuVUH8Tq56qjFhXfhQtoXPkfpoNrWhCYTLTx5He9RMPiY2uY"
    "vhAapmQzuHpi4qzkKMPxv3iALh5E41z87Qe2S3CsbCDLbqs"
)
ZPUB_WITH_ONES_ADDR0 = "bc1qzl23szxwl8tl2p9e72he3p64kg26wpxy455ufd"


# ── is_xpub ───────────────────────────────────────────────────────────────────

class TestIsXpub:
    def test_zpub(self):
        assert is_xpub(ZPUB_BIP84) is True

    def test_xpub_prefix(self):
        assert is_xpub("xpub" + "A" * 107) is True

    def test_ypub_prefix(self):
        assert is_xpub("ypub" + "A" * 107) is True

    def test_invalid_prefix(self):
        assert is_xpub("apub" + "A" * 107) is False

    def test_empty(self):
        assert is_xpub("") is False

    def test_case_insensitive(self):
        assert is_xpub("ZPUB" + "A" * 107) is True


# ── Base58Check ───────────────────────────────────────────────────────────────

class TestBase58:
    def test_roundtrip(self):
        payload = b"\x00" + bytes(range(20))
        assert _b58check_decode(_b58check_encode(payload)) == payload

    def test_leading_zeros_in_payload(self):
        """P2PKH addresses start with version byte 0x00 — leading zero must survive roundtrip."""
        payload = b"\x00" + b"\xde\xad\xbe\xef" * 5
        encoded = _b58check_encode(payload)
        assert encoded.startswith("1")
        assert _b58check_decode(encoded) == payload

    def test_invalid_checksum(self):
        encoded = _b58check_encode(b"\x00" + bytes(20))
        corrupted = encoded[:-1] + ("A" if encoded[-1] != "A" else "B")
        with pytest.raises(ValueError, match="checksum"):
            _b58check_decode(corrupted)

    def test_b58decode_only_counts_leading_ones(self):
        """Regression: '1' chars in the middle must NOT be counted as leading zeros."""
        # Encode a payload that will produce '1's mid-string when base58-encoded
        raw = _b58decode(ZPUB_WITH_ONES)
        # The zpub should decode to exactly 82 bytes (78 payload + 4 checksum)
        assert len(raw) == 82


# ── Address encoding ──────────────────────────────────────────────────────────

class TestAddressEncoding:
    # Known P2PKH vector: hash160 of compressed pubkey → address
    # Source: Bitcoin wiki / known test data
    def test_p2pkh_version_byte(self):
        addr = _p2pkh(bytes(33))  # all-zero pubkey (not valid on curve, but tests encoding)
        assert addr.startswith("1")

    def test_p2sh_p2wpkh_version_byte(self):
        addr = _p2sh_p2wpkh(bytes(33))
        assert addr.startswith("3")

    def test_p2wpkh_hrp(self):
        addr = _p2wpkh(bytes(33))
        assert addr.startswith("bc1q")

    def test_p2tr_hrp(self):
        """P2TR addresses must start with bc1p (witness version 1)."""
        # Use the generator point's compressed pubkey as test input
        from custom_components.satoshi_sensor.xpub import _compress, _Gx, _Gy
        pub = _compress(_Gx, _Gy)
        addr = _p2tr(pub)
        assert addr.startswith("bc1p")
        # Taproot addresses are 62 characters long
        assert len(addr) == 62

    def test_p2tr_deterministic(self):
        """Same pubkey must always produce the same P2TR address."""
        from custom_components.satoshi_sensor.xpub import _compress, _Gx, _Gy
        pub = _compress(_Gx, _Gy)
        assert _p2tr(pub) == _p2tr(pub)

    def test_p2pkh_known_hash160(self):
        """P2PKH: version 0x00 + hash160 → base58check."""
        h = bytes.fromhex("89abcdefabbaabbaabbaabbaabbaabbaabbaabba")
        addr = _b58check_encode(b"\x00" + h)
        decoded = _b58check_decode(addr)
        assert decoded == b"\x00" + h

    def test_hash160_length(self):
        assert len(_hash160(b"test")) == 20


# ── Address derivation ────────────────────────────────────────────────────────

class TestDeriveAddresses:
    def test_bip84_vector_index_0(self):
        """BIP84 official test vector — index 0."""
        addrs = derive_addresses(ZPUB_BIP84, 0, 1)
        assert addrs[0] == BIP84_ADDRESSES[0]

    def test_bip84_vector_first_three(self):
        """BIP84 official test vector — first three addresses."""
        addrs = derive_addresses(ZPUB_BIP84, 0, 3)
        assert addrs == BIP84_ADDRESSES

    def test_bip84_offset(self):
        """Deriving from offset should match slice of full derivation."""
        all_addrs = derive_addresses(ZPUB_BIP84, 0, 5)
        offset_addrs = derive_addresses(ZPUB_BIP84, 2, 3)
        assert offset_addrs == all_addrs[2:5]

    def test_zpub_with_ones_in_string(self):
        """Regression: zpub containing '1' mid-string must derive correctly."""
        addrs = derive_addresses(ZPUB_WITH_ONES, 0, 1)
        assert addrs[0] == ZPUB_WITH_ONES_ADDR0

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError, match="Unsupported prefix"):
            derive_addresses("apub" + "A" * 107, 0, 1)

    def test_returns_correct_count(self):
        addrs = derive_addresses(ZPUB_BIP84, 0, 5)
        assert len(addrs) == 5

    def test_p2wpkh_address_format(self):
        """zpub must produce bc1q... native segwit addresses."""
        addrs = derive_addresses(ZPUB_BIP84, 0, 3)
        for addr in addrs:
            assert addr.startswith("bc1q"), f"Expected bc1q..., got {addr}"

    def test_empty_derivation(self):
        assert derive_addresses(ZPUB_BIP84, 0, 0) == []

    def test_change_chain_differs_from_external(self):
        """Change chain (m/.../1) must produce different addresses than external (m/.../0)."""
        ext = derive_addresses(ZPUB_BIP84, 0, 3, chain=0)
        chg = derive_addresses(ZPUB_BIP84, 0, 3, chain=1)
        assert len(chg) == 3
        # All change addresses must differ from external
        for addr in chg:
            assert addr not in ext
            assert addr.startswith("bc1q")

    def test_change_chain_deterministic(self):
        """Same xpub + chain=1 must produce the same addresses each time."""
        a = derive_addresses(ZPUB_BIP84, 0, 2, chain=1)
        b = derive_addresses(ZPUB_BIP84, 0, 2, chain=1)
        assert a == b
