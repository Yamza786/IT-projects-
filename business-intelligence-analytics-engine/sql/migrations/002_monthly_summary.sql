CREATE VIEW monthly_category_summary AS
SELECT
  substr(booked_on, 1, 7) AS month,
  category,
  direction,
  COUNT(*) AS transaction_count,
  SUM(amount_cents) AS amount_cents
FROM ledger_transactions
GROUP BY substr(booked_on, 1, 7), category, direction;
