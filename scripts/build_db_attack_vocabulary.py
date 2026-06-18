"""Build SQLite database #3: ATT&CK data used for VERIS mappings."""

from __future__ import annotations

import json
import sqlite3

from paths import (
    ATTACK_GIT_TAGS,
    ATTACK_VOCAB_DB,
    ATTACK_VERSIONS,
    ROOT,
    attack_bundle_path,
    find_mapping_json_for_attack,
)


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS attack_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            git_tag TEXT,
            domain TEXT NOT NULL DEFAULT 'enterprise',
            source_file TEXT
        );

        CREATE TABLE IF NOT EXISTS tactics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attack_version_id INTEGER NOT NULL,
            stix_id TEXT NOT NULL,
            external_id TEXT,
            name TEXT NOT NULL,
            shortname TEXT,
            description TEXT,
            FOREIGN KEY (attack_version_id) REFERENCES attack_versions (id),
            UNIQUE (attack_version_id, stix_id)
        );

        CREATE TABLE IF NOT EXISTS techniques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attack_version_id INTEGER NOT NULL,
            stix_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_subtechnique INTEGER NOT NULL DEFAULT 0,
            deprecated INTEGER NOT NULL DEFAULT 0,
            platforms TEXT,
            tactic_shortnames TEXT,
            used_in_mapping INTEGER NOT NULL DEFAULT 0,
            veris_mapping_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (attack_version_id) REFERENCES attack_versions (id),
            UNIQUE (attack_version_id, external_id)
        );

        CREATE TABLE IF NOT EXISTS mitigations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attack_version_id INTEGER NOT NULL,
            stix_id TEXT NOT NULL,
            external_id TEXT,
            name TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (attack_version_id) REFERENCES attack_versions (id),
            UNIQUE (attack_version_id, stix_id)
        );

        CREATE TABLE IF NOT EXISTS technique_mitigations (
            technique_id INTEGER NOT NULL,
            mitigation_id INTEGER NOT NULL,
            PRIMARY KEY (technique_id, mitigation_id),
            FOREIGN KEY (technique_id) REFERENCES techniques (id),
            FOREIGN KEY (mitigation_id) REFERENCES mitigations (id)
        );

        CREATE INDEX IF NOT EXISTS idx_techniques_external_id
            ON techniques (external_id);
        CREATE INDEX IF NOT EXISTS idx_techniques_mapping
            ON techniques (used_in_mapping);
        CREATE INDEX IF NOT EXISTS idx_tactics_shortname
            ON tactics (shortname);
        """
    )


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def mitre_external_id(obj: dict) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def load_mapped_techniques(attack_version: str) -> dict[str, int]:
    json_path = find_mapping_json_for_attack(attack_version)
    if json_path is None:
        return {}

    data = load_json(json_path)
    counts: dict[str, int] = {}
    for obj in data.get("mapping_objects", []):
        technique_id = obj.get("attack_object_id")
        if technique_id:
            counts[technique_id] = counts.get(technique_id, 0) + 1
    return counts


def load_attack_version(conn: sqlite3.Connection, version: str) -> int:
    bundle_path = attack_bundle_path(version)
    if not bundle_path.exists():
        raise FileNotFoundError(
            f"Missing {bundle_path}. Run scripts/download_attack_data.py first."
        )

    cursor = conn.execute(
        """
        INSERT OR REPLACE INTO attack_versions (
            id, version, git_tag, domain, source_file
        ) VALUES (
            (SELECT id FROM attack_versions WHERE version = ?),
            ?, ?, 'enterprise', ?
        )
        """,
        (
            version,
            version,
            ATTACK_GIT_TAGS[version],
            str(bundle_path.relative_to(ROOT)),
        ),
    )
    if cursor.lastrowid:
        version_id = cursor.lastrowid
    else:
        version_id = conn.execute(
            "SELECT id FROM attack_versions WHERE version = ?", (version,)
        ).fetchone()[0]

    conn.execute("DELETE FROM technique_mitigations WHERE technique_id IN (SELECT id FROM techniques WHERE attack_version_id = ?)", (version_id,))
    conn.execute("DELETE FROM techniques WHERE attack_version_id = ?", (version_id,))
    conn.execute("DELETE FROM mitigations WHERE attack_version_id = ?", (version_id,))
    conn.execute("DELETE FROM tactics WHERE attack_version_id = ?", (version_id,))

    bundle = load_json(bundle_path)
    objects = bundle.get("objects", [])
    by_stix_id = {obj["id"]: obj for obj in objects if "id" in obj}

    tactic_id_by_stix: dict[str, int] = {}
    for obj in objects:
        if obj.get("type") != "x-mitre-tactic":
            continue
        cursor = conn.execute(
            """
            INSERT INTO tactics (
                attack_version_id, stix_id, external_id, name, shortname, description
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                obj["id"],
                mitre_external_id(obj),
                obj.get("name", ""),
                obj.get("x_mitre_shortname"),
                obj.get("description"),
            ),
        )
        tactic_id_by_stix[obj["id"]] = cursor.lastrowid

    mitigation_id_by_stix: dict[str, int] = {}
    for obj in objects:
        if obj.get("type") != "course-of-action":
            continue
        cursor = conn.execute(
            """
            INSERT INTO mitigations (
                attack_version_id, stix_id, external_id, name, description
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                version_id,
                obj["id"],
                mitre_external_id(obj),
                obj.get("name", ""),
                obj.get("description"),
            ),
        )
        mitigation_id_by_stix[obj["id"]] = cursor.lastrowid

    technique_id_by_stix: dict[str, int] = {}
    mapped_counts = load_mapped_techniques(version)

    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue

        external_id = mitre_external_id(obj)
        if not external_id:
            continue

        phases = obj.get("kill_chain_phases", [])
        tactic_shortnames = sorted(
            {
                phase.get("phase_name")
                for phase in phases
                if phase.get("kill_chain_name") == "mitre-attack" and phase.get("phase_name")
            }
        )
        platforms = obj.get("x_mitre_platforms", [])

        cursor = conn.execute(
            """
            INSERT INTO techniques (
                attack_version_id, stix_id, external_id, name, description,
                is_subtechnique, deprecated, platforms, tactic_shortnames,
                used_in_mapping, veris_mapping_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                obj["id"],
                external_id,
                obj.get("name", ""),
                obj.get("description"),
                int(bool(obj.get("x_mitre_is_subtechnique", False))),
                int(bool(obj.get("x_mitre_deprecated", False))),
                json.dumps(platforms),
                json.dumps(tactic_shortnames),
                int(external_id in mapped_counts),
                mapped_counts.get(external_id, 0),
            ),
        )
        technique_id_by_stix[obj["id"]] = cursor.lastrowid

    mitigation_links = 0
    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        if obj.get("relationship_type") != "mitigates":
            continue

        source = obj.get("source_ref")
        target = obj.get("target_ref")
        mitigation_id = mitigation_id_by_stix.get(source)
        technique_id = technique_id_by_stix.get(target)
        if mitigation_id and technique_id:
            conn.execute(
                """
                INSERT OR IGNORE INTO technique_mitigations (technique_id, mitigation_id)
                VALUES (?, ?)
                """,
                (technique_id, mitigation_id),
            )
            mitigation_links += 1

    loaded_external_ids = {
        mitre_external_id(by_stix_id[stix_id])
        for stix_id in technique_id_by_stix
    }
    loaded_external_ids.discard(None)

    return {
        "tactics": len(tactic_id_by_stix),
        "techniques": len(technique_id_by_stix),
        "mitigations": len(mitigation_id_by_stix),
        "mitigation_links": mitigation_links,
        "mapped_techniques": len(loaded_external_ids & set(mapped_counts)),
    }


def print_summary(conn: sqlite3.Connection) -> None:
    print("\n=== Base #3 : ATT&CK vocabulary (mapping source data) ===")
    print(f"Database : {ATTACK_VOCAB_DB}")

    for row in conn.execute(
        """
        SELECT av.version,
               (SELECT COUNT(*) FROM tactics t WHERE t.attack_version_id = av.id),
               (SELECT COUNT(*) FROM techniques te WHERE te.attack_version_id = av.id),
               (SELECT COUNT(*) FROM techniques te
                WHERE te.attack_version_id = av.id AND te.used_in_mapping = 1),
               (SELECT COUNT(*) FROM mitigations m WHERE m.attack_version_id = av.id)
        FROM attack_versions av
        ORDER BY av.version
        """
    ):
        print(
            f"\n  ATT&CK {row[0]}"
            f"\n    tactics           : {row[1]}"
            f"\n    techniques        : {row[2]} total, {row[3]} used in mapping"
            f"\n    mitigations       : {row[4]}"
        )

    print("\n  Top mapped techniques (ATT&CK 19.1):")
    for row in conn.execute(
        """
        SELECT te.external_id, te.name, te.veris_mapping_count
        FROM techniques te
        JOIN attack_versions av ON te.attack_version_id = av.id
        WHERE av.version = '19.1' AND te.used_in_mapping = 1
        ORDER BY te.veris_mapping_count DESC
        LIMIT 5
        """
    ):
        print(f"    {row[0]} ({row[1]}) -> {row[2]} VERIS mappings")


def main() -> None:
    ATTACK_VOCAB_DB.parent.mkdir(parents=True, exist_ok=True)
    if ATTACK_VOCAB_DB.exists():
        ATTACK_VOCAB_DB.unlink()

    with sqlite3.connect(ATTACK_VOCAB_DB) as conn:
        create_schema(conn)

        for version in ATTACK_VERSIONS:
            stats = load_attack_version(conn, version)
            print(
                f"ATT&CK {version}: {stats['techniques']} techniques, "
                f"{stats['mapped_techniques']} in mappings, "
                f"{stats['mitigations']} mitigations"
            )

        conn.commit()
        print_summary(conn)


if __name__ == "__main__":
    main()
