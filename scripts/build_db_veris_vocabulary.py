"""Build SQLite database #2: VERIS vocabulary used for ATT&CK mappings."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from paths import (
    ROOT,
    VERIS_ENUM_DIR,
    VERIS_GIT_REFS,
    VERIS_VERSIONS,
    VERIS_VOCAB_DB,
    find_mapping_json_for_veris,
    veris_schema_dir,
)

MAPPING_AXES = {"action", "attribute", "value_chain"}


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            veris_version TEXT NOT NULL UNIQUE,
            git_ref TEXT,
            schema_description TEXT,
            source_dir TEXT
        );

        CREATE TABLE IF NOT EXISTS capability_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_version_id INTEGER NOT NULL,
            group_key TEXT NOT NULL,
            group_label TEXT,
            FOREIGN KEY (schema_version_id) REFERENCES schema_versions (id),
            UNIQUE (schema_version_id, group_key)
        );

        CREATE TABLE IF NOT EXISTS capabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_version_id INTEGER NOT NULL,
            capability_id TEXT NOT NULL,
            capability_group TEXT,
            axis TEXT,
            category TEXT,
            subcategory TEXT,
            value TEXT,
            description TEXT,
            used_in_mapping INTEGER NOT NULL DEFAULT 0,
            attack_technique_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (schema_version_id) REFERENCES schema_versions (id),
            UNIQUE (schema_version_id, capability_id)
        );

        CREATE TABLE IF NOT EXISTS enumerations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_version_id INTEGER NOT NULL,
            axis TEXT NOT NULL,
            category TEXT,
            subcategory TEXT,
            value TEXT NOT NULL,
            description TEXT,
            capability_id TEXT,
            used_in_mapping INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (schema_version_id) REFERENCES schema_versions (id),
            UNIQUE (schema_version_id, axis, category, subcategory, value)
        );

        CREATE INDEX IF NOT EXISTS idx_capabilities_group
            ON capabilities (capability_group);
        CREATE INDEX IF NOT EXISTS idx_capabilities_mapping
            ON capabilities (used_in_mapping);
        CREATE INDEX IF NOT EXISTS idx_enumerations_axis
            ON enumerations (axis, category, subcategory);
        CREATE INDEX IF NOT EXISTS idx_enumerations_mapping
            ON enumerations (used_in_mapping);
        """
    )


def normalize_capability_id(capability_id: str) -> str:
    parts = capability_id.split(".")
    if len(parts) == 3:
        return ".".join(part.lower() for part in parts)
    if len(parts) >= 4:
        axis, category, subcategory, *value_parts = parts
        value = ".".join(value_parts)
        return f"{axis.lower()}.{category.lower()}.{subcategory.lower()}.{value}"
    return capability_id.lower()


def parse_capability_id(capability_id: str) -> tuple[str, str, str | None, str]:
    normalized = normalize_capability_id(capability_id)
    parts = normalized.split(".")
    if len(parts) >= 4:
        return parts[0], parts[1], parts[2], ".".join(parts[3:])
    if len(parts) == 3:
        return parts[0], parts[1], None, parts[2]
    raise ValueError(f"Unexpected capability_id format: {capability_id}")


def capability_id_from_parts(
    axis: str, category: str, subcategory: str | None, value: str
) -> str:
    if subcategory:
        return f"{axis.lower()}.{category.lower()}.{subcategory.lower()}.{value}"
    return f"{axis.lower()}.{category.lower()}.{value}"


def load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def walk_enumerations(
    enum_node: object,
    label_node: object,
    path: list[str],
) -> list[tuple[str, str, str, str, str | None]]:
    rows: list[tuple[str, str, str, str, str | None]] = []

    if isinstance(enum_node, list):
        axis = path[0] if path else ""
        category = path[1] if len(path) > 1 else ""
        subcategory = path[2] if len(path) > 2 else ""
        label_map = label_node if isinstance(label_node, dict) else {}
        for value in enum_node:
            if not isinstance(value, str):
                continue
            description = label_map.get(value) if isinstance(label_map, dict) else None
            rows.append((axis, category, subcategory, value, description))
        return rows

    if not isinstance(enum_node, dict):
        return rows

    for key, child_enum in enum_node.items():
        if path and path[0] not in MAPPING_AXES:
            continue
        child_label = label_node.get(key, {}) if isinstance(label_node, dict) else {}
        rows.extend(walk_enumerations(child_enum, child_label, path + [key]))

    return rows


def load_schema_version(conn: sqlite3.Connection, veris_version: str) -> int:
    version_dir = veris_schema_dir(veris_version)
    schema_path = version_dir / "verisc.json"
    if not schema_path.exists():
        raise FileNotFoundError(
            f"Missing {schema_path}. Run scripts/download_veris_schema.py first."
        )

    schema = load_json(schema_path)
    git_ref = VERIS_GIT_REFS[veris_version]

    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO schema_versions (
            id, veris_version, git_ref, schema_description, source_dir
        ) VALUES (
            (SELECT id FROM schema_versions WHERE veris_version = ?),
            ?, ?, ?, ?
        )
        """,
        (
            veris_version,
            veris_version,
            git_ref,
            schema.get("description"),
            str(version_dir.relative_to(ROOT)),
        ),
    )
    if cursor.lastrowid:
        return cursor.lastrowid
    return conn.execute(
        "SELECT id FROM schema_versions WHERE veris_version = ?",
        (veris_version,),
    ).fetchone()[0]


def load_enumerations(conn: sqlite3.Connection, schema_version_id: int, veris_version: str) -> int:
    version_dir = veris_schema_dir(veris_version)
    enum_data = load_json(version_dir / "verisc-enum.json")
    label_data = load_json(version_dir / "verisc-labels.json")

    conn.execute("DELETE FROM enumerations WHERE schema_version_id = ?", (schema_version_id,))

    rows: list[tuple] = []
    for axis in MAPPING_AXES:
        if axis not in enum_data:
            continue
        for axis_name, category, subcategory, value, description in walk_enumerations(
            enum_data[axis],
            label_data.get(axis, {}),
            [axis],
        ):
            capability_id = capability_id_from_parts(
                axis_name, category, subcategory, value
            )
            rows.append(
                (
                    schema_version_id,
                    axis_name,
                    category or None,
                    subcategory or None,
                    value,
                    description,
                    capability_id,
                    0,
                )
            )

    conn.executemany(
        """
        INSERT OR IGNORE INTO enumerations (
            schema_version_id, axis, category, subcategory, value,
            description, capability_id, used_in_mapping
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def load_capabilities_from_mappings(
    conn: sqlite3.Connection,
    schema_version_id: int,
    veris_version: str,
) -> tuple[int, set[str], dict[str, str]]:
    json_path = find_mapping_json_for_veris(veris_version)
    if json_path is None:
        return 0, set(), {}

    data = load_json(json_path)
    conn.execute("DELETE FROM capabilities WHERE schema_version_id = ?", (schema_version_id,))
    conn.execute(
        "DELETE FROM capability_groups WHERE schema_version_id = ?",
        (schema_version_id,),
    )

    capability_groups = data.get("metadata", {}).get("capability_groups", {})
    for group_key, group_label in capability_groups.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO capability_groups (
                schema_version_id, group_key, group_label
            ) VALUES (?, ?, ?)
            """,
            (schema_version_id, group_key, group_label),
        )

    seen: dict[str, tuple[str, str]] = {}
    technique_counts: dict[str, int] = {}
    for obj in data.get("mapping_objects", []):
        capability_id = normalize_capability_id(obj["capability_id"])
        technique_counts[capability_id] = technique_counts.get(capability_id, 0) + 1
        if capability_id not in seen:
            seen[capability_id] = (
                obj.get("capability_description", ""),
                obj.get("capability_group", ""),
            )

    rows = []
    for capability_id, (description, group) in seen.items():
        axis, category, subcategory, value = parse_capability_id(capability_id)
        rows.append(
            (
                schema_version_id,
                capability_id,
                group,
                axis,
                category,
                subcategory,
                value,
                description,
                1,
                technique_counts[capability_id],
            )
        )

    conn.executemany(
        """
        INSERT OR IGNORE INTO capabilities (
            schema_version_id, capability_id, capability_group, axis, category,
            subcategory, value, description, used_in_mapping, attack_technique_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows), set(seen.keys()), capability_groups


def mark_mapped_enumerations(
    conn: sqlite3.Connection,
    schema_version_id: int,
    mapped_capability_ids: set[str],
) -> None:
    if not mapped_capability_ids:
        return

    conn.execute(
        "UPDATE enumerations SET used_in_mapping = 0 WHERE schema_version_id = ?",
        (schema_version_id,),
    )
    conn.executemany(
        """
        UPDATE enumerations
        SET used_in_mapping = 1
        WHERE schema_version_id = ? AND capability_id = ?
        """,
        [(schema_version_id, capability_id) for capability_id in mapped_capability_ids],
    )


def load_ctid_enumerations(conn: sqlite3.Connection) -> int:
    """Store CTID enumeration CSV rows for cross-reference."""
    csv_path = VERIS_ENUM_DIR / "veris1_3_7-enumerations-groups.csv"
    if not csv_path.exists():
        return 0

    # Enrich descriptions on 1.3.7 when enumeration CSV has better text.
    schema_version_id = conn.execute(
        "SELECT id FROM schema_versions WHERE veris_version = '1.3.7'"
    ).fetchone()
    if schema_version_id is None:
        return 0
    schema_version_id = schema_version_id[0]

    updated = 0
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            capability_id = capability_id_from_parts(
                row["AXES"],
                row["CATEGORY"],
                row["SUB CATEGORY"],
                row["VALUE"],
            )
            description = row.get("DESCRIPTION")
            cursor = conn.execute(
                """
                UPDATE enumerations
                SET description = ?
                WHERE schema_version_id = ?
                  AND capability_id = ?
                  AND (description IS NULL OR description = '')
                """,
                (description, schema_version_id, capability_id),
            )
            updated += cursor.rowcount

            cursor = conn.execute(
                """
                UPDATE capabilities
                SET description = ?
                WHERE schema_version_id = ?
                  AND capability_id = ?
                  AND (description IS NULL OR description = '')
                """,
                (description, schema_version_id, capability_id),
            )
            updated += cursor.rowcount

    return updated


def print_summary(conn: sqlite3.Connection) -> None:
    print("\n=== Base #2 : VERIS vocabulary (mapping source data) ===")
    print(f"Database : {VERIS_VOCAB_DB}")

    for row in conn.execute(
        """
        SELECT sv.veris_version, sv.git_ref,
               (SELECT COUNT(*) FROM enumerations e WHERE e.schema_version_id = sv.id),
               (SELECT COUNT(*) FROM enumerations e
                WHERE e.schema_version_id = sv.id AND e.used_in_mapping = 1),
               (SELECT COUNT(*) FROM capabilities c WHERE c.schema_version_id = sv.id),
               (SELECT COUNT(*) FROM capability_groups g WHERE g.schema_version_id = sv.id)
        FROM schema_versions sv
        ORDER BY sv.veris_version
        """
    ):
        print(
            f"\n  VERIS {row[0]} (ref {row[1]})"
            f"\n    enumerations      : {row[2]} total, {row[3]} used in mapping"
            f"\n    capabilities      : {row[4]}"
            f"\n    capability groups : {row[5]}"
        )

    print("\n  Sample mapped capabilities (VERIS 1.4.1):")
    for row in conn.execute(
        """
        SELECT c.capability_id, c.description, c.attack_technique_count
        FROM capabilities c
        JOIN schema_versions sv ON c.schema_version_id = sv.id
        WHERE sv.veris_version = '1.4.1' AND c.used_in_mapping = 1
        ORDER BY c.attack_technique_count DESC
        LIMIT 5
        """
    ):
        desc = (row[1] or "")[:70]
        print(f"    {row[0]} -> {row[2]} techniques | {desc}...")


def main() -> None:
    VERIS_VOCAB_DB.parent.mkdir(parents=True, exist_ok=True)
    if VERIS_VOCAB_DB.exists():
        VERIS_VOCAB_DB.unlink()

    with sqlite3.connect(VERIS_VOCAB_DB) as conn:
        create_schema(conn)

        for veris_version in VERIS_VERSIONS:
            schema_version_id = load_schema_version(conn, veris_version)
            enum_count = load_enumerations(conn, schema_version_id, veris_version)
            cap_count, mapped_ids, _ = load_capabilities_from_mappings(
                conn, schema_version_id, veris_version
            )
            mark_mapped_enumerations(conn, schema_version_id, mapped_ids)
            print(
                f"VERIS {veris_version}: {enum_count} enumerations, "
                f"{cap_count} mapping capabilities"
            )

        enriched = load_ctid_enumerations(conn)
        if enriched:
            print(f"Enriched {enriched} descriptions from CTID enumeration CSV")

        conn.commit()
        print_summary(conn)


if __name__ == "__main__":
    main()
