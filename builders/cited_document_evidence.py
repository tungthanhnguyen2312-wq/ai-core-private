"""Consumer-safe pass-through for Producer cited-document retrieval results."""
from __future__ import annotations
from typing import Any, Mapping

ALLOWED_TICKERS={"HPG","VNM","VCB"}

def attach(context: dict[str,Any], query: Mapping[str,Any], result: Mapping[str,Any]) -> dict[str,Any]:
    ticker=str(context.get("ticker") or "")
    requested=str(query.get("ticker") or ticker)
    section={"query":{"ticker":requested,"period":query.get("period"),"metric":query.get("metric"),"keyword":query.get("keyword")},"ticker":ticker,"retrieval_status":result.get("state","unavailable"),"reason":result.get("reason"),"results":[]}
    if ticker not in ALLOWED_TICKERS or requested != ticker:
        section.update({"retrieval_status":"unavailable","reason":"unsupported_query"})
    else:
        for item in result.get("results",[]) if isinstance(result.get("results"),list) else []:
            if item.get("ticker") != ticker or not item.get("citations"): continue
            section["results"].append({"document_id":item.get("document_id"),"document_sha256":item.get("document_sha256"),"chunk_id":item.get("chunk_id"),"page":item.get("page"),"section":item.get("section"),"published_at":item.get("published_at"),"observed_at":item.get("observed_at"),"citation_ids":[x.get("citation_id") for x in item["citations"] if x.get("citation_id")]})
        section["results"].sort(key=lambda x:(str(x["document_id"]),str(x["chunk_id"])))
        if section["retrieval_status"]=="available" and not section["results"]: section.update({"retrieval_status":"unavailable","reason":"no_source_supported_passage"})
    context["cited_document_evidence"]=section
    return context