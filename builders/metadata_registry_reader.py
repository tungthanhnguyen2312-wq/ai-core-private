"""Consumer-side reader for immutable vnstock_metadata_snapshot registry snapshots produced by
stock-core-private/metadata_registry_export.py --registry-snapshot (see that repo's
docs/metadata_registry_snapshot_contract.md for how snapshots are named and written, and
docs/metadata_registry_reader_contract.md in this repo for this module's own contract).

Pure reader: never writes, never deletes, never touches any database, and never falls back to a
live source. Fails closed -- raises SnapshotError -- on anything malformed, ambiguous, or
internally inconsistent rather than returning a partial or best-effort result.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
SCHEMA_PATH = _REPO_ROOT / "validation" / "schemas" / "vnstock_metadata_snapshot_registry_handoff.schema.json"

SNAPSHOT_FILENAME_RE = re.compile(
    r"^vnstock_metadata_snapshot_(?P<stamp>\d{8}T\d{6}Z)_(?P<content_hash>[0-9a-f]{12})\.jsonl$"
)


def _load_sibling_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _THIS_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Loaded by explicit file path rather than a normal import so this module works regardless of how
# it itself was imported/on what sys.path -- no dependency on the caller's import style.
_schema_validator = _load_sibling_module("metadata_registry_reader_schema_validator", "validate_json_schema_subset.py")


class SnapshotError(ValueError):
    """Raised for any malformed, ambiguous, or internally inconsistent snapshot. Fail-closed:
    callers get a clear exception, never a partial or best-effort result."""


def _match_snapshot_filename(name: str) -> re.Match[str]:
    match = SNAPSHOT_FILENAME_RE.match(name)
    if not match:
        raise SnapshotError(f"filename does not match the registry snapshot naming contract: {name!r}")
    return match


def select_newest_snapshot(directory: Path) -> Path:
    """Deterministically select the newest valid-looking snapshot filename in `directory` by its
    embedded UTC timestamp. Files that don't match the naming contract -- including partial/temp
    files such as `.tmp-*` left by an interrupted producer write -- are ignored, not rejected:
    they simply aren't candidates. Raises SnapshotError if no candidate exists, or if more than
    one candidate shares the latest timestamp (ambiguous -- never guesses)."""
    directory = Path(directory)
    candidates: list[tuple[str, Path]] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = SNAPSHOT_FILENAME_RE.match(path.name)
        if match:
            candidates.append((match.group("stamp"), path))
    if not candidates:
        raise SnapshotError(f"no snapshot files matching the naming contract found in {directory}")
    newest_stamp = max(stamp for stamp, _ in candidates)  # zero-padded fixed-width -> lexicographic == chronological
    newest = [path for stamp, path in candidates if stamp == newest_stamp]
    if len(newest) > 1:
        names = sorted(p.name for p in newest)
        raise SnapshotError(
            f"ambiguous snapshot selection: {len(newest)} files share the newest timestamp "
            f"{newest_stamp}: {names}"
        )
    return newest[0]


def read_snapshot(target: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Read and fully validate ONE registry snapshot. `target` may be an explicit file, or a
    directory (the newest valid-looking snapshot in it is selected via select_newest_snapshot).
    Never touches any database and never falls back to one. Returns records grouped as
    {ticker: {field: record}}, each record exactly as read and schema-validated -- nothing added,
    removed, or recomputed. Never modifies `target`. Raises SnapshotError on:

    - a filename that does not match the naming contract;
    - a directory with no candidates, or an ambiguous (tied-timestamp) selection;
    - content whose actual sha256 does not match the hash embedded in its filename;
    - any line that fails to parse as JSON or fails schema validation;
    - any duplicate (ticker, field) identity within the file;
    - more than one distinct transform_version value within the file.
    """
    target = Path(target)
    if target.is_dir():
        path = select_newest_snapshot(target)
    elif target.is_file():
        path = target
    else:
        raise SnapshotError(f"snapshot path does not exist: {target}")

    match = _match_snapshot_filename(path.name)
    expected_hash = match.group("content_hash")

    body = path.read_bytes()
    actual_hash = hashlib.sha256(body).hexdigest()[:12]
    if actual_hash != expected_hash:
        raise SnapshotError(
            f"content hash mismatch for {path.name}: filename says {expected_hash}, actual "
            f"content hash is {actual_hash} -- refusing a snapshot whose name and content disagree"
        )

    lines = body.decode("utf-8").splitlines()
    if not lines:
        raise SnapshotError(f"snapshot file is empty: {path}")

    schema = _schema_validator.load_json(SCHEMA_PATH)
    records: list[dict[str, Any]] = []
    line_errors: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            line_errors.append(f"line {line_number}: invalid JSON ({exc})")
            continue
        errors = _schema_validator.validate(record, schema)
        if errors:
            line_errors.append(f"line {line_number}: {errors}")
            continue
        records.append(record)
    if line_errors:
        raise SnapshotError(f"{path.name}: {len(line_errors)} invalid record(s):\n" + "\n".join(line_errors))

    identity_counts = Counter((r["ticker"], r["field"]) for r in records)
    duplicates = sorted(key for key, count in identity_counts.items() if count > 1)
    if duplicates:
        raise SnapshotError(f"{path.name}: duplicate (ticker, field) identities: {duplicates}")

    transform_versions = {r["transform_version"] for r in records}
    if len(transform_versions) > 1:
        raise SnapshotError(
            f"{path.name}: mixed transform_version values in one snapshot: {sorted(transform_versions)}"
        )

    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["ticker"], {})[record["field"]] = record
    return grouped
