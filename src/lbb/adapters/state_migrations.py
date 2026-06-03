STATE_SCHEMA_V1 = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS engraved_sides (
  order_number TEXT NOT NULL,
  item_id      TEXT NOT NULL,
  side_name    TEXT NOT NULL,
  engraved_at  TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (order_number, item_id, side_name)
);

CREATE TABLE IF NOT EXISTS order_overrides (
  order_number TEXT PRIMARY KEY,
  status       TEXT NOT NULL,
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_comments (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  order_number TEXT NOT NULL,
  text         TEXT NOT NULL,
  author       TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
