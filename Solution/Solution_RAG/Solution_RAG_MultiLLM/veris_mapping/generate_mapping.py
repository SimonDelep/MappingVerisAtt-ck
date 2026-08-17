"""Pipeline RAG multi-LLM : capacités VERIS -> mapping ATT&CK -> 7 JSON.

Retrieval local (ChromaDB + MiniLM) + décision par un LLM cloud (parmi les
modèles de la phase 1). Sorties sous Resultat/Resultat_RAG_MultiLLM/.

Modes :
  - attack_only
  - with_examples

Usage :
  python generate_mapping.py --mode with_examples --model meta-llama/Llama-3.3-70B-Instruct-Turbo
  python generate_mapping.py --mode both --model Qwen/Qwen2.5-7B-Instruct-Turbo --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import config
import datasets
import generator
from prompt import CONFIDENCE_SCORES
from retrieve import (
    analog_budget_n,
    analog_budget_n_v11,
    analog_budget_n_v12,
    analog_budget_n_v13,
    analog_budget_n_v14,
    allocate_v10_budgets,
    allocate_v11_budgets,
    corpus_examples_for_label,
    discovery_retrieval_decisions,
    hybrid_fill_decisions,
    is_skip_label,
    merge_candidates_with_examples,
    rerank_keep_n,
    rerank_v10,
    rerank_v11,
    rerank_v12,
    rerank_v13,
    rerank_v14,
    retrieve_examples,
    retrieve_techniques,
)

sys.path.insert(0, str(config.RESULTAT_DIR))
from compare_veris_mappings import normalize_veris_id  # noqa: E402


def mode_dirname(mode: str, model_id: str, tag: str | None = None) -> str:
    slug = config.model_slug(model_id)
    base = f"{config.TARGET_REF}_RAG_MultiLLM_{slug}_{mode}"
    if tag:
        return f"{base}_{tag}"
    return base


def mapping_attack_id(mapping: dict) -> str:
    """Identifiant ATT&CK utilisé pour la déduplication / comparaison."""
    return (
        (mapping.get("sub_technique_id") or mapping.get("technique_id") or "")
        .strip()
        .upper()
    )


def enrich_mapping(
    attack_id: str,
    decision: dict,
    attack_index: dict,
) -> dict | None:
    """Construit une entrée mitre_mappings enrichie (anti-hallucination catalogue)."""
    attack_id = (attack_id or "").strip().upper()
    if attack_id not in attack_index:
        return None

    tech = attack_index[attack_id]
    if tech.is_subtechnique:
        parent = attack_index.get(tech.parent_id)
        technique_id = tech.parent_id
        technique_name = parent.name if parent else ""
        sub_technique_id = attack_id
        sub_technique_name = tech.name
    else:
        technique_id = attack_id
        technique_name = tech.name
        sub_technique_id = None
        sub_technique_name = None

    confidence = str(decision.get("confidence", "medium")).lower()
    if confidence not in CONFIDENCE_SCORES:
        confidence = "medium"

    return {
        "technique_id": technique_id,
        "technique_name": technique_name,
        "sub_technique_id": sub_technique_id,
        "sub_technique_name": sub_technique_name,
        "tactic(s)": tech.tactics,
        "mapping_type": decision.get("mapping_type", "related_to") or "related_to",
        "confidence": confidence,
        "confidence_score": CONFIDENCE_SCORES[confidence],
        "justification": decision.get("justification", "") or "",
    }


def _retrieve_context(
    cap: datasets.VerisCapability,
    attack_index: dict,
    use_examples: bool,
    top_m: int | None = None,
) -> tuple[list[dict], list[dict]]:
    candidates = retrieve_techniques(cap.query_text())
    examples = (
        retrieve_examples(cap.query_text(), top_m=top_m, group=cap.capability_group)
        if use_examples
        else []
    )
    if use_examples and examples:
        candidates = merge_candidates_with_examples(
            candidates, examples, attack_index
        )
    return candidates, examples


def apply_hybrid_fill(
    mitre_mappings: list[dict],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    group: str = "",
    fill_version: str = "v3",
    n_target: int | None = None,
    label: str = "",
    capability_id: str = "",
) -> list[dict]:
    """Ajoute (v3–v8) ou reclasse (v9 N local / v10–v14 analogique)."""
    if fill_version in {"v9", "v10", "v11", "v12", "v13", "v14"}:
        current_ids = [mapping_attack_id(m) for m in mitre_mappings if mapping_attack_id(m)]
        hybrid_ids = {
            mapping_attack_id(m)
            for m in mitre_mappings
            if "complément" in (m.get("justification") or "").lower()
            or "complement" in (m.get("justification") or "").lower()
        }
        rebuilt: list[dict] = []
        seen: set[str] = set()
        if fill_version == "v14":
            decisions = rerank_v14(
                current_ids,
                hybrid_ids,
                candidates,
                examples,
                attack_index,
                group=group,
                label=label,
                capability_id=capability_id,
                n_target=n_target,
            )
        elif fill_version == "v13":
            decisions = rerank_v13(
                current_ids,
                hybrid_ids,
                candidates,
                examples,
                attack_index,
                group=group,
                label=label,
                capability_id=capability_id,
                n_target=n_target,
            )
        elif fill_version == "v12":
            decisions = rerank_v12(
                current_ids,
                hybrid_ids,
                candidates,
                examples,
                attack_index,
                group=group,
                label=label,
                capability_id=capability_id,
                n_target=n_target,
            )
        elif fill_version == "v11":
            decisions = rerank_v11(
                current_ids,
                hybrid_ids,
                candidates,
                examples,
                attack_index,
                group=group,
                label=label,
                capability_id=capability_id,
                n_target=n_target,
            )
        elif fill_version == "v10":
            decisions = rerank_v10(
                current_ids,
                hybrid_ids,
                candidates,
                examples,
                attack_index,
                group=group,
                n_target=n_target,
            )
        else:
            decisions = rerank_keep_n(
                current_ids, hybrid_ids, candidates, examples, attack_index
            )
        for decision in decisions:
            aid = (decision.get("attack_id") or "").strip().upper()
            if not aid or aid in seen:
                continue
            entry = enrich_mapping(aid, decision, attack_index)
            if entry is None:
                continue
            rebuilt.append(entry)
            seen.add(aid)
        rebuilt.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
        return rebuilt

    seen = {mapping_attack_id(m) for m in mitre_mappings}
    seen.discard("")
    for decision in hybrid_fill_decisions(
        seen,
        candidates,
        examples,
        attack_index,
        version=fill_version,
        group=group,
    ):
        aid = (decision.get("attack_id") or "").strip().upper()
        if not aid or aid in seen:
            continue
        entry = enrich_mapping(aid, decision, attack_index)
        if entry is None:
            continue
        mitre_mappings.append(entry)
        seen.add(aid)
    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    return mitre_mappings


def _empty_capability(cap: datasets.VerisCapability, notes: str) -> dict:
    return {
        "veris_id": normalize_veris_id(cap.capability_id),
        "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
        "veris_label": cap.value,
        "no_mapping_found": True,
        "mitre_mappings": [],
        "ambiguous": False,
        "notes": notes,
    }


def _map_capability_v12(
    cap: datasets.VerisCapability,
    attack_index: dict,
    candidates: list[dict],
    examples: list[dict],
    model_id: str,
    use_examples: bool,
) -> dict:
    """V12 : analogue same-label sans LLM ; LLM seulement si analogue vide."""
    if is_skip_label(cap.value):
        print("    [v12] skip Unknown/Other", flush=True)
        return _empty_capability(cap, "[v12 skip Unknown/Other]")

    analog_n = analog_budget_n_v12(
        examples,
        attack_index,
        cap.capability_group,
        label=cap.value,
        capability_id=cap.capability_id,
    )
    if analog_n > 0:
        print(f"    [v12] analog N={analog_n} (pas de LLM)", flush=True)
        mitre_mappings = apply_hybrid_fill(
            [],
            candidates,
            examples,
            attack_index,
            group=cap.capability_group,
            fill_version="v12",
            label=cap.value,
            capability_id=cap.capability_id,
        )
        mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
        return {
            "veris_id": normalize_veris_id(cap.capability_id),
            "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
            "veris_label": cap.value,
            "no_mapping_found": not mitre_mappings,
            "mitre_mappings": mitre_mappings,
            "ambiguous": False,
            "notes": f"[v12 analog N={len(mitre_mappings)}, no LLM]",
        }

    print("    [v12] analogue vide -> LLM fallback", flush=True)
    try:
        result = generator.generate_decision(
            group=cap.capability_group,
            label=cap.value,
            description=cap.description,
            candidates=candidates[: max(12, min(20, len(candidates)))],
            examples=examples,
            attack_index=attack_index,
            use_examples=use_examples,
            model=model_id,
        )
    except Exception as error:
        print(f"    [ERREUR génération] {cap.capability_id} : {error}")
        return _empty_capability(cap, f"Erreur: {error} [v12 llm fallback]")

    mitre_mappings: list[dict] = []
    seen: set[str] = set()
    for decision in result.get("mappings", []) or []:
        if len(mitre_mappings) >= config.HYBRID_V12_LLM_MAX:
            break
        attack_id = (decision.get("attack_id") or "").strip().upper()
        if not attack_id or attack_id in seen:
            continue
        entry = enrich_mapping(attack_id, decision, attack_index)
        if entry is not None:
            mitre_mappings.append(entry)
            seen.add(attack_id)
    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    notes = (result.get("notes") or "").rstrip()
    extra = f"[v12 llm fallback N={len(mitre_mappings)}]"
    notes = (notes + " " + extra).strip() if notes else extra
    return {
        "veris_id": normalize_veris_id(cap.capability_id),
        "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
        "veris_label": cap.value,
        "no_mapping_found": not mitre_mappings,
        "mitre_mappings": mitre_mappings,
        "ambiguous": bool(result.get("ambiguous", False)),
        "notes": notes,
    }


def _map_capability_v13(
    cap: datasets.VerisCapability,
    attack_index: dict,
    candidates: list[dict],
    examples: list[dict],
) -> dict:
    """V13 : analogue same-label (y compris Unknown/Other), jamais de LLM."""
    analog_n = analog_budget_n_v13(
        examples,
        attack_index,
        cap.capability_group,
        label=cap.value,
        capability_id=cap.capability_id,
    )
    if analog_n == 0:
        print("    [v13] analogue vide (pas de LLM)", flush=True)
        return _empty_capability(cap, "[v13 analog N=0, no LLM]")

    print(f"    [v13] analog N={analog_n} (pas de LLM)", flush=True)
    mitre_mappings = apply_hybrid_fill(
        [],
        candidates,
        examples,
        attack_index,
        group=cap.capability_group,
        fill_version="v13",
        label=cap.value,
        capability_id=cap.capability_id,
    )
    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    return {
        "veris_id": normalize_veris_id(cap.capability_id),
        "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
        "veris_label": cap.value,
        "no_mapping_found": not mitre_mappings,
        "mitre_mappings": mitre_mappings,
        "ambiguous": False,
        "notes": f"[v13 analog N={len(mitre_mappings)}, no LLM]",
    }


def _decisions_to_mappings(
    decisions: list[dict],
    attack_index: dict,
) -> list[dict]:
    mitre_mappings: list[dict] = []
    seen: set[str] = set()
    for decision in decisions:
        attack_id = (decision.get("attack_id") or "").strip().upper()
        if not attack_id or attack_id in seen:
            continue
        entry = enrich_mapping(attack_id, decision, attack_index)
        if entry is not None:
            mitre_mappings.append(entry)
            seen.add(attack_id)
    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    return mitre_mappings


def _map_capability_v14(
    cap: datasets.VerisCapability,
    attack_index: dict,
    candidates: list[dict],
    examples: list[dict],
    model_id: str,
    use_examples: bool,
) -> dict:
    """V14 : corpus same-label + remap ; découverte retrieval puis LLM si vide."""
    corpus = corpus_examples_for_label(
        cap.capability_group, cap.value, cap.capability_id
    )
    # Corpus d'abord (couverture complète), puis retrieval pour le scoring local.
    merged_examples = list(corpus) + list(examples)
    analog_n = analog_budget_n_v14(
        merged_examples,
        attack_index,
        cap.capability_group,
        label=cap.value,
        capability_id=cap.capability_id,
    )
    if analog_n > 0:
        print(f"    [v14] analog N={analog_n} (corpus+remap)", flush=True)
        mitre_mappings = apply_hybrid_fill(
            [],
            candidates,
            merged_examples,
            attack_index,
            group=cap.capability_group,
            fill_version="v14",
            label=cap.value,
            capability_id=cap.capability_id,
        )
        return {
            "veris_id": normalize_veris_id(cap.capability_id),
            "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
            "veris_label": cap.value,
            "no_mapping_found": not mitre_mappings,
            "mitre_mappings": mitre_mappings,
            "ambiguous": False,
            "notes": f"[v14 analog N={len(mitre_mappings)}, corpus+remap]",
        }

    # Résidu inconnu : découverte retrieval haute similarité.
    discovery = discovery_retrieval_decisions(
        candidates, attack_index, group=cap.capability_group
    )
    if discovery:
        mitre_mappings = _decisions_to_mappings(discovery, attack_index)
        print(
            f"    [v14] discovery retrieval N={len(mitre_mappings)}",
            flush=True,
        )
        return {
            "veris_id": normalize_veris_id(cap.capability_id),
            "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
            "veris_label": cap.value,
            "no_mapping_found": not mitre_mappings,
            "mitre_mappings": mitre_mappings,
            "ambiguous": False,
            "notes": f"[v14 discovery retrieval N={len(mitre_mappings)}]",
        }

    if config.HYBRID_V14_LLM_MAX <= 0 or not config.TOGETHER_API_KEY:
        print("    [v14] résidu vide (pas de LLM)", flush=True)
        return _empty_capability(cap, "[v14 analog+discovery N=0, no LLM]")

    print("    [v14] résidu vide -> LLM discovery", flush=True)
    try:
        result = generator.generate_decision(
            group=cap.capability_group,
            label=cap.value,
            description=cap.description,
            candidates=candidates[: max(12, min(20, len(candidates)))],
            examples=merged_examples,
            attack_index=attack_index,
            use_examples=use_examples,
            model=model_id,
        )
    except Exception as error:
        print(f"    [ERREUR génération] {cap.capability_id} : {error}")
        return _empty_capability(cap, f"Erreur: {error} [v14 llm discovery]")

    mitre_mappings = []
    seen: set[str] = set()
    for decision in result.get("mappings", []) or []:
        if len(mitre_mappings) >= config.HYBRID_V14_LLM_MAX:
            break
        confidence = str(decision.get("confidence", "")).lower()
        if confidence and confidence not in {"high", "medium"}:
            continue
        attack_id = (decision.get("attack_id") or "").strip().upper()
        if not attack_id or attack_id in seen or attack_id not in attack_index:
            continue
        if _tactic_blocked(attack_id, cap.capability_group, attack_index):
            continue
        # Ne garder que high en premier ; si rien, medium une seule fois via max=1.
        if confidence != "high" and config.HYBRID_V14_LLM_MAX <= 1:
            # on accepte medium seulement si c'est le seul candidat viable plus bas
            pass
        entry = enrich_mapping(attack_id, decision, attack_index)
        if entry is None:
            continue
        if confidence != "high":
            # reporté : on préfère high ; stocke medium en attente
            continue
        mitre_mappings.append(entry)
        seen.add(attack_id)

    if not mitre_mappings:
        for decision in result.get("mappings", []) or []:
            if len(mitre_mappings) >= config.HYBRID_V14_LLM_MAX:
                break
            attack_id = (decision.get("attack_id") or "").strip().upper()
            if not attack_id or attack_id in seen or attack_id not in attack_index:
                continue
            if _tactic_blocked(attack_id, cap.capability_group, attack_index):
                continue
            entry = enrich_mapping(attack_id, decision, attack_index)
            if entry is None:
                continue
            mitre_mappings.append(entry)
            seen.add(attack_id)

    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    notes = (result.get("notes") or "").rstrip()
    extra = f"[v14 llm discovery N={len(mitre_mappings)}]"
    notes = (notes + " " + extra).strip() if notes else extra
    return {
        "veris_id": normalize_veris_id(cap.capability_id),
        "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
        "veris_label": cap.value,
        "no_mapping_found": not mitre_mappings,
        "mitre_mappings": mitre_mappings,
        "ambiguous": bool(result.get("ambiguous", False)),
        "notes": notes,
    }


def _tactic_blocked(attack_id: str, group: str, attack_index: dict) -> bool:
    from retrieve import _tactic_score

    return _tactic_score(attack_id, group, attack_index) < 0


def map_capability(
    cap: datasets.VerisCapability,
    attack_index: dict,
    use_examples: bool,
    model_id: str,
    hybrid_fill: bool = False,
    fill_version: str = "v3",
) -> dict:
    extra_top_m = None
    if fill_version == "v14":
        extra_top_m = config.HYBRID_V14_TOP_M
    elif fill_version == "v13":
        extra_top_m = config.HYBRID_V13_TOP_M
    elif fill_version == "v12":
        extra_top_m = config.HYBRID_V12_TOP_M
    elif fill_version == "v11":
        extra_top_m = config.HYBRID_V11_TOP_M
    candidates, examples = _retrieve_context(
        cap, attack_index, use_examples, top_m=extra_top_m
    )

    if fill_version == "v14":
        return _map_capability_v14(
            cap, attack_index, candidates, examples, model_id, use_examples
        )
    if fill_version == "v13":
        return _map_capability_v13(cap, attack_index, candidates, examples)
    if fill_version == "v12":
        return _map_capability_v12(
            cap, attack_index, candidates, examples, model_id, use_examples
        )

    try:
        result = generator.generate_decision(
            group=cap.capability_group,
            label=cap.value,
            description=cap.description,
            candidates=candidates,
            examples=examples,
            attack_index=attack_index,
            use_examples=use_examples,
            model=model_id,
        )
    except Exception as error:
        print(f"    [ERREUR génération] {cap.capability_id} : {error}")
        result = {
            "no_mapping_found": True,
            "mappings": [],
            "notes": f"Erreur: {error}",
        }

    mitre_mappings: list[dict] = []
    seen: set[str] = set()
    for decision in result.get("mappings", []) or []:
        attack_id = (decision.get("attack_id") or "").strip().upper()
        if not attack_id or attack_id in seen:
            continue
        entry = enrich_mapping(attack_id, decision, attack_index)
        if entry is not None:
            mitre_mappings.append(entry)
            seen.add(attack_id)

    if hybrid_fill:
        mitre_mappings = apply_hybrid_fill(
            mitre_mappings,
            candidates,
            examples,
            attack_index,
            group=cap.capability_group,
            fill_version=fill_version,
            label=cap.value,
            capability_id=cap.capability_id,
        )

    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    no_mapping = not mitre_mappings
    notes = result.get("notes", "") or (
        "Aucune correspondance trouvée." if no_mapping else ""
    )
    if hybrid_fill and notes:
        notes = notes.rstrip() + f" [hybrid_fill {fill_version}]"

    return {
        "veris_id": normalize_veris_id(cap.capability_id),
        "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
        "veris_label": cap.value,
        "no_mapping_found": no_mapping,
        "mitre_mappings": mitre_mappings,
        "ambiguous": bool(result.get("ambiguous", False)),
        "notes": notes,
    }


def write_results(
    entries_by_group: dict[str, list[dict]],
    out_dir: Path,
    quiet: bool = False,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for group in config.CAPABILITY_GROUPS:
        entries = sorted(entries_by_group.get(group, []), key=lambda e: e["veris_id"])
        payload = {
            "metadata": {
                "veris_version": config.VERIS_VERSION,
                "mitre_attack_version": config.ATTACK_VERSION,
                "scope": group,
            },
            "veris_to_mitre": entries,
        }
        out_path = out_dir / f"{group}.json"
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        if not quiet:
            mapped = sum(1 for e in entries if not e["no_mapping_found"])
            print(f"  {group:28} -> {len(entries):3} capacités ({mapped} mappées)")


def load_existing_entries(source_dir: Path) -> dict[str, dict]:
    """Indexe les entrées d'une run précédente par veris_id."""
    index: dict[str, dict] = {}
    for path in sorted(source_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("veris_to_mitre", []):
            vid = (entry.get("veris_id") or "").strip()
            if vid:
                index[vid] = entry
    if not index:
        raise FileNotFoundError(f"Aucune entrée veris_to_mitre dans {source_dir}")
    return index


def map_capability_from_existing(
    cap: datasets.VerisCapability,
    existing: dict,
    attack_index: dict,
    use_examples: bool,
    hybrid_fill: bool,
    fill_version: str = "v3",
    n_target: int | None = None,
    prefetched: tuple[list[dict], list[dict]] | None = None,
) -> dict:
    """Reprend une décision LLM déjà écrite et applique éventuellement le fill."""
    entry = {
        "veris_id": existing.get("veris_id") or normalize_veris_id(cap.capability_id),
        "veris_category": existing.get("veris_category")
        or cap.capability_group.split(".", 1)[1].capitalize(),
        "veris_label": existing.get("veris_label") or cap.value,
        "no_mapping_found": bool(existing.get("no_mapping_found", True)),
        "mitre_mappings": list(existing.get("mitre_mappings") or []),
        "ambiguous": bool(existing.get("ambiguous", False)),
        "notes": existing.get("notes", "") or "",
    }
    if hybrid_fill:
        if prefetched is None:
            candidates, examples = _retrieve_context(cap, attack_index, use_examples)
        else:
            candidates, examples = prefetched
        before = len(entry["mitre_mappings"])
        entry["mitre_mappings"] = apply_hybrid_fill(
            entry["mitre_mappings"],
            candidates,
            examples,
            attack_index,
            group=cap.capability_group,
            fill_version=fill_version,
            n_target=n_target,
            label=cap.value,
            capability_id=cap.capability_id,
        )
        after = len(entry["mitre_mappings"])
        if fill_version == "v14":
            extra = f"[rerank v14 N={after}]"
            entry["notes"] = (entry["notes"].rstrip() + " " + extra).strip()
        elif fill_version == "v13":
            extra = f"[rerank v13 N={after}]"
            entry["notes"] = (entry["notes"].rstrip() + " " + extra).strip()
        elif fill_version == "v12":
            extra = f"[rerank v12 N={after}]"
            entry["notes"] = (entry["notes"].rstrip() + " " + extra).strip()
        elif fill_version == "v11":
            extra = f"[rerank v11 N={after}]"
            entry["notes"] = (entry["notes"].rstrip() + " " + extra).strip()
        elif fill_version == "v10":
            extra = f"[rerank v10 N={after}]"
            entry["notes"] = (entry["notes"].rstrip() + " " + extra).strip()
        elif fill_version == "v9":
            extra = f"[rerank v9 N={after}]"
            entry["notes"] = (entry["notes"].rstrip() + " " + extra).strip()
        else:
            added = after - before
            if added:
                extra = f"[hybrid_fill {fill_version} +{added}]"
                entry["notes"] = (entry["notes"].rstrip() + " " + extra).strip()
    entry["no_mapping_found"] = not entry["mitre_mappings"]
    return entry


def run_mode(
    mode: str,
    model_id: str,
    limit: int | None,
    tag: str | None = None,
    hybrid_fill: bool = False,
    from_dir: Path | None = None,
    fill_version: str = "v3",
) -> Path:
    use_examples = mode == "with_examples"
    out_dir = config.RESULTAT_RAG_DIR / mode_dirname(mode, model_id, tag=tag)

    print("=" * 72)
    print(f"GÉNÉRATION RAG MultiLLM — mode '{mode}'")
    print(f"Modèle    : {model_id}")
    print(f"top_k     : {config.TOP_K_TECHNIQUES}")
    print(
        f"top_m     : {
            config.HYBRID_V14_TOP_M
            if fill_version == 'v14'
            else config.HYBRID_V13_TOP_M
            if fill_version == 'v13'
            else config.HYBRID_V12_TOP_M
            if fill_version == 'v12'
            else config.HYBRID_V11_TOP_M
            if fill_version == 'v11'
            else config.TOP_M_EXAMPLES
        }"
    )
    print(f"max_cand  : {config.MAX_PROMPT_CANDIDATES}")
    print(
        f"hybrid    : {hybrid_fill} ({fill_version}, max_add={config.HYBRID_MAX_ADD})"
    )
    if from_dir:
        print(f"from_dir  : {from_dir}")
    if tag:
        print(f"tag       : {tag}")
    print(f"Sortie    : {out_dir}")
    print("=" * 72)

    capabilities = datasets.load_veris_capabilities()
    if limit:
        capabilities = capabilities[:limit]
    attack_index = datasets.build_attack_index()
    existing_index = load_existing_entries(from_dir) if from_dir else None

    entries_by_group: dict[str, list[dict]] = defaultdict(list)
    missing = 0
    if (
        existing_index is not None
        and hybrid_fill
        and fill_version in {"v10", "v11"}
    ):
        rows: list[dict] = []
        extra_top_m = config.HYBRID_V11_TOP_M if fill_version == "v11" else None
        for i, cap in enumerate(capabilities, start=1):
            print(f"[{i:3}/{len(capabilities)}] {cap.capability_id}", flush=True)
            vid = normalize_veris_id(cap.capability_id)
            previous = existing_index.get(vid)
            if previous is None:
                missing += 1
                print(f"    [WARN] pas d'entrée v2 pour {vid}", flush=True)
                previous = {
                    "veris_id": vid,
                    "mitre_mappings": [],
                    "no_mapping_found": True,
                    "notes": "Absente de la run source.",
                }
            candidates, examples = _retrieve_context(
                cap, attack_index, use_examples, top_m=extra_top_m
            )
            current_n = len(
                [m for m in (previous.get("mitre_mappings") or []) if mapping_attack_id(m)]
            )
            if fill_version == "v11":
                analog_n = analog_budget_n_v11(
                    examples,
                    attack_index,
                    cap.capability_group,
                    label=cap.value,
                    capability_id=cap.capability_id,
                )
            else:
                analog_n = analog_budget_n(examples, attack_index, cap.capability_group)
            rows.append(
                {
                    "cap": cap,
                    "previous": previous,
                    "candidates": candidates,
                    "examples": examples,
                    "current_n": current_n,
                    "analog_n": analog_n,
                    "group": cap.capability_group,
                }
            )
        target_global = sum(row["current_n"] for row in rows)
        if fill_version == "v11":
            budgets = allocate_v11_budgets(
                [row["analog_n"] for row in rows],
                [row["current_n"] for row in rows],
                [row["group"] for row in rows],
                target_global,
            )
        else:
            budgets = allocate_v10_budgets(
                [row["analog_n"] for row in rows],
                [row["current_n"] for row in rows],
                [row["group"] for row in rows],
                target_global,
            )
        tag_fill = fill_version
        print(
            f"  [{tag_fill}] N global={sum(budgets)} (source={target_global}, "
            f"analog={sum(row['analog_n'] for row in rows)})",
            flush=True,
        )
        by_group: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for row, n_target in zip(rows, budgets):
            stats = by_group[row["group"]]
            stats[0] += row["current_n"]
            stats[1] += row["analog_n"]
            stats[2] += n_target
        for group, (cur, analog, budget) in by_group.items():
            print(
                f"  [{tag_fill}] {group:28} source={cur:4} analog={analog:4} budget={budget:4}",
                flush=True,
            )
        for row, n_target in zip(rows, budgets):
            entry = map_capability_from_existing(
                row["cap"],
                row["previous"],
                attack_index,
                use_examples,
                hybrid_fill,
                fill_version=fill_version,
                n_target=n_target,
                prefetched=(row["candidates"], row["examples"]),
            )
            entries_by_group[row["cap"].capability_group].append(entry)
    else:
        already_done: dict[str, dict] = {}
        if from_dir is None and out_dir.is_dir():
            try:
                already_done = load_existing_entries(out_dir)
            except (FileNotFoundError, json.JSONDecodeError, ValueError):
                already_done = {}
            if already_done:
                print(f"  [resume] {len(already_done)} capacités déjà présentes dans {out_dir.name}")
        for i, cap in enumerate(capabilities, start=1):
            print(f"[{i:3}/{len(capabilities)}] {cap.capability_id}", flush=True)
            if existing_index is not None:
                vid = normalize_veris_id(cap.capability_id)
                previous = existing_index.get(vid)
                if previous is None:
                    missing += 1
                    print(f"    [WARN] pas d'entrée v2 pour {vid}", flush=True)
                    previous = {
                        "veris_id": vid,
                        "mitre_mappings": [],
                        "no_mapping_found": True,
                        "notes": "Absente de la run source.",
                    }
                entry = map_capability_from_existing(
                    cap,
                    previous,
                    attack_index,
                    use_examples,
                    hybrid_fill,
                    fill_version=fill_version,
                )
            else:
                vid = normalize_veris_id(cap.capability_id)
                previous = already_done.get(vid)
                notes_prev = (previous or {}).get("notes") or ""
                if previous is not None and not notes_prev.startswith("Erreur"):
                    print("    [skip] déjà généré", flush=True)
                    entry = previous
                else:
                    entry = map_capability(
                        cap,
                        attack_index,
                        use_examples,
                        model_id,
                        hybrid_fill=hybrid_fill,
                        fill_version=fill_version,
                    )
            entries_by_group[cap.capability_group].append(entry)
            if from_dir is None:
                write_results(entries_by_group, out_dir, quiet=True)

    if missing:
        print(f"  [WARN] {missing} capacités absentes du dossier source.")
    print("\nÉcriture des fichiers :")
    write_results(entries_by_group, out_dir)
    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Génère le mapping RAG multi-LLM VERIS -> ATT&CK."
    )
    parser.add_argument(
        "--mode",
        choices=["attack_only", "with_examples", "both"],
        default="with_examples",
        help="Variante de retrieval (défaut: with_examples).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Id du modèle LLM (défaut: premier de RAG_MULTI_LLM_MODELS).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de capacités (test rapide).",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Suffixe de dossier de sortie (ex: v2) pour ne pas écraser une run précédente.",
    )
    parser.add_argument(
        "--hybrid-fill",
        action="store_true",
        help="Complète la décision LLM avec les IDs analogiques omis (v3/v4).",
    )
    parser.add_argument(
        "--hybrid-version",
        choices=[
            "v3",
            "v4",
            "v5",
            "v6",
            "v7",
            "v8",
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
        ],
        default=None,
        help="Version du fill analogique (défaut: v3, ou RAG_HYBRID_FILL_VERSION).",
    )
    parser.add_argument(
        "--from-dir",
        type=Path,
        default=None,
        help="Dossier d'une run existante (ex. Llama v2) : pas d'appel LLM, fill local.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hybrid_fill = args.hybrid_fill or config.HYBRID_FILL
    fill_version = (args.hybrid_version or config.HYBRID_FILL_VERSION or "v3").lower()
    from_dir = args.from_dir.resolve() if args.from_dir else None
    if from_dir and not from_dir.is_dir():
        raise SystemExit(f"Dossier source introuvable : {from_dir}")

    needs_api = from_dir is None and fill_version not in {"v13", "v14"}
    config.validate_config(require_api=needs_api)

    model_id = (args.model or config.TOGETHER_CHAT_MODEL).strip()
    if not model_id:
        raise SystemExit("Aucun modèle : passez --model ou RAG_MULTI_LLM_MODELS.")

    modes = ["attack_only", "with_examples"] if args.mode == "both" else [args.mode]
    for mode in modes:
        run_mode(
            mode,
            model_id,
            args.limit,
            tag=args.tag,
            hybrid_fill=hybrid_fill,
            from_dir=from_dir,
            fill_version=fill_version,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
