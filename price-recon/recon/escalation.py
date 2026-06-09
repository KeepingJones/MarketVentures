"""
Escalation routing for price breaks.

In production, breaks route to different teams:
  CRITICAL FX        → Market Data team (immediately — affects entire book)
  CRITICAL equity    → Reference Data team
  CRITICAL bond      → Fixed Income Ops
  WARNING            → Market Data team (next morning)
  INFO               → No action, logged only
"""
import logging
from data.models import PriceBreak

logger = logging.getLogger(__name__)

ESCALATION_ROUTES = {
    "fx":        {"CRITICAL": "Market Data Team (immediate)",  "WARNING": "Market Data Team",      "INFO": None},
    "equity":    {"CRITICAL": "Reference Data Team",           "WARNING": "Market Data Team",      "INFO": None},
    "govt_bond": {"CRITICAL": "Fixed Income Ops",              "WARNING": "Market Data Team",      "INFO": None},
    "corp_bond": {"CRITICAL": "Fixed Income Ops",              "WARNING": "Fixed Income Ops",      "INFO": None},
    "commodity": {"CRITICAL": "Market Data Team",              "WARNING": "Market Data Team",      "INFO": None},
    "volatility":{"CRITICAL": "Market Data Team",              "WARNING": "Market Data Team",      "INFO": None},
    "default":   {"CRITICAL": "Market Data Team",              "WARNING": "Market Data Team",      "INFO": None},
}


def get_escalation_owner(b: PriceBreak) -> str | None:
    """Return the team that owns this break, or None if no action needed."""
    routes = ESCALATION_ROUTES.get(b.asset_class, ESCALATION_ROUTES["default"])
    return routes.get(b.severity)


def log_escalations(breaks: list[PriceBreak]) -> list[dict]:
    """Log all breaks that require action and return escalation records."""
    escalations = []
    for b in breaks:
        owner = get_escalation_owner(b)
        if owner:
            record = {
                "ticker": b.ticker,
                "asset_class": b.asset_class,
                "severity": b.severity,
                "cause": b.break_cause,
                "diff_pct": b.diff_pct,
                "owner": owner,
                "timestamp": b.timestamp.isoformat(),
            }
            escalations.append(record)
            logger.warning(
                f"[{b.severity}] {b.ticker} ({b.asset_class}) - "
                f"{b.break_cause} {b.diff_pct:.2f}% -> {owner}"
            )
    return escalations
