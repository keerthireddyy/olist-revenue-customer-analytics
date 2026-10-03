/* ============================================================================
   OLIST ANALYTICS — mart layer
   Every query below is exported to data/processed/ by scripts/01_build_warehouse.py
   All revenue marts filter on is_revenue_order = 1 (delivered + shipped only).
   ============================================================================ */

/* ---------------------------------------------------- MART: monthly KPI trend */
-- :mart_monthly_kpi
SELECT
    f.order_month                                              AS order_month,
    COUNT(DISTINCT f.order_id)                                 AS orders,
    COUNT(DISTINCT f.customer_unique_id)                       AS customers,
    ROUND(SUM(f.order_revenue), 2)                             AS revenue,
    ROUND(SUM(f.order_revenue) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2)      AS aov,
    ROUND(SUM(f.order_revenue) / NULLIF(COUNT(DISTINCT f.customer_unique_id), 0), 2) AS revenue_per_customer,
    SUM(f.item_count)                                          AS items_sold,
    ROUND(AVG(f.days_to_deliver), 1)                           AS avg_delivery_days,
    ROUND(AVG(f.avg_review_score), 2)                          AS avg_review_score
FROM fact_order_summary f
WHERE f.is_revenue_order = 1
GROUP BY 1
ORDER BY 1;

/* ------------------------------------------------------- MART: customer RFM */
/* RFM measured against the last order date in the dataset ("as-of" snapshot),
   which is the correct way to score an analytics snapshot rather than today(). */
-- :mart_rfm
WITH base AS (
    SELECT
        f.customer_unique_id,
        MAX(f.order_date)                                    AS last_order_date,
        MIN(f.order_date)                                    AS first_order_date,
        COUNT(DISTINCT f.order_id)                           AS frequency,
        SUM(f.order_revenue)                                 AS monetary,
        SUM(f.item_count)                                    AS items_bought
    FROM fact_order_summary f
    WHERE f.is_revenue_order = 1
    GROUP BY 1
),
as_of AS (SELECT MAX(order_date) AS as_of_date FROM fact_order_summary WHERE is_revenue_order = 1),
scored AS (
    SELECT
        b.*,
        a.as_of_date,
        datediff('day', b.last_order_date, a.as_of_date)     AS recency_days,
        datediff('day', b.first_order_date, b.last_order_date) AS lifespan_days,
        NTILE(5) OVER (ORDER BY datediff('day', b.last_order_date, a.as_of_date) DESC) AS r_score,
        NTILE(5) OVER (ORDER BY b.frequency)                             AS f_score,
        NTILE(5) OVER (ORDER BY b.monetary)                                   AS m_score
    FROM base b CROSS JOIN as_of a          -- base is already 1 row per customer
)
SELECT
    customer_unique_id,
    first_order_date,
    last_order_date,
    as_of_date,
    recency_days,
    frequency,
    ROUND(monetary, 2)                                       AS monetary,
    items_bought,
    r_score,
    f_score,
    m_score,
    CAST(r_score AS VARCHAR) || CAST(f_score AS VARCHAR) || CAST(m_score AS VARCHAR) AS rfm_cell,
    ROUND(monetary / NULLIF(frequency, 0), 2)                AS avg_order_value,
    CASE WHEN frequency > 1 THEN 1 ELSE 0 END                AS is_repeat_customer
FROM scored;

/* ---------------------------------------------- MART: RFM segment roll-up */
-- :mart_rfm_segments
SELECT
    segment,
    COUNT(*)                                                 AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)       AS pct_customers,
    ROUND(SUM(monetary), 2)                                  AS revenue,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS pct_revenue,
    ROUND(AVG(monetary), 2)                                  AS avg_monetary,
    ROUND(AVG(frequency), 2)                                 AS avg_frequency,
    ROUND(AVG(recency_days), 0)                              AS avg_recency_days
FROM mart_customer_segment
GROUP BY 1
ORDER BY revenue DESC;

/* ------------------------------------------------- MART: monthly cohort retention */
/* A cohort = the month a customer placed their FIRST revenue order.
   Retention = % of that cohort ordering again in month_offset N. */
-- :mart_cohort
WITH firsts AS (
    SELECT customer_unique_id, MIN(order_month) AS cohort_month
    FROM fact_order_summary WHERE is_revenue_order = 1
    GROUP BY 1
),
activity AS (
    SELECT DISTINCT f.customer_unique_id, f.order_month
    FROM fact_order_summary f WHERE f.is_revenue_order = 1
),
joined AS (
    SELECT
        ft.cohort_month,
        a.order_month,
        (YEAR(a.order_month) - YEAR(ft.cohort_month)) * 12
          + (MONTH(a.order_month) - MONTH(ft.cohort_month)) AS month_offset,
        a.customer_unique_id
    FROM firsts ft JOIN activity a USING (customer_unique_id)
),
sizes AS (
    SELECT cohort_month, COUNT(DISTINCT customer_unique_id) AS cohort_size
    FROM firsts GROUP BY 1
)
SELECT
    j.cohort_month,
    s.cohort_size,
    j.month_offset,
    COUNT(DISTINCT j.customer_unique_id)                     AS active_customers,
    ROUND(100.0 * COUNT(DISTINCT j.customer_unique_id) / s.cohort_size, 2) AS retention_pct
FROM joined j JOIN sizes s USING (cohort_month)
WHERE j.month_offset BETWEEN 0 AND 24
GROUP BY 1, 2, 3
ORDER BY 1, 3;

/* ---------------------------------------------------- MART: revenue concentration (Pareto) */
-- :mart_pareto
WITH cust AS (
    SELECT customer_unique_id, SUM(order_revenue) AS monetary
    FROM fact_order_summary WHERE is_revenue_order = 1
    GROUP BY 1
),
ranked AS (
    SELECT
        customer_unique_id,
        monetary,
        ROW_NUMBER() OVER (ORDER BY monetary DESC)                                  AS rk,
        SUM(monetary) OVER (ORDER BY monetary DESC ROWS UNBOUNDED PRECEDING)        AS cum_revenue,
        SUM(monetary) OVER ()                                                       AS total_revenue,
        COUNT(*) OVER ()                                                            AS total_customers
    FROM cust
)
SELECT
    rk,
    customer_unique_id,
    ROUND(monetary, 2)                                     AS monetary,
    ROUND(cum_revenue, 2)                                  AS cumulative_revenue,
    ROUND(100.0 * rk / total_customers, 4)                 AS pct_customers,
    ROUND(100.0 * cum_revenue / total_revenue, 4)          AS pct_revenue
FROM ranked;

/* ------------------------------------------------------- MART: category performance */
-- :mart_category
SELECT
    dp.category,
    COUNT(DISTINCT fo.order_id)                              AS orders,
    SUM(1)                                                   AS items_sold,
    ROUND(SUM(foi.price), 2)                                 AS revenue,
    ROUND(SUM(foi.freight_value), 2)                         AS freight,
    ROUND(SUM(foi.price) / NULLIF(SUM(1), 0), 2)             AS avg_unit_price,
    ROUND(100.0 * SUM(foi.price) / SUM(SUM(foi.price)) OVER (), 2) AS pct_revenue,
    COUNT(DISTINCT fr.review_id)                             AS reviews,
    ROUND(AVG(fr.review_score), 2)                           AS avg_review_score
FROM fact_order_items foi
JOIN fact_orders fo      ON foi.order_id = fo.order_id
LEFT JOIN dim_product dp ON foi.product_id = dp.product_id
LEFT JOIN fact_reviews fr ON fo.order_id = fr.order_id
WHERE fo.is_revenue_order = 1
GROUP BY 1
HAVING SUM(foi.price) > 0
ORDER BY revenue DESC;

/* --------------------------------------------------------- MART: state performance */
-- :mart_state
SELECT
    COALESCE(dc.customer_state, 'UNKNOWN')                   AS customer_state,
    COUNT(DISTINCT fo.order_id)                              AS orders,
    COUNT(DISTINCT fo.customer_unique_id)                    AS customers,
    ROUND(SUM(foi.price), 2)                                 AS revenue,
    ROUND(SUM(foi.price) / NULLIF(COUNT(DISTINCT fo.order_id), 0), 2) AS aov,
    ROUND(100.0 * SUM(foi.price) / SUM(SUM(foi.price)) OVER (), 2)    AS pct_revenue,
    ROUND(AVG(fo.days_to_deliver), 1)                        AS avg_delivery_days,
    ROUND(AVG(fr.review_score), 2)                           AS avg_review_score
FROM fact_orders fo
LEFT JOIN dim_customer dc ON fo.customer_unique_id = dc.customer_unique_id
JOIN fact_order_items foi ON fo.order_id = foi.order_id
LEFT JOIN fact_reviews fr ON fo.order_id = fr.order_id
WHERE fo.is_revenue_order = 1
GROUP BY 1
ORDER BY revenue DESC;

/* --------------------------------------------------------- MART: delivery SLA */
-- :mart_delivery_sla
SELECT
    fo.order_month,
    COUNT(*)                                                 AS delivered_orders,
    ROUND(AVG(fo.days_to_deliver), 2)                        AS avg_delivery_days,
    ROUND(MEDIAN(fo.days_to_deliver), 2)                     AS median_delivery_days,
    SUM(CASE WHEN fo.days_vs_estimate >= 0 THEN 1 ELSE 0 END) AS on_time_orders,
    ROUND(100.0 * SUM(CASE WHEN fo.days_vs_estimate >= 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS on_time_pct,
    ROUND(AVG(fo.days_to_ship), 2)                           AS avg_days_to_ship,
    ROUND(AVG(fo.days_vs_estimate), 2)                       AS avg_days_vs_estimate
FROM fact_orders fo
WHERE fo.order_status = 'delivered'
  AND fo.days_to_deliver IS NOT NULL
  AND fo.days_to_deliver BETWEEN 0 AND 200
GROUP BY 1
ORDER BY 1;

/* --------------------------------------------------------- MART: payment mix */
-- :mart_payment
SELECT
    fp.payment_type,
    COUNT(DISTINCT fp.order_id)                              AS orders,
    ROUND(SUM(fp.payment_value), 2)                          AS value,
    ROUND(100.0 * SUM(fp.payment_value) / SUM(SUM(fp.payment_value)) OVER (), 2) AS pct_value,
    ROUND(AVG(fp.payment_installments), 2)                   AS avg_installments,
    ROUND(AVG(CASE WHEN fp.payment_installments > 1 THEN 1.0 ELSE 0 END), 4)     AS pct_multi_installment
FROM fact_payments fp
JOIN fact_orders fo ON fp.order_id = fo.order_id
WHERE fo.is_revenue_order = 1
GROUP BY 1
ORDER BY value DESC;

/* ------------------------------------- MART: repeat vs one-time purchase behaviour */
-- :mart_repeat
WITH cust AS (
    SELECT customer_unique_id, COUNT(DISTINCT order_id) AS orders, SUM(order_revenue) AS monetary
    FROM fact_order_summary WHERE is_revenue_order = 1
    GROUP BY 1
)
SELECT
    CASE WHEN orders = 1 THEN '1 order'
         WHEN orders = 2 THEN '2 orders'
         WHEN orders = 3 THEN '3 orders'
         ELSE '4+ orders' END                                AS order_bucket,
    COUNT(*)                                                 AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)       AS pct_customers,
    ROUND(SUM(monetary), 2)                                  AS revenue,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS pct_revenue,
    ROUND(AVG(monetary), 2)                                  AS avg_monetary
FROM cust
GROUP BY 1
ORDER BY 1;

/* ------------------------------------------ MART: review score vs delivery delay */
-- :mart_review_delay
SELECT
    CASE
        WHEN days_vs_estimate IS NULL       THEN 'no data'
        WHEN days_vs_estimate >= 7          THEN '7+ days early'
        WHEN days_vs_estimate >= 3          THEN '3-6 days early'
        WHEN days_vs_estimate >= 0          THEN '0-2 days early'
        WHEN days_vs_estimate >= -3         THEN '1-3 days late'
        ELSE '4+ days late'
    END                                                      AS delivery_bucket,
    COUNT(*)                                                 AS orders,
    ROUND(AVG(avg_review_score), 3)                          AS avg_review_score,
    ROUND(100.0 * SUM(CASE WHEN avg_review_score <= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_bad_reviews
FROM fact_order_summary
WHERE order_status = 'delivered' AND avg_review_score IS NOT NULL
GROUP BY 1
ORDER BY MIN(days_vs_estimate) DESC;
