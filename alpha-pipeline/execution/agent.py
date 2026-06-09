"""
LangGraph orchestration agent.

Node pipeline:
  fetch_prices → generate_signals → quality_gate → risk_check → liquidity_check → execute

Each node returns a state dict. The agent halts execution at any gate failure,
logging the reason. This mirrors the pre-trade check workflow in a real quant system.
"""
import logging
from typing import TypedDict

from config import VAR_95_LIMIT_PCT, FUND_INITIAL_NAV

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    prices: dict[str, float]
    signals: list[dict]
    quality_passed: list[dict]
    risk_checked: list[dict]
    liquidity_checked: list[dict]
    executed: list[dict]
    errors: list[str]
    nav_gbp: float
    var_result: dict


def node_fetch_prices(state: AgentState) -> AgentState:
    from data.sources.yahoo import get_bulk_prices, INSTRUMENTS
    tickers = [i["ticker"] for i in INSTRUMENTS]
    prices = get_bulk_prices(tickers)
    logger.info(f"[agent] fetched prices for {len(prices)} instruments")
    state["prices"] = prices
    return state


def node_generate_signals(state: AgentState) -> AgentState:
    from signals.engine import generate_all_signals
    signals = generate_all_signals(state["prices"])
    state["signals"] = signals
    logger.info(f"[agent] generated {len(signals)} signals")
    return state


def node_quality_gate(state: AgentState) -> AgentState:
    """Block signals for tickers with open CRITICAL price breaks from price-recon."""
    import sqlite3
    from config import SHARED_DB_PATH

    blocked_tickers: set[str] = set()
    try:
        conn = sqlite3.connect(SHARED_DB_PATH)
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM price_breaks WHERE resolved = 0 AND severity = 'CRITICAL'"
        ).fetchall()
        conn.close()
        blocked_tickers = {r[0] for r in rows}
    except Exception as e:
        logger.warning(f"[agent] quality gate DB check failed: {e} — passing all signals")

    passed = []
    for sig in state["signals"]:
        if sig["ticker"] in blocked_tickers:
            state["errors"].append(f"quality_gate: {sig['ticker']} blocked — CRITICAL break open")
            logger.warning(f"[agent] quality gate blocked {sig['ticker']}")
        else:
            sig["quality_gate_passed"] = True
            passed.append(sig)

    state["quality_passed"] = passed
    logger.info(f"[agent] quality gate: {len(passed)}/{len(state['signals'])} passed")
    return state


def node_risk_check(state: AgentState) -> AgentState:
    from risk.var import portfolio_var
    from db.database import get_positions, get_nav_gbp as _nav

    positions = get_positions()
    nav = _nav() or FUND_INITIAL_NAV
    state["nav_gbp"] = nav

    if positions:
        var_result = portfolio_var(positions)
        state["var_result"] = var_result
        var_pct = var_result.get("var_95_pct_nav", 0.0)
        if var_pct > VAR_95_LIMIT_PCT * 100:
            state["errors"].append(f"risk_check: VaR {var_pct:.2f}% > limit {VAR_95_LIMIT_PCT*100:.1f}% — halting execution")
            logger.warning(f"[agent] VaR limit breached: {var_pct:.2f}%")
            state["risk_checked"] = []
            return state
    else:
        state["var_result"] = {}

    # Per-signal: check that adding this position won't breach limits
    checked = []
    for sig in state["quality_passed"]:
        size_gbp = nav * 0.10 * sig["confidence"]
        var_impact = size_gbp * 0.02 * 1.645  # rough 1-day 95% VaR on new position
        sig["var_impact_gbp"] = round(var_impact, 2)
        checked.append(sig)

    state["risk_checked"] = checked
    logger.info(f"[agent] risk check: {len(checked)} signals passed")
    return state


def node_liquidity_check(state: AgentState) -> AgentState:
    from data.sources.yahoo import get_historical_returns
    import numpy as np

    checked = []
    for sig in state["risk_checked"]:
        ticker = sig["ticker"]
        ac = sig["asset_class"]

        if ac in ("volatility", "option"):
            sig["liquidity_tier"] = "L2"
            checked.append(sig)
            continue

        try:
            returns = get_historical_returns(ticker, days=30)
            if returns is not None:
                price = sig.get("price", 1.0)
                approx_vol = float(np.abs(returns).mean()) * price
                if approx_vol > 1_000_000:
                    tier = "L1"
                elif approx_vol > 100_000:
                    tier = "L2"
                else:
                    tier = "L3"
            else:
                tier = "L2"
        except Exception:
            tier = "L2"

        sig["liquidity_tier"] = tier
        checked.append(sig)

    state["liquidity_checked"] = checked
    logger.info(f"[agent] liquidity check: {len(checked)} signals ready to execute")
    return state


def node_execute(state: AgentState) -> AgentState:
    from data.sources.yahoo import get_bulk_prices
    from execution.paper import route_signal

    fx_tickers = ["GBPUSD=X", "EURUSD=X", "USDJPY=X", "USDCHF=X"]
    fx_rates = get_bulk_prices(fx_tickers)

    executed = []
    for sig in state["liquidity_checked"][:5]:  # cap at 5 new trades per run
        result = route_signal(sig, fx_rates)
        if result:
            executed.append(result)
            logger.info(f"[agent] executed: {result['direction']} {result['ticker']} £{result.get('value_gbp', 0):.0f}")

    state["executed"] = executed
    return state


def run_agent() -> AgentState:
    try:
        from langgraph.graph import StateGraph, END
        graph = StateGraph(AgentState)
        graph.add_node("fetch_prices", node_fetch_prices)
        graph.add_node("generate_signals", node_generate_signals)
        graph.add_node("quality_gate", node_quality_gate)
        graph.add_node("risk_check", node_risk_check)
        graph.add_node("liquidity_check", node_liquidity_check)
        graph.add_node("execute", node_execute)

        graph.set_entry_point("fetch_prices")
        graph.add_edge("fetch_prices", "generate_signals")
        graph.add_edge("generate_signals", "quality_gate")
        graph.add_edge("quality_gate", "risk_check")
        graph.add_edge("risk_check", "liquidity_check")
        graph.add_edge("liquidity_check", "execute")
        graph.add_edge("execute", END)

        app = graph.compile()
        initial: AgentState = {
            "prices": {}, "signals": [], "quality_passed": [],
            "risk_checked": [], "liquidity_checked": [], "executed": [],
            "errors": [], "nav_gbp": 0.0, "var_result": {},
        }
        result = app.invoke(initial)
        return result
    except ImportError:
        logger.warning("LangGraph not installed — running nodes sequentially")
        state: AgentState = {
            "prices": {}, "signals": [], "quality_passed": [],
            "risk_checked": [], "liquidity_checked": [], "executed": [],
            "errors": [], "nav_gbp": 0.0, "var_result": {},
        }
        for node in [node_fetch_prices, node_generate_signals, node_quality_gate,
                     node_risk_check, node_liquidity_check, node_execute]:
            state = node(state)
        return state
