"""Canonical serialization and digest helpers shared by every instrument.

One rule: a byte sequence has exactly one digest, and every digest recorded
anywhere in the system comes from these two functions. Nothing else in the
codebase calls hashlib directly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())
