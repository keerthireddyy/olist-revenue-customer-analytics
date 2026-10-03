#!/usr/bin/env python3
"""
03_dashboard.py — interactive Streamlit dashboard
-------------------------------------------------
Run from the project root:
    streamlit run scripts/03_dashboard.py --server.address 0.0.0.0 --server.port 8501

Reads the mart CSVs produced by 01_build_warehouse.py and lets a reviewer
slice the revenue & customer analytics interactively.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CHARTS = ROOT / "reports" / "charts"

NAVY = "#1f3b63"
TEAL = "#2a9d8f"
AMBER = "#e9a13b"
RED = "#d64545"

st.set_page_config(page_title="Olist Revenue & Customer Analytics", layout="wide")

@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / f"{name}.csv")

kpi = load("mart_monthly_kpi")
kpi["order_month"] = pd.to_datetime(kpi["order_month"])
rfm = load("mart_rfm")
segs = load("mart_rfm_segments")
coh = load("mart_cohort")
coh["cohort_month"] = pd.to_datetime(coh["cohort_month"])
pareto = load("mart_pareto")
cat = load("mart_category")
state = load("mart_state")
sla = load("mart_delivery_sla")
sla["order_month"] = pd.to_datetime(sla["order_month"])
pay = load("mart_payment")
rep = load("mart_repeat")
rd = load("mart_review_delay")
orders = load("fact_order_summary")

st.title("🛒 Olist — Revenue & Customer Analytics")
st.caption("Brazilian e-commerce marketplace · 99,441 orders · Sep 2016 – Sep 2018 · "
           "delivered+shipped = revenue orders · source: Kaggle Olist dataset")

# ------------------------------------------------------------------ KPI cards
c1, c2, c3, c4, c5, c6 = st.columns(6)
rev = kpi["revenue"].sum()
c1.metric("Revenue (delivered)", f"R$ {rev/1e6:.2f}M")
c2.metric("Orders", f"{int(kpi['orders'].sum()):,}")
c3.metric("Customers", f"{int(rfm.customer_unique_id.nunique()):,}")
c4.metric("Avg order value", f"R$ {rev/kpi['orders'].sum():.0f}")
c5.metric("Repeat customers", f"{(rfm.is_repeat_customer.mean()*100):.1f}%")
c6.metric("On-time delivery", f"{sla.on_time_pct.mean():.1f}%")

# --------------------------------------------------------------------- tabs
tab_trend, tab_rfm, tab_cohort, tab_mix, tab_sla, tab_geo = st.tabs(
    ["📈 Trend", "🎯 RFM", "🧬 Cohorts", "🧺 Category / Payment", "🚚 Delivery & CSAT", "🗺️ Geography"])

with tab_trend:
    c_l, c_r = st.columns([2, 1])
    fig = px.bar(kpi, x="order_month", y="revenue", color="revenue",
                 color_continuous_scale="Blues", title="Monthly revenue (R$)")
    fig.update_layout(coloraxis_showscale=False)
    c_l.plotly_chart(fig, use_container_width=True)

    fig = px.line(kpi, x="order_month", y="aov", markers=True, title="Average order value (R$)")
    c_r.plotly_chart(fig, use_container_width=True)

    c_l, c_r = st.columns([2, 1])
    fig = px.line(kpi, x="order_month", y="avg_delivery_days", markers=True,
                  title="Avg delivery days (delivered orders)")
    c_l.plotly_chart(fig, use_container_width=True)
    fig = px.line(kpi, x="order_month", y="avg_review_score", markers=True,
                  title="Avg review score")
    c_r.plotly_chart(fig, use_container_width=True)

    with st.expander("Monthly KPI table"):
        st.dataframe(kpi.sort_values("order_month", ascending=False), use_container_width=True)

with tab_rfm:
    c_l, c_r = st.columns(2)
    fig = px.bar(segs.sort_values("revenue", ascending=True), y="segment", x="revenue",
                 orientation="h", title="Revenue by RFM segment (R$)")
    fig.update_traces(marker_color=NAVY)
    c_l.plotly_chart(fig, use_container_width=True)

    fig = go.Figure()
    s_ = segs.sort_values("revenue", ascending=False)
    fig.add_bar(x=s_["segment"], y=s_["pct_customers"], name="% customers", marker_color=TEAL)
    fig.add_bar(x=s_["segment"], y=s_["pct_revenue"], name="% revenue", marker_color=AMBER)
    fig.update_layout(title="Customers vs revenue share by segment", barmode="group")
    c_r.plotly_chart(fig, use_container_width=True)

    st.caption("💡 **Story:** 97% of customers buy exactly once. `frequency` was therefore scored "
               "on its *distinct values* (1 / 2 / 3-4 / 5+ orders) instead of quintiles — a naive "
               "NTILE would split identical 1-order customers into different tiers.")

    st.dataframe(segs[["segment", "customers", "pct_customers", "revenue", "pct_revenue",
                       "avg_monetary", "avg_frequency", "avg_recency_days"]],
                 use_container_width=True)

    st.subheader("Customer explorer")
    q = st.text_input("Search customer id", "")
    if q:
        st.dataframe(rfm[rfm.customer_unique_id.str.contains(q, case=False)].head(20),
                     use_container_width=True)

with tab_cohort:
    wide = coh.pivot_table(index="cohort_month", columns="month_offset",
                           values="retention_pct", aggfunc="first")
    fig = px.imshow(wide, color_continuous_scale="YlGnBu", aspect="auto",
                    title="Monthly cohort retention (%) — near-zero repeat behaviour")
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="months since first order", yaxis_title="cohort month")
    st.plotly_chart(fig, use_container_width=True)

with tab_mix:
    c_l, c_r = st.columns(2)
    fig = px.bar(cat.head(15), x="revenue", y="category", orientation="h",
                 title="Top 15 categories by revenue (R$)")
    fig.update_traces(marker_color=NAVY)
    c_l.plotly_chart(fig, use_container_width=True)

    fig = px.pie(pay, values="value", names="payment_type", hole=0.45,
                 title="Transaction value by payment type")
    c_r.plotly_chart(fig, use_container_width=True)

    c_l, c_r = st.columns(2)
    fig = px.bar(rep, x="order_bucket", y="pct_customers", title="% customers by number of orders")
    c_l.plotly_chart(fig, use_container_width=True)
    fig = px.bar(rep, x="order_bucket", y="pct_revenue", title="% revenue by number of orders")
    c_r.plotly_chart(fig, use_container_width=True)

    fig = px.scatter(pareto.sample(3000, random_state=7), x="pct_customers", y="pct_revenue",
                     title="Pareto curve (sampled)")
    fig.update_layout(xaxis_title="% of customers", yaxis_title="% cumulative revenue")
    st.plotly_chart(fig, use_container_width=True)

with tab_sla:
    c_l, c_r = st.columns(2)
    fig = px.line(sla, x="order_month", y="on_time_pct", markers=True,
                  title="On-time delivery % vs customer estimate")
    fig.add_hline(y=90, line_dash="dash", line_color=RED)
    c_l.plotly_chart(fig, use_container_width=True)

    rd_ = rd[rd.delivery_bucket != "no data"]
    fig = px.bar(rd_, x="delivery_bucket", y="pct_bad_reviews",
                 title="% of orders with a 1–2★ review", color="pct_bad_reviews",
                 color_continuous_scale="Reds")
    fig.update_layout(coloraxis_showscale=False)
    c_r.plotly_chart(fig, use_container_width=True)

    st.info("🚨 Orders delivered **4+ days late** get a 1–2★ review **74.6%** of the time vs "
            "**8.9%** for early deliveries (Welch t-test p ≈ 0). Delivery is the CSAT lever.")

with tab_geo:
    fig = px.bar(state.head(12), x="customer_state", y="revenue",
                 title="Top 12 states by revenue (R$)")
    fig.update_traces(marker_color=NAVY)
    st.plotly_chart(fig, use_container_width=True)
    fig = px.bar(state.head(12), x="customer_state", y="avg_delivery_days",
                 title="Avg delivery days by state (same order)")
    fig.update_traces(marker_color=AMBER)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(state, use_container_width=True)

st.caption("Static chart pack lives in `reports/charts/` · findings in `reports/findings.json`")
