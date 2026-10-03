#!/usr/bin/env python3
"""
02_analysis.py
--------------
Step 2: read the mart CSVs produced by 01_build_warehouse.py, run the analytics
(RFM, cohort retention, Pareto, category/state, delivery SLA, payment mix),
statistically test the delivery-delay -> review-score hypothesis, and write
every chart to reports/charts/ plus a machine-readable findings.json.

Run from the project root:
    python3 scripts/02_analysis.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CHARTS = ROOT / "reports" / "charts"
REPORTS = ROOT / "reports"

# BRL -> INR at an illustrative rate, purely so the resume/report can quote INR.
BRL_TO_INR = 15.0

plt.rcParams.update({
    "figure.dpi": 130,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "font.size": 9,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
})
NAVY, TEAL, AMBER, RED, GREY = "#1f3b63", "#2a9d8f", "#e9a13b", "#d64545", "#8d99ae"
SEGMENT_ORDER = [
    "Champions", "Loyal Customers", "Potential Loyalists", "New / Promising",
    "Need Attention", "At Risk", "Cant Lose Them", "Hibernating / Lost", "Other",
]


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / f"{name}.csv")


def brl(x: float) -> str:
    return f"R${x/1e6:.2f}M" if abs(x) >= 1e6 else f"R${x:,.0f}"


def save(fig, name: str) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHARTS / name, bbox_inches="tight")
    plt.close(fig)
    print(f"  chart -> reports/charts/{name}")


# ------------------------------------------------------------------ 1. TREND
# The raw series contains a 2016 marketplace ramp-up (Sep-16: 2 orders,
# Nov-16: no orders at all, Dec-16: 1 order) and a partial final month.
# Trend and MoM growth are therefore measured on an explicit analysis window;
# totals elsewhere in the project still use the full dataset.
WINDOW_START = "2017-01-01"


def chart_trend(kpi: pd.DataFrame) -> dict:
    kpi = kpi.copy()
    kpi["order_month"] = pd.to_datetime(kpi["order_month"])
    last_month = kpi["order_month"].max()
    kpi["partial"] = kpi["order_month"].isin([kpi["order_month"].min(), last_month])
    kpi["in_window"] = (kpi["order_month"] >= pd.Timestamp(WINDOW_START)) & ~kpi["partial"]

    kpi["rev_mom_pct"] = np.nan
    win = kpi.index[kpi["in_window"]]
    kpi.loc[win, "rev_mom_pct"] = kpi.loc[win, "revenue"].pct_change() * 100

    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5))

    ax = axes[0, 0]
    colors = [NAVY if w else GREY for w in kpi["in_window"]]
    ax.bar(kpi["order_month"], kpi["revenue"] / 1e3, color=colors, width=22)
    ax.set_title("Monthly revenue (R$ thousands)")
    ax.set_ylabel("R$ 000s")
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(45); lbl.set_ha("right")

    ax = axes[0, 1]
    ax.plot(kpi.loc[kpi["in_window"], "order_month"], kpi.loc[kpi["in_window"], "orders"],
            marker="o", ms=3, color=TEAL)
    ax.set_title("Monthly orders (analysis window)")
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(45); lbl.set_ha("right")

    ax = axes[1, 0]
    ax.plot(kpi.loc[kpi["in_window"], "order_month"], kpi.loc[kpi["in_window"], "aov"],
            marker="o", ms=3, color=AMBER)
    ax.set_title("Average order value (R$, analysis window)")
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(45); lbl.set_ha("right")

    ax = axes[1, 1]
    ax.bar(kpi.loc[kpi["in_window"], "order_month"], kpi.loc[kpi["in_window"], "rev_mom_pct"],
           color=[TEAL if v >= 0 else RED for v in kpi.loc[kpi["in_window"], "rev_mom_pct"]], width=22)
    ax.axhline(0, color=GREY, lw=1)
    ax.set_title("Revenue month-on-month growth (%)")
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(45); lbl.set_ha("right")

    fig.suptitle("Revenue trend  (grey = pre-window ramp-up / partial month, excluded from growth)",
                 y=1.0, fontsize=12, fontweight="bold")
    save(fig, "01_monthly_trend.png")

    w = kpi[kpi["in_window"]].reset_index(drop=True)
    first, last = w.iloc[0], w.iloc[-1]
    months = len(w)
    cagr = ((last["revenue"] / first["revenue"]) ** (12 / max(months - 1, 1)) - 1) * 100
    return {
        "window_start": str(first["order_month"].date()),
        "window_end": str(last["order_month"].date()),
        "months_in_window": int(months),
        "peak_month": str(w.loc[w["revenue"].idxmax(), "order_month"].date()),
        "peak_revenue_brl": round(float(w["revenue"].max()), 2),
        "first_month_revenue_brl": round(float(first["revenue"]), 2),
        "last_month_revenue_brl": round(float(last["revenue"]), 2),
        "window_growth_pct": round(float((last["revenue"] / first["revenue"] - 1) * 100), 1),
        "annualised_growth_pct": round(float(cagr), 1),
        "best_mom_pct": round(float(w["rev_mom_pct"].max()), 1),
        "best_mom_month": str(w.loc[w["rev_mom_pct"].idxmax(), "order_month"].date()),
        "worst_mom_pct": round(float(w["rev_mom_pct"].min()), 1),
        "worst_mom_month": str(w.loc[w["rev_mom_pct"].idxmin(), "order_month"].date()),
    }


# ------------------------------------------------------------------ 2. COHORT
def chart_cohort(coh: pd.DataFrame) -> dict:
    coh = coh.copy()
    coh["cohort_month"] = pd.to_datetime(coh["cohort_month"])
    wide = coh.pivot_table(index="cohort_month", columns="month_offset",
                           values="retention_pct", aggfunc="first")
    sizes = coh.groupby("cohort_month")["cohort_size"].first()

    # keep only cohorts that had a chance to be observed at offset 1
    max_offset = int(coh["month_offset"].max())
    show = wide.loc[[c for c in wide.index
                     if (wide.index.max() - c).days / 30.44 >= 1]]
    show = show[[c for c in show.columns if c <= 12]]

    fig, ax = plt.subplots(figsize=(11, 6))
    im = ax.imshow(show.values, cmap="YlGnBu", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(show.shape[1]), [f"M+{c}" for c in show.columns])
    ax.set_yticks(range(show.shape[0]),
                  [f"{d:%b-%y}  (n={sizes[d]:,})" for d in show.index])
    for i in range(show.shape[0]):
        for j in range(show.shape[1]):
            v = show.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                        fontsize=7, color="white" if v > 55 else "#222")
    ax.set_title("Monthly cohort retention (% of cohort ordering again) — retention is very low")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="%")
    save(fig, "02_cohort_retention.png")

    m1 = coh[coh["month_offset"] == 1].sort_values("cohort_month")
    m1 = m1[m1["cohort_size"] > 1000]
    return {
        "median_m1_retention_pct": round(float(m1["retention_pct"].median()), 2),
        "best_m1_retention_pct": round(float(m1["retention_pct"].max()), 2),
        "worst_m1_retention_pct": round(float(m1["retention_pct"].min()), 2),
        "max_observed_offset": max_offset,
    }


# --------------------------------------------------------------------- 3. RFM
def chart_rfm(segments: pd.DataFrame, rfm: pd.DataFrame) -> dict:
    seg = segments.copy()
    seg["segment"] = pd.Categorical(seg["segment"],
                                    categories=[s for s in SEGMENT_ORDER if s in set(seg["segment"])],
                                    ordered=True)
    seg = seg.sort_values("segment")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))

    ax = axes[0]
    ax.barh(seg["segment"].astype(str), seg["revenue"] / 1e6, color=NAVY)
    ax.set_title("Revenue by RFM segment (R$M)")
    ax.invert_yaxis()

    ax = axes[1]
    ax.barh(seg["segment"].astype(str), seg["pct_customers"], color=TEAL, label="% customers")
    ax.barh(seg["segment"].astype(str), seg["pct_revenue"], color=AMBER, alpha=0.75, label="% revenue")
    ax.set_title("Share of customers vs share of revenue")
    ax.invert_yaxis()
    ax.legend(fontsize=8)

    ax = axes[2]
    sc = ax.scatter(rfm["frequency"], rfm["monetary"], s=2, alpha=0.06, color=NAVY)
    ax.set_xscale("symlog"); ax.set_yscale("symlog")
    ax.set_xlabel("orders per customer (log)"); ax.set_ylabel("lifetime R$ (log)")
    ax.set_title("Spend concentration by purchase frequency")
    save(fig, "03_rfm_segments.png")

    top = seg.sort_values("revenue", ascending=False).iloc[0]
    return {
        "top_segment": str(top["segment"]),
        "top_segment_customers": int(top["customers"]),
        "top_segment_pct_customers": float(top["pct_customers"]),
        "top_segment_pct_revenue": float(top["pct_revenue"]),
        "at_risk_customers": int(seg.loc[seg["segment"] == "At Risk", "customers"].sum()),
        "at_risk_revenue_brl": round(float(seg.loc[seg["segment"] == "At Risk", "revenue"].sum()), 2),
        "cant_lose_revenue_brl": round(float(seg.loc[seg["segment"] == "Cant Lose Them", "revenue"].sum()), 2),
        "segments_table": seg[["segment", "customers", "pct_customers", "revenue",
                               "pct_revenue", "avg_monetary", "avg_frequency",
                               "avg_recency_days"]].astype(str).to_dict("records"),
    }


# ------------------------------------------------------------------ 4. PARETO
def chart_pareto(par: pd.DataFrame) -> dict:
    n = len(par)
    marks = {}
    for pct in (1, 5, 10, 20, 30, 50):
        row = par.iloc[min(int(round(n * pct / 100)) - 1, n - 1)]
        marks[pct] = round(float(row["pct_revenue"]), 2)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(par["pct_customers"], par["pct_revenue"], color=NAVY, lw=2)
    ax.fill_between(par["pct_customers"], par["pct_revenue"], alpha=0.12, color=NAVY)
    ax.plot([0, 100], [0, 100], ls="--", color=GREY, lw=1, label="perfect equality")
    for pct, rev in marks.items():
        ax.scatter([pct], [rev], color=RED, zorder=5, s=28)
        ax.annotate(f"top {pct}% -> {rev:.0f}% of R$", (pct, rev),
                    textcoords="offset points", xytext=(8, -10), fontsize=8, color=RED)
    ax.set_xlabel("% of customers (ranked by lifetime spend)")
    ax.set_ylabel("% of cumulative revenue")
    ax.set_title("Revenue concentration (Pareto) — extreme skew")
    ax.legend(fontsize=8)
    save(fig, "04_pareto.png")

    repeat = load("mart_repeat")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].bar(repeat["order_bucket"], repeat["pct_customers"], color=TEAL)
    axes[0].set_title("% of customers by number of orders")
    for i, v in enumerate(repeat["pct_customers"]):
        axes[0].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=8)
    axes[1].bar(repeat["order_bucket"], repeat["pct_revenue"], color=NAVY)
    axes[1].set_title("% of revenue by number of orders")
    for i, v in enumerate(repeat["pct_revenue"]):
        axes[1].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=8)
    fig.suptitle("Repeat purchase behaviour", fontsize=12, fontweight="bold")
    save(fig, "05_repeat_purchase.png")

    return {
        "concentration": marks,
        "one_time_customer_pct": float(repeat.loc[repeat["order_bucket"] == "1 order", "pct_customers"].iloc[0]),
        "repeat_customer_pct": round(100 - float(repeat.loc[repeat["order_bucket"] == "1 order", "pct_customers"].iloc[0]), 2),
    }


# --------------------------------------------------- 5. CATEGORY / STATE / PAY
def chart_category(cat: pd.DataFrame) -> dict:
    top = cat.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(top["category"], top["revenue"] / 1e6, color=NAVY)
    ax.set_title("Top 12 categories by revenue (R$M)")
    for i, (rev, score) in enumerate(zip(top["revenue"] / 1e6, top["avg_review_score"])):
        ax.text(rev + 0.02, i, f"{rev:.2f}  ({score:.2f}★)", va="center", fontsize=8)
    save(fig, "06_category_revenue.png")
    return {
        "top_category": str(cat.iloc[0]["category"]),
        "top_category_pct_revenue": float(cat.iloc[0]["pct_revenue"]),
        "top3_pct_revenue": round(float(cat.head(3)["pct_revenue"].sum()), 2),
        "categories_total": int(len(cat)),
    }


def chart_state(st: pd.DataFrame) -> dict:
    top = st.head(10)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(top["customer_state"], top["revenue"] / 1e6, color=NAVY)
    axes[0].set_title("Top 10 states by revenue (R$M)")
    for i, v in enumerate(top["revenue"] / 1e6):
        axes[0].text(i, v + 0.03, f"{v:.2f}", ha="center", fontsize=8)
    axes[1].bar(top["customer_state"], top["avg_delivery_days"], color=AMBER)
    axes[1].set_title("Avg delivery days — same states")
    for i, v in enumerate(top["avg_delivery_days"]):
        axes[1].text(i, v + 0.2, f"{v:.1f}", ha="center", fontsize=8)
    fig.suptitle("Geography: revenue vs delivery speed", fontsize=12, fontweight="bold")
    save(fig, "07_state.png")

    corr = stats.pearsonr(st["avg_delivery_days"], st["avg_review_score"])
    return {
        "top_state": str(top.iloc[0]["customer_state"]),
        "top3_states_pct_revenue": round(float(st.head(3)["pct_revenue"].sum()), 2),
        "delivery_vs_review_r": round(float(corr[0]), 3),
        "delivery_vs_review_p": round(float(corr[1]), 4),
        "slowest_state": str(st.sort_values("avg_delivery_days", ascending=False).iloc[0]["customer_state"]),
        "slowest_state_days": float(st.sort_values("avg_delivery_days", ascending=False).iloc[0]["avg_delivery_days"]),
    }


def chart_payment(pay: pd.DataFrame) -> dict:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].pie(pay["pct_value"], labels=pay["payment_type"], autopct="%1.1f%%",
                colors=[NAVY, TEAL, AMBER, RED], startangle=90, textprops={"fontsize": 8})
    axes[0].set_title("Share of transaction value by payment type")
    axes[1].bar(pay["payment_type"], pay["pct_multi_installment"] * 100, color=TEAL)
    axes[1].set_title("% of payments using more than one instalment")
    for i, v in enumerate(pay["pct_multi_installment"] * 100):
        axes[1].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=8)
    fig.suptitle("Payment behaviour", fontsize=12, fontweight="bold")
    save(fig, "08_payment_mix.png")
    return {
        "card_pct_value": float(pay.loc[pay["payment_type"] == "credit_card", "pct_value"].iloc[0]),
        "card_avg_installments": float(pay.loc[pay["payment_type"] == "credit_card", "avg_installments"].iloc[0]),
    }


# --------------------------------------------------------------- 6. SLA / CSAT
def chart_sla(sla: pd.DataFrame, rd: pd.DataFrame, orders_csv: pd.DataFrame) -> dict:
    sla = sla.copy()
    sla["order_month"] = pd.to_datetime(sla["order_month"])
    sla = sla[sla["order_month"] >= pd.Timestamp(WINDOW_START)]
    rd = rd[rd["delivery_bucket"] != "no data"].copy()
    order = ["7+ days early", "3-6 days early", "0-2 days early", "1-3 days late", "4+ days late"]
    rd["delivery_bucket"] = pd.Categorical(rd["delivery_bucket"], categories=order, ordered=True)
    rd = rd.sort_values("delivery_bucket")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))

    ax = axes[0]
    ax.plot(sla["order_month"], sla["on_time_pct"], marker="o", ms=3, color=TEAL)
    ax.axhline(90, ls="--", color=RED, lw=1)
    ax.set_title("On-time delivery % (vs customer estimate)")
    ax.set_ylim(0, 100)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(45); lbl.set_ha("right")

    ax = axes[1]
    ax.bar(rd["delivery_bucket"].astype(str), rd["avg_review_score"], color=NAVY)
    ax.set_title("Review score by delivery timeliness")
    ax.set_ylim(0, 5)
    for i, v in enumerate(rd["avg_review_score"]):
        ax.text(i, v + 0.08, f"{v:.2f}", ha="center", fontsize=8)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(20); lbl.set_ha("right")

    ax = axes[2]
    ax.bar(rd["delivery_bucket"].astype(str), rd["pct_bad_reviews"], color=RED)
    ax.set_title("% of orders with a 1-2 star review")
    for i, v in enumerate(rd["pct_bad_reviews"]):
        ax.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=8)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(20); lbl.set_ha("right")

    fig.suptitle("Delivery SLA vs customer satisfaction", fontsize=12, fontweight="bold")
    save(fig, "09_delivery_vs_csat.png")

    # statistical test on the order-level data
    df = orders_csv.dropna(subset=["days_vs_estimate", "avg_review_score"])
    late = df[df["days_vs_estimate"] < 0]["avg_review_score"]
    ontime = df[df["days_vs_estimate"] >= 0]["avg_review_score"]
    welch = stats.ttest_ind(late, ontime, equal_var=False)

    early = rd[rd["delivery_bucket"] == "0-2 days early"]["avg_review_score"]
    late4 = rd[rd["delivery_bucket"] == "4+ days late"]["avg_review_score"]
    return {
        "avg_on_time_pct": round(float(sla["on_time_pct"].mean()), 2),
        "late_orders": int(len(late)),
        "late_pct_of_delivered": round(100 * len(late) / len(df), 2),
        "late_avg_review": round(float(late.mean()), 3),
        "ontime_avg_review": round(float(ontime.mean()), 3),
        "welch_t": round(float(welch[0]), 2),
        "welch_p": float(f"{welch[1]:.3e}"),
        "bad_review_rate_ontime_pct": float(rd.loc[rd["delivery_bucket"] == "0-2 days early", "pct_bad_reviews"].iloc[0]),
        "bad_review_rate_late_pct": float(rd.loc[rd["delivery_bucket"] == "4+ days late", "pct_bad_reviews"].iloc[0]),
        "avg_delivery_days": round(float(sla["avg_delivery_days"].mean()), 2),
    }


# ---------------------------------------------------------------------- main
def main() -> None:
    print("[1/6] trend");      trend = chart_trend(load("mart_monthly_kpi"))
    print("[2/6] cohorts");    coh = chart_cohort(load("mart_cohort"))
    print("[3/6] rfm");        rfm = chart_rfm(load("mart_rfm_segments"), load("mart_rfm"))
    print("[4/6] pareto");     par = chart_pareto(load("mart_pareto"))
    print("[5/6] category/state/payment")
    cat = chart_category(load("mart_category"))
    st = chart_state(load("mart_state"))
    pay = chart_payment(load("mart_payment"))
    print("[6/6] delivery SLA")
    sla = chart_sla(load("mart_delivery_sla"), load("mart_review_delay"),
                    load("fact_order_summary"))

    findings = {"trend": trend, "cohort": coh, "rfm": rfm, "pareto": par,
                "category": cat, "state": st, "payment": pay, "sla": sla}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "findings.json").write_text(json.dumps(findings, indent=2, default=str), encoding="utf-8")
    print("\nfindings -> reports/findings.json")
    print(json.dumps(findings, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
