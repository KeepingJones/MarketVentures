"""
EOD Excel reconciliation report — the deliverable the Head of Market Data reads.

Sheet structure mirrors production Bloomberg/Refinitiv EOD break reports:
  1. Summary     — break counts by asset class and severity, run metadata
  2. Breaks      — full break list, sorted by severity
  3. Escalations — breaks requiring action with assigned owner
  4. Prices      — all quotes fetched this run for audit trail
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import REPORT_OUTPUT_DIR
from data.models import PriceBreak, PriceQuote
from recon.escalation import log_escalations

# Severity colour coding — mirrors Bloomberg terminal alert colours
SEVERITY_FILLS = {
    "CRITICAL": PatternFill("solid", fgColor="FFCCCC"),   # red
    "WARNING":  PatternFill("solid", fgColor="FFF2CC"),   # amber
    "INFO":     PatternFill("solid", fgColor="E8F4FD"),   # blue
}
HEADER_FILL   = PatternFill("solid", fgColor="1F3864")
HEADER_FONT   = Font(color="FFFFFF", bold=True)
BOLD          = Font(bold=True)
THIN_BORDER   = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)


def _auto_width(ws, min_w=10, max_w=50):
    for col in ws.columns:
        length = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(length + 2, min_w), max_w)


def _header_row(ws, headers: list[str], row: int = 1):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER


def generate_eod_report(
    breaks: list[PriceBreak],
    quotes: Optional[list[PriceQuote]] = None,
    run_date: Optional[str] = None,
) -> Path:
    if not run_date:
        run_date = datetime.utcnow().strftime("%Y-%m-%d")

    wb = openpyxl.Workbook()

    # ── Sheet 1: Summary ──────────────────────────────────────────────────────
    ws_sum = wb.active
    ws_sum.title = "Summary"

    ws_sum["A1"] = "EOD Price Reconciliation Report"
    ws_sum["A1"].font = Font(size=14, bold=True)
    ws_sum["A2"] = f"Run date: {run_date}"
    ws_sum["A3"] = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    ws_sum["A5"] = "Total breaks"
    ws_sum["B5"] = len(breaks)
    ws_sum["A6"] = "Critical"
    ws_sum["B6"] = sum(1 for b in breaks if b.severity == "CRITICAL")
    ws_sum["A7"] = "Warning"
    ws_sum["B7"] = sum(1 for b in breaks if b.severity == "WARNING")
    ws_sum["A8"] = "Info"
    ws_sum["B8"] = sum(1 for b in breaks if b.severity == "INFO")

    ws_sum.cell(6, 2).fill = SEVERITY_FILLS["CRITICAL"]
    ws_sum.cell(7, 2).fill = SEVERITY_FILLS["WARNING"]

    # Break counts by asset class
    _header_row(ws_sum, ["Asset Class", "Critical", "Warning", "Info", "Total"], row=10)
    asset_classes = sorted(set(b.asset_class for b in breaks))
    for row_idx, ac in enumerate(asset_classes, 11):
        ac_breaks = [b for b in breaks if b.asset_class == ac]
        ws_sum.cell(row_idx, 1, ac)
        ws_sum.cell(row_idx, 2, sum(1 for b in ac_breaks if b.severity == "CRITICAL")).fill = SEVERITY_FILLS["CRITICAL"] if any(b.severity == "CRITICAL" for b in ac_breaks) else PatternFill()
        ws_sum.cell(row_idx, 3, sum(1 for b in ac_breaks if b.severity == "WARNING"))
        ws_sum.cell(row_idx, 4, sum(1 for b in ac_breaks if b.severity == "INFO"))
        ws_sum.cell(row_idx, 5, len(ac_breaks))

    _auto_width(ws_sum)

    # ── Sheet 2: Breaks ───────────────────────────────────────────────────────
    ws_brk = wb.create_sheet("Breaks")
    headers = ["Severity", "Ticker", "Asset Class", "Source A", "Source B",
               "Price A", "Price B", "Diff %", "Tolerance %", "Cause", "Timestamp"]
    _header_row(ws_brk, headers)

    for row_idx, b in enumerate(breaks, 2):
        vals = [b.severity, b.ticker, b.asset_class, b.source_a, b.source_b,
                b.price_a, b.price_b, round(b.diff_pct, 4), round(b.tolerance_pct, 4),
                b.break_cause, b.timestamp.strftime("%Y-%m-%d %H:%M")]
        for col, v in enumerate(vals, 1):
            cell = ws_brk.cell(row_idx, col, v)
            cell.border = THIN_BORDER
        # Colour-code severity column
        ws_brk.cell(row_idx, 1).fill = SEVERITY_FILLS.get(b.severity, PatternFill())

    _auto_width(ws_brk)

    # ── Sheet 3: Escalations ─────────────────────────────────────────────────
    ws_esc = wb.create_sheet("Escalations")
    escalations = log_escalations(breaks)
    _header_row(ws_esc, ["Severity", "Ticker", "Asset Class", "Diff %", "Cause", "Owner", "Timestamp"])
    for row_idx, e in enumerate(escalations, 2):
        vals = [e["severity"], e["ticker"], e["asset_class"], e["diff_pct"],
                e["cause"], e["owner"], e["timestamp"]]
        for col, v in enumerate(vals, 1):
            ws_esc.cell(row_idx, col, v).border = THIN_BORDER
        ws_esc.cell(row_idx, 1).fill = SEVERITY_FILLS.get(e["severity"], PatternFill())
    _auto_width(ws_esc)

    # ── Sheet 4: All Prices ───────────────────────────────────────────────────
    if quotes:
        ws_px = wb.create_sheet("Prices")
        _header_row(ws_px, ["Ticker", "Source", "Asset Class", "Currency", "Price", "Bid", "Ask", "Volume", "Timestamp"])
        for row_idx, q in enumerate(quotes, 2):
            vals = [q.ticker, q.source, q.asset_class, q.currency, q.price,
                    q.bid, q.ask, q.volume, q.timestamp.strftime("%Y-%m-%d %H:%M")]
            for col, v in enumerate(vals, 1):
                ws_px.cell(row_idx, col, v).border = THIN_BORDER
        _auto_width(ws_px)

    # Save
    out_path = REPORT_OUTPUT_DIR / f"price-recon-{run_date}.xlsx"
    wb.save(out_path)
    return out_path
