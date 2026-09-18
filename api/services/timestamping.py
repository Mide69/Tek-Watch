"""RFC 3161 timestamps: proof from someone other than us that the log is old.

Hash-chaining proves nobody edited an entry after the fact. It cannot prove
when an entry was made, because every timestamp in the chain is one we wrote
ourselves. A regulator asking "when did you know?" is entitled to something
better than our word.

So once a day the head of the chain is sent to an independent timestamping
authority, which returns a signed token saying it saw that exact hash at that
exact time. Anyone can check it later with openssl and the authority's
certificate, with no help from us and no trust in us.

Two design decisions worth knowing:

* Anchoring is daily and best effort, never in the path of anything. If the
  authority is slow or down, the log carries on and tries again tomorrow.
  Evidence must not depend on somebody else's uptime.
* The request is built by hand. RFC 3161 needs about sixty bytes of ASN.1 and
  a status check, and pulling an unmaintained ASN.1 library into a compliance
  product to save that is a worse trade than writing it out.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# FreeTSA publishes a public RFC 3161 service and its certificates, so an
# auditor can verify a token without an account. Override with TSA_URL.
DEFAULT_TSA_URL = "https://freetsa.org/tsr"
TSA_TIMEOUT_SECONDS = 10.0

# 2.16.840.1.101.3.4.2.1 — SHA-256, as DER content bytes.
_SHA256_OID = bytes([0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01])

GRANTED = {0, 1}   # 0 granted, 1 granted with modifications

VERIFY_INSTRUCTIONS = (
    "Each anchor holds an RFC 3161 token from an independent timestamping authority, "
    "covering the hash of the entry before it. To check one yourself, save the token as "
    "token.tsr, download the authority's certificates, and run: "
    "openssl ts -verify -digest <anchored_hash> -in token.tsr -CAfile cacert.pem "
    "-untrusted tsa.crt. TekWatch is not involved in that check."
)


# ── the small amount of DER this needs ───────────────────────────────────────

def _length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _tlv(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _length(len(content)) + content


def _integer(value: int) -> bytes:
    body = value.to_bytes(max(1, (value.bit_length() + 8) // 8), "big")
    return _tlv(0x02, body)


def build_request(digest: bytes, nonce: int, cert_req: bool = True) -> bytes:
    """A TimeStampReq for one SHA-256 digest.

    TimeStampReq ::= SEQUENCE {
        version        INTEGER (1),
        messageImprint SEQUENCE { algorithm AlgorithmIdentifier, hashed OCTET STRING },
        nonce          INTEGER OPTIONAL,
        certReq        BOOLEAN DEFAULT FALSE }
    """
    if len(digest) != 32:
        raise ValueError("SHA-256 digest must be 32 bytes")
    algorithm = _tlv(0x30, _tlv(0x06, _SHA256_OID) + _tlv(0x05, b""))
    imprint = _tlv(0x30, algorithm + _tlv(0x04, digest))
    body = _integer(1) + imprint + _integer(nonce) + _tlv(0x01, b"\xff" if cert_req else b"\x00")
    return _tlv(0x30, body)


def _read_tlv(data: bytes, offset: int) -> Tuple[int, bytes, int]:
    """(tag, content, next offset) for one DER element."""
    if offset + 2 > len(data):
        raise ValueError("truncated DER")
    tag = data[offset]
    first = data[offset + 1]
    offset += 2
    if first < 0x80:
        size = first
    else:
        count = first & 0x7F
        if count == 0 or offset + count > len(data):
            raise ValueError("bad DER length")
        size = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    if offset + size > len(data):
        raise ValueError("DER element runs past the end")
    return tag, data[offset:offset + size], offset + size


def parse_status(response: bytes) -> int:
    """The PKIStatus out of a TimeStampResp, so a refusal is not stored as proof."""
    tag, outer, _ = _read_tlv(response, 0)
    if tag != 0x30:
        raise ValueError("response is not a SEQUENCE")
    tag, status_info, _ = _read_tlv(outer, 0)
    if tag != 0x30:
        raise ValueError("first element is not PKIStatusInfo")
    tag, status, _ = _read_tlv(status_info, 0)
    if tag != 0x02:
        raise ValueError("status is not an INTEGER")
    return int.from_bytes(status, "big") if status else 0


# ── asking for one ───────────────────────────────────────────────────────────

def stamp(
    anchored_hash: str,
    url: str = DEFAULT_TSA_URL,
    timeout: float = TSA_TIMEOUT_SECONDS,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """A timestamp token for a hash, or None if the authority did not give one.

    Never raises. A timestamp is worth having and never worth stopping the
    evidence log for, so every failure is logged and swallowed.
    """
    if not url:
        return None
    try:
        digest = bytes.fromhex(anchored_hash)
    except ValueError:
        logger.warning("Refusing to timestamp a value that is not a hash")
        return None

    nonce = secrets.randbits(64)
    try:
        response = httpx.post(
            url,
            content=build_request(digest, nonce),
            headers={"Content-Type": "application/timestamp-query"},
            timeout=timeout,
        )
        response.raise_for_status()
        status = parse_status(response.content)
    except Exception as exc:  # noqa: BLE001 — anchoring must never break recording
        logger.warning("Timestamp not obtained from %s: %s", url, exc)
        return None

    if status not in GRANTED:
        logger.warning("Timestamp authority %s refused with status %s", url, status)
        return None

    return {
        "anchored_hash": anchored_hash,
        "authority": url,
        "status": status,
        "nonce": str(nonce),
        "requested_at": (now or datetime.now(timezone.utc)).isoformat(),
        "token_b64": base64.b64encode(response.content).decode("ascii"),
        "token_sha256": hashlib.sha256(response.content).hexdigest(),
        "verify": VERIFY_INSTRUCTIONS,
    }
