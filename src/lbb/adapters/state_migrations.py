STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS engraved_keys (
  order_number TEXT NOT NULL,
  file_key     TEXT NOT NULL,
  engraved_at  TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (order_number, file_key)
);
"""
