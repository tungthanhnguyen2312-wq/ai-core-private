"""Immutable, acceptance-gated retention for structured current-research responses."""
from __future__ import annotations
import copy, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence
from builders.structured_research_synthesis_boundary import LEGACY_DIRECT, accept_structured_research_synthesis

SCHEMA_VERSION = "1.0.0"; CONTRACT_VERSION = "accepted_structured_synthesis_corpus/v1"
def _canonical(v: Any) -> str: return json.dumps(v, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
def _identity(p: str, v: Any) -> str: return p + hashlib.sha256(_canonical(v).encode()).hexdigest()
def _context_identity(context: Mapping[str, Any]) -> str: return _identity("current_research_context:", context)

def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"registered_accepted_response_count": len(records), "unique_ticker_count": len({r["ticker"] for r in records}), "unique_research_session_count": len({r["research_session"] for r in records}), "unexplained_residual": 0}

def empty_accepted_structured_synthesis_corpus() -> dict[str, Any]:
    corpus = {"schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION, "records": [], "summary": _summary([]), "authority_boundary": {"is_actionable": False, "accepted_response_retention_only": True, "does_not_generate_or_upgrade_synthesis": True, "prohibited_interpretations": ["recommendation", "probability", "expected_return", "target_price", "intrinsic_value", "position_size", "PIT", "RAW_AS_TRADED", "backtest"]}}
    corpus["corpus_identity"] = _identity("accepted_structured_synthesis_corpus:", corpus); return corpus

def replay_accepted_structured_synthesis_corpus(corpus: Mapping[str, Any]) -> None:
    if corpus.get("contract_version") != CONTRACT_VERSION: raise ValueError("CORPUS_CONTRACT_VERSION_MISMATCH")
    expected = dict(corpus); identity = expected.pop("corpus_identity", None)
    if _identity("accepted_structured_synthesis_corpus:", expected) != identity: raise ValueError("CORPUS_IDENTITY_MISMATCH")
    records = corpus.get("records")
    if not isinstance(records, list) or corpus.get("summary") != _summary(records): raise ValueError("CORPUS_SUMMARY_MISMATCH")
    ids = [r.get("accepted_synthesis_identity") for r in records if isinstance(r, Mapping)]
    if len(ids) != len(set(ids)): raise ValueError("CORPUS_DUPLICATE_IDENTITY")

def register_accepted_structured_synthesis(corpus: Mapping[str, Any], context: Mapping[str, Any], response: str | Mapping[str, Any], *, packet_consumption_mode: str = LEGACY_DIRECT) -> dict[str, Any]:
    replay_accepted_structured_synthesis_corpus(corpus)
    accepted = accept_structured_research_synthesis(context, response, packet_consumption_mode=packet_consumption_mode)
    if accepted.get("status") != "accepted": return {"status": "REJECTED", "reason_codes": list(accepted.get("reasons") or []), "corpus": copy.deepcopy(dict(corpus)), "record": None}
    output, meta = accepted["accepted_output"], accepted["derived_contract_metadata"]
    context_id = _context_identity(context); identity = _identity("accepted_structured_synthesis:", {"accepted_response": output, "source_context_identity": context_id, "packet_consumption_mode": packet_consumption_mode})
    record = {"schema_version": SCHEMA_VERSION, "registration_status": "ACCEPTED", "accepted_synthesis_identity": identity, "ticker": output["ticker"], "research_session": output["analysis_session"], "source_context_identity": context_id, "packet_consumption_mode": packet_consumption_mode, "accepted_response": copy.deepcopy(output), "acceptance_metadata": {"known_evidence_refs": copy.deepcopy(meta.get("known_evidence_refs") or []), "packet_direct_conflicts": copy.deepcopy(meta.get("current_research_decision_packet_component_conflicts") or []), "packet_legacy_parity": copy.deepcopy(meta.get("packet_legacy_parity")), "source_sessions": {k: copy.deepcopy(v) for k,v in meta.items() if k.endswith("_session") or k.endswith("_source_sessions")}}, "evidence_ref_count": len(output.get("provenance_references") or []), "authority_limitation_count": len(output.get("authority_limitations") or []), "retained_reference": f"records/{identity.split(':',1)[1]}.json"}
    existing = next((r for r in corpus["records"] if r.get("accepted_synthesis_identity") == identity), None)
    if existing is not None:
        if _canonical(existing) == _canonical(record): return {"status": "DUPLICATE_IDENTICAL", "reason_codes": [], "corpus": copy.deepcopy(dict(corpus)), "record": copy.deepcopy(existing)}
        return {"status": "CONFLICT_FAIL_CLOSED", "reason_codes": ["accepted_synthesis_identity_content_conflict"], "corpus": copy.deepcopy(dict(corpus)), "record": None}
    records = sorted([*copy.deepcopy(corpus["records"]), record], key=lambda r: r["accepted_synthesis_identity"])
    updated = {**copy.deepcopy(dict(corpus)), "records": records, "summary": _summary(records)}; updated.pop("corpus_identity", None); updated["corpus_identity"] = _identity("accepted_structured_synthesis_corpus:", updated)
    return {"status": "REGISTERED", "reason_codes": [], "corpus": updated, "record": copy.deepcopy(record)}

def register_many(corpus: Mapping[str, Any], inputs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    current = copy.deepcopy(dict(corpus)); results=[]
    for item in sorted(inputs, key=lambda x: (str(x.get("ticker")), _canonical(x.get("response")))):
        if not isinstance(item, Mapping) or not isinstance(item.get("context"), Mapping) or "response" not in item:
            results.append({"status":"MALFORMED","reason_codes":["registration_input_malformed"]}); continue
        outcome = register_accepted_structured_synthesis(current, item["context"], item["response"], packet_consumption_mode=item.get("packet_consumption_mode", LEGACY_DIRECT)); current=outcome["corpus"]; results.append({"status":outcome["status"],"reason_codes":outcome["reason_codes"],"accepted_synthesis_identity": outcome["record"].get("accepted_synthesis_identity") if outcome.get("record") else None})
    return {"corpus": current, "receipt": {"input_count":len(inputs), "result_counts": {s:sum(r["status"]==s for r in results) for s in sorted({r["status"] for r in results})}, "results":results}}

def query_accepted_structured_synthesis_corpus(corpus: Mapping[str, Any], **filters: str) -> list[dict[str, Any]]:
    allowed={"ticker","research_session","accepted_synthesis_identity","source_context_identity"}
    if set(filters)-allowed or not all(isinstance(v,str) for v in filters.values()): raise ValueError("INVALID_CORPUS_QUERY")
    return [copy.deepcopy(dict(r)) for r in corpus.get("records",[]) if isinstance(r,Mapping) and all(r.get(k)==v for k,v in filters.items())]

def corpus_to_dossier_batch_inputs(corpus: Mapping[str, Any], contexts_by_identity: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Explicit adapter; callers supply contexts, so corpus never reconstructs them."""
    replay_accepted_structured_synthesis_corpus(corpus); rows=[]
    for r in corpus["records"]:
        context=contexts_by_identity.get(r["source_context_identity"])
        rows.append({"ticker":r["ticker"], "context":copy.deepcopy(context) if isinstance(context,Mapping) else None, "synthesis":copy.deepcopy(r["accepted_response"]), "corpus_accepted_synthesis_identity":r["accepted_synthesis_identity"]})
    return rows

def render_accepted_structured_synthesis_inventory(corpus: Mapping[str, Any]) -> str:
    s=corpus["summary"]; lines=["# Accepted Structured Synthesis Corpus", "", f"Corpus identity: `{corpus['corpus_identity']}`", f"Registered accepted responses: `{s['registered_accepted_response_count']}`", "", "| Ticker | Research session | Accepted synthesis identity |", "|---|---|---|"]
    lines += [f"| {r['ticker']} | {r['research_session']} | `{r['accepted_synthesis_identity']}` |" for r in corpus["records"]]
    if not corpus["records"]: lines += ["| - | - | No real retained accepted structured synthesis records |"]
    return "\n".join(lines)+"\n"

def _atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".corpus-",suffix=".tmp")
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="") as h:h.write(content)
        os.replace(tmp,path)
    except Exception:
        if os.path.exists(tmp):os.unlink(tmp)
        raise
def write_accepted_structured_synthesis_corpus(output_dir: Path, corpus: Mapping[str, Any]) -> dict[str, Path]:
    replay_accepted_structured_synthesis_corpus(corpus); files={output_dir/"accepted_structured_synthesis_corpus.json":_canonical(corpus)+"\n",output_dir/"accepted_structured_synthesis_inventory.md":render_accepted_structured_synthesis_inventory(corpus)}
    for r in corpus["records"]: files[output_dir/r["retained_reference"]]=_canonical(r)+"\n"
    for p,c in files.items():
        if p.exists() and p.read_text(encoding="utf-8")!=c:raise ValueError("IMMUTABLE_CORPUS_OUTPUT_CONFLICT:"+str(p))
    for p,c in files.items():
        if not p.exists():_atomic(p,c)
    return {"corpus":output_dir/"accepted_structured_synthesis_corpus.json","inventory":output_dir/"accepted_structured_synthesis_inventory.md"}
