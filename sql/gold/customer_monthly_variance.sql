-- gold_customer_monthly_variance: actual vs budgeted net spend per customer per month.
-- Depends on gold_monthly_spend (for the complete-month calendar).
--
-- Budget = the customer's average net spend over the three previous months.
-- The budget comes only from earlier months, so actual and budget are independent
-- and the variance doesn't sum to zero by construction. (The original notebook
-- budgeted from the same month's average, which made every variance net to zero.)
--
-- Perspective: card-portfolio volume. Spend above budget is Favourable,
-- spend below budget is Adverse.
-- Months with no transactions inside a customer's active span count as zero spend.
WITH customer_month AS (
    SELECT
        user_id,
        CAST(date_trunc('month', transaction_date) AS DATE) AS month_start,
        COUNT(*)    AS transaction_count,
        SUM(amount) AS actual_spend
    FROM silver_transactions
    GROUP BY 1, 2
),
span AS (
    SELECT user_id, MIN(month_start) AS first_month, MAX(month_start) AS last_month
    FROM customer_month
    GROUP BY 1
),
grid AS (
    SELECT
        user_id,
        CAST(UNNEST(generate_series(first_month, last_month, INTERVAL 1 MONTH)) AS DATE) AS month_start
    FROM span
),
filled AS (
    SELECT
        g.user_id,
        g.month_start,
        COALESCE(cm.transaction_count, 0) AS transaction_count,
        COALESCE(cm.actual_spend, 0)      AS actual_spend
    FROM grid g
    LEFT JOIN customer_month cm USING (user_id, month_start)
),
budgeted AS (
    SELECT
        *,
        AVG(actual_spend) OVER w   AS budget_spend,
        COUNT(actual_spend) OVER w AS budget_months
    FROM filled
    WINDOW w AS (PARTITION BY user_id ORDER BY month_start ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING)
)
SELECT
    b.user_id,
    b.month_start,
    YEAR(b.month_start)  AS year,
    MONTH(b.month_start) AS month,
    b.transaction_count,
    b.actual_spend,
    b.budget_spend,
    b.actual_spend - b.budget_spend AS variance,
    CASE WHEN ABS(b.budget_spend) >= 1
         THEN 100.0 * (b.actual_spend - b.budget_spend) / ABS(b.budget_spend) END AS variance_pct,
    CASE WHEN b.actual_spend >= b.budget_spend THEN 'Favourable' ELSE 'Adverse' END AS variance_type,
    ABS(b.actual_spend - b.budget_spend) >= 0.10 * ABS(b.budget_spend) AS is_material  -- 10% threshold
FROM budgeted b
JOIN gold_monthly_spend m ON m.month_start = b.month_start AND m.is_complete_month
WHERE b.budget_months = 3          -- a full three-month budget history is required
ORDER BY b.user_id, b.month_start;
