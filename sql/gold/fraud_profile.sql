-- gold_fraud_profile: fraud rate by transaction attribute (long format: one row per dimension value).
-- Covers labelled transactions only (inner join to fraud labels).
WITH labelled AS (
    SELECT
        t.*,
        f.is_fraud,
        c.card_type,
        c.card_brand,
        c.has_chip AS card_has_chip
    FROM silver_transactions t
    JOIN silver_fraud_labels f USING (transaction_id)
    LEFT JOIN silver_cards c USING (card_id)
),
long AS (
    SELECT 'Entry method' AS dimension, CAST(use_chip AS VARCHAR) AS dimension_value, is_fraud, amount FROM labelled
    UNION ALL SELECT 'Channel', CASE WHEN is_online THEN 'Online' ELSE 'In person' END, is_fraud, amount FROM labelled
    UNION ALL SELECT 'Error flagged', CASE WHEN has_error THEN 'Error' ELSE 'No error' END, is_fraud, amount FROM labelled
    UNION ALL SELECT 'Card type', card_type, is_fraud, amount FROM labelled
    UNION ALL SELECT 'Card brand', card_brand, is_fraud, amount FROM labelled
    UNION ALL SELECT 'Transaction type', CASE WHEN amount < 0 THEN 'Refund' ELSE 'Purchase' END, is_fraud, amount FROM labelled
    UNION ALL SELECT 'Hour of day', LPAD(CAST(HOUR(transaction_date) AS VARCHAR), 2, '0'), is_fraud, amount FROM labelled
)
SELECT
    dimension,
    dimension_value,
    COUNT(*)                                        AS labelled_transactions,
    COUNT(*) FILTER (WHERE is_fraud)                AS fraud_transactions,
    COUNT(*) FILTER (WHERE is_fraud) / COUNT(*)     AS fraud_rate,
    SUM(amount) FILTER (WHERE is_fraud)             AS fraud_value
FROM long
GROUP BY 1, 2
ORDER BY 1, 2;
