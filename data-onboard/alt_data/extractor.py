"""
Unstructured alt data ingestion: PDF → structured JSON signal via Ollama.

Accepts earnings transcripts, SEC filings, or research reports.
Extracts: ticker, sentiment, revenue_guidance, earnings_surprise, key_risks.

Input: PDF file path or raw text
Output: structured dict matching config.ALT_DATA_SIGNAL_SCHEMA
"""
import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from config import (
    OLLAMA_URL, OLLAMA_MODEL,
    ALT_DATA_INPUT_DIR, ALT_DATA_OUTPUT_DIR,
    ALT_DATA_EXTRACTION_PROMPT, ALT_DATA_SIGNAL_SCHEMA,
)
from db.database import save_alt_signal

logger = logging.getLogger(__name__)


def _read_pdf_text(path: Path) -> Optional[str]:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text[:8000]  # Ollama context limit
    except ImportError:
        try:
            import PyPDF2
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
            return text[:8000]
        except ImportError:
            logger.warning("No PDF reader installed (pdfplumber or PyPDF2)")
            return None
    except Exception as e:
        logger.error(f"PDF read failed for {path}: {e}")
        return None


def _detect_source_type(filename: str) -> str:
    name = filename.lower()
    if "transcript" in name or "earnings" in name:
        return "earnings_transcript"
    if "10-k" in name or "10k" in name or "sec" in name or "filing" in name:
        return "sec_filing"
    return "research_report"


def extract_signal_from_text(text: str, source_file: str) -> Optional[dict]:
    schema_str = json.dumps({k: str(v) for k, v in ALT_DATA_SIGNAL_SCHEMA.items()}, indent=2)
    prompt = ALT_DATA_EXTRACTION_PROMPT.format(schema=schema_str, text=text[:6000])

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        raw = resp.json().get("response", "").strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        signal = json.loads(raw)
        return signal
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned non-JSON for {source_file}: {e}")
        return None
    except Exception as e:
        logger.error(f"Alt data extraction failed for {source_file}: {e}")
        return None


def process_file(file_path: Path) -> Optional[dict]:
    source_file = file_path.name
    source_type = _detect_source_type(source_file)

    if file_path.suffix.lower() == ".pdf":
        text = _read_pdf_text(file_path)
    elif file_path.suffix.lower() in (".txt", ".md"):
        text = file_path.read_text(encoding="utf-8", errors="ignore")[:8000]
    else:
        logger.warning(f"Unsupported file type: {file_path.suffix}")
        return None

    if not text:
        return None

    signal = extract_signal_from_text(text, source_file)
    if not signal:
        return None

    signal["source_type"] = source_type

    save_alt_signal(
        source_file=source_file,
        ticker=signal.get("ticker"),
        sentiment=signal.get("sentiment", "neutral"),
        revenue_guidance=signal.get("revenue_guidance", "N/A"),
        earnings_surprise=signal.get("earnings_surprise", "N/A"),
        key_risks=signal.get("key_risks", []),
        source_type=source_type,
        confidence=float(signal.get("confidence", 0.5)),
    )

    output_dir = Path(ALT_DATA_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / (file_path.stem + "_signal.json")
    out_path.write_text(json.dumps(signal, indent=2))
    logger.info(f"Alt signal saved → {out_path}")

    return signal


def process_all_pending() -> list[dict]:
    input_dir = Path(ALT_DATA_INPUT_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path(ALT_DATA_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    supported = (".pdf", ".txt", ".md")
    files = [f for f in input_dir.iterdir() if f.suffix.lower() in supported]

    if not files:
        logger.info("No alt data files in input directory")
        return []

    for f in files:
        already_done = (output_dir / (f.stem + "_signal.json")).exists()
        if already_done:
            logger.info(f"Skipping {f.name} — already processed")
            continue
        result = process_file(f)
        if result:
            results.append(result)

    logger.info(f"Alt data: processed {len(results)} new files")
    return results
