-- gold_monthly_spend: one row per calendar month, portfolio level.
--
-- "Spend" is cardholder transaction value. The dataset has no issuer revenue
-- (no interchange, fees or interest), so this is a volume measure, not revenue.
--   gross_spend = purchases (amount > 0)
--   refunds     = reversals, shown as a positive number (amount < 0)
--   net_spend   = gross_spend - refunds  (the forecasting target)
--
-- Forecast features are strictly backward-looking: every lag and rolling window
-- ends at the previous month (... AND 1 PRECEDING), so no feature contains the
-- value it is used to predict. Windows run over complete months only.
WITH monthly AS (
    SELECT
        CAST(date_trunc('month', transaction_date) AS DATE)            AS month_start,
        COUNT(*)                                                       AS transaction_count,
        COUNT(DISTINCT user_id)                                        AS active_customers,
        COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0)             AS gross_spend,
        COALESCE(-SUM(amount) FILTER (WHERE amount < 0), 0)            AS refunds,
        SUM(amount)                                                    AS net_spend,
        COUNT(DISTINCT CAST(transaction_date AS DATE))                 AS days_with_activity
    FROM silver_transactions
    GROUP BY 1
),
flagged AS (
    SELECT
        *,
        -- a month is complete when every calendar day has activity (2,000 customers
        -- transact daily, so a short month means the extract starts/ends mid-month)
        days_with_activity = DAY(last_day(month_start)) AS is_complete_month
    FROM monthly
),
features AS (
    SELECT
        month_start,
        LAG(net_spend, 1)  OVER w AS lag_1_month,
        LAG(net_spend, 2)  OVER w AS lag_2_month,
        LAG(net_spend, 3)  OVER w AS lag_3_month,
        LAG(net_spend, 12) OVER w AS lag_12_month,
        -- windows are NULL until they hold their full number of months
        CASE WHEN COUNT(net_spend) OVER (w ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) = 3
             THEN AVG(net_spend) OVER (w ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) END AS rolling_mean_3_months,
        CASE WHEN COUNT(net_spend) OVER (w ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) = 6
             THEN AVG(net_spend) OVER (w ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) END AS rolling_mean_6_months,
        CASE WHEN COUNT(net_spend) OVER (w ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) = 6
             THEN STDDEV_SAMP(net_spend) OVER (w ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) END AS rolling_std_6_months,
        -- descriptive only (uses the current month): not a model feature
        100.0 * (net_spend - LAG(net_spend, 1) OVER w) / NULLIF(LAG(net_spend, 1) OVER w, 0) AS mom_growth_pct,
        100.0 * (net_spend - LAG(net_spend, 12) OVER w) / NULLIF(LAG(net_spend, 12) OVER w, 0) AS yoy_growth_pct
    FROM flagged
    WHERE is_complete_month
    WINDOW w AS (ORDER BY month_start)
)
SELECT
    f.month_start,
    YEAR(f.month_start)    AS year,
    MONTH(f.month_start)   AS month,
    QUARTER(f.month_start) AS quarter,
    f.transaction_count,
    f.active_customers,
    f.gross_spend,
    f.refunds,
    f.net_spend,
    f.net_spend / NULLIF(f.transaction_count, 0) AS avg_transaction_value,
    f.days_with_activity,
    f.is_complete_month,
    x.lag_1_month,
    x.lag_2_month,
    x.lag_3_month,
    x.lag_12_month,
    x.rolling_mean_3_months,
    x.rolling_mean_6_months,
    x.rolling_std_6_months,
    x.mom_growth_pct,
    x.yoy_growth_pct
FROM flagged f
LEFT JOIN features x USING (month_start)
ORDER BY f.month_start;
