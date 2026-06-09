import time
import logging
from typing import Optional
from datetime import datetime

import yfinance as yf

from data.models import PriceQuote

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[PriceQuote, float]] = {}
_TTL = 300  # 5 min — same pattern as trading-bot PriceCache


def get_quote(ticker: str, asset_class: str, currency: str) -> Optional[PriceQuote]:
    now = time.time()
    if ticker in _cache:
        quote, ts = _cache[ticker]
        if now - ts < _TTL:
            return quote

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d")
        if hist.empty:
            logger.warning(f"Yahoo: no data for {ticker}")
            return None

        closes = hist["Close"].tolist()
        price = closes[-1]
        volume = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else None

        # Attempt bid/ask from fast_info
        bid = ask = None
        try:
            fi = t.fast_info
            bid = float(fi.bid) if hasattr(fi, "bid") and fi.bid else None
            ask = float(fi.ask) if hasattr(fi, "ask") and fi.ask else None
        except Exception:
            pass

        quote = PriceQuote(
            ticker=ticker,
            source="yahoo",
            asset_class=asset_class,
            currency=currency,
            price=round(float(price), 6),
            bid=round(float(bid), 6) if bid else None,
            ask=round(float(ask), 6) if ask else None,
            volume=volume,
            timestamp=datetime.utcnow(),
        )
        _cache[ticker] = (quote, now)
        return quote

    except Exception as e:
        logger.error(f"Yahoo fetch failed for {ticker}: {e}")
        return None


def get_bulk_quotes(instruments: list[dict]) -> list[PriceQuote]:
    quotes = []
    tickers = [i["ticker"] for i in instruments]

    try:
        raw = yf.download(tickers, period="2d", auto_adjust=True, progress=False, group_by="ticker")
    except Exception as e:
        logger.error(f"Yahoo bulk download failed: {e}")
        return []

    for inst in instruments:
        ticker = inst["ticker"]
        try:
            if len(tickers) == 1:
                closes = raw["Close"].dropna()
            else:
                closes = raw[ticker]["Close"].dropna() if ticker in raw.columns.get_level_values(0) else None

            if closes is None or closes.empty:
                logger.warning(f"Yahoo bulk: no close for {ticker}")
                continue

            price = float(closes.iloc[-1])
            quotes.append(PriceQuote(
                ticker=ticker,
                source="yahoo",
                asset_class=inst["asset_class"],
                currency=inst["currency"],
                price=round(price, 6),
                timestamp=datetime.utcnow(),
            ))
        except Exception as e:
            logger.warning(f"Yahoo bulk parse failed for {ticker}: {e}")
            # Fallback to single fetch
            q = get_quote(ticker, inst["asset_class"], inst["currency"])
            if q:
                quotes.append(q)

    return quotes
