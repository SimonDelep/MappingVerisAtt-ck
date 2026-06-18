"""Build SQLite database #1: VERIS <-> ATT&CK enterprise mapping versions."""

from __future__ import annotations

import json
import sqlite3

from paths import MAPPING_DIR, MAPPINGS_DB, ROOT, find_mapping_json_files


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS mapping_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mapping_framework TEXT,
            mapping_framework_version TEXT NOT NULL,
            attack_version TEXT NOT NULL,
            technology_domain TEXT NOT NULL,
            creation_date TEXT,
            last_update TEXT,
            source_file TEXT,
            mapping_count INTEGER,
            UNIQUE (mapping_framework_version, attack_version, technology_domain)
        );

        CREATE TABLE IF NOT EXISTS mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mapping_set_id INTEGER NOT NULL,
            capability_id TEXT NOT NULL,
            capability_description TEXT,
            capability_group TEXT,
            mapping_type TEXT,
            attack_object_id TEXT NOT NULL,
            attack_object_name TEXT,
            status TEXT,
            FOREIGN KEY (mapping_set_id) REFERENCES mapping_sets (id),
            UNIQUE (
                mapping_set_id, capability_id, attack_object_id, mapping_type
            )
        );

        CREATE INDEX IF NOT EXISTS idx_mappings_set_id
            ON mappings (mapping_set_id);
        CREATE INDEX IF NOT EXISTS idx_mappings_capability_id
            ON mappings (capability_id);
        CREATE INDEX IF NOT EXISTS idx_mappings_attack_object_id
            ON mappings (attack_object_id);
        CREATE INDEX IF NOT EXISTS idx_mapping_sets_versions
            ON mapping_sets (
                mapping_framework_version, attack_version, technology_domain
            );
        """
    )


def find_json_files() -> list:
    return find_mapping_json_files()


def load_mapping_set(conn: sqlite3.Connection, json_path: Path) -> int:
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    veris_version = meta.get("mapping_framework_version")
    attack_version = meta.get("attack_version")
    domain = meta.get("technology_domain")

    conn.execute(
        """
        DELETE FROM mappings
        WHERE mapping_set_id IN (
            SELECT id FROM mapping_sets
            WHERE mapping_framework_version = ?
              AND attack_version = ?
              AND technology_domain = ?
        )
        """,
        (veris_version, attack_version, domain),
    )
    conn.execute(
        """
        DELETE FROM mapping_sets
        WHERE mapping_framework_version = ?
          AND attack_version = ?
          AND technology_domain = ?
        """,
        (veris_version, attack_version, domain),
    )

    cursor = conn.execute(
        """
        INSERT INTO mapping_sets (
            mapping_framework, mapping_framework_version, attack_version,
            technology_domain, creation_date, last_update, source_file
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meta.get("mapping_framework"),
            veris_version,
            attack_version,
            domain,
            meta.get("creation_date"),
            meta.get("last_update"),
            str(json_path.relative_to(ROOT)),
        ),
    )
    mapping_set_id = cursor.lastrowid

    rows = [
        (
            mapping_set_id,
            obj["capability_id"],
            obj.get("capability_description"),
            obj.get("capability_group"),
            obj.get("mapping_type"),
            obj["attack_object_id"],
            obj.get("attack_object_name"),
            obj.get("status"),
        )
        for obj in data["mapping_objects"]
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO mappings (
            mapping_set_id, capability_id, capability_description,
            capability_group, mapping_type, attack_object_id,
            attack_object_name, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.execute(
        "UPDATE mapping_sets SET mapping_count = ? WHERE id = ?",
        (len(rows), mapping_set_id),
    )
    return len(rows)


def print_summary(conn: sqlite3.Connection) -> None:
    total_sets = conn.execute("SELECT COUNT(*) FROM mapping_sets").fetchone()[0]
    total_mappings = conn.execute("SELECT COUNT(*) FROM mappings").fetchone()[0]

    print("\n=== Base #1 : VERIS <-> ATT&CK mappings (enterprise) ===")
    print(f"Database : {MAPPINGS_DB}")
    print(f"Mapping sets : {total_sets}")
    print(f"Total mappings : {total_mappings}")
    print("\nPar version :")
    for row in conn.execute(
        """
        SELECT mapping_framework_version, attack_version, technology_domain,
               mapping_count, last_update
        FROM mapping_sets
        ORDER BY mapping_framework_version, attack_version, technology_domain
        """
    ):
        print(
            f"  VERIS {row[0]} | ATT&CK {row[1]} | {row[2]:10} "
            f"-> {row[3]:4} mappings (updated {row[4]})"
        )


def main() -> None:
    json_files = find_json_files()
    if not json_files:
        raise FileNotFoundError(
            f"No *_json.json files in {MAPPING_DIR}. "
            "Run scripts/download_veris_mappings.py first."
        )

    MAPPINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    if MAPPINGS_DB.exists():
        MAPPINGS_DB.unlink()

    with sqlite3.connect(MAPPINGS_DB) as conn:
        create_schema(conn)
        for json_path in json_files:
            count = load_mapping_set(conn, json_path)
            rel = json_path.relative_to(MAPPING_DIR)
            print(f"Loaded {count:4} mappings from {rel}")
        conn.commit()
        print_summary(conn)


if __name__ == "__main__":
    main()
