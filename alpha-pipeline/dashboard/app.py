"""
Streamlit dashboard — alpha-pipeline live paper portfolio view.

Panels:
  - Fund NAV + drawdown
  - VaR (95/99) vs limits
  - Positions table
  - Signals log
  - FX hedge status
  - Stress test P&L
  - Run agent button
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from config import FUND_INITIAL_NAV, VAR_95_LIMIT_PCT
from db.database import (
    get_positions, get_nav_gbp, get_latest_snapshot,
    get_snapshot_history, get_signals, get_trades, get_active_forwards,
)

st.set_page_config(
    page_title="alpha-pipeline — Paper Portfolio",
    page_icon="📊",
    layout="wide",
)

st.title("alpha-pipeline — Paper Trading Portfolio")
st.caption(f"PAPER_TRADE_MODE = True | GBP fund | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")


@st.cache_data(ttl=60)
def load_data():
    positions = get_positions()
    nav = get_nav_gbp() or FUND_INITIAL_NAV
    snapshot = get_latest_snapshot()
    signals = get_signals(limit=20)
    trades = get_trades(limit=20)
    forwards = get_active_forwards()
    history = get_snapshot_history(limit=30)
    return positions, nav, snapshot, signals, trades, forwards, history


positions, nav, snapshot, signals, trades, forwards, history = load_data()

# ── Summary metrics ───────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    pnl = nav - FUND_INITIAL_NAV
    st.metric("GBP NAV", f"£{nav:,.0f}", delta=f"£{pnl:+,.0f}")
with col2:
    drawdown = snapshot["drawdown_pct"] if snapshot else 0.0
    st.metric("Drawdown", f"{drawdown:.2f}%")
with col3:
    var95 = snapshot["var_95_gbp"] if snapshot else 0.0
    var95_pct = var95 / nav * 100 if nav else 0.0
    limit_pct = VAR_95_LIMIT_PCT * 100
    st.metric("1-day VaR 95%", f"£{var95:,.0f}", delta=f"{var95_pct:.2f}% / limit {limit_pct:.1f}%",
              delta_color="inverse")
with col4:
    open_breaks = snapshot["open_breaks"] if snapshot else 0
    st.metric("Open Breaks", open_breaks, delta_color="inverse")
with col5:
    st.metric("Positions", len(positions))

st.divider()

# ── Positions ─────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Positions")
    if positions:
        df_pos = pd.DataFrame(positions)[["ticker", "asset_class", "currency",
                                           "quantity", "current_price",
                                           "market_value_gbp", "unrealised_pnl_gbp",
                                           "liquidity_tier"]]
        df_pos["market_value_gbp"] = df_pos["market_value_gbp"].map("£{:,.0f}".format)
        df_pos["unrealised_pnl_gbp"] = df_pos["unrealised_pnl_gbp"].map("£{:+,.0f}".format)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)
    else:
        st.info("No positions yet. Run the agent to generate signals and execute trades.")

with col_right:
    st.subheader("Latest Signals")
    if signals:
        df_sig = pd.DataFrame(signals)[["ticker", "asset_class", "signal_type",
                                         "direction", "confidence", "quality_gate_passed",
                                         "executed"]]
        df_sig["confidence"] = df_sig["confidence"].map("{:.0%}".format)
        st.dataframe(df_sig, use_container_width=True, hide_index=True)
    else:
        st.info("No signals yet.")

st.divider()

# ── Risk ──────────────────────────────────────────────────────────────────────
if snapshot:
    st.subheader("Stress Test P&L")
    stress_cols = st.columns(4)
    stress_items = [
        ("GFC 2008", snapshot.get("stress_gfc_gbp", 0)),
        ("COVID 2020", snapshot.get("stress_covid_gbp", 0)),
        ("Rate Shock 2022", snapshot.get("stress_rate_shock_gbp", 0)),
        ("VaR 99%", -(snapshot.get("var_99_gbp", 0))),
    ]
    for col, (label, val) in zip(stress_cols, stress_items):
        col.metric(label, f"£{val:+,.0f}", delta_color="inverse")

# ── FX hedges ─────────────────────────────────────────────────────────────────
if forwards:
    st.subheader("Active FX Forwards (Hedges)")
    df_fwd = pd.DataFrame(forwards)[["pair", "notional_gbp", "spot_rate",
                                       "forward_rate", "tenor_days", "expires_at"]]
    df_fwd["notional_gbp"] = df_fwd["notional_gbp"].map("£{:,.0f}".format)
    st.dataframe(df_fwd, use_container_width=True, hide_index=True)

st.divider()

# ── NAV history chart ─────────────────────────────────────────────────────────
if history:
    st.subheader("NAV History")
    df_hist = pd.DataFrame(history)[["timestamp", "nav_gbp", "var_95_gbp"]].set_index("timestamp")
    st.line_chart(df_hist, use_container_width=True)

# ── Recent trades ─────────────────────────────────────────────────────────────
if trades:
    st.subheader("Recent Trades")
    df_tr = pd.DataFrame(trades)[["timestamp", "ticker", "direction",
                                    "quantity", "price", "value_gbp", "broker"]]
    df_tr["value_gbp"] = df_tr["value_gbp"].map("£{:,.0f}".format)
    st.dataframe(df_tr, use_container_width=True, hide_index=True)

# ── Run agent ─────────────────────────────────────────────────────────────────
st.divider()
if st.button("▶ Run Agent (fetch → signal → risk → execute)", type="primary"):
    with st.spinner("Running alpha-pipeline agent…"):
        try:
            from execution.agent import run_agent
            from db.database import save_snapshot
            from risk.var import portfolio_var, stress_test

            result = run_agent()
            positions_now = get_positions()
            nav_now = get_nav_gbp() or FUND_INITIAL_NAV

            var_result = portfolio_var(positions_now) if positions_now else {}
            stress_result = stress_test(positions_now) if positions_now else {}

            save_snapshot(
                nav_gbp=nav_now,
                peak_nav_gbp=max(nav_now, FUND_INITIAL_NAV),
                drawdown_pct=max(0, (FUND_INITIAL_NAV - nav_now) / FUND_INITIAL_NAV * 100),
                var_95=var_result.get("var_95_gbp", 0.0),
                var_99=var_result.get("var_99_gbp", 0.0),
                stress=stress_result.get("stress_results", {}),
                open_breaks=len([e for e in result.get("errors", []) if "quality_gate" in e]),
                critical_breaks=0,
            )

            executed = result.get("executed", [])
            errors = result.get("errors", [])
            st.success(f"Agent complete. Executed: {len(executed)} trades.")
            if errors:
                for e in errors:
                    st.warning(e)
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Agent error: {e}")
