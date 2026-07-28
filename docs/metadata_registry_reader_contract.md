# vnstock_metadata_snapshot Registry Reader Contract

`builders/metadata_registry_reader.py` reads immutable registry snapshot files produced by
`stock-core-private/metadata_registry_export.py --registry-snapshot` (see that repo's
`docs/metadata_registry_snapshot_contract.md` for how snapshots are produced and named). This is
a pure reader: it never writes, never deletes, never touches any database, and never falls back
to a live source.

## Input

`read_snapshot(target)` accepts either:

- an explicit path to one snapshot file, or
- a directory, in which case the newest valid-looking snapshot in it is selected (see below).

## Snapshot selection (directory mode)

Only files matching the naming contract
(`vnstock_metadata_snapshot_<UTC-YYYYMMDDTHHMMSSZ>_<content-sha256-12>.jsonl`) are candidates.
Anything else in the directory -- including partial/temp files such as `.tmp-*` left by an
interrupted producer write -- is silently excluded from candidacy; a directory is allowed to
contain such files without causing an error. Candidates are compared by their embedded UTC
timestamp. If two or more candidates share the latest timestamp, selection is ambiguous and
`read_snapshot` raises rather than guessing.

## Output

`{ticker: {field: record}}` -- every validated record, grouped first by ticker then by field.
Records are returned exactly as read; nothing is added, removed, or recomputed.

## Fail-closed behavior

`read_snapshot` raises `SnapshotError` (never returns a partial result) for any of:

- an explicit target whose filename does not match the naming contract;
- a directory with no matching candidates, or an ambiguous (tied-timestamp) selection;
- content whose actual sha256 does not match the hash embedded in its filename;
- any line that fails to parse as JSON, or fails validation against
  `validation/schemas/vnstock_metadata_snapshot_registry_handoff.schema.json`;
- any duplicate `(ticker, field)` identity within the file;
- more than one distinct `transform_version` value within the file.

There is no implicit fallback to `vn_stock.db` or any other live source, no silent skipping of an
invalid line, and no fabricated provenance, timestamp, hash, or value -- a record is returned
exactly as validated, or the whole read fails.

## Non-goals (reader milestone)

- No retention, archival, or cleanup of snapshot files.
- No scheduling or automatic invocation.
- No API/service; this is a plain Python function against local files.
- No writing: this module never creates, modifies, or deletes any file.

## Opt-in shadow integration in `build_ticker_context.py`

`build_context_package(..., metadata_registry_snapshot: Path | None = None)` adds one optional,
keyword-only-in-practice parameter, defaulting to `None`.

- **Default (`None`, every existing caller):** metadata is read from `vn_stock.db` via
  `load_metadata_slice`, exactly as before this integration. Nothing about the default path
  changed -- not the function, not its arguments, not its output.
- **Explicit file or directory:** the metadata section (only) is read instead via
  `load_metadata_slice_from_registry_snapshot(ticker, metadata_registry_snapshot)`, which calls
  this same `read_snapshot`/`select_newest_snapshot` reader -- no second reader implementation --
  and converts the grouped-by-ticker result into the exact slice shape `load_metadata_slice`
  produces (same field names, same `-1`-sentinel and `margin_status` normalization, same warning
  annotations), so the two sources are interchangeable to every downstream consumer of
  `context["metadata"]`.
- The routing decision (`_select_metadata_loader`) never mixes the two sources for one context:
  exactly one loader runs. There is no fallback from a requested snapshot back to the DB, and no
  automatic search of `stock-core-private/registry_snapshots/metadata/` or any other production
  directory -- the caller must always pass the path explicitly.
- An invalid/malformed/ambiguous snapshot, or one missing a required field, raises `SnapshotError`
  (fail-closed) from the loader; `build_context_package`'s existing per-section exception handling
  (already catching `ValueError`, of which `SnapshotError` is a subclass) then marks `metadata` as
  unavailable with an explicit warning -- the same behavior it already has for a missing DB row or
  any other loader failure, never a fabricated or partial metadata slice.

`compare_metadata_slices(db_slice, registry_slice)` is a separate, pure, in-memory helper -- not
called from `build_context_package` -- for comparing two already-loaded slices (e.g., one from
each source) and reporting per-field `exact_match` / `null_mismatch` / `value_mismatch` /
`provenance_mismatch`. It writes nothing and cannot affect context output.

### Non-goals (integration milestone)

- No wiring into the daily pipeline, `run.py`, or any scheduled job.
- No automatic shadow-mode invocation inside `build_context_package` -- a caller must explicitly
  load both slices and call `compare_metadata_slices` itself.
- No change to the default (DB) behavior for any existing caller.
- No persistence of shadow-comparison reports; they are returned in memory only.
- No decision here about whether/when the registry path should ever become the default.
