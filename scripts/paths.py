"""Shared project paths for raw data and SQLite databases."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Raw data layout:
#   data/raw/attack/{version}/enterprise-attack.json
#   data/raw/veris/{version}/verisc*.json
#   data/raw/veris/enumerations/*.csv
#   data/raw/mapping/attack-{attack}_veris-{veris}/*
RAW_DIR = ROOT / "data" / "raw"
ATTACK_DIR = RAW_DIR / "attack"
VERIS_DIR = RAW_DIR / "veris"
VERIS_ENUM_DIR = VERIS_DIR / "enumerations"
MAPPING_DIR = RAW_DIR / "mapping"

DB_DIR = ROOT / "data" / "databases"
MAPPINGS_DB = DB_DIR / "veris_attack_mappings.db"
VERIS_VOCAB_DB = DB_DIR / "veris_vocabulary.db"
ATTACK_VOCAB_DB = DB_DIR / "attack_vocabulary.db"

# Enterprise mapping sets: (attack_version, veris_version, file_stem)
MAPPING_SETS = [
    ("9.0", "1.3.5", "veris-1.3.5_attack-9.0-enterprise"),
    ("12.1", "1.3.7", "veris-1.3.7_attack-12.1-enterprise"),
    ("16.1", "1.4.0", "veris-1.4.0_attack-16.1-enterprise"),
    ("19.1", "1.4.1", "veris-1.4.1_attack-19.1-enterprise"),
]

VERIS_VERSIONS = ["1.3.5", "1.3.7", "1.4.0", "1.4.1"]
ATTACK_VERSIONS = ["9.0", "12.1", "16.1", "19.1"]

VERIS_GIT_REFS = {
    "1.3.5": "1.3.5",
    "1.3.7": "1.3.6",
    "1.4.0": "v1.4.0",
    "1.4.1": "master",
}

ATTACK_GIT_TAGS = {
    "9.0": "ATT&CK-v9.0",
    "12.1": "ATT&CK-v12.1",
    "16.1": "ATT&CK-v16.1",
    "19.1": "ATT&CK-v19.1",
}


def mapping_set_dir(attack_version: str, veris_version: str) -> Path:
    return MAPPING_DIR / f"attack-{attack_version}_veris-{veris_version}"


def veris_schema_dir(veris_version: str) -> Path:
    return VERIS_DIR / veris_version


def attack_bundle_path(attack_version: str) -> Path:
    return ATTACK_DIR / attack_version / "enterprise-attack.json"


def find_mapping_json_files() -> list[Path]:
    return sorted(MAPPING_DIR.glob("attack-*_veris-*/*_json.json"))


def find_mapping_json_for_veris(veris_version: str) -> Path | None:
    matches = sorted(MAPPING_DIR.glob(f"attack-*_veris-{veris_version}/*_json.json"))
    return matches[-1] if matches else None


def find_mapping_json_for_attack(attack_version: str) -> Path | None:
    matches = sorted(MAPPING_DIR.glob(f"attack-{attack_version}_veris-*/*_json.json"))
    return matches[-1] if matches else None
