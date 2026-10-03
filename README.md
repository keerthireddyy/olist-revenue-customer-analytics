# 🛒 Olist — Revenue & Customer Analytics (Data Analyst Portfolio Project)

**Business question:** *Which customers and categories drive profit at Olist, and who is about to leave?*

A complete, reproducible data-analytics project over the real **Kaggle Brazilian E-Commerce (Olist)** dataset:
**99,441 orders · 112,650 order items · 103,886 payments · 99,224 reviews · 96,096 unique customers** (Sep 2016 – Sep 2018).

```
raw CSVs (9 tables)
   │  scripts/01_build_warehouse.py   (SQL star schema + data-quality checks)
   ▼
data/warehouse.duckdb   ← 4 dims · 5 facts
   │  sql/02_marts.sql                (11 analytics marts)
   ▼
data/processed/*.csv    (15 mart CSVs)
   │  scripts/02_analysis.py          (charts + stats + findings.json)
   ▼
reports/charts/*  ·  reports/executive_summary.md
   │  scripts/03_dashboard.py         (interactive Streamlit)
   ▼
live dashboard
```

## Quick start

```bash
pip install -r requirements.txt

python3 scripts/01_build_warehouse.py     # raw -> DuckDB warehouse -> mart CSVs (~10s)
python3 scripts/02_analysis.py            # 9 charts + reports/findings.json
streamlit run scripts/03_dashboard.py --server.address 0.0.0.0 --server.port 8501
```

The executed notebook with full narrative is `notebooks/olist_revenue_customer_analytics.ipynb`.

## What's inside

| Path | What it is |
|---|---|
| `data/raw/` | The 9 Olist CSVs (the **dataset**, ~140 MB; commit or use `scripts/download_dataset.py`) |
| `sql/01_schema.sql` | Star schema: dim_customer/product/seller/date + fact_orders/order_items/payments/reviews + denormalised `fact_order_summary` |
| `sql/02_marts.sql` | 11 marts: monthly KPI, RFM, RFM segments, cohorts, Pareto, category, state, delivery SLA, payment mix, repeat, review-vs-delay |
| `scripts/01_build_warehouse.py` | Builds warehouse, exports marts, runs 15 automated data-quality checks |
| `scripts/02_analysis.py` | Analytics + 9 publication-quality charts + Welch t-test |
| `scripts/03_dashboard.py` | Interactive Streamlit dashboard (6 tabs) |
| `notebooks/…ipynb` | Executed end-to-end narrative notebook |
| `reports/executive_summary.md` | 1-page memo with 5 findings and 5 costed recommendations |
| `reports/resume_and_interview.md` | Paste-ready resume bullets + interview Q&A |
| `reports/charts/` | 9 PNG charts |
| `reports/headline_metrics.json`, `data_quality.json`, `findings.json` | Machine-readable results |

## Headline results (all from the code in this repo)

- **R$13.44M** revenue on 98,126 revenue orders · AOV **R$137** · growth **+638%** over the Jan-17→Aug-18 window
- **97.0% one-time buyers**; M+1 cohort retention ≈ **0.5%** — growth is fully acquisition-funded
- Pareto: top **10%** of customers = **41.3%** of revenue
- Late deliveries (4+ days): **1.86★, 74.6%** bad reviews vs **4.31★, 8.9%** on-time (Welch t = −101, p ≈ 0)
- Top categories health_beauty / computers_accessories / home_furniture ≈ 26% of revenue; SP+RJ+MG ≈ 63%
- 78.5% of value on credit card, 3.5 avg instalments

## Modelling decisions worth discussing in an interview

1. **Revenue = delivered + shipped orders**, item price + freight; cancelled orders excluded from revenue but kept for cancellation-rate analysis.
2. **RFM F-score uses distinct-value tiers** (1 / 2 / 3-4 / 5+ orders), not NTILE — with 96.97% of customers tied at frequency 1, quintiles would split identical customers arbitrarily.
3. **RFM snapshot scored against the last order date in the data**, not `today()`.
4. **Revenue reconciliation disclosed**: item-based R$13.44M vs payment-based R$15.60M (+16%) — payments include later-cancelled orders and split rows; we report item-based and say so.
5. **2016 ramp-up and partial months flagged grey** and excluded from growth math.

## Dataset

`scripts/download_dataset.py` fetches the 9 CSVs (~140 MB). The copies in `data/raw/` were verified against the published Olist release (row counts match exactly).
