"""Provider-neutral prepare/ingest workflow; no model invocation or prose generation."""
from __future__ import annotations
import copy,hashlib,json
from typing import Any,Mapping,Sequence
from builders.structured_research_synthesis_boundary import LEGACY_DIRECT,accept_structured_research_synthesis
from builders.accepted_structured_synthesis_corpus import register_accepted_structured_synthesis,corpus_to_dossier_batch_inputs
SCHEMA_VERSION='1.0.0';CONTRACT_VERSION='current_research_synthesis_operational_workflow/v1'
def _c(v):return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)
def _i(p,v):return p+hashlib.sha256(_c(v).encode()).hexdigest()
_COMPONENTS=('watchlist_tactical_entry_classifier','current_opportunity_decision_context','current_research_decision_packet','current_research_scenario_context','current_market_sector_leadership_context','current_financial_momentum_context','current_corporate_event_context','current_research_risk_register','market_wide_current_valuation','market_wide_historical_research_context')
def build_synthesis_request_package(context:Mapping[str,Any],*,packet_consumption_mode:str=LEGACY_DIRECT)->dict[str,Any]:
 if not isinstance(context,Mapping) or not isinstance(context.get('ticker'),str):raise ValueError('REQUEST_CONTEXT_MALFORMED')
 meta=accept_structured_research_synthesis(context,{},packet_consumption_mode=packet_consumption_mode).get('derived_contract_metadata',{})
 compact={k:{f:v for f,v in value.items() if f in {'status','session','research_session','source_artifact_identity','authority_boundary','reason_codes'}} for k in _COMPONENTS if isinstance((value:=context.get(k)),Mapping)}
 request={'schema_version':SCHEMA_VERSION,'contract_version':CONTRACT_VERSION,'ticker':context['ticker'],'research_session':None,'context_identity':_i('current_research_context:',context),'packet_consumption_mode':packet_consumption_mode,'permitted_evidence_refs':copy.deepcopy(meta.get('known_evidence_refs') or []),'deterministic_decision_context':copy.deepcopy(meta.get('expected_upstream_decision_context') or {}),'component_metadata':compact,'scenario_contracts':{'evidence_bound':'current_evidence_bound_scenario Bear/Base/Bull is not probability','research_axis':'current_research_scenario_context CONSERVATIVE/BASE/SPECULATIVE is distinct'},'required_response_schema':{'uses_existing':'structured_research_synthesis_response/v1','is_actionable_must_be_false':True,'required_fields':['ticker','analysis_session','thesis','counter_thesis','supporting_evidence','counter_evidence','unresolved_questions','authority_limitations','provenance_references']},'prohibited_claims':['probability','expected_return','target_price','intrinsic_value','BUY_SELL_HOLD','new_entry_action','risk_score','position_size','capacity','leverage','PIT','RAW_AS_TRADED','backtest'],'authority_limitations':['Use only permitted_evidence_refs. Do not upgrade deterministic decisions or component-local dates.']}
 request['request_identity']=_i('current_research_synthesis_request:',request);return request
def prepare_synthesis_session(inputs:Sequence[Mapping[str,Any]],*,session_label:str)->dict[str,Any]:
 if not isinstance(session_label,str) or not session_label:raise ValueError('SESSION_LABEL_MALFORMED')
 seen=set();packages=[];contexts={}
 for item in inputs:
  if not isinstance(item,Mapping) or not isinstance(item.get('context'),Mapping):raise ValueError('SESSION_INPUT_MALFORMED')
  p=build_synthesis_request_package(item['context'],packet_consumption_mode=item.get('packet_consumption_mode',LEGACY_DIRECT));t=p['ticker']
  if t in seen:raise ValueError('SESSION_DUPLICATE_TICKER:'+t)
  seen.add(t);packages.append(p);contexts[t]=copy.deepcopy(item['context'])
 packages.sort(key=lambda x:x['ticker']);manifest={'schema_version':SCHEMA_VERSION,'contract_version':CONTRACT_VERSION,'session_label':session_label,'requests':packages,'denominator':len(packages),'authority_boundary':{'is_actionable':False,'no_model_invocation':True,'explicit_response_ingestion_only':True}}
 manifest['session_identity']=_i('current_research_synthesis_session:',manifest);return {'manifest':manifest,'contexts_by_ticker':contexts}
def ingest_synthesis_session(prepared:Mapping[str,Any],responses_by_ticker:Mapping[str,Any],corpus:Mapping[str,Any])->dict[str,Any]:
 manifest=prepared.get('manifest');contexts=prepared.get('contexts_by_ticker')
 if not isinstance(manifest,Mapping) or not isinstance(contexts,Mapping) or not isinstance(responses_by_ticker,Mapping):raise ValueError('SESSION_INGEST_INPUT_MALFORMED')
 current=copy.deepcopy(dict(corpus));rows=[]
 for req in manifest.get('requests',[]):
  ticker=req['ticker'];response=responses_by_ticker.get(ticker);context=contexts.get(ticker)
  if response is None:rows.append({'ticker':ticker,'disposition':'NO_RESPONSE_FILE','reason_codes':['explicit_response_not_supplied']});continue
  outcome=register_accepted_structured_synthesis(current,context,response,packet_consumption_mode=req['packet_consumption_mode']);current=outcome['corpus'];rows.append({'ticker':ticker,'disposition':'ACCEPTED' if outcome['status'] in {'REGISTERED','DUPLICATE_IDENTICAL'} else 'REJECTED','registration_status':outcome['status'],'accepted_synthesis_identity':outcome['record'].get('accepted_synthesis_identity') if outcome.get('record') else None,'reason_codes':outcome['reason_codes']})
 handoff=corpus_to_dossier_batch_inputs(current,{_i('current_research_context:',v):v for v in contexts.values()})
 result={'session_identity':manifest['session_identity'],'response_results':rows,'accepted_count':sum(r['disposition']=='ACCEPTED' for r in rows),'rejected_count':sum(r['disposition']=='REJECTED' for r in rows),'no_response_count':sum(r['disposition']=='NO_RESPONSE_FILE' for r in rows),'updated_corpus_identity':current['corpus_identity'],'dossier_batch_inputs':handoff,'unexplained_residual':len(rows)-sum(1 for r in rows if r['disposition'] in {'ACCEPTED','REJECTED','NO_RESPONSE_FILE'})}
 return {'corpus':current,'ingestion_manifest':result}
