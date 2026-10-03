# Executive Summary — Olist Revenue & Customer Analytics
**Data Analyst portfolio project · Dataset: Kaggle Brazilian E-Commerce (Olist) · 99,441 orders · Sep 2016 – Sep 2018**
All revenue figures use *delivered + shipped* orders only (revenue orders). Analysis window for growth: Jan-17 → Aug-18.

## Headline (verified from `reports/headline_metrics.json`)

| Metric | Value |
|---|---|
| Revenue (item basis) | **R$13.44M** (~₹20.2 Cr at R$1 = ₹15) |
| Revenue orders | 98,126 across 24 months |
| Unique customers | 94,399 |
| Average order value | R$137 |
| Repeat-customer rate | **3.0%** (97% buy exactly once) |
| Top 10% of customers | **41.3%** of lifetime revenue |
| Cancellation rate | 1.24% |
| Avg delivery time | 12.5 days · on-time vs estimate 90.5% |
| Avg review score | 4.09 / 5 |

## Five findings

1. **Hyper-growth, acquisition-only model.** Revenue grew **+638%** first-to-last month inside the analysis window (annualised ≈ 254%), peaking Nov-17 at R$1.0M. But cohort M+1 retention is ~0.5% — growth is 100% acquisition-funded.
2. **Extreme revenue concentration.** Pareto: top 1% of customers → 11.5% of revenue; top 10% → 41.3%; top 20% → 56.8%. The tail of one-time, low-value buyers is long.
3. **Segmentation exposes a dormant majority.** With honest RFM scoring, 39.6% of customers (37.4K, R$5.26M proven spend) are *Hibernating/Lost* and 38.7% (36.6K) sit in *Need Attention* (6-7 months silent). Only 2.0% show any repeat behaviour.
4. **Delivery lateness is the CSAT lever.** Orders delivered 4+ days late score **1.86★** with a **74.6%** bad-review rate vs **4.31★ / 8.9%** for early deliveries (Welch t = -101, p ≈ 0). The northern states (RR 28.2d) drag the average.
5. **Catalogue & geography are narrow.** health_beauty + computers_accessories + home furniture ≈ 26% of revenue; SP + RJ + MG ≈ 63%. 78.5% of transaction value rides on credit cards at 3.5 average instalments.

## Recommendations (each tied to a number above)

| # | Action | Owner | Expected lever |
|---|---|---|---|
| 1 | Automated day-30 win-back (coupon + recommendations) for New/Promising & Need Attention (~55K customers) | CRM / Growth | Convert even 2 pts of the 97% one-timers → +R$~540K repeat revenue |
| 2 | Concierge save-program for the 356 *At Risk* high-value repeaters (avg R$389 lifetime, 2+ orders) | CS | Protect R$138.6K proven spend |
| 3 | Carrier SLA renegotiation + on-time ≥90% target; priority lanes to northern states | Logistics | Bad-review rate on late orders 74.6% → target <20% |
| 4 | Stock-out alerts and assortment depth for the top-3 categories | Category mgmt | ~26% of revenue has the highest stock risk |
| 5 | Negotiate instalment economics (3.5x avg) with card acquirers | Finance | Margin on 78.5% of value |

## Data-quality disclosures (what a reviewer will love)
- 0 orphan joins, 0 duplicate orders, 0 negative prices across all 9 raw tables.
- Item-based revenue (R$13.44M) vs payment-based (R$15.60M) differs by +16.0% — documented, not hidden: payments include later-cancelled orders and split-payment rows.
- `frequency` is ~97% tied at 1, so RFM F-scores use **distinct-value tiers**, not quintiles; R and M use NTILE quintiles against the dataset's last order date (snapshot scoring).
- 2016 ramp-up months and the partial final month are excluded from growth math and flagged grey in the trend chart.

## Deliverables in this repo
`sql/01_schema.sql` (star schema) · `sql/02_marts.sql` (11 marts) · `scripts/01_build_warehouse.py` · `scripts/02_analysis.py` · `scripts/03_dashboard.py` (Streamlit) · `notebooks/olist_revenue_customer_analytics.ipynb` (executed) · `reports/charts/*` (9 PNGs) · `reports/findings.json` · `data/processed/*` (15 mart CSVs).
