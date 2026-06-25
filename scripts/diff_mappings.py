"""Diff two VERIS <-> ATT&CK enterprise mapping sets.

Compares an "old" mapping set against a "new" one and reports what changed:
  * VERIS capabilities (enums) added / removed
  * (capability -> ATT&CK technique) pairs added / removed
  * per shared capability: techniques added / removed and mappable status flips

By default it compares:
    veris-1.4.0 / attack-16.1   (old)
    veris-1.4.1 / attack-19.1   (new)

A console summary is printed and detailed CSV reports are written under
data/diffs/<old>_to_<new>/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from paths import ROOT, mapping_set_dir

# Default comparison requested for the project.
DEFAULT_OLD = ("16.1", "1.4.0")  # (attack_version, veris_version)
DEFAULT_NEW = ("19.1", "1.4.1")

DIFF_DIR = ROOT / "data" / "diffs"

# A capability is "mappable" when it points to a real ATT&CK object.
# non_mappable rows carry an empty attack_object_id.
NON_MAPPABLE = "non_mappable"


def mapping_csv_path(attack_version: str, veris_version: str) -> Path:
    """Locate the enterprise mapping CSV for a given version pair."""
    folder = mapping_set_dir(attack_version, veris_version)
    stem = f"veris-{veris_version}_attack-{attack_version}-enterprise.csv"
    return folder / stem


def load_mapping(attack_version: str, veris_version: str) -> pd.DataFrame:
    path = mapping_csv_path(attack_version, veris_version)
    if not path.exists():
        raise FileNotFoundError(f"Mapping CSV not found: {path}")

    df = pd.read_csv(path, dtype=str).fillna("")
    # Normalise the capability id so that the casing inconsistency seen in
    # VERIS 1.4.1 (e.g. "Action.Social.Variety.Baiting") does not create
    # false "added/removed" results when comparing across versions.
    df["capability_key"] = df["capability_id"].str.strip().str.lower()
    df["attack_object_id"] = df["attack_object_id"].str.strip()
    df["mapping_type"] = df["mapping_type"].str.strip()
    return df


def mappable_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that point to an actual ATT&CK object (drop non_mappable / blanks)."""
    return df[(df["attack_object_id"] != "") & (df["mapping_type"] != NON_MAPPABLE)]


def capability_label(df: pd.DataFrame) -> dict[str, str]:
    """Map normalised key -> first original capability_id seen (for display)."""
    labels: dict[str, str] = {}
    for key, original in zip(df["capability_key"], df["capability_id"]):
        labels.setdefault(key, original)
    return labels


def pair_set(df: pd.DataFrame) -> set[tuple[str, str]]:
    """Set of (capability_key, attack_object_id) for mappable rows."""
    sub = mappable_rows(df)
    return set(zip(sub["capability_key"], sub["attack_object_id"]))


def technique_names(df: pd.DataFrame) -> dict[str, str]:
    names: dict[str, str] = {}
    for tid, name in zip(df["attack_object_id"], df["attack_object_name"]):
        if tid:
            names.setdefault(tid, name)
    return names


def diff_capabilities(
    old_df: pd.DataFrame, new_df: pd.DataFrame
) -> tuple[list[str], list[str], list[str]]:
    old_keys = set(old_df["capability_key"])
    new_keys = set(new_df["capability_key"])
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    shared = sorted(old_keys & new_keys)
    return added, removed, shared


def diff_pairs(
    old_df: pd.DataFrame, new_df: pd.DataFrame
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    old_pairs = pair_set(old_df)
    new_pairs = pair_set(new_df)
    added = new_pairs - old_pairs
    removed = old_pairs - new_pairs
    return added, removed


def capability_technique_map(df: pd.DataFrame) -> dict[str, set[str]]:
    sub = mappable_rows(df)
    result: dict[str, set[str]] = {}
    for key, tid in zip(sub["capability_key"], sub["attack_object_id"]):
        result.setdefault(key, set()).add(tid)
    return result


def build_capability_change_rows(
    old_df: pd.DataFrame,
    new_df: pd.DataFrame,
    shared: list[str],
    labels: dict[str, str],
    names: dict[str, str],
) -> list[dict[str, str]]:
    old_map = capability_technique_map(old_df)
    new_map = capability_technique_map(new_df)

    rows: list[dict[str, str]] = []
    for key in shared:
        old_t = old_map.get(key, set())
        new_t = new_map.get(key, set())
        added_t = sorted(new_t - old_t)
        removed_t = sorted(old_t - new_t)

        old_mappable = bool(old_t)
        new_mappable = bool(new_t)
        status_change = ""
        if old_mappable and not new_mappable:
            status_change = "became_non_mappable"
        elif not old_mappable and new_mappable:
            status_change = "became_mappable"

        if not added_t and not removed_t and not status_change:
            continue

        rows.append(
            {
                "capability_id": labels.get(key, key),
                "status_change": status_change,
                "techniques_added": "; ".join(
                    f"{t} ({names.get(t, '')})" for t in added_t
                ),
                "techniques_removed": "; ".join(f"{t}" for t in removed_t),
                "n_added": str(len(added_t)),
                "n_removed": str(len(removed_t)),
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--old", nargs=2, metavar=("ATTACK", "VERIS"), default=DEFAULT_OLD
    )
    parser.add_argument(
        "--new", nargs=2, metavar=("ATTACK", "VERIS"), default=DEFAULT_NEW
    )
    args = parser.parse_args()

    old_attack, old_veris = args.old
    new_attack, new_veris = args.new

    old_df = load_mapping(old_attack, old_veris)
    new_df = load_mapping(new_attack, new_veris)

    labels = {**capability_label(old_df), **capability_label(new_df)}
    names = {**technique_names(old_df), **technique_names(new_df)}

    cap_added, cap_removed, shared = diff_capabilities(old_df, new_df)
    pairs_added, pairs_removed = diff_pairs(old_df, new_df)
    change_rows = build_capability_change_rows(
        old_df, new_df, shared, labels, names
    )

    out_dir = (
        DIFF_DIR
        / f"veris-{old_veris}_attack-{old_attack}"
        f"_to_veris-{new_veris}_attack-{new_attack}"
    )

    write_csv(
        [{"capability_id": labels[k]} for k in cap_added],
        out_dir / "capabilities_added.csv",
    )
    write_csv(
        [{"capability_id": labels[k]} for k in cap_removed],
        out_dir / "capabilities_removed.csv",
    )
    write_csv(
        [
            {"capability_id": labels[k], "attack_object_id": t,
             "attack_object_name": names.get(t, "")}
            for k, t in sorted(pairs_added)
        ],
        out_dir / "pairs_added.csv",
    )
    write_csv(
        [
            {"capability_id": labels[k], "attack_object_id": t,
             "attack_object_name": names.get(t, "")}
            for k, t in sorted(pairs_removed)
        ],
        out_dir / "pairs_removed.csv",
    )
    write_csv(change_rows, out_dir / "capability_changes.csv")

    print("=== Diff mappings ===")
    print(f"OLD : VERIS {old_veris} / ATT&CK {old_attack} "
          f"({len(old_df)} rows, {old_df['capability_key'].nunique()} capabilities)")
    print(f"NEW : VERIS {new_veris} / ATT&CK {new_attack} "
          f"({len(new_df)} rows, {new_df['capability_key'].nunique()} capabilities)")
    print()
    print(f"Capabilities added   : {len(cap_added)}")
    print(f"Capabilities removed : {len(cap_removed)}")
    print(f"Shared capabilities  : {len(shared)}")
    print(f"  of which changed   : {len(change_rows)}")
    print()
    print(f"Mapping pairs added   : {len(pairs_added)}")
    print(f"Mapping pairs removed : {len(pairs_removed)}")
    print()
    print(f"Detailed CSV reports written to: {out_dir.relative_to(ROOT)}")

    if cap_added:
        print("\nExamples of new capabilities:")
        for key in cap_added[:10]:
            print(f"  + {labels[key]}")


if __name__ == "__main__":
    main()
