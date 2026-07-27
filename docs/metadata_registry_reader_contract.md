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

## Non-goals (this milestone)

- No wiring into `build_ticker_context.py` or any other runtime consumer.
- No retention, archival, or cleanup of snapshot files.
- No scheduling or automatic invocation.
- No API/service; this is a plain Python function against local files.
- No writing: this module never creates, modifies, or deletes any file.
