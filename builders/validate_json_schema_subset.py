"""Dependency-free validator for the JSON Schema subset used by AI ANALYZE.

Supported keywords: type, required, properties, items, enum, const, pattern,
minItems, maxItems, minimum and maximum. It is not a full Draft 2020-12 engine.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(instance, item) for item in allowed):
            return [f"{path}: expected type {allowed}, got {type(instance).__name__}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{path}.{key}"))
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))
    if isinstance(instance, str) and "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
        errors.append(f"{path}: does not match pattern {schema['pattern']!r}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate JSON with the AI ANALYZE schema subset.")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--instance", action="append", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        schema = load_json(Path(args.schema))
        results = []
        failed = False
        for raw in args.instance:
            instance = load_json(Path(raw))
            errors = validate(instance, schema)
            failed = failed or bool(errors)
            results.append({"instance":str(Path(raw)),"valid":not errors,"errors":errors})
        print(json.dumps({"schema":args.schema,"results":results,"validator":"dependency-free documented subset"}, ensure_ascii=False, indent=2))
        return 2 if failed else 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
