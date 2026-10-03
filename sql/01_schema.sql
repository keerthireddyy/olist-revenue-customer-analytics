/* ============================================================================
   OLIST ANALYTICS WAREHOUSE — schema.sql
   ----------------------------------------------------------------------------
   Builds a clean star schema (4 dims + 5 facts) on top of the raw Olist CSVs.
   Engine : DuckDB (runs the same SQL on Postgres with minor type changes)
   Grain    : one row per ORDER in fact_orders, one row per ORDER-ITEM in fact_order_items

   Design decisions (these are the things interviewers probe):
   1. Revenue is defined at ORDER-ITEM grain (price + freight), not order grain,
      because one order can contain several items and several sellers.
   2. Canceled / unavailable / created orders are EXCLUDED from revenue marts via
      the is_revenue_order flag, but kept in the warehouse so cancellation rate
      can still be measured.
   3. customer_unique_id (not customer_id) is the true customer key. Olist's
      customer_id is per-order, so using it inflates the customer count.
   4. Category names are English-first with Portuguese fallback.
   ============================================================================ */

CREATE OR REPLACE TABLE raw_orders AS
SELECT * FROM read_csv_auto('data/raw/olist_orders_dataset.csv', header=true, ignore_errors=true);

CREATE OR REPLACE TABLE raw_items AS
SELECT * FROM read_csv_auto('data/raw/olist_order_items_dataset.csv', header=true, ignore_errors=true);

CREATE OR REPLACE TABLE raw_payments AS
SELECT * FROM read_csv_auto('data/raw/olist_order_payments_dataset.csv', header=true, ignore_errors=true);

CREATE OR REPLACE TABLE raw_reviews AS
SELECT * FROM read_csv_auto('data/raw/olist_order_reviews_dataset.csv', header=true, ignore_errors=true);

CREATE OR REPLACE TABLE raw_customers AS
SELECT * FROM read_csv_auto('data/raw/olist_customers_dataset.csv', header=true, ignore_errors=true);

CREATE OR REPLACE TABLE raw_products AS
SELECT * FROM read_csv_auto('data/raw/olist_products_dataset.csv', header=true, ignore_errors=true);

CREATE OR REPLACE TABLE raw_sellers AS
SELECT * FROM read_csv_auto('data/raw/olist_sellers_dataset.csv', header=true, ignore_errors=true);

CREATE OR REPLACE TABLE raw_category_translation AS
SELECT * FROM read_csv_auto('data/raw/product_category_name_translation.csv', header=true, ignore_errors=true);


/* ---------------------------------------------------------------- DIMENSIONS */

CREATE OR REPLACE TABLE dim_customer AS
SELECT
    c.customer_unique_id,
    MIN(c.customer_id)                                   AS first_customer_id,
    UPPER(TRIM(c.customer_state))                        AS customer_state,
    c.customer_zip_code_prefix                           AS customer_zip_prefix,
    COUNT(DISTINCT c.customer_id)                        AS customer_id_count
FROM raw_customers c
GROUP BY 1, 3, 4;

CREATE OR REPLACE TABLE dim_product AS
SELECT
    p.product_id,
    COALESCE(NULLIF(TRIM(t.product_category_name_english), ''),
             p.product_category_name,
             'uncategorised')                            AS category,
    p.product_category_name                              AS category_pt,
    p.product_name_lenght                                AS product_name_length,
    p.product_description_lenght                         AS product_description_length,
    p.product_photos_qty                                 AS product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    ROUND(p.product_length_cm * p.product_height_cm * p.product_width_cm, 1) AS product_volume_cm3
FROM raw_products p
LEFT JOIN raw_category_translation t
       ON p.product_category_name = t.product_category_name;

CREATE OR REPLACE TABLE dim_seller AS
SELECT
    s.seller_id,
    UPPER(TRIM(s.seller_state))                          AS seller_state,
    s.seller_zip_code_prefix                             AS seller_zip_prefix
FROM raw_sellers s;

/* Calendar spine so months with zero sales still appear in trend charts */
CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT MIN(CAST(order_purchase_timestamp AS DATE))  AS min_d,
           MAX(CAST(order_purchase_timestamp AS DATE))  AS max_d
    FROM raw_orders
),
days AS (
    SELECT unnest(generate_series(min_d, max_d, INTERVAL 1 DAY)) AS date_day
    FROM bounds
)
SELECT
    CAST(date_day AS DATE)                               AS date_day,
    date_trunc('month', date_day)::DATE                  AS date_month,
    date_trunc('quarter', date_day)::DATE                AS date_quarter,
    YEAR(date_day)                                       AS year,
    MONTH(date_day)                                      AS month,
    strftime(date_day, '%b-%y')                          AS month_label,
    strftime(date_day, '%Y-Q') || CAST(QUARTER(date_day) AS VARCHAR) AS quarter_label,
    DAYOFWEEK(date_day)                                  AS dow,
    DAYOFYEAR(date_day)                                  AS doy
FROM days;


/* -------------------------------------------------------------------- FACTS */

CREATE OR REPLACE TABLE fact_orders AS
SELECT
    o.order_id,
    c.customer_unique_id,
    o.order_status,
    CAST(o.order_purchase_timestamp AS TIMESTAMP)        AS order_purchase_ts,
    CAST(o.order_purchase_timestamp AS DATE)             AS order_date,
    date_trunc('month', CAST(o.order_purchase_timestamp AS DATE))::DATE AS order_month,
    CAST(o.order_approved_at AS TIMESTAMP)               AS order_approved_ts,
    CAST(o.order_delivered_carrier_date AS TIMESTAMP)    AS shipped_ts,
    CAST(o.order_delivered_customer_date AS TIMESTAMP)   AS delivered_ts,
    CAST(o.order_estimated_delivery_date AS DATE)        AS estimated_delivery_date,
    CASE WHEN o.order_status IN ('delivered','shipped') THEN 1 ELSE 0 END AS is_revenue_order,
    CASE WHEN o.order_status IN ('canceled','unavailable') THEN 1 ELSE 0 END AS is_cancelled_order,
    datediff('minute', CAST(o.order_purchase_timestamp AS TIMESTAMP),
                       CAST(o.order_approved_at AS TIMESTAMP)) / 60.0      AS hours_to_approve,
    datediff('day', CAST(o.order_approved_at AS TIMESTAMP),
                    CAST(o.order_delivered_carrier_date AS TIMESTAMP))     AS days_to_ship,
    datediff('day', CAST(o.order_purchase_timestamp AS TIMESTAMP),
                    CAST(o.order_delivered_customer_date AS TIMESTAMP))    AS days_to_deliver,
    datediff('day', CAST(o.order_delivered_customer_date AS TIMESTAMP),
                    CAST(o.order_estimated_delivery_date AS DATE))         AS days_vs_estimate
FROM raw_orders o
LEFT JOIN (SELECT DISTINCT customer_id, customer_unique_id FROM raw_customers) c
       ON o.customer_id = c.customer_id;

CREATE OR REPLACE TABLE fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    TRY_CAST(i.price AS DOUBLE)                          AS price,
    TRY_CAST(i.freight_value AS DOUBLE)                  AS freight_value,
    TRY_CAST(i.price AS DOUBLE) + TRY_CAST(i.freight_value AS DOUBLE) AS revenue,
    CAST(i.shipping_limit_date AS TIMESTAMP)             AS shipping_limit_ts
FROM raw_items i;

/* Payments: one row per payment, so SUM(value) is the money actually collected */
CREATE OR REPLACE TABLE fact_payments AS
SELECT
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    TRY_CAST(p.payment_installments AS INTEGER)          AS payment_installments,
    TRY_CAST(p.payment_value AS DOUBLE)                  AS payment_value
FROM raw_payments p;

CREATE OR REPLACE TABLE fact_reviews AS
SELECT
    r.review_id,
    r.order_id,
    TRY_CAST(r.review_score AS INTEGER)                  AS review_score,
    r.review_comment_title,
    r.review_comment_message,
    CAST(r.review_creation_date AS TIMESTAMP)            AS review_creation_ts,
    CAST(r.review_answer_timestamp AS TIMESTAMP)         AS review_answer_ts,
    datediff('hour', CAST(r.review_creation_date AS TIMESTAMP),
                     CAST(r.review_answer_timestamp AS TIMESTAMP)) / 24.0 AS days_to_answer_review
FROM raw_reviews r;

/* Denormalised order-level fact: the workhorse table for every mart below */
CREATE OR REPLACE TABLE fact_order_summary AS
SELECT
    fo.order_id,
    fo.customer_unique_id,
    dc.customer_state,
    fo.order_status,
    fo.is_revenue_order,
    fo.is_cancelled_order,
    fo.order_date,
    fo.order_month,
    fo.days_to_deliver,
    fo.days_vs_estimate,
    itm.item_count,
    itm.seller_count,
    itm.order_revenue,
    itm.order_freight,
    COALESCE(pay.payment_value, 0)                       AS payment_value,
    rev.avg_review_score
FROM fact_orders fo
LEFT JOIN dim_customer dc ON fo.customer_unique_id = dc.customer_unique_id
LEFT JOIN (
    SELECT order_id,
           COUNT(*)                        AS item_count,
           COUNT(DISTINCT seller_id)       AS seller_count,
           SUM(price)                      AS order_revenue,
           SUM(freight_value)              AS order_freight
    FROM fact_order_items GROUP BY 1
) itm ON fo.order_id = itm.order_id
LEFT JOIN (
    SELECT order_id, SUM(payment_value) AS payment_value
    FROM fact_payments GROUP BY 1
) pay ON fo.order_id = pay.order_id
LEFT JOIN (
    SELECT order_id, AVG(review_score) AS avg_review_score
    FROM fact_reviews GROUP BY 1
) rev ON fo.order_id = rev.order_id;


/* ============================================================ MART TABLES === */
/* Materialised so downstream marts can reference it without CSV round-trips. */

CREATE OR REPLACE TABLE mart_rfm_base AS
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
as_of AS (SELECT MAX(order_date) AS as_of_date FROM fact_order_summary WHERE is_revenue_order = 1)
SELECT
    b.customer_unique_id,
    b.first_order_date,
    b.last_order_date,
    a.as_of_date,
    datediff('day', b.last_order_date, a.as_of_date)         AS recency_days,
    b.frequency,
    ROUND(b.monetary, 2)                                     AS monetary,
    b.items_bought,
    NTILE(5) OVER (ORDER BY datediff('day', b.last_order_date, a.as_of_date) DESC) AS r_score,
/* f_score: frequency has only 9 distinct values and 96.97% of customers sit
       at 1 order, so a quintile split (NTILE) would carve identical customers
       into different tiers. Score it explicitly instead. */
    CASE WHEN b.frequency = 1 THEN 1
         WHEN b.frequency = 2 THEN 2
         WHEN b.frequency <= 4 THEN 3
         ELSE 4 END                                        AS f_score,
    NTILE(5) OVER (ORDER BY b.monetary)                      AS m_score,
    ROUND(b.monetary / NULLIF(b.frequency, 0), 2)            AS avg_order_value,
    CASE WHEN b.frequency > 1 THEN 1 ELSE 0 END              AS is_repeat_customer
FROM base b CROSS JOIN as_of a;

ALTER TABLE mart_rfm_base
    ADD COLUMN rfm_cell VARCHAR;

UPDATE mart_rfm_base
SET rfm_cell = CAST(r_score AS VARCHAR) || CAST(f_score AS VARCHAR) || CAST(m_score AS VARCHAR);

CREATE OR REPLACE TABLE mart_customer_segment AS
SELECT
    r.*,
/* Segment grid over R (1-5) x F (1-4). Every R value is covered, so no
       customer can fall through to an "Other" bucket. */
    CASE
        WHEN r_score = 5 AND f_score >= 3 THEN 'Champions'
        WHEN r_score = 5 AND f_score = 2  THEN 'Loyal Customers'
        WHEN r_score = 5                  THEN 'New / Promising'
        WHEN r_score = 4 AND f_score >= 2 THEN 'Loyal Customers'
        WHEN r_score = 4                  THEN 'Need Attention'
        WHEN r_score = 3 AND f_score >= 2 THEN 'Potential Loyalists'
        WHEN r_score = 3                  THEN 'Need Attention'
        WHEN r_score = 2 AND f_score >= 2 AND monetary > (SELECT AVG(monetary) FROM mart_rfm_base)
                                          THEN 'At Risk'
        ELSE 'Hibernating / Lost'
    END AS segment
FROM mart_rfm_base r;
