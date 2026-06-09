"""FastAPI routes — vendor catalogue, quality scores, entitlement checks, LLM query."""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db.database import (
    get_vendors, get_vendor, get_datasets, get_risk_path_datasets,
    get_latest_quality_scores, get_vendor_quality_history,
    get_usage_by_desk, get_cost_allocation,
    check_entitlement, log_usage, get_sla_summary,
)
from config import OLLAMA_URL, OLLAMA_MODEL, CONTRACTS_INDEX, RAG_TOP_K

logger = logging.getLogger(__name__)
app = FastAPI(title="market-data-hub", version="1.0")

_STATIC = Path(__file__).parent.parent / "dashboard"
if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/")
def index():
    html = _STATIC / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return {"status": "market-data-hub running", "docs": "/docs"}


# ── Vendor catalogue ──────────────────────────────────────────────────────────

@app.get("/api/vendors")
def vendors(status: Optional[str] = Query(None)):
    return get_vendors(status=status)


@app.get("/api/vendors/{vendor_id}")
def vendor_detail(vendor_id: str):
    v = get_vendor(vendor_id)
    if not v:
        raise HTTPException(404, f"Vendor {vendor_id} not found")
    scores = get_vendor_quality_history(vendor_id, limit=10)
    return {**v, "quality_history": scores}


@app.get("/api/datasets")
def datasets(vendor_id: Optional[str] = Query(None), asset_class: Optional[str] = Query(None)):
    return get_datasets(vendor_id=vendor_id, asset_class=asset_class)


@app.get("/api/datasets/risk-path")
def risk_path_datasets():
    return get_risk_path_datasets()


# ── Quality scores ────────────────────────────────────────────────────────────

@app.get("/api/quality")
def quality_scores():
    return get_latest_quality_scores()


@app.post("/api/quality/run")
def run_quality_scoring():
    from data.quality_scorer import run_all_scoring
    results = run_all_scoring()
    return {"scored": len(results), "results": results}


# ── Usage & cost allocation ───────────────────────────────────────────────────

@app.get("/api/usage")
def usage():
    return get_usage_by_desk()


@app.get("/api/cost-allocation")
def cost_allocation():
    return get_cost_allocation()


class UsageEvent(BaseModel):
    vendor_id: str
    desk: str
    event_type: str = "query"
    dataset_id: Optional[int] = None
    records: int = 0


@app.post("/api/usage")
def track_usage(event: UsageEvent):
    log_usage(event.vendor_id, event.desk, event.event_type, event.dataset_id, event.records)
    return {"status": "logged"}


# ── Entitlement check ─────────────────────────────────────────────────────────

class EntitlementRequest(BaseModel):
    vendor_id: str
    desk: str
    licence_type: str
    dataset_id: Optional[int] = None


@app.post("/api/entitlement/check")
def entitlement_check(req: EntitlementRequest):
    allowed, reason = check_entitlement(
        req.vendor_id, req.desk, req.licence_type, req.dataset_id
    )
    return {"allowed": allowed, "reason": reason, "desk": req.desk,
            "licence_type": req.licence_type}


# ── SLA summary ───────────────────────────────────────────────────────────────

@app.get("/api/sla")
def sla_summary(window_days: int = 30):
    return get_sla_summary(window_days=window_days)


# ── LLM query over catalogue ──────────────────────────────────────────────────

class LLMQuery(BaseModel):
    question: str
    desk: Optional[str] = None


@app.post("/api/query")
def llm_query(req: LLMQuery):
    try:
        import httpx
        vendors = get_vendors()
        datasets = get_datasets()
        scores = get_latest_quality_scores()

        context = f"""You are a market data catalogue assistant.

Vendors: {json.dumps([{k: v[k] for k in ('id','name','status','cost_usd_annual')} for v in vendors], indent=2)}

Datasets (sample): {json.dumps([{k: v[k] for k in ('vendor_id','name','asset_class','licence_type','quality_score')} for v in datasets[:20]], indent=2)}

Quality scores: {json.dumps([{k: v[k] for k in ('vendor_id','vendor_name','overall_score','freshness_score')} for v in scores], indent=2)}

Answer the question concisely. If asked about licences or entitlements, cite the licence_type field.
Question: {req.question}"""

        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": context, "stream": False},
            timeout=30.0,
        )
        answer = resp.json().get("response", "No response from LLM.")
        return {"question": req.question, "answer": answer, "model": OLLAMA_MODEL}
    except Exception as e:
        logger.error(f"LLM query failed: {e}")
        return {"question": req.question, "answer": f"LLM unavailable: {e}", "model": OLLAMA_MODEL}


# ── RAG over vendor contracts ─────────────────────────────────────────────────

class ContractQuery(BaseModel):
    question: str


@app.post("/api/contracts/query")
def contract_rag(req: ContractQuery):
    try:
        index_path = Path(CONTRACTS_INDEX)
        if not index_path.exists():
            return {"answer": "No contracts indexed yet. Add PDFs to ./contracts/ and run /api/contracts/index.", "chunks_used": 0}

        chunks = json.loads(index_path.read_text())

        question_lower = req.question.lower()
        keywords = [w for w in question_lower.split() if len(w) > 3]
        scored = []
        for chunk in chunks:
            text = chunk.get("text", "").lower()
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                scored.append((hits, chunk))
        scored.sort(key=lambda x: -x[0])
        top_chunks = [c["text"] for _, c in scored[:RAG_TOP_K]]

        if not top_chunks:
            return {"answer": "No relevant contract clauses found.", "chunks_used": 0}

        import httpx
        context = "\n---\n".join(top_chunks)
        prompt = f"""You are a legal assistant reviewing vendor data contracts.
Contract excerpts:
{context}

Question: {req.question}
Answer citing the specific clause or section:"""

        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30.0,
        )
        answer = resp.json().get("response", "No response.")
        return {"answer": answer, "chunks_used": len(top_chunks)}
    except Exception as e:
        logger.error(f"Contract RAG failed: {e}")
        return {"answer": f"RAG error: {e}", "chunks_used": 0}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    vendors = get_vendors(status="active")
    scores = get_latest_quality_scores()
    return {
        "status": "ok",
        "service": "market-data-hub",
        "active_vendors": len(vendors),
        "scored_vendors": len(scores),
        "endpoints": ["/api/vendors", "/api/datasets", "/api/quality",
                      "/api/usage", "/api/cost-allocation", "/api/entitlement/check",
                      "/api/query", "/api/contracts/query", "/api/sla"],
    }
