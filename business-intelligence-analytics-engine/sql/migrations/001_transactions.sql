CREATE TABLE ledger_transactions (
  transaction_id TEXT PRIMARY KEY CHECK (length(transaction_id) BETWEEN 1 AND 64),
  booked_on TEXT NOT NULL CHECK (length(booked_on) = 10),
  amount_cents INTEGER NOT NULL CHECK (amount_cents BETWEEN 1 AND 100000000000),
  direction TEXT NOT NULL CHECK (direction IN ('income', 'expense')),
  category TEXT NOT NULL CHECK (length(category) BETWEEN 1 AND 80),
  source_id TEXT NOT NULL CHECK (length(source_id) BETWEEN 1 AND 96),
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
