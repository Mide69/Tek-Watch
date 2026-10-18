"""Versioned technical-control packs. A mapping is not a legal compliance opinion."""
import hashlib
import json
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent.parent / "control_packs"


def load_pack(pack_id="uk-aws-2026-10"):
    # Only bundled, reviewed-for-release identifiers can select executable rules.
    if pack_id != "uk-aws-2026-10":
        raise ValueError("Unsupported control pack")
    raw = (PACK_DIR / (pack_id + ".json")).read_bytes()
    pack = json.loads(raw)
    pack["sha256"] = hashlib.sha256(raw).hexdigest()
    return pack
