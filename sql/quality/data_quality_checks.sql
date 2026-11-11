-- Silver-layer data quality checks (stage 3).
-- severity = 'control': should be 0. A non-zero count means a rule or a key is broken.
-- severity = 'profile': describes the data; any count is acceptable but must be understood.
WITH checks AS (
    -- Primary-key uniqueness
    SELECT 'PK01' AS check_id, 'control' AS severity, 'users' AS table_name, 'duplicate user_id' AS check_name,
           COUNT(*) - COUNT(DISTINCT user_id) AS flagged_rows, COUNT(*) AS total_rows FROM silver_users
    UNION ALL
    SELECT 'PK02', 'control', 'cards', 'duplicate card_id',
           COUNT(*) - COUNT(DISTINCT card_id), COUNT(*) FROM silver_cards
    UNION ALL
    SELECT 'PK03', 'control', 'mcc_codes', 'duplicate mcc_code',
           COUNT(*) - COUNT(DISTINCT mcc_code), COUNT(*) FROM silver_mcc_codes
    UNION ALL
    SELECT 'PK04', 'control', 'transactions', 'duplicate transaction_id',
           COUNT(*) - COUNT(DISTINCT transaction_id), COUNT(*) FROM silver_transactions
    UNION ALL
    SELECT 'PK05', 'control', 'fraud_labels', 'duplicate transaction_id',
           COUNT(*) - COUNT(DISTINCT transaction_id), COUNT(*) FROM silver_fraud_labels

    -- Referential integrity
    UNION ALL
    SELECT 'RI01', 'control', 'cards', 'card user_id not in users',
           COUNT(*) FILTER (WHERE u.user_id IS NULL), COUNT(*)
    FROM silver_cards c LEFT JOIN silver_users u USING (user_id)
    UNION ALL
    SELECT 'RI02', 'control', 'transactions', 'user_id not in users',
           COUNT(*) FILTER (WHERE u.user_id IS NULL), COUNT(*)
    FROM silver_transactions t LEFT JOIN silver_users u USING (user_id)
    UNION ALL
    SELECT 'RI03', 'control', 'transactions', 'card_id not in cards',
           COUNT(*) FILTER (WHERE c.card_id IS NULL), COUNT(*)
    FROM silver_transactions t LEFT JOIN silver_cards c USING (card_id)
    UNION ALL
    SELECT 'RI04', 'control', 'transactions', 'card belongs to a different user',
           COUNT(*) FILTER (WHERE c.user_id <> t.user_id), COUNT(*)
    FROM silver_transactions t JOIN silver_cards c USING (card_id)
    UNION ALL
    SELECT 'RI05', 'control', 'transactions', 'mcc_code not in mcc_codes',
           COUNT(*) FILTER (WHERE m.mcc_code IS NULL), COUNT(*)
    FROM silver_transactions t LEFT JOIN silver_mcc_codes m USING (mcc_code)
    UNION ALL
    SELECT 'RI06', 'control', 'fraud_labels', 'label has no matching transaction',
           COUNT(*) FILTER (WHERE t.transaction_id IS NULL), COUNT(*)
    FROM silver_fraud_labels f LEFT JOIN silver_transactions t USING (transaction_id)

    -- Parsing completeness (a null here means a bronze value failed to parse)
    UNION ALL
    SELECT 'NP01', 'control', 'transactions', 'amount failed to parse',
           COUNT(*) FILTER (WHERE amount IS NULL), COUNT(*) FROM silver_transactions
    UNION ALL
    SELECT 'NP02', 'control', 'transactions', 'transaction_date failed to parse',
           COUNT(*) FILTER (WHERE transaction_date IS NULL), COUNT(*) FROM silver_transactions
    UNION ALL
    SELECT 'NP03', 'control', 'cards', 'acct_open_date or expires failed to parse',
           COUNT(*) FILTER (WHERE acct_open_date IS NULL OR expires IS NULL), COUNT(*) FROM silver_cards
    UNION ALL
    SELECT 'NP04', 'control', 'users', 'income or debt failed to parse',
           COUNT(*) FILTER (WHERE yearly_income IS NULL OR per_capita_income IS NULL OR total_debt IS NULL),
           COUNT(*) FROM silver_users
    UNION ALL
    SELECT 'NP05', 'control', 'fraud_labels', 'label not Yes/No',
           COUNT(*) FILTER (WHERE is_fraud IS NULL), COUNT(*) FROM silver_fraud_labels

    -- Profiling (informational)
    UNION ALL
    SELECT 'PR01', 'profile', 'transactions', 'refunds / reversals (amount < 0)',
           COUNT(*) FILTER (WHERE is_refund), COUNT(*) FROM silver_transactions
    UNION ALL
    SELECT 'PR02', 'profile', 'transactions', 'zero-value transactions',
           COUNT(*) FILTER (WHERE amount = 0), COUNT(*) FROM silver_transactions
    UNION ALL
    SELECT 'PR03', 'profile', 'transactions', 'transactions with an error code',
           COUNT(*) FILTER (WHERE has_error), COUNT(*) FROM silver_transactions
    UNION ALL
    SELECT 'PR04', 'profile', 'transactions', 'online transactions (no merchant state)',
           COUNT(*) FILTER (WHERE is_online), COUNT(*) FROM silver_transactions
    UNION ALL
    SELECT 'PR05', 'profile', 'transactions', 'transactions without a fraud label',
           COUNT(*) FILTER (WHERE f.transaction_id IS NULL), COUNT(*)
    FROM silver_transactions t LEFT JOIN silver_fraud_labels f USING (transaction_id)
    UNION ALL
    SELECT 'PR06', 'profile', 'fraud_labels', 'labelled fraud (is_fraud = true)',
           COUNT(*) FILTER (WHERE is_fraud), COUNT(*) FROM silver_fraud_labels
)
SELECT
    check_id,
    severity,
    table_name,
    check_name,
    flagged_rows,
    total_rows,
    ROUND(100.0 * flagged_rows / NULLIF(total_rows, 0), 3) AS flagged_pct,
    CASE
        WHEN severity = 'profile' THEN 'INFO'
        WHEN flagged_rows = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM checks
ORDER BY check_id;
