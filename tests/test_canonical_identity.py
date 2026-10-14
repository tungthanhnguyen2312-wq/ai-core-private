"""Pin the shared canonical identity to the bytes the builders produced before consolidation."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders import canonical_identity as ci
from builders import current_research_synthesis_operational_workflow as workflow
from builders import prospective_research_attribution as attribution

# Frozen against the per-builder implementations at 07b822f.
_VALUE = {"ticker": "HPG", "b": [1, 2.5, "Hòa Phát"], "a": None}
_FROZEN = "current_research_context:dcb146de66ef47d02abec3d305546695f8268906630859798e32ec64581d1430"


def test_content_identity_is_frozen() -> None:
    assert ci.content_identity("current_research_context:", _VALUE) == _FROZEN
    assert ci.canonical_json(_VALUE) == '{"a":null,"b":[1,2.5,"H\\u00f2a Ph\\u00e1t"],"ticker":"HPG"}'


def test_builders_share_one_implementation() -> None:
    assert workflow._i is ci.content_identity
    assert attribution._identity is ci.content_identity


def test_non_finite_numbers_are_refused() -> None:
    with pytest.raises(ValueError):
        ci.content_identity("x:", {"value": math.nan})


def test_identity_string_and_json_object(tmp_path: Path) -> None:
    assert ci.is_identity_string("a:b") and not ci.is_identity_string(" ") and not ci.is_identity_string("ab")
    path = tmp_path / "x.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected JSON object"):
        ci.load_json_object(path)
    with pytest.raises(FileNotFoundError):
        ci.load_json_object(tmp_path / "missing.json")
