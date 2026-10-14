"""Shared canonical JSON identity and file helpers for Consumer builders.

One implementation for the content-identity and file-digest rules that builders
previously copied verbatim.  Identities are byte-for-byte unchanged: canonical
JSON is ASCII-escaped, key-sorted, compact and refuses NaN/Infinity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def is_identity_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and ":" in value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value
