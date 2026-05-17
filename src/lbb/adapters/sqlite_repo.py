import json
import sqlite3
from pathlib import Path

from lbb.adapters.migrations import SCHEMA_V1
from lbb.core.models import Material, Sku, SkuProfile, Template
from lbb.ports.repository import ProfileRepository


class SqliteProfileRepository(ProfileRepository):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA_V1)

    def get(self, sku: Sku) -> SkuProfile | None:
        row = self._conn.execute(
            """
            SELECT sp.sku, sp.overrides_json,
                   t.id AS tid, t.name AS tname, t.lbrn2_path, t.canvas_w_mm, t.canvas_h_mm,
                   m.id AS mid, m.name AS mname, m.clb_library, m.clb_entry, m.notes
            FROM sku_profiles sp
            JOIN templates  t ON t.id = sp.template_id
            JOIN materials  m ON m.id = sp.material_id
            WHERE sp.sku = ?
            """,
            (sku.value,),
        ).fetchone()
        if not row:
            return None
        return SkuProfile(
            sku=Sku(row["sku"]),
            template=Template(
                id=row["tid"],
                name=row["tname"],
                lbrn2_path=row["lbrn2_path"],
                canvas_w_mm=row["canvas_w_mm"],
                canvas_h_mm=row["canvas_h_mm"],
            ),
            material=Material(
                id=row["mid"],
                name=row["mname"],
                clb_library=row["clb_library"],
                clb_entry=row["clb_entry"],
                notes=row["notes"],
            ),
            overrides=json.loads(row["overrides_json"] or "{}"),
        )

    def upsert(self, profile: SkuProfile) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sku_profiles (sku, template_id, material_id, overrides_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                    template_id    = excluded.template_id,
                    material_id    = excluded.material_id,
                    overrides_json = excluded.overrides_json,
                    updated_at     = datetime('now')
                """,
                (
                    profile.sku.value,
                    profile.template.id,
                    profile.material.id,
                    json.dumps(profile.overrides),
                ),
            )

    def upsert_material(self, m: Material) -> Material:
        with self._conn:
            new_id = self._conn.execute(
                """
                INSERT INTO materials (name, clb_library, clb_entry, notes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    clb_library = excluded.clb_library,
                    clb_entry   = excluded.clb_entry,
                    notes       = excluded.notes
                RETURNING id
                """,
                (m.name, m.clb_library, m.clb_entry, m.notes),
            ).fetchone()[0]
        return Material(
            id=new_id,
            name=m.name,
            clb_library=m.clb_library,
            clb_entry=m.clb_entry,
            notes=m.notes,
        )

    def upsert_template(self, t: Template) -> Template:
        with self._conn:
            new_id = self._conn.execute(
                """
                INSERT INTO templates (name, lbrn2_path, canvas_w_mm, canvas_h_mm)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    lbrn2_path  = excluded.lbrn2_path,
                    canvas_w_mm = excluded.canvas_w_mm,
                    canvas_h_mm = excluded.canvas_h_mm
                RETURNING id
                """,
                (t.name, t.lbrn2_path, t.canvas_w_mm, t.canvas_h_mm),
            ).fetchone()[0]
        return Template(
            id=new_id,
            name=t.name,
            lbrn2_path=t.lbrn2_path,
            canvas_w_mm=t.canvas_w_mm,
            canvas_h_mm=t.canvas_h_mm,
        )

    def list_materials(self) -> list[Material]:
        return [
            Material(
                id=r["id"],
                name=r["name"],
                clb_library=r["clb_library"],
                clb_entry=r["clb_entry"],
                notes=r["notes"],
            )
            for r in self._conn.execute("SELECT * FROM materials ORDER BY name")
        ]

    def list_templates(self) -> list[Template]:
        return [
            Template(
                id=r["id"],
                name=r["name"],
                lbrn2_path=r["lbrn2_path"],
                canvas_w_mm=r["canvas_w_mm"],
                canvas_h_mm=r["canvas_h_mm"],
            )
            for r in self._conn.execute("SELECT * FROM templates ORDER BY name")
        ]
