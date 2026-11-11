-- gold_customer_profile: one row per customer who has at least one transaction.
-- Feeds RFM segmentation, the customer KPIs and the Power BI customer table.
-- Every measure is aggregated straight from transactions (one row each), so
-- nothing is double-counted. The original segmentation query joined monthly
-- rows and repeated totals once per active month.
WITH ref AS (
    SELECT CAST(MAX(transaction_date) AS DATE) + 1 AS reference_date FROM silver_transactions
),
txn AS (
    SELECT
        user_id,
        MIN(transaction_date)                                   AS first_transaction,
        MAX(transaction_date)                                   AS last_transaction,
        COUNT(*)                                                AS transaction_count,
        COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0)      AS gross_spend,
        COALESCE(-SUM(amount) FILTER (WHERE amount < 0), 0)     AS refunds,
        SUM(amount)                                             AS net_spend,
        AVG(amount) FILTER (WHERE amount > 0)                   AS avg_purchase_value,
        COUNT(DISTINCT date_trunc('month', transaction_date))   AS active_months,
        COUNT(DISTINCT mcc_code)                                AS distinct_categories,
        COUNT(DISTINCT merchant_id)                             AS distinct_merchants,
        AVG(CAST(is_online AS INTEGER))                         AS online_share,
        AVG(CAST(has_error AS INTEGER))                         AS error_share
    FROM silver_transactions
    GROUP BY 1
),
top_category AS (
    SELECT user_id, arg_max(mcc_code, n) AS top_mcc_code
    FROM (SELECT user_id, mcc_code, COUNT(*) AS n FROM silver_transactions GROUP BY 1, 2)
    GROUP BY 1
),
fraud AS (
    SELECT
        t.user_id,
        COUNT(f.transaction_id)                       AS labelled_transactions,
        COUNT(*) FILTER (WHERE f.is_fraud)            AS fraud_transactions
    FROM silver_transactions t
    JOIN silver_fraud_labels f USING (transaction_id)
    GROUP BY 1
),
cards AS (
    SELECT
        user_id,
        COUNT(*)                                       AS cards_held,
        SUM(credit_limit)                              AS total_credit_limit,
        COUNT(*) FILTER (WHERE card_type = 'Credit')   AS credit_cards,
        BOOL_OR(card_on_dark_web)                      AS any_card_on_dark_web
    FROM silver_cards
    GROUP BY 1
)
SELECT
    t.user_id,
    u.current_age,
    u.gender,
    u.yearly_income,
    u.total_debt,
    u.credit_score,
    c.cards_held,
    c.credit_cards,
    c.total_credit_limit,
    c.any_card_on_dark_web,
    t.first_transaction,
    t.last_transaction,
    DATE_DIFF('day', CAST(t.last_transaction AS DATE), r.reference_date)          AS recency_days,
    DATE_DIFF('month', t.first_transaction, t.last_transaction) + 1               AS tenure_months,
    t.active_months,
    t.transaction_count,
    t.transaction_count / (DATE_DIFF('month', t.first_transaction, t.last_transaction) + 1.0)
                                                                                 AS transactions_per_month,
    t.gross_spend,
    t.refunds,
    t.net_spend,
    t.net_spend / (DATE_DIFF('month', t.first_transaction, t.last_transaction) + 1.0)
                                                                                 AS avg_monthly_net_spend,
    t.avg_purchase_value,
    t.distinct_categories,
    t.distinct_merchants,
    tc.top_mcc_code,
    m.category_description                                                        AS top_category,
    t.online_share,
    t.error_share,
    COALESCE(fr.labelled_transactions, 0)                                         AS labelled_transactions,
    COALESCE(fr.fraud_transactions, 0)                                            AS fraud_transactions,
    COALESCE(fr.fraud_transactions, 0) / NULLIF(fr.labelled_transactions, 0)      AS fraud_rate,
    r.reference_date
FROM txn t
CROSS JOIN ref r
LEFT JOIN silver_users u    USING (user_id)
LEFT JOIN cards c           USING (user_id)
LEFT JOIN top_category tc   USING (user_id)
LEFT JOIN silver_mcc_codes m ON m.mcc_code = tc.top_mcc_code
LEFT JOIN fraud fr          USING (user_id)
ORDER BY t.user_id;
