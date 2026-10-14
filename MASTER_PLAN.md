# Consumer control-plane pointer

This repository is a Consumer contract layer. Current program state, sequencing,
and source/authority decisions belong to Producer: its compact current-state view
[`../stock-core-private/docs/ACTIVE_STATE.md`](../stock-core-private/docs/ACTIVE_STATE.md) and
[`../stock-core-private/docs/ROADMAP_STATE.json`](../stock-core-private/docs/ROADMAP_STATE.json)
(queried with `tools/stocklookup_roadmap.py`). Producer `docs/STATE.md` is preserved history.

Start Consumer work with `AGENTS.md`, then the current Producer authority required
by the task, then [the Consumer authority map](docs/current_consumer_authority_map.md).
Earlier phase plans and this file's predecessor are historical control-plane
material, not authorization to begin work.
