from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PriceQuote(BaseModel):
    ticker: str
    source: str                       # "yahoo", "fred", "ecb", "alpha_vantage"
    asset_class: str
    currency: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_stale: bool = False


class PriceBreak(BaseModel):
    ticker: str
    asset_class: str
    source_a: str
    source_b: str
    price_a: float
    price_b: float
    diff_pct: float                   # abs % difference
    tolerance_pct: float
    break_cause: str                  # from config.BREAK_CAUSES
    severity: str                     # "INFO" | "WARNING" | "CRITICAL"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False


class Instrument(BaseModel):
    ticker: str
    asset_class: str
    currency: str
    name: str
    liquidity_tier: Optional[str] = None  # L1 / L2 / L3
    adv_usd_30d: Optional[float] = None


class FXRate(BaseModel):
    pair: str                         # e.g. "GBPUSD"
    rate: float
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FXForward(BaseModel):
    """Simulated FX forward via interest rate parity: F = S * (1 + r_d) / (1 + r_f)"""
    pair: str
    spot_rate: float
    forward_rate: float
    tenor_days: int
    domestic_rate: float              # GBP risk-free
    foreign_rate: float               # USD/EUR/JPY risk-free
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PositionRisk(BaseModel):
    ticker: str
    asset_class: str
    market_value_gbp: float
    var_95_gbp: float
    var_99_gbp: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    liquidity_tier: str = "L3"
    days_to_liquidate: Optional[float] = None
    fx_hedge_ratio: float = 0.0


class PortfolioSnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    nav_gbp: float
    peak_nav_gbp: float
    drawdown_pct: float
    var_95_gbp: float
    var_99_gbp: float
    stress_results: dict
    positions: list[PositionRisk]
    open_breaks: int
    critical_breaks: int


class CreditRating(BaseModel):
    """Mock Bloomberg CRAT field schema — S&P/Moody's/Fitch don't have free APIs."""
    isin: str
    issuer: str
    agency: str                       # "SP" | "MOODY" | "FITCH"
    rating: str                       # e.g. "BBB+"
    outlook: str                      # "Stable" | "Positive" | "Negative" | "Watch"
    effective_date: datetime
    prior_rating: Optional[str] = None
    asset_class: str = "corp_bond"
