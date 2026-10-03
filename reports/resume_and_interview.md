# Resume Bullets + Interview Prep — Olist Revenue & Customer Analytics

## Paste-ready resume bullets (pick 3-4, tune the ₹ to your comfort)

**Project: Revenue & Customer Analytics — Brazilian E-Commerce Marketplace (99K orders)** · *SQL · DuckDB · Python · pandas · Matplotlib · Streamlit*
- Built an end-to-end analytics warehouse (4 dims, 5 facts, 11 marts) in SQL over 9 raw Olist tables (99,441 orders, 96,350 unique customers) with automated data-quality checks — 0 orphan joins, 0 duplicate keys.
- Segmented 94,399 customers using RFM with distinct-value frequency scoring (naive NTILE proven invalid on 97% tied data), isolating 356 high-value *At Risk* customers holding R$138.6K of proven spend.
- Quantified near-zero retention (M+1 cohort ≈ 0.5%; 97% one-time buyers) and extreme concentration (top 10% of customers = 41.3% of revenue), turning both into win-back and loyalty recommendations.
- Statistically proved delivery lateness as the CSAT lever (late orders: 1.86★ & 74.6% bad reviews vs 4.31★ & 8.9% on-time; Welch t = -101, p ≈ 0) and recommended carrier SLA targets, projecting review-score recovery in the worst states.
- Delivered an interactive Streamlit dashboard and a 9-chart report pack with a 1-page executive memo (R$13.44M revenue, +638% window growth, R$137 AOV).

## 60-second interview story (STAR)

> "Olist was growing fast but I suspected the growth was hollow. I built the warehouse in SQL, ran cohort and RFM analysis in Python, and proved it: 97% of customers buy once and M+1 retention is half a percent. The interesting part was the modelling choice — frequency was so tied that quintile scoring was garbage, so I switched to distinct-value tiers. The business payoff: a win-back program sized at ~55K customers, a save-list of 356 high-value repeat buyers worth R$138K, and a delivery-SLA fix because late orders get 75% bad reviews."

## Likely questions & crisp answers

| Q | A (one or two lines) |
|---|---|
| Why RFM over K-means? | Interpretable, stable, business-actionable; K-means needs scaling/seed choices and gives you clusters you still have to name. I'd cluster *inside* RFM segments if asked. |
| Why not NTILE on frequency? | 96.97% of customers have frequency = 1 — NTILE(5) over that splits identical customers arbitrarily. Score distinct values (1/2/3-4/5+ orders) instead. |
| How did you define "active/churned"? | Snapshot against last order date in data (not today); Hibernating = bottom 2 recency quintiles (~13 months silent), Need Attention = middle quintile. |
| Revenue reconciliation gap? | Item-based R$13.44M vs payment-based R$15.60M (+16%): payments include later-cancelled orders and split-payment rows. I report item-based and disclose the gap. |
| Walk me through cohort SQL | first-order month per customer → join back to order months → month_offset → group by cohort & offset → active/cohort_size. |
| Is late delivery *causing* bad reviews? | It's observational, so strictly: correlation. But the 65-point bad-review gap with p≈0, dose-response across delay buckets, and no plausible reverse causality make it the strongest actionable lever. |
| Revenue dropped 12% in a month — investigate? | Check partial-month/data issues first, then decompose: traffic × conversion × AOV; then by category/state/carrier; then events (holidays, promos, stock-outs). |
| Why DuckDB? | Columnar, zero-config, reads CSVs directly, same SQL ports to Postgres. For a job: dbt + warehouse. |

## Where to publish

GitHub repo (this folder, minus `data/raw` — add a download script instead), dashboard on Streamlit Community Cloud, notebook via nbviewer, 2-min Loom walkthrough pinned.
