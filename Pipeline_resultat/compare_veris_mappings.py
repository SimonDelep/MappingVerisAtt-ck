#!/usr/bin/env python3
"""
Compare deux fichiers JSON de mapping VERIS -> ATT&CK.

Formats supportes (auto-detectes) :
  - CTID / Mappings Explorer : cle "mapping_objects"
  - Mapping genere localement : cle "veris_to_mitre"

Usage:
  python compare_veris_mappings.py reference.json comparison.json
  python compare_veris_mappings.py xxx.json yyy.json --scope action.hacking -o rapport.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

MappingFormat = Literal["ctid", "veris_to_mitre"]

SCOPE_PREFIXES = {
    "action.hacking": ("hacking.",),
    "action.malware": ("malware.",),
    "action.social": ("social.",),
    "attribute.integrity": ("integrity.",),
    "attribute.confidentiality": ("confidentiality.",),
    "attribute.availability": ("availability.",),
    "value_chain.development": ("development.",),
}

TOP_LEVEL_PREFIXES = {"action", "attribute", "value_chain", "value-chain"}


# Represente une liaison VERIS <-> technique ATT&CK.
@dataclass(frozen=True)
class MappingPair:
    veris_id: str
    attack_id: str


# Contient tous les resultats de la comparaison entre deux mappings.
@dataclass
class ComparisonResult:
    scope: str
    mapping_a_label: str
    mapping_b_label: str
    mapping_a_pairs: set[MappingPair] = field(default_factory=set)
    mapping_b_pairs: set[MappingPair] = field(default_factory=set)
    intersection: set[MappingPair] = field(default_factory=set)
    only_in_a: set[MappingPair] = field(default_factory=set)
    only_in_b: set[MappingPair] = field(default_factory=set)
    veris_ids_a: set[str] = field(default_factory=set)
    veris_ids_b: set[str] = field(default_factory=set)
    veris_only_in_a: set[str] = field(default_factory=set)
    veris_only_in_b: set[str] = field(default_factory=set)
    veris_common: set[str] = field(default_factory=set)
    per_veris: dict[str, dict[str, Any]] = field(default_factory=dict)
    capability_metrics: dict[str, Any] = field(default_factory=dict)

    # Calcule la part des paires de B qui existent aussi dans A.
    @property
    def precision(self) -> float:
        if not self.mapping_b_pairs:
            return 0.0
        return len(self.intersection) / len(self.mapping_b_pairs)

    # Calcule la part des paires de A retrouvees dans B.
    @property
    def recall(self) -> float:
        if not self.mapping_a_pairs:
            return 0.0
        return len(self.intersection) / len(self.mapping_a_pairs)

    # Calcule la moyenne harmonique entre precision et rappel.
    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    # Mesure la similarite entre les deux ensembles de paires (intersection / union).
    @property
    def jaccard(self) -> float:
        union = self.mapping_a_pairs | self.mapping_b_pairs
        if not union:
            return 0.0
        return len(self.intersection) / len(union)


# Nettoie un libelle VERIS (minuscules, espaces et tirets -> underscores).
def normalize_label(label: str) -> str:
    label = label.strip().lower().replace("-", "_")
    label = re.sub(r"\s+", "_", label)
    label = re.sub(r"_+", "_", label)
    return label.strip("_")


# Convertit un ID VERIS brut vers un format commun comparable.
def normalize_veris_id(raw_id: str) -> str:
    parts = [p.strip() for p in raw_id.split(".") if p.strip()]
    lowered = [p.lower().replace("-", "_") for p in parts]

    if lowered and lowered[0] in TOP_LEVEL_PREFIXES:
        lowered = lowered[1:]

    if not lowered:
        return ""

    if len(lowered) >= 3:
        category, kind, *label_parts = lowered
        label = normalize_label(" ".join(label_parts).replace("_", " "))
        return f"{category}.{kind}.{label}"

    if len(lowered) == 2:
        return f"{lowered[0]}.{normalize_label(lowered[1].replace('_', ' '))}"

    return normalize_label(lowered[0])


# Normalise un ID ATT&CK (majuscules, ignore les valeurs invalides).
def normalize_attack_id(raw_id: str | None) -> str | None:
    if not raw_id:
        return None
    raw_id = raw_id.strip().upper()
    if not raw_id.startswith("T"):
        return None
    return raw_id


# Charge et parse un fichier JSON local.
def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


# Detecte si le JSON est au format CTID ou au format veris_to_mitre.
def detect_mapping_format(data: dict[str, Any]) -> MappingFormat:
    if "mapping_objects" in data:
        return "ctid"
    if "veris_to_mitre" in data:
        return "veris_to_mitre"
    raise ValueError(
        "Format JSON non reconnu. Attendu : 'mapping_objects' (CTID) ou 'veris_to_mitre' (local)."
    )


# Verifie qu'un veris_id appartient au scope demande (ex: hacking.*).
def veris_id_matches_scope(veris_id: str, scope: str | None) -> bool:
    if not scope:
        return True
    prefixes = SCOPE_PREFIXES.get(scope.lower())
    if prefixes:
        return veris_id.startswith(prefixes)
    return True


# Extrait les paires VERIS-ATT&CK depuis un JSON au format CTID.
def extract_ctid_pairs(
    data: dict[str, Any],
    scope: str | None,
) -> tuple[set[MappingPair], set[str]]:
    pairs: set[MappingPair] = set()
    veris_ids: set[str] = set()
    scope_norm = scope.lower() if scope else None

    for obj in data.get("mapping_objects", []):
        group = (obj.get("capability_group") or "").lower()
        if scope_norm and group != scope_norm:
            continue

        veris_id = normalize_veris_id(obj.get("capability_id", ""))
        attack_id = normalize_attack_id(obj.get("attack_object_id"))
        if not veris_id or not attack_id:
            continue

        pairs.add(MappingPair(veris_id, attack_id))
        veris_ids.add(veris_id)

    return pairs, veris_ids


# Extrait les paires VERIS-ATT&CK depuis un JSON au format veris_to_mitre.
def extract_veris_to_mitre_pairs(
    data: dict[str, Any],
    scope: str | None,
    source_label: str,
) -> tuple[set[MappingPair], set[str]]:
    pairs: set[MappingPair] = set()
    veris_ids: set[str] = set()
    scope_norm = scope.lower() if scope else None

    metadata_scope = (data.get("metadata", {}).get("scope") or "").lower()
    if scope_norm and metadata_scope and scope_norm not in metadata_scope:
        print(
            f"Attention ({source_label}) : scope metadata '{metadata_scope}' "
            f"differe du filtre '{scope_norm}'.",
            file=sys.stderr,
        )

    for entry in data.get("veris_to_mitre", []):
        veris_id = normalize_veris_id(entry.get("veris_id", ""))
        if not veris_id or not veris_id_matches_scope(veris_id, scope_norm):
            continue

        if entry.get("no_mapping_found"):
            veris_ids.add(veris_id)
            continue

        for mapping in entry.get("mitre_mappings", []):
            attack_id = normalize_attack_id(
                mapping.get("sub_technique_id") or mapping.get("technique_id")
            )
            if attack_id:
                pairs.add(MappingPair(veris_id, attack_id))
                veris_ids.add(veris_id)

    return pairs, veris_ids


# Choisit le bon extracteur selon le format detecte dans le JSON.
def extract_pairs(
    data: dict[str, Any],
    scope: str | None,
    source_label: str,
) -> tuple[set[MappingPair], set[str], MappingFormat]:
    mapping_format = detect_mapping_format(data)
    if mapping_format == "ctid":
        pairs, veris_ids = extract_ctid_pairs(data, scope)
    else:
        pairs, veris_ids = extract_veris_to_mitre_pairs(data, scope, source_label)
    return pairs, veris_ids, mapping_format


# Compare technique par technique pour chaque capability VERIS.
def build_per_veris_breakdown(
    by_veris_a: dict[str, set[str]],
    by_veris_b: dict[str, set[str]],
) -> dict[str, dict[str, Any]]:
    breakdown: dict[str, dict[str, Any]] = {}

    for veris_id in sorted(set(by_veris_a) | set(by_veris_b)):
        attacks_a = by_veris_a.get(veris_id, set())
        attacks_b = by_veris_b.get(veris_id, set())
        common = attacks_a & attacks_b

        breakdown[veris_id] = {
            "mapping_a_count": len(attacks_a),
            "mapping_b_count": len(attacks_b),
            "common_count": len(common),
            "common_attack_ids": sorted(common),
            "only_in_a_attack_ids": sorted(attacks_a - attacks_b),
            "only_in_b_attack_ids": sorted(attacks_b - attacks_a),
            "recall": len(common) / len(attacks_a) if attacks_a else None,
            "precision": len(common) / len(attacks_b) if attacks_b else None,
        }

    return breakdown


# Calcule des statistiques globales au niveau des capabilities VERIS.
def compute_capability_metrics(
    by_veris_a: dict[str, set[str]],
    by_veris_b: dict[str, set[str]],
) -> dict[str, Any]:
    common_caps = sorted(set(by_veris_a) & set(by_veris_b))
    only_a_caps = sorted(set(by_veris_a) - set(by_veris_b))
    only_b_caps = sorted(set(by_veris_b) - set(by_veris_a))

    caps_with_overlap = 0
    caps_exact_match = 0
    recall_values: list[float] = []
    precision_values: list[float] = []

    for veris_id in common_caps:
        attacks_a = by_veris_a[veris_id]
        attacks_b = by_veris_b[veris_id]
        common = attacks_a & attacks_b
        if common:
            caps_with_overlap += 1
        if attacks_a == attacks_b:
            caps_exact_match += 1
        if attacks_a:
            recall_values.append(len(common) / len(attacks_a))
        if attacks_b:
            precision_values.append(len(common) / len(attacks_b))

    return {
        "common_capability_count": len(common_caps),
        "only_in_a_capability_count": len(only_a_caps),
        "only_in_b_capability_count": len(only_b_caps),
        "capabilities_with_at_least_one_common_technique": caps_with_overlap,
        "capabilities_with_exact_technique_set_match": caps_exact_match,
        "mean_recall_on_common_capabilities": (
            round(sum(recall_values) / len(recall_values), 4) if recall_values else None
        ),
        "mean_precision_on_common_capabilities": (
            round(sum(precision_values) / len(precision_values), 4) if precision_values else None
        ),
        "only_in_a_capabilities": only_a_caps,
        "only_in_b_capabilities": only_b_caps,
    }


# Orchestre la comparaison complete entre les deux mappings.
def compare_mappings(
    data_a: dict[str, Any],
    data_b: dict[str, Any],
    label_a: str,
    label_b: str,
    scope: str | None,
) -> ComparisonResult:
    pairs_a, veris_a, _ = extract_pairs(data_a, scope, label_a)
    pairs_b, veris_b, _ = extract_pairs(data_b, scope, label_b)

    intersection = pairs_a & pairs_b
    only_in_a = pairs_a - pairs_b
    only_in_b = pairs_b - pairs_a

    by_veris_a: dict[str, set[str]] = defaultdict(set)
    by_veris_b: dict[str, set[str]] = defaultdict(set)
    for pair in pairs_a:
        by_veris_a[pair.veris_id].add(pair.attack_id)
    for pair in pairs_b:
        by_veris_b[pair.veris_id].add(pair.attack_id)

    return ComparisonResult(
        scope=scope or "all",
        mapping_a_label=label_a,
        mapping_b_label=label_b,
        mapping_a_pairs=pairs_a,
        mapping_b_pairs=pairs_b,
        intersection=intersection,
        only_in_a=only_in_a,
        only_in_b=only_in_b,
        veris_ids_a=veris_a,
        veris_ids_b=veris_b,
        veris_only_in_a=sorted(veris_a - veris_b),
        veris_only_in_b=sorted(veris_b - veris_a),
        veris_common=sorted(veris_a & veris_b),
        per_veris=build_per_veris_breakdown(by_veris_a, by_veris_b),
        capability_metrics=compute_capability_metrics(by_veris_a, by_veris_b),
    )


# Convertit un ensemble de paires en liste de dictionnaires pour le JSON.
def pairs_to_rows(pairs: set[MappingPair]) -> list[dict[str, str]]:
    return [
        {"veris_id": pair.veris_id, "attack_id": pair.attack_id}
        for pair in sorted(pairs, key=lambda p: (p.veris_id, p.attack_id))
    ]


# Transforme un ComparisonResult en structure serialisable en JSON.
def result_to_dict(result: ComparisonResult) -> dict[str, Any]:
    return {
        "scope": result.scope,
        "mapping_a": result.mapping_a_label,
        "mapping_b": result.mapping_b_label,
        "summary": {
            "mapping_a_pair_count": len(result.mapping_a_pairs),
            "mapping_b_pair_count": len(result.mapping_b_pairs),
            "common_pair_count": len(result.intersection),
            "only_in_a_pair_count": len(result.only_in_a),
            "only_in_b_pair_count": len(result.only_in_b),
            "precision": round(result.precision, 4),
            "recall": round(result.recall, 4),
            "f1": round(result.f1, 4),
            "jaccard": round(result.jaccard, 4),
            "mapping_a_veris_capability_count": len(result.veris_ids_a),
            "mapping_b_veris_capability_count": len(result.veris_ids_b),
            "veris_only_in_a": result.veris_only_in_a,
            "veris_only_in_b": result.veris_only_in_b,
        },
        "capability_metrics": result.capability_metrics,
        "pairs": {
            "common": pairs_to_rows(result.intersection),
            "only_in_a": pairs_to_rows(result.only_in_a),
            "only_in_b": pairs_to_rows(result.only_in_b),
        },
        "per_veris": result.per_veris,
    }


# Affiche un resume lisible de la comparaison dans le terminal.
def print_summary(result: ComparisonResult) -> None:
    print("=" * 72)
    print("COMPARAISON MAPPING VERIS -> ATT&CK")
    print("=" * 72)
    print(f"Scope filtre : {result.scope}")
    print(f"Mapping A    : {result.mapping_a_label}")
    print(f"Mapping B    : {result.mapping_b_label}")
    print()
    print(f"Paires A     : {len(result.mapping_a_pairs)}")
    print(f"Paires B     : {len(result.mapping_b_pairs)}")
    print(f"Paires communes : {len(result.intersection)}")
    print(f"Seulement A  : {len(result.only_in_a)}")
    print(f"Seulement B  : {len(result.only_in_b)}")
    print()
    print("Metriques globales (A = reference, B = comparaison):")
    print(f"  Precision  : {result.precision:.1%}")
    print(f"  Rappel     : {result.recall:.1%}")
    print(f"  F1         : {result.f1:.1%}")
    print(f"  Jaccard    : {result.jaccard:.1%}")
    print()
    print(f"Capabilities VERIS (A) : {len(result.veris_ids_a)}")
    print(f"Capabilities VERIS (B) : {len(result.veris_ids_b)}")

    cm = result.capability_metrics
    if cm:
        print()
        print("Metriques sur les capabilities communes:")
        print(f"  Capabilities communes : {cm['common_capability_count']}")
        print(
            "  Avec >= 1 technique commune : "
            f"{cm['capabilities_with_at_least_one_common_technique']}"
        )
        print(
            "  Ensemble de techniques identique : "
            f"{cm['capabilities_with_exact_technique_set_match']}"
        )
        if cm["mean_recall_on_common_capabilities"] is not None:
            print(
                "  Rappel moyen  : "
                f"{cm['mean_recall_on_common_capabilities']:.1%}"
            )
        if cm["mean_precision_on_common_capabilities"] is not None:
            print(
                "  Precision moyenne : "
                f"{cm['mean_precision_on_common_capabilities']:.1%}"
            )

    if result.veris_only_in_a:
        print(f"\nCapabilities seulement dans A ({len(result.veris_only_in_a)}):")
        for veris_id in result.veris_only_in_a[:10]:
            print(f"  - {veris_id}")
        if len(result.veris_only_in_a) > 10:
            print(f"  ... et {len(result.veris_only_in_a) - 10} autres")

    if result.veris_only_in_b:
        print(f"\nCapabilities seulement dans B ({len(result.veris_only_in_b)}):")
        for veris_id in result.veris_only_in_b[:10]:
            print(f"  - {veris_id}")
        if len(result.veris_only_in_b) > 10:
            print(f"  ... et {len(result.veris_only_in_b) - 10} autres")

    divergent = [
        (veris_id, info)
        for veris_id, info in result.per_veris.items()
        if info["only_in_a_attack_ids"] or info["only_in_b_attack_ids"]
    ]
    divergent.sort(
        key=lambda item: (
            len(item[1]["only_in_a_attack_ids"]) + len(item[1]["only_in_b_attack_ids"]),
            item[0],
        ),
        reverse=True,
    )

    print("\nPlus grandes divergences (par capability VERIS):")
    for veris_id, info in divergent[:8]:
        print(f"\n  {veris_id}")
        if info["only_in_a_attack_ids"]:
            print(f"    A seulement : {', '.join(info['only_in_a_attack_ids'][:8])}")
            if len(info["only_in_a_attack_ids"]) > 8:
                print(f"    ... +{len(info['only_in_a_attack_ids']) - 8}")
        if info["only_in_b_attack_ids"]:
            print(f"    B seulement : {', '.join(info['only_in_b_attack_ids'][:8])}")
            if len(info["only_in_b_attack_ids"]) > 8:
                print(f"    ... +{len(info['only_in_b_attack_ids']) - 8}")


# Definit et lit les arguments de la ligne de commande.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare deux fichiers JSON de mapping VERIS -> ATT&CK."
    )
    parser.add_argument(
        "mapping_a",
        type=Path,
        help="Premier fichier JSON (reference)",
    )
    parser.add_argument(
        "mapping_b",
        type=Path,
        help="Second fichier JSON (comparaison)",
    )
    parser.add_argument(
        "--scope",
        default="action.hacking",
        help="Capability group a filtrer (ex: action.hacking). Utiliser 'all' pour tout.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Chemin du rapport JSON detaille",
    )
    return parser.parse_args()


# Point d'entree : charge les fichiers, compare et ecrit le rapport.
def main() -> int:
    args = parse_args()
    scope = None if args.scope.lower() == "all" else args.scope

    data_a = load_json(args.mapping_a.resolve())
    data_b = load_json(args.mapping_b.resolve())

    result = compare_mappings(
        data_a,
        data_b,
        label_a=args.mapping_a.name,
        label_b=args.mapping_b.name,
        scope=scope,
    )
    print_summary(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(result_to_dict(result), handle, ensure_ascii=False, indent=2)
        print(f"\nRapport detaille ecrit dans : {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
