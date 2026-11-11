-- gold_category_monthly: spend and fraud by merchant category (MCC) and month.
-- Fraud figures cover labelled transactions only: train_fraud_labels.json
-- labels a subset of transactions, so fraud_rate = fraud / labelled, never fraud / all.
SELECT
    CAST(date_trunc('month', t.transaction_date) AS DATE)  AS month_start,
    t.mcc_code,
    COALESCE(m.category_description, 'Unknown MCC')        AS category,
    COUNT(*)                                               AS transaction_count,
    COUNT(DISTINCT t.user_id)                              AS customers,
    COALESCE(SUM(t.amount) FILTER (WHERE t.amount > 0), 0) AS gross_spend,
    SUM(t.amount)                                          AS net_spend,
    COUNT(f.transaction_id)                                AS labelled_transactions,
    COUNT(*) FILTER (WHERE f.is_fraud)                     AS fraud_transactions,
    COUNT(*) FILTER (WHERE f.is_fraud) / NULLIF(COUNT(f.transaction_id), 0) AS fraud_rate
FROM silver_transactions t
LEFT JOIN silver_mcc_codes m USING (mcc_code)
LEFT JOIN silver_fraud_labels f USING (transaction_id)
GROUP BY 1, 2, 3
ORDER BY 1, 2;
