"""
PDF stakeholder report — generated via ReportLab.

Sections:
  1. Executive Summary — NAV, P&L, risk vs limits, open breaks
  2. Risk — VaR (95/99), Greeks summary, stress test P&L
  3. Liquidity — L1/L2/L3 breakdown, days-to-liquidate
  4. FX Hedging — GBP NAV, currency exposure, forward roll calendar
  5. Data Health — vendor quality scores, SLA breaches, open breaks

Designed for Head of Market Data and COO — charts first, tables second.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import REPORT_OUTPUT_DIR, FUND_BASE_CURRENCY


def generate_pdf_report(data: dict, run_date: Optional[str] = None) -> Path:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, white
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable,
        )
    except ImportError as e:
        raise ImportError(f"reportlab not installed: {e}")

    if not run_date:
        run_date = datetime.utcnow().strftime("%Y-%m-%d")

    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_OUTPUT_DIR / f"market-ops-{run_date}.pdf"

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    BLUE = HexColor("#3182ce")
    GREY = HexColor("#718096")

    def h1(text):
        return Paragraph(f"<font size=18 color='#1a1f2e'><b>{text}</b></font>", styles["Normal"])

    def h2(text):
        return Paragraph(f"<font size=13 color='#2d3748'><b>{text}</b></font>", styles["Normal"])

    def body(text):
        return Paragraph(f"<font size=10 color='#4a5568'>{text}</font>", styles["Normal"])

    def metric_row(label: str, value: str, note: str = "", alert: bool = False):
        color = "#e53e3e" if alert else "#2d3748"
        return [
            Paragraph(f"<font size=10 color='#718096'>{label}</font>", styles["Normal"]),
            Paragraph(f"<font size=12 color='{color}'><b>{value}</b></font>", styles["Normal"]),
            Paragraph(f"<font size=9 color='#a0aec0'>{note}</font>", styles["Normal"]),
        ]

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(h1("GBP Fund — Market Operations Report"))
    story.append(Spacer(1, 0.3*cm))
    story.append(body(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | "
                       f"Run date: {run_date} | PAPER_TRADE_MODE = True"))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=0.5*cm))

    fund = data.get("fund", {})
    nav = fund.get("nav_gbp", 0)
    drawdown = fund.get("drawdown_pct", 0)
    var95 = fund.get("var_95_gbp", 0)
    var99 = fund.get("var_99_gbp", 0)
    alerts = data.get("alerts", [])
    breaks_data = data.get("breaks", {})
    open_breaks = breaks_data.get("total_open", 0)
    critical_breaks = breaks_data.get("critical", 0)

    # ── Section 1: Executive Summary ─────────────────────────────────────────
    story.append(h2("1. Executive Summary"))
    story.append(Spacer(1, 0.3*cm))

    summary_data = [
        ["Metric", "Value", "Note"],
        metric_row("Fund NAV", f"£{nav:,.0f}", f"{FUND_BASE_CURRENCY} paper fund"),
        metric_row("Drawdown", f"{drawdown:.2f}%", "from peak", alert=drawdown > 5),
        metric_row("1-day VaR 95%", f"£{var95:,.0f}", f"{var95/nav*100:.2f}% of NAV" if nav else ""),
        metric_row("1-day VaR 99%", f"£{var99:,.0f}", f"{var99/nav*100:.2f}% of NAV" if nav else ""),
        metric_row("Open Price Breaks", str(open_breaks), f"{critical_breaks} critical",
                   alert=critical_breaks > 0),
    ]

    t = Table(summary_data, colWidths=[5*cm, 5*cm, 7*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2d3748")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f7fafc"), white]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    if alerts:
        story.append(Spacer(1, 0.3*cm))
        story.append(body("<b>Active Alerts:</b>"))
        for alert in alerts:
            color = "#e53e3e" if alert["level"] == "CRITICAL" else "#d69e2e"
            story.append(body(f"<font color='{color}'>⚠ [{alert['level']}] {alert['message']}</font>"))

    story.append(Spacer(1, 0.5*cm))

    # ── Section 2: Risk ───────────────────────────────────────────────────────
    story.append(h2("2. Risk"))
    story.append(Spacer(1, 0.3*cm))

    pnl_by_ac = data.get("pnl_by_asset_class", [])
    if pnl_by_ac:
        risk_data = [["Asset Class", "Market Value (£)", "Unrealised P&L (£)", "Positions"]]
        for row in pnl_by_ac:
            pnl_val = row.get("total_pnl_gbp", 0) or 0
            pnl_color = "#38a169" if pnl_val >= 0 else "#e53e3e"
            risk_data.append([
                row.get("asset_class", ""),
                f"£{(row.get('total_mv_gbp') or 0):,.0f}",
                Paragraph(f"<font color='{pnl_color}'>£{pnl_val:+,.0f}</font>", styles["Normal"]),
                str(row.get("position_count", 0)),
            ])
        rt = Table(risk_data, colWidths=[5*cm, 5*cm, 5*cm, 2*cm])
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2d3748")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f7fafc"), white]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(rt)

    story.append(Spacer(1, 0.5*cm))

    # ── Section 3: Liquidity ──────────────────────────────────────────────────
    story.append(h2("3. Liquidity"))
    story.append(Spacer(1, 0.3*cm))

    positions = data.get("positions", [])
    if positions:
        tier_counts = {"L1": 0, "L2": 0, "L3": 0}
        tier_mv = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
        for pos in positions:
            tier = pos.get("liquidity_tier", "L3")
            if tier in tier_counts:
                tier_counts[tier] += 1
                tier_mv[tier] += pos.get("market_value_gbp", 0) or 0

        liq_data = [["Tier", "Positions", "Market Value (£)", "Description"],
                    ["L1", str(tier_counts["L1"]), f"£{tier_mv['L1']:,.0f}", "Liquidate in 1 day"],
                    ["L2", str(tier_counts["L2"]), f"£{tier_mv['L2']:,.0f}", "Liquidate in 5 days"],
                    ["L3", str(tier_counts["L3"]), f"£{tier_mv['L3']:,.0f}", "Liquidate in 20+ days"]]
        lt = Table(liq_data, colWidths=[3*cm, 4*cm, 5*cm, 5*cm])
        lt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2d3748")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f7fafc"), white]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(lt)

    story.append(Spacer(1, 0.5*cm))

    # ── Section 4: FX Hedging ─────────────────────────────────────────────────
    story.append(h2("4. FX Hedging"))
    story.append(Spacer(1, 0.3*cm))

    forwards = data.get("fx_forwards", [])
    if forwards:
        fwd_data = [["Pair", "Notional (£)", "Spot", "Forward", "Tenor (days)", "Expires"]]
        for fwd in forwards[:10]:
            fwd_data.append([
                fwd.get("pair", ""),
                f"£{fwd.get('notional_gbp', 0):,.0f}",
                f"{fwd.get('spot_rate', 0):.4f}",
                f"{fwd.get('forward_rate', 0):.4f}",
                str(fwd.get("tenor_days", 0)),
                str(fwd.get("expires_at", ""))[:10],
            ])
        ft = Table(fwd_data, colWidths=[3*cm, 3.5*cm, 3*cm, 3*cm, 3*cm, 3*cm])
        ft.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2d3748")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f7fafc"), white]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(ft)
    else:
        story.append(body("No active FX forwards."))

    story.append(Spacer(1, 0.5*cm))

    # ── Section 5: Data Health ────────────────────────────────────────────────
    story.append(h2("5. Data Health"))
    story.append(Spacer(1, 0.3*cm))

    vendor_health = data.get("vendor_health", [])
    if vendor_health:
        vh_data = [["Vendor", "Quality Score", "Freshness", "Completeness", "Latency (min)"]]
        for v in vendor_health:
            score = v.get("overall_score", 0) or 0
            score_color = "#38a169" if score >= 80 else ("#d69e2e" if score >= 50 else "#e53e3e")
            vh_data.append([
                v.get("vendor_name", v.get("vendor_id", "")),
                Paragraph(f"<font color='{score_color}'><b>{score:.1f}</b></font>", styles["Normal"]),
                f"{v.get('freshness_score', 0) or 0:.1f}",
                f"{v.get('completeness_score', 0) or 0:.1f}",
                f"{v.get('latency_minutes', 0) or 0:.1f}",
            ])
        vht = Table(vh_data, colWidths=[5*cm, 4*cm, 3*cm, 3*cm, 3*cm])
        vht.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2d3748")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f7fafc"), white]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(vht)

    sla_penalties = data.get("sla_penalties", [])
    penalties_with_cost = [p for p in sla_penalties if p.get("penalty_usd", 0) > 0]
    if penalties_with_cost:
        story.append(Spacer(1, 0.3*cm))
        story.append(body("<b>SLA Penalties Due:</b>"))
        for p in penalties_with_cost:
            story.append(body(f"  {p['vendor_name']}: {p['total_outage_hours']:.1f}h outage → "
                               f"${p['penalty_usd']:.2f} rebate owed"))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=GREY))
    story.append(Spacer(1, 0.2*cm))
    story.append(body(f"<i>Generated by market-ops — GBP Fund Portfolio | PAPER_TRADE_MODE = True | {run_date}</i>"))

    doc.build(story)
    return out_path
