SCHEMA_V1 = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS materials (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT UNIQUE NOT NULL,
  clb_library  TEXT NOT NULL,
  clb_entry    TEXT NOT NULL,
  notes        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS templates (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT UNIQUE NOT NULL,
  lbrn2_path   TEXT NOT NULL,
  canvas_w_mm  REAL NOT NULL,
  canvas_h_mm  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sku_profiles (
  sku             TEXT PRIMARY KEY,
  template_id     INTEGER NOT NULL REFERENCES templates(id),
  material_id     INTEGER NOT NULL REFERENCES materials(id),
  overrides_json  TEXT NOT NULL DEFAULT '{}',
  updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_by      TEXT NOT NULL DEFAULT 'system'
);
"""
