#!/usr/bin/env python3
"""
Compare en lot les mappings VERIS -> ATT&CK produits par les 3 solutions IA
(FINE_TUNE, PROMPT, RAG) avec les mappings officiels des experts.

Principe
--------
On parcourt les dossiers de solutions (par defaut Resultat_FINE_TUNE,
Resultat_PROMPT, Resultat_RAG). Chaque solution contient un ou plusieurs
sous-dossiers nommes d'apres la version du mapping, par exemple :

    Resultat_RAG/veris-1.4.1_attack-19.1-enterprise_Exemple/

Le prefixe du nom de dossier ("veris-1.4.1_attack-19.1-enterprise") identifie
le mapping de reference correspondant dans Mapping_des_experts :

    Mapping_des_experts/veris-1.4.1_attack-19.1-enterprise_json.json

Chaque sous-dossier doit contenir 7 fichiers JSON (un par capability_group) au
format `veris_to_mitre`. Le script :
  1. valide la presence des 7 fichiers attendus ;
  2. agrege les 7 fichiers et calcule des metriques globales vs experts ;
  3. detaille les metriques par capability_group ;
  4. classe les 3 solutions pour chaque version.

Usage
-----
    python compare_veris_mappings_v2.py
    python compare_veris_mappings_v2.py --solutions Resultat_RAG -o rapport.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Permet d'importer le module v1 quel que soit le repertoire courant.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from compare_veris_mappings import (  # noqa: E402
    SCOPE_PREFIXES,
    ComparisonResult,
    compare_mappings,
    load_json,
    result_to_dict,
)

DEFAULT_SOLUTIONS = ["Resultat_FINE_TUNE", "Resultat_PROMPT", "Resultat_RAG"]
EXPERTS_DIRNAME = "Mapping_des_experts"
EXPERTS_SUFFIX = "_json.json"

# Les 7 capability_groups attendus = un fichier <group>.json par sous-dossier.
EXPECTED_SCOPES = list(SCOPE_PREFIXES.keys())


@dataclass
class SolutionReport:
    solution: str
    version_dir: str
    version_ref: str | None = None
    expert_file: str | None = None
    present_scopes: list[str] = field(default_factory=list)
    missing_scopes: list[str] = field(default_factory=list)
    extra_files: list[str] = field(default_factory=list)
    global_result: ComparisonResult | None = None
    per_scope: dict[str, ComparisonResult] = field(default_factory=dict)
    error: str | None = None


# Construit l'index {reference: chemin} des mappings experts disponibles.
def index_expert_references(experts_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(experts_dir.glob(f"*{EXPERTS_SUFFIX}")):
        ref = path.name[: -len(EXPERTS_SUFFIX)]
        index[ref] = path
    return index


# Retrouve la reference experte dont le nom prefixe le dossier de version.
def match_expert_ref(version_dir_name: str, expert_refs: list[str]) -> str | None:
    candidates = [ref for ref in expert_refs if version_dir_name.startswith(ref)]
    if not candidates:
        return None
    return max(candidates, key=len)


# Fusionne les entrees veris_to_mitre de plusieurs fichiers en un seul mapping.
def merge_scope_files(scope_files: dict[str, Path]) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    for path in scope_files.values():
        data = load_json(path)
        merged.extend(data.get("veris_to_mitre", []))
    return {"veris_to_mitre": merged}


# Analyse un sous-dossier de version pour une solution donnee.
def evaluate_version_dir(
    solution: str,
    version_dir: Path,
    expert_index: dict[str, Path],
    expert_cache: dict[str, dict[str, Any]],
) -> SolutionReport:
    report = SolutionReport(solution=solution, version_dir=version_dir.name)

    ref = match_expert_ref(version_dir.name, list(expert_index))
    if ref is None:
        report.error = (
            f"Aucun mapping expert ne correspond au dossier '{version_dir.name}'."
        )
        return report
    report.version_ref = ref
    report.expert_file = expert_index[ref].name

    # Inventaire des fichiers du sous-dossier.
    present_files: dict[str, Path] = {}
    json_files = {p.name for p in version_dir.glob("*.json")}
    for scope in EXPECTED_SCOPES:
        candidate = version_dir / f"{scope}.json"
        if candidate.is_file():
            present_files[scope] = candidate
            report.present_scopes.append(scope)
        else:
            report.missing_scopes.append(scope)
    expected_names = {f"{scope}.json" for scope in EXPECTED_SCOPES}
    report.extra_files = sorted(json_files - expected_names)

    if not present_files:
        report.error = "Aucun fichier de scope attendu trouve."
        return report

    expert_data = expert_cache.setdefault(ref, load_json(expert_index[ref]))

    # Comparaison globale : tous les scopes agreges vs mapping expert complet.
    combined = merge_scope_files(present_files)
    report.global_result = compare_mappings(
        expert_data,
        combined,
        label_a=report.expert_file,
        label_b=f"{solution}/{version_dir.name} (agrege)",
        scope=None,
    )

    # Comparaison detaillee par capability_group.
    for scope, path in present_files.items():
        report.per_scope[scope] = compare_mappings(
            expert_data,
            load_json(path),
            label_a=report.expert_file,
            label_b=path.name,
            scope=scope,
        )

    return report


# Collecte les rapports pour toutes les solutions demandees.
def collect_reports(
    base_dir: Path,
    solutions: list[str],
    expert_index: dict[str, Path],
) -> list[SolutionReport]:
    reports: list[SolutionReport] = []
    expert_cache: dict[str, dict[str, Any]] = {}

    for solution in solutions:
        sol_dir = base_dir / solution
        if not sol_dir.is_dir():
            reports.append(
                SolutionReport(
                    solution=solution,
                    version_dir="-",
                    error=f"Dossier introuvable : {sol_dir}",
                )
            )
            continue

        version_dirs = sorted(p for p in sol_dir.iterdir() if p.is_dir())
        if not version_dirs:
            reports.append(
                SolutionReport(
                    solution=solution,
                    version_dir="-",
                    error="Aucun sous-dossier de version.",
                )
            )
            continue

        for version_dir in version_dirs:
            reports.append(
                evaluate_version_dir(solution, version_dir, expert_index, expert_cache)
            )

    return reports


def pct(value: float) -> str:
    return f"{value:6.1%}"


# Affiche le detail d'un rapport de solution.
def print_report(report: SolutionReport) -> None:
    print("-" * 72)
    print(f"Solution : {report.solution}")
    print(f"Dossier  : {report.version_dir}")

    if report.error:
        print(f"  [ERREUR] {report.error}")
        return

    print(f"Version  : {report.version_ref}")
    print(f"Experts  : {report.expert_file}")
    print(
        f"Fichiers : {len(report.present_scopes)}/{len(EXPECTED_SCOPES)} scopes presents"
    )
    if report.missing_scopes:
        print(f"  MANQUANTS : {', '.join(report.missing_scopes)}")
    if report.extra_files:
        print(f"  EN TROP   : {', '.join(report.extra_files)}")

    g = report.global_result
    if g is not None:
        print()
        print("  GLOBAL (tous scopes agreges) :")
        print(
            f"    Paires experts={len(g.mapping_a_pairs):4}  "
            f"solution={len(g.mapping_b_pairs):4}  communes={len(g.intersection):4}"
        )
        print(
            f"    Precision={pct(g.precision)}  Rappel={pct(g.recall)}  "
            f"F1={pct(g.f1)}  Jaccard={pct(g.jaccard)}"
        )

    if report.per_scope:
        print()
        print("  PAR CAPABILITY_GROUP :")
        header = (
            f"    {'scope':28} {'exp':>5} {'sol':>5} {'comm':>5} "
            f"{'Prec':>7} {'Rapp':>7} {'F1':>7}"
        )
        print(header)
        for scope in EXPECTED_SCOPES:
            r = report.per_scope.get(scope)
            if r is None:
                print(f"    {scope:28} {'-- absent --':>33}")
                continue
            print(
                f"    {scope:28} "
                f"{len(r.mapping_a_pairs):5} {len(r.mapping_b_pairs):5} "
                f"{len(r.intersection):5} "
                f"{pct(r.precision):>7} {pct(r.recall):>7} {pct(r.f1):>7}"
            )


# Affiche un classement des solutions par version (sur le F1 global).
def print_leaderboard(reports: list[SolutionReport]) -> None:
    by_version: dict[str, list[SolutionReport]] = {}
    for report in reports:
        if report.error or report.global_result is None:
            continue
        by_version.setdefault(report.version_ref or "?", []).append(report)

    if not by_version:
        return

    print("=" * 72)
    print("CLASSEMENT DES SOLUTIONS (F1 global vs experts)")
    print("=" * 72)
    for version, items in sorted(by_version.items()):
        print(f"\nVersion : {version}")
        ranked = sorted(items, key=lambda r: r.global_result.f1, reverse=True)
        print(
            f"  {'#':>2} {'solution':20} {'Prec':>7} {'Rapp':>7} "
            f"{'F1':>7} {'Jacc':>7}"
        )
        for rank, report in enumerate(ranked, start=1):
            g = report.global_result
            print(
                f"  {rank:>2} {report.solution:20} "
                f"{pct(g.precision):>7} {pct(g.recall):>7} "
                f"{pct(g.f1):>7} {pct(g.jaccard):>7}"
            )


# Convertit un rapport en structure serialisable en JSON.
def report_to_dict(report: SolutionReport) -> dict[str, Any]:
    return {
        "solution": report.solution,
        "version_dir": report.version_dir,
        "version_ref": report.version_ref,
        "expert_file": report.expert_file,
        "present_scopes": report.present_scopes,
        "missing_scopes": report.missing_scopes,
        "extra_files": report.extra_files,
        "error": report.error,
        "global": result_to_dict(report.global_result)
        if report.global_result is not None
        else None,
        "per_scope": {
            scope: result_to_dict(result)
            for scope, result in report.per_scope.items()
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare en lot les mappings des solutions IA (FINE_TUNE, PROMPT, RAG) "
            "avec les mappings experts."
        )
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=SCRIPT_DIR,
        help="Dossier racine contenant les dossiers de solutions et Mapping_des_experts.",
    )
    parser.add_argument(
        "--experts",
        type=Path,
        default=None,
        help="Dossier des mappings experts (defaut : <base>/Mapping_des_experts).",
    )
    parser.add_argument(
        "--solutions",
        nargs="+",
        default=DEFAULT_SOLUTIONS,
        help="Noms des dossiers de solutions a comparer.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Chemin d'un rapport JSON detaille.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = args.base.resolve()
    experts_dir = (args.experts or base_dir / EXPERTS_DIRNAME).resolve()

    if not experts_dir.is_dir():
        print(f"[ERREUR] Dossier experts introuvable : {experts_dir}", file=sys.stderr)
        return 1

    expert_index = index_expert_references(experts_dir)
    if not expert_index:
        print(
            f"[ERREUR] Aucun mapping expert (*{EXPERTS_SUFFIX}) dans {experts_dir}.",
            file=sys.stderr,
        )
        return 1

    print("=" * 72)
    print("COMPARAISON v2 : SOLUTIONS IA vs EXPERTS")
    print("=" * 72)
    print(f"Base      : {base_dir}")
    print(f"Experts   : {experts_dir} ({len(expert_index)} references)")
    print(f"Solutions : {', '.join(args.solutions)}")
    print()

    reports = collect_reports(base_dir, args.solutions, expert_index)
    for report in reports:
        print_report(report)
    print()
    print_leaderboard(reports)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "base": str(base_dir),
            "experts_dir": str(experts_dir),
            "expert_references": sorted(expert_index),
            "reports": [report_to_dict(r) for r in reports],
        }
        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"\nRapport detaille ecrit dans : {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
