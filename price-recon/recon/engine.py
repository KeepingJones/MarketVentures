"""
Core reconciliation engine.

Fetches prices from all live sources, cross-checks them pairwise per instrument,
classifies every break, assigns liquidity-adjusted tolerances, and returns
the full break list ready for DB persistence + reporting.
"""
import logging
from datetime import datetime

from config import INSTRUMENTS, TOLERANCES
from data.models import PriceQuote, PriceBreak
from data.sources.yahoo import get_bulk_quotes
from data.sources.fred import get_all_quotes
from data.sources.ecb import get_fx_rates
from recon.classifier import classify_break
from recon.liquidity import get_liquidity_tier, get_tolerance_for_tier

logger = logging.getLogger(__name__)


class ReconEngine:
    def __init__(self):
        self._quotes: dict[str, list[PriceQuote]] = {}  # ticker → [quotes from each source]

    # ── Data ingestion ────────────────────────────────────────────────────────

    def fetch_all(self) -> dict[str, list[PriceQuote]]:
        """Pull prices from all sources and index by ticker."""
        self._quotes = {}

        # Yahoo Finance — primary source for equities, FX, bonds ETF, commodities, vol
        yahoo_quotes = get_bulk_quotes(INSTRUMENTS)
        for q in yahoo_quotes:
            self._quotes.setdefault(q.ticker, []).append(q)

        # FRED — secondary source for govt bond yields, credit spreads, rates
        fred_quotes = get_all_quotes()
        for q in fred_quotes:
            self._quotes.setdefault(q.ticker, []).append(q)

        # ECB — secondary source for EUR FX rates (cross-checks Yahoo FX)
        ecb_quotes = get_fx_rates()
        for q in ecb_quotes:
            self._quotes.setdefault(q.ticker, []).append(q)

        logger.info(
            f"Fetched prices for {len(self._quotes)} instruments "
            f"({sum(len(v) for v in self._quotes.values())} total quotes)"
        )
        return self._quotes

    # ── Reconciliation ────────────────────────────────────────────────────────

    def reconcile(self) -> list[PriceBreak]:
        """
        Cross-check every instrument that has 2+ source quotes.
        Returns list of PriceBreak objects — one per source pair per instrument.
        """
        if not self._quotes:
            self.fetch_all()

        breaks: list[PriceBreak] = []
        inst_map = {i["ticker"]: i for i in INSTRUMENTS}

        for ticker, quotes in self._quotes.items():
            if len(quotes) < 2:
                continue  # Only one source — nothing to reconcile

            inst = inst_map.get(ticker, {})
            asset_class = inst.get("asset_class", "default")
            base_tolerance = TOLERANCES.get(asset_class, TOLERANCES["default"])

            # Get liquidity tier to scale tolerance
            tier = get_liquidity_tier(ticker, asset_class)
            tolerance = get_tolerance_for_tier(base_tolerance, tier)

            # Pairwise comparison across sources
            for i in range(len(quotes)):
                for j in range(i + 1, len(quotes)):
                    q_a, q_b = quotes[i], quotes[j]
                    if q_a.price <= 0 or q_b.price <= 0:
                        continue

                    diff_pct = abs(q_a.price - q_b.price) / q_a.price * 100

                    cause, severity = classify_break(
                        ticker, asset_class, q_a, q_b, diff_pct, tolerance
                    )

                    # Skip INFO-level within-spread non-issues unless they're FX
                    if severity == "INFO" and asset_class not in ("fx",):
                        continue

                    breaks.append(PriceBreak(
                        ticker=ticker,
                        asset_class=asset_class,
                        source_a=q_a.source,
                        source_b=q_b.source,
                        price_a=round(q_a.price, 6),
                        price_b=round(q_b.price, 6),
                        diff_pct=round(diff_pct, 4),
                        tolerance_pct=round(tolerance, 4),
                        break_cause=cause,
                        severity=severity,
                        timestamp=datetime.utcnow(),
                    ))

        # Sort: CRITICAL first, then WARNING, then by ticker
        breaks.sort(key=lambda b: ({"CRITICAL": 0, "WARNING": 1, "INFO": 2}.get(b.severity, 3), b.ticker))
        logger.info(
            f"Reconciliation complete: {len(breaks)} breaks "
            f"({sum(1 for b in breaks if b.severity == 'CRITICAL')} critical)"
        )
        return breaks

    def run(self) -> tuple[dict[str, list[PriceQuote]], list[PriceBreak]]:
        """Fetch + reconcile in one call. Returns (quotes_by_ticker, breaks)."""
        quotes = self.fetch_all()
        breaks = self.reconcile()
        return quotes, breaks
