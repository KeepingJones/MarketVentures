"""Yahoo Finance data source — reused pattern from price-recon with 5-min TTL cache."""
import time
import logging
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[dict, float]] = {}
_TTL = 300  # 5-min cache (same as trading-bot PriceCache pattern)

# Instruments universe: imported from price-recon config to keep universes in sync
INSTRUMENTS = [
    {"ticker": "AAPL",    "asset_class": "equity",    "currency": "USD"},
    {"ticker": "MSFT",    "asset_class": "equity",    "currency": "USD"},
    {"ticker": "BP.L",    "asset_class": "equity",    "currency": "GBP"},
    {"ticker": "SHEL.L",  "asset_class": "equity",    "currency": "GBP"},
    {"ticker": "9984.T",  "asset_class": "equity",    "currency": "JPY"},
    {"ticker": "SAP.DE",  "asset_class": "equity",    "currency": "EUR"},
    {"ticker": "SPY",     "asset_class": "equity",    "currency": "USD"},
    {"ticker": "GBPUSD=X","asset_class": "fx",        "currency": "USD"},
    {"ticker": "EURUSD=X","asset_class": "fx",        "currency": "USD"},
    {"ticker": "USDJPY=X","asset_class": "fx",        "currency": "JPY"},
    {"ticker": "USDCHF=X","asset_class": "fx",        "currency": "CHF"},
    {"ticker": "TLT",     "asset_class": "govt_bond", "currency": "USD"},
    {"ticker": "IGLT.L",  "asset_class": "govt_bond", "currency": "GBP"},
    {"ticker": "LQD",     "asset_class": "corp_bond", "currency": "USD"},
    {"ticker": "GC=F",    "asset_class": "commodity", "currency": "USD"},
    {"ticker": "CL=F",    "asset_class": "commodity", "currency": "USD"},
    {"ticker": "^VIX",    "asset_class": "volatility","currency": "USD"},
]


def get_price(ticker: str) -> Optional[float]:
    now = time.time()
    if ticker in _cache:
        data, ts = _cache[ticker]
        if now - ts < _TTL:
            return data.get("price")
    try:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
        if hist.empty:
            return None
        price = float(hist["Close"].dropna().iloc[-1])
        _cache[ticker] = ({"price": price}, now)
        return price
    except Exception as e:
        logger.warning(f"Yahoo price failed for {ticker}: {e}")
        return None


def get_bulk_prices(tickers: Optional[list[str]] = None) -> dict[str, float]:
    if tickers is None:
        tickers = [i["ticker"] for i in INSTRUMENTS]

    now = time.time()
    cached = {t: _cache[t][0]["price"] for t in tickers
              if t in _cache and now - _cache[t][1] < _TTL}
    missing = [t for t in tickers if t not in cached]

    if not missing:
        return cached

    try:
        raw = yf.download(missing, period="2d", auto_adjust=True,
                          progress=False, group_by="ticker")
        for ticker in missing:
            try:
                if len(missing) == 1:
                    closes = raw["Close"].dropna()
                else:
                    closes = raw[ticker]["Close"].dropna() if ticker in raw.columns.get_level_values(0) else None
                if closes is not None and not closes.empty:
                    price = float(closes.iloc[-1])
                    cached[ticker] = price
                    _cache[ticker] = ({"price": price}, now)
            except Exception:
                fallback = get_price(ticker)
                if fallback:
                    cached[ticker] = fallback
    except Exception as e:
        logger.error(f"Yahoo bulk download failed: {e}")
        for t in missing:
            p = get_price(t)
            if p:
                cached[t] = p

    return cached


def get_options_chain(ticker: str = "SPY") -> Optional[dict]:
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return None
        nearest = exps[0]
        chain = t.option_chain(nearest)
        calls = chain.calls[["strike", "lastPrice", "impliedVolatility", "delta", "gamma"]].head(10)
        puts  = chain.puts[["strike", "lastPrice", "impliedVolatility", "delta", "gamma"]].head(10)
        return {
            "ticker": ticker,
            "expiry": nearest,
            "calls": calls.to_dict("records"),
            "puts": puts.to_dict("records"),
        }
    except Exception as e:
        logger.warning(f"Options chain failed for {ticker}: {e}")
        return None


def get_historical_returns(ticker: str, days: int = 252) -> Optional[pd.Series]:
    try:
        hist = yf.Ticker(ticker).history(period=f"{days + 10}d", interval="1d")
        if hist.empty:
            return None
        closes = hist["Close"].dropna()
        returns = closes.pct_change().dropna()
        return returns.tail(days)
    except Exception as e:
        logger.warning(f"Historical returns failed for {ticker}: {e}")
        return None
