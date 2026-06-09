"""FastAPI routes — vendor onboarding pipeline API."""
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db.database import (
    get_all_vendors, get_vendor, get_stage_log,
    get_qa_assessments, get_figi_mappings, get_coverage_gaps,
    get_alt_signals, advance_stage,
)
from config import PIPELINE_STAGES

logger = logging.getLogger(__name__)
app = FastAPI(title="data-onboard", version="1.0")

_STATIC = Path(__file__).parent.parent / "dashboard"
if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/")
def index():
    html = _STATIC / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return {"status": "data-onboard running", "docs": "/docs"}


# ── Pipeline ──────────────────────────────────────────────────────────────────

@app.get("/api/vendors")
def vendors():
    return get_all_vendors()


@app.get("/api/vendors/{vendor_id}")
def vendor_detail(vendor_id: str):
    v = get_vendor(vendor_id)
    if not v:
        raise HTTPException(404, f"Vendor {vendor_id} not found")
    return {
        **v,
        "stage_log": get_stage_log(vendor_id),
        "qa_assessments": get_qa_assessments(vendor_id),
        "figi_mappings": get_figi_mappings(vendor_id),
        "coverage_gaps": get_coverage_gaps(vendor_id),
    }


class IntakeForm(BaseModel):
    vendor_name: str
    vendor_id: str
    contact_email: str
    api_endpoint: str
    asset_classes: list[str]
    sample_tickers: Optional[list[str]] = None


@app.post("/api/intake")
def intake(form: IntakeForm):
    from pipeline.intake import process_intake
    result = process_intake(form.model_dump(exclude={"sample_tickers"}),
                            sample_tickers=form.sample_tickers)
    return result


class StageAdvance(BaseModel):
    stage: str
    status: str = "pass"
    notes: str = ""


@app.post("/api/vendors/{vendor_id}/advance")
def advance(vendor_id: str, req: StageAdvance):
    if req.stage not in PIPELINE_STAGES:
        raise HTTPException(400, f"Invalid stage. Valid stages: {PIPELINE_STAGES}")
    advance_stage(vendor_id, req.stage, req.status, req.notes)
    return {"status": "updated", "vendor_id": vendor_id, "new_stage": req.stage}


# ── QA ────────────────────────────────────────────────────────────────────────

@app.post("/api/vendors/{vendor_id}/qa")
def run_qa(vendor_id: str):
    v = get_vendor(vendor_id)
    if not v:
        raise HTTPException(404, f"Vendor {vendor_id} not found")
    from qa.assessor import simulate_qa_assessment
    result = simulate_qa_assessment(vendor_id, v["vendor_name"])
    return result


# ── Alt data ──────────────────────────────────────────────────────────────────

@app.post("/api/alt-data/process")
def process_alt_data():
    from alt_data.extractor import process_all_pending
    results = process_all_pending()
    return {"processed": len(results), "signals": results}


@app.get("/api/alt-data/signals")
def alt_signals(limit: int = 20):
    return get_alt_signals(limit=limit)


@app.post("/api/alt-data/upload")
async def upload_alt_data(file: UploadFile = File(...)):
    from config import ALT_DATA_INPUT_DIR
    import aiofiles
    input_dir = Path(ALT_DATA_INPUT_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)
    dest = input_dir / file.filename
    async with aiofiles.open(dest, "wb") as f:
        content = await file.read()
        await f.write(content)
    return {"status": "uploaded", "filename": file.filename, "size_bytes": len(content)}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    vendors = get_all_vendors()
    by_stage = {}
    for v in vendors:
        s = v["current_stage"]
        by_stage[s] = by_stage.get(s, 0) + 1
    return {
        "status": "ok",
        "service": "data-onboard",
        "total_vendors": len(vendors),
        "pipeline_stages": PIPELINE_STAGES,
        "by_stage": by_stage,
        "endpoints": ["/api/vendors", "/api/intake", "/api/alt-data/signals",
                      "/api/alt-data/process", "/api/alt-data/upload"],
    }
