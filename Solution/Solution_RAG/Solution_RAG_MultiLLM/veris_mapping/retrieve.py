"""Récupération de contexte pour une capacité VERIS.

- `retrieve_techniques` : top-k techniques ATT&CK candidates (collection ATT&CK).
- `retrieve_examples`   : top-m mappings experts similaires (anciennes versions).
- `merge_candidates_with_examples` : union retrieval ∪ IDs issus des exemples.

`retrieve_examples` n'est appelé que par la variante de RAG "avec exemples".
"""

from __future__ import annotations

import json

import config
from embeddings import embed_query
from vectorstore import get_collection, query


def retrieve_techniques(query_text: str, top_k: int | None = None) -> list[dict]:
    top_k = top_k or config.TOP_K_TECHNIQUES
    collection = get_collection(config.ATTACK_COLLECTION)
    embedding = embed_query(query_text)
    hits = query(collection, embedding, top_k=top_k)

    candidates = []
    for hit in hits:
        meta = hit.get("metadata", {})
        candidates.append(
            {
                "attack_id": meta.get("attack_id", hit.get("id", "")),
                "name": meta.get("name", ""),
                "tactics": [t for t in (meta.get("tactics") or "").split(",") if t],
                "is_subtechnique": bool(meta.get("is_subtechnique")),
                "parent_id": meta.get("parent_id") or None,
                "distance": hit.get("distance"),
                "document": hit.get("document", ""),
            }
        )
    return candidates


def retrieve_examples(
    query_text: str,
    top_m: int | None = None,
    group: str | None = None,
) -> list[dict]:
    top_m = top_m or config.TOP_M_EXAMPLES
    collection = get_collection(config.EXAMPLES_COLLECTION)
    if collection.count() == 0:
        return []
    n_hits = min(top_m, max(1, collection.count()))
    embedding = embed_query(query_text)
    where = {"capability_group": group} if group else None
    try:
        hits = query(collection, embedding, top_k=n_hits, where=where)
        if where and not hits:
            hits = query(collection, embedding, top_k=n_hits)
    except Exception:
        hits = query(collection, embedding, top_k=n_hits)

    examples = []
    for hit in hits:
        meta = hit.get("metadata", {})
        try:
            mapped = json.loads(meta.get("mapped_json", "[]"))
        except json.JSONDecodeError:
            mapped = []
        hit_id = str(hit.get("id") or "")
        capability_id = ""
        if "::" in hit_id:
            capability_id = hit_id.split("::", 1)[1]
        examples.append(
            {
                "source_version": meta.get("source_version", ""),
                "capability_id": capability_id,
                "capability_group": meta.get("capability_group", ""),
                "label": meta.get("label", ""),
                "mapped": mapped,
                "mapped_summary": meta.get("mapped_summary", ""),
                "distance": hit.get("distance"),
            }
        )
    return examples


def merge_candidates_with_examples(
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    max_candidates: int | None = None,
) -> list[dict]:
    """Union retrieval ∪ techniques des exemples experts (dédupliquée).

    Les IDs issus des exemples absents du top-k sont ajoutés en fin de liste,
    enrichis depuis le catalogue ATT&CK local. Plafond : MAX_PROMPT_CANDIDATES.
    """
    max_candidates = max_candidates or config.MAX_PROMPT_CANDIDATES
    merged: list[dict] = []
    seen: set[str] = set()

    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid in seen:
            continue
        entry = dict(cand)
        entry["attack_id"] = aid
        # Complète la description depuis le catalogue si absente.
        if not (entry.get("document") or entry.get("description")) and aid in attack_index:
            tech = attack_index[aid]
            entry["document"] = tech.document_text()
            entry["description"] = tech.description
            if not entry.get("name"):
                entry["name"] = tech.name
            if not entry.get("tactics"):
                entry["tactics"] = list(tech.tactics)
        merged.append(entry)
        seen.add(aid)
        if len(merged) >= max_candidates:
            return merged

    for example in examples:
        for mapped in example.get("mapped") or []:
            aid = (mapped.get("attack_id") or "").strip().upper()
            if not aid or aid in seen:
                continue
            if aid not in attack_index:
                continue
            tech = attack_index[aid]
            merged.append(
                {
                    "attack_id": aid,
                    "name": tech.name or mapped.get("attack_name", ""),
                    "tactics": list(tech.tactics),
                    "is_subtechnique": tech.is_subtechnique,
                    "parent_id": tech.parent_id,
                    "distance": None,
                    "document": tech.document_text(),
                    "description": tech.description,
                    "from_example": True,
                }
            )
            seen.add(aid)
            if len(merged) >= max_candidates:
                return merged

    return merged


def _candidate_similarity(candidate: dict) -> float:
    dist = candidate.get("distance")
    if isinstance(dist, (int, float)):
        return 1.0 - float(dist)
    return 0.0


def example_support_ids(examples: list[dict], attack_index: dict) -> set[str]:
    """Identifiants ATT&CK présents dans les exemples experts récupérés."""
    ids: set[str] = set()
    for example in examples:
        for mapped in example.get("mapped") or []:
            aid = (mapped.get("attack_id") or "").strip().upper()
            if aid and aid in attack_index:
                ids.add(aid)
    return ids


def closest_example_ids(examples: list[dict], attack_index: dict) -> list[str]:
    """IDs de l'exemple expert le plus proche, dans l'ordre."""
    if not examples:
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for mapped in examples[0].get("mapped") or []:
        aid = (mapped.get("attack_id") or "").strip().upper()
        if not aid or aid in seen or aid not in attack_index:
            continue
        ids.append(aid)
        seen.add(aid)
    return ids


def hybrid_fill_max_add(
    group: str,
    n_chosen: int,
    examples: list[dict],
    attack_index: dict,
) -> int:
    """Budget d'ajouts v4 : rattraper la taille de l'exemple le plus proche, plafonné par scope."""
    scope_cap = config.HYBRID_SCOPE_MAX_ADD.get(group, config.HYBRID_MAX_ADD)
    analog_n = len(closest_example_ids(examples, attack_index))
    if analog_n == 0:
        analog_n = min(len(example_support_ids(examples, attack_index)), 6)
    remaining = max(0, analog_n - n_chosen)
    return min(scope_cap, remaining)


def hybrid_fill_decisions(
    chosen_ids: set[str],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    max_add: int | None = None,
    version: str = "v3",
    group: str = "",
) -> list[dict]:
    """Complète la décision LLM par analogie (v3–v9), sans nouvel appel API."""
    support = example_support_ids(examples, attack_index)
    closest = closest_example_ids(examples, attack_index)
    chosen = {aid.strip().upper() for aid in chosen_ids if aid}

    if version == "v4":
        if max_add is None:
            max_add = hybrid_fill_max_add(group, len(chosen), examples, attack_index)
        return _hybrid_fill_v4(chosen, candidates, support, attack_index, max_add)
    if version == "v5":
        return _hybrid_fill_v5(
            chosen, candidates, support, attack_index, group, max_add
        )
    if version == "v6":
        return _hybrid_fill_v6(
            chosen, candidates, support, closest, attack_index, group, max_add
        )
    if version == "v7":
        return _hybrid_fill_v7(chosen, candidates, support, attack_index, group, max_add)
    if version == "v8":
        return _hybrid_fill_v8(
            chosen, candidates, support, closest, attack_index, group, max_add
        )

    max_add = config.HYBRID_MAX_ADD if max_add is None else max_add
    return _hybrid_fill_v3(chosen, candidates, support, closest, attack_index, max_add)


def _hybrid_fill_v3(
    chosen: set[str],
    candidates: list[dict],
    support: set[str],
    closest: list[str],
    attack_index: dict,
    max_add: int,
) -> list[dict]:
    if max_add <= 0:
        return []
    additions: list[dict] = []
    ranked = sorted(
        candidates,
        key=lambda c: (
            (c.get("attack_id") or "").strip().upper() in support,
            _candidate_similarity(c),
        ),
        reverse=True,
    )
    for cand in ranked:
        if len(additions) >= max_add:
            return additions
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid in chosen or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        supported = aid in support
        high_sim = sim >= config.RETRIEVAL_SIM_HIGH
        if not supported and not high_sim:
            continue
        if not supported and sim < config.RETRIEVAL_SIM_MED:
            continue
        note = f"Complément v3 (sim={sim:.2f})."
        if supported:
            note += " Soutenu par un mapping expert d'une version proche."
        additions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high_sim else "medium",
                "justification": note,
            }
        )
        chosen.add(aid)

    for aid in closest:
        if len(additions) >= max_add:
            break
        if aid in chosen or aid not in attack_index:
            continue
        additions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "medium",
                "justification": "Complément v3 : suggéré par l'exemple expert le plus proche.",
            }
        )
        chosen.add(aid)
    return additions


def _hybrid_fill_v4(
    chosen: set[str],
    candidates: list[dict],
    support: set[str],
    attack_index: dict,
    max_add: int,
) -> list[dict]:
    """V4 : uniquement des IDs soutenus par un exemple + présents dans le top-k.

    Pas d'ajout 'similarité seule' ni 'exemple hors candidats' → moins de
    sur-génération sur social / value_chain. Budget = rattrapage analogique.
    """
    if max_add <= 0:
        return []
    additions: list[dict] = []
    ranked = sorted(
        (
            c
            for c in candidates
            if (c.get("attack_id") or "").strip().upper() in support
        ),
        key=_candidate_similarity,
        reverse=True,
    )
    for cand in ranked:
        if len(additions) >= max_add:
            break
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid in chosen or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        dist = cand.get("distance")
        if isinstance(dist, (int, float)) and sim < config.RETRIEVAL_SIM_MED:
            continue
        high_sim = sim >= config.RETRIEVAL_SIM_HIGH
        additions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high_sim else "medium",
                "justification": (
                    f"Complément v4 (sim={sim:.2f}). "
                    "Soutenu par un mapping expert d'une version proche."
                ),
            }
        )
        chosen.add(aid)
    return additions


def _family_ids(attack_id: str, attack_index: dict) -> set[str]:
    """Parent + sous-techniques de la même famille ATT&CK."""
    tech = attack_index.get(attack_id)
    if tech is None:
        return set()
    family: set[str] = {attack_id}
    parent = (tech.parent_id or "").strip().upper() if tech.is_subtechnique else attack_id
    if parent:
        family.add(parent)
    for other_id, other in attack_index.items():
        if other.is_subtechnique and (other.parent_id or "").strip().upper() == parent:
            family.add(other_id.strip().upper())
    return family


def _hybrid_fill_v5(
    chosen: set[str],
    candidates: list[dict],
    support: set[str],
    attack_index: dict,
    group: str,
    max_add: int | None,
) -> list[dict]:
    """V5 : fill agressif sur les scopes sous-générés + expansion famille ATT&CK.

    - aucun ajout sur social / value_chain (déjà trop de paires en v2)
    - IDs analogiques (exemples) ou haute similarité
    - si Llama a choisi Txxxx, on peut ajouter parent/sous-techniques candidates
      soutenues par un exemple
    """
    if group in config.HYBRID_V5_SKIP_SCOPES:
        return []
    if max_add is None:
        max_add = config.HYBRID_V5_MAX_ADD.get(group, config.HYBRID_MAX_ADD)
    if max_add <= 0:
        return []

    related: set[str] = set()
    for aid in list(chosen):
        related |= _family_ids(aid, attack_index)

    ranked = sorted(
        candidates,
        key=lambda c: (
            (c.get("attack_id") or "").strip().upper() in support,
            (c.get("attack_id") or "").strip().upper() in related,
            _candidate_similarity(c),
        ),
        reverse=True,
    )
    additions: list[dict] = []
    for cand in ranked:
        if len(additions) >= max_add:
            break
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid in chosen or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        supported = aid in support
        in_family = aid in related
        high_sim = sim >= config.RETRIEVAL_SIM_HIGH
        if not (supported or in_family or high_sim):
            continue
        if in_family and not supported:
            dist = cand.get("distance")
            if isinstance(dist, (int, float)) and sim < config.RETRIEVAL_SIM_MED:
                continue
        if not supported and not in_family and not high_sim:
            continue
        reasons = []
        if supported:
            reasons.append("exemple expert")
        if in_family:
            reasons.append("famille ATT&CK")
        if high_sim:
            reasons.append(f"sim={sim:.2f}")
        additions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high_sim or supported else "medium",
                "justification": "Complément v5 (" + ", ".join(reasons) + ").",
            }
        )
        chosen.add(aid)
        related |= _family_ids(aid, attack_index)
    return additions


def _hybrid_fill_v6(
    chosen: set[str],
    candidates: list[dict],
    support: set[str],
    closest: list[str],
    attack_index: dict,
    group: str,
    max_add: int | None,
) -> list[dict]:
    """V6 : fill analogique v3, mais sans toucher aux scopes déjà sur-générés.

    Pas d'expansion famille (échec v5). social / value_chain restent en Llama v2.
    """
    if group in config.HYBRID_V5_SKIP_SCOPES:
        return []
    if max_add is None:
        max_add = config.HYBRID_V6_MAX_ADD.get(group, config.HYBRID_MAX_ADD)
    return _hybrid_fill_v3(
        chosen, candidates, support, closest, attack_index, max_add
    )


def _hybrid_fill_v7(
    chosen: set[str],
    candidates: list[dict],
    support: set[str],
    attack_index: dict,
    group: str,
    max_add: int | None,
) -> list[dict]:
    """V7 : skips v6 + uniquement analogie (exemples ∩ candidats).

    Pas de similarité seule ni d'exemple hors top-k. Budget plus haut sur
    hacking / confidentiality (encore sous-générés), plus bas sur malware.
    """
    if group in config.HYBRID_V5_SKIP_SCOPES:
        return []
    if max_add is None:
        max_add = config.HYBRID_V7_MAX_ADD.get(group, config.HYBRID_MAX_ADD)
    return _hybrid_fill_v4(chosen, candidates, support, attack_index, max_add)


def _hybrid_fill_v8(
    chosen: set[str],
    candidates: list[dict],
    support: set[str],
    closest: list[str],
    attack_index: dict,
    group: str,
    max_add: int | None,
) -> list[dict]:
    """V8 : base v6 + 2e passe analogique sur hacking / confidentiality.

    La v6 plafonne à 5–8 ajouts mixtes ; le 2e passage n'ajoute que des IDs
    déjà vus dans les exemples experts et encore absents, pour remonter le
    rappel sans réintroduire la famille ATT&CK (échec v5).
    """
    additions = _hybrid_fill_v6(
        chosen, candidates, support, closest, attack_index, group, max_add
    )
    extra_cap = config.HYBRID_V8_EXTRA_ADD.get(group, 0)
    if extra_cap <= 0:
        return additions
    extra = _hybrid_fill_v4(
        chosen, candidates, support, attack_index, extra_cap
    )
    return additions + extra


def rerank_keep_n(
    current_ids: list[str],
    hybrid_ids: set[str],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
) -> list[dict]:
    """V9 : garde exactement N mappings, remplace les plus faibles du pool.

    Score : exemple expert > exemple le plus proche > similarité haute > LLM
    d'origine > complément déjà retenu. Le volume N (celui de la v8) est
    conservé ; seuls les identifiants changent.
    """
    n_target = len(current_ids)
    if n_target == 0:
        return []

    support = example_support_ids(examples, attack_index)
    closest = closest_example_ids(examples, attack_index)
    current_set = {aid.strip().upper() for aid in current_ids if aid}
    hybrid_norm = {aid.strip().upper() for aid in hybrid_ids if aid}

    sims: dict[str, float] = {}
    pool: set[str] = set(current_set)
    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        sims[aid] = max(sim, sims.get(aid, 0.0))
        if (
            aid in support
            or aid in closest
            or aid in current_set
            or sim >= config.RETRIEVAL_SIM_MED
        ):
            pool.add(aid)
    for aid in closest:
        if aid in attack_index:
            pool.add(aid)
            sims.setdefault(aid, 0.0)

    def score(aid: str) -> tuple[float, float]:
        sim = sims.get(aid, 0.0)
        value = 0.0
        if aid in support:
            value += 3.0
        if aid in closest:
            value += 2.0
        if sim >= config.RETRIEVAL_SIM_HIGH:
            value += 2.0
        elif sim >= config.RETRIEVAL_SIM_MED:
            value += 1.0
        if aid in current_set and aid not in hybrid_norm:
            value += 1.5
        elif aid in current_set:
            value += 0.3
        return (value, sim)

    ranked = sorted(pool, key=score, reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for aid in ranked:
        if aid in seen:
            continue
        selected.append(aid)
        seen.add(aid)
        if len(selected) >= n_target:
            break
    for aid in current_ids:
        if len(selected) >= n_target:
            break
        aid = aid.strip().upper()
        if aid and aid not in seen and aid in attack_index:
            selected.append(aid)
            seen.add(aid)

    decisions: list[dict] = []
    for aid in selected:
        sim = sims.get(aid, 0.0)
        reasons = []
        if aid in support:
            reasons.append("exemple")
        if aid in closest:
            reasons.append("exemple proche")
        if sim >= config.RETRIEVAL_SIM_HIGH:
            reasons.append(f"sim={sim:.2f}")
        if aid in current_set and aid not in hybrid_norm:
            reasons.append("LLM")
        note = "Reclassement v9 (N constant"
        if reasons:
            note += ", " + ", ".join(reasons)
        note += ")."
        high_sim = sim >= config.RETRIEVAL_SIM_HIGH
        decisions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if (high_sim or aid in support) else "medium",
                "justification": note,
            }
        )
    return decisions


def _example_similarity(example: dict) -> float:
    dist = example.get("distance")
    if isinstance(dist, (int, float)):
        return max(0.05, min(1.0, 1.0 - float(dist)))
    return 0.35


def examples_for_group(examples: list[dict], group: str) -> list[dict]:
    """Garde les exemples du même capability_group ; sinon fallback tous."""
    group_l = (group or "").strip().lower()
    if not group_l:
        return list(examples)
    same = [
        example
        for example in examples
        if (example.get("capability_group") or "").strip().lower() == group_l
    ]
    return same or list(examples)


def analog_budget_n(examples: list[dict], attack_index: dict, group: str) -> int:
    """Taille analogique : IDs de l'exemple le plus proche du même groupe."""
    scoped = examples_for_group(examples, group)
    analog_n = len(closest_example_ids(scoped, attack_index))
    if analog_n == 0:
        analog_n = min(len(example_support_ids(scoped, attack_index)), 8)
    return analog_n


def weighted_example_support(
    examples: list[dict], attack_index: dict
) -> dict[str, float]:
    """Poids analogique = somme des similarités des exemples qui contiennent l'ID."""
    weights: dict[str, float] = {}
    for example in examples:
        sim = _example_similarity(example)
        for mapped in example.get("mapped") or []:
            aid = (mapped.get("attack_id") or "").strip().upper()
            if aid and aid in attack_index:
                weights[aid] = weights.get(aid, 0.0) + sim
    return weights


def _parent_id(aid: str, attack_index: dict) -> str | None:
    tech = attack_index.get(aid)
    if tech and getattr(tech, "is_subtechnique", False):
        parent = (tech.parent_id or "").strip().upper()
        return parent or None
    if "." in aid:
        return aid.split(".", 1)[0]
    return None


def _tactic_score(aid: str, group: str, attack_index: dict) -> float:
    allowed = config.HYBRID_V10_SCOPE_TACTICS.get(group)
    if not allowed:
        return 0.0
    tech = attack_index.get(aid)
    if not tech or not tech.tactics:
        return 0.0
    allowed_l = {t.lower() for t in allowed}
    tactics = {str(t).strip().lower() for t in tech.tactics if t}
    if tactics & allowed_l:
        return 1.0
    return -0.8


def _family_allows(
    aid: str,
    selected: list[str],
    analog: set[str],
    attack_index: dict,
) -> bool:
    """Refuse parent+enfants hors analogie, et les sœurs non analogiques."""
    parent = _parent_id(aid, attack_index)
    analog_children: dict[str, set[str]] = {}
    for analog_id in analog:
        analog_parent = _parent_id(analog_id, attack_index)
        if analog_parent:
            analog_children.setdefault(analog_parent, set()).add(analog_id)

    if parent:
        if parent in analog_children and aid not in analog and aid not in analog_children[parent]:
            return False
        if parent in selected and not (parent in analog and aid in analog):
            return False
        return True

    selected_children = [sid for sid in selected if _parent_id(sid, attack_index) == aid]
    if selected_children and aid not in analog:
        return False
    if aid in analog_children and aid not in analog:
        return False
    return True


def allocate_v10_budgets(
    analog_ns: list[int],
    current_ns: list[int],
    groups: list[str],
    target_global: int,
) -> list[int]:
    """Réalloue N par capacité : analogique local, somme globale constante.

    Les scopes shrink restent à la taille analogique (pas de scale-up).
    Le reliquat va aux autres scopes, prioritairement grow.
    """
    n_caps = len(analog_ns)
    if n_caps == 0:
        return []
    target_global = max(0, int(target_global))
    desired: list[int] = []
    locked: list[bool] = []
    for analog_n, current_n, group in zip(analog_ns, current_ns, groups):
        shrink = group in config.HYBRID_V10_SHRINK_SCOPES
        if shrink:
            n = analog_n
        elif analog_n > 0:
            n = analog_n
        else:
            n = current_n
        max_mult = config.HYBRID_V10_SCOPE_MAX_MULT.get(group, 2.0)
        if current_n > 0 and not shrink:
            n = min(n, max(current_n, int(round(current_n * max_mult))))
        desired.append(max(0, int(n)))
        locked.append(shrink)

    if target_global == 0:
        return [0] * n_caps
    if sum(desired) == 0:
        return list(current_ns)

    budgets = [0] * n_caps
    for i, (n, is_locked) in enumerate(zip(desired, locked)):
        if is_locked:
            budgets[i] = n
    remaining = target_global - sum(budgets)
    free = [i for i, is_locked in enumerate(locked) if not is_locked]
    if remaining < 0:
        order = sorted(range(n_caps), key=lambda i: (0 if locked[i] else 1, -budgets[i]))
        for idx in order:
            if remaining >= 0:
                break
            take = min(budgets[idx], -remaining)
            budgets[idx] -= take
            remaining += take
        return budgets
    free_desired = sum(desired[i] for i in free) or 1
    scaled = [desired[i] * remaining / free_desired for i in free]
    for idx, value in zip(free, scaled):
        budgets[idx] = int(round(value))
    drift = target_global - sum(budgets)

    def _grow_key(idx: int) -> tuple[int, float, int]:
        grow_rank = 0 if groups[idx] in config.HYBRID_V10_GROW_SCOPES else 1
        remainder = 0.0
        if idx in free:
            pos = free.index(idx)
            remainder = scaled[pos] - budgets[idx]
        return (grow_rank, -remainder, -analog_ns[idx])

    def _shrink_key(idx: int) -> tuple[int, int]:
        shrink_rank = 0 if groups[idx] in config.HYBRID_V10_SHRINK_SCOPES else 1
        return (shrink_rank, -budgets[idx])

    while drift != 0:
        if drift > 0:
            order = sorted(
                [i for i in (free or range(n_caps)) if analog_ns[i] > 0 or current_ns[i] > 0]
                or list(range(n_caps)),
                key=_grow_key,
            )
            budgets[order[0]] += 1
            drift -= 1
        else:
            order = sorted(
                [i for i in range(n_caps) if budgets[i] > 0],
                key=_shrink_key,
            )
            if not order:
                break
            budgets[order[0]] -= 1
            drift += 1
    return budgets


def rerank_v10(
    current_ids: list[str],
    hybrid_ids: set[str],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    group: str = "",
    n_target: int | None = None,
) -> list[dict]:
    """V10 : budget analogique, support pondéré, dédup famille, prior tactique."""
    current_set = {aid.strip().upper() for aid in current_ids if aid}
    hybrid_norm = {aid.strip().upper() for aid in hybrid_ids if aid}
    scoped = examples_for_group(examples, group)
    analog = set(closest_example_ids(scoped, attack_index))
    support_w = weighted_example_support(scoped, attack_index)
    if n_target is None:
        n_target = analog_budget_n(examples, attack_index, group) or len(current_ids)
    n_target = max(0, int(n_target))
    if n_target == 0:
        return []

    sims: dict[str, float] = {}
    pool: set[str] = set(current_set)
    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        sims[aid] = max(sim, sims.get(aid, 0.0))
        if aid in support_w or aid in analog or aid in current_set or sim >= config.RETRIEVAL_SIM_MED:
            pool.add(aid)
    for aid in list(support_w) + list(analog):
        if aid in attack_index:
            pool.add(aid)
            sims.setdefault(aid, 0.0)

    def score(aid: str) -> tuple[float, float]:
        sim = sims.get(aid, 0.0)
        value = 0.0
        value += 2.2 * support_w.get(aid, 0.0)
        if aid in analog:
            value += 2.0
        if sim >= config.RETRIEVAL_SIM_HIGH:
            value += 2.0
        elif sim >= config.RETRIEVAL_SIM_MED:
            value += 1.0
        if aid in current_set and aid not in hybrid_norm:
            value += 1.0
        elif aid in current_set:
            value += 0.2
        value += _tactic_score(aid, group, attack_index)
        return (value, sim)

    ranked = sorted(pool, key=score, reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for aid in ranked:
        if aid in seen:
            continue
        if not _family_allows(aid, selected, analog, attack_index):
            continue
        selected.append(aid)
        seen.add(aid)
        if len(selected) >= n_target:
            break
    for aid in ranked:
        if len(selected) >= n_target:
            break
        if aid in seen:
            continue
        selected.append(aid)
        seen.add(aid)
    for aid in current_ids:
        if len(selected) >= n_target:
            break
        aid = aid.strip().upper()
        if aid and aid not in seen and aid in attack_index:
            selected.append(aid)
            seen.add(aid)

    decisions: list[dict] = []
    for aid in selected:
        sim = sims.get(aid, 0.0)
        weight = support_w.get(aid, 0.0)
        reasons = []
        if aid in analog:
            reasons.append("exemple proche")
        if weight > 0:
            reasons.append(f"support={weight:.2f}")
        if sim >= config.RETRIEVAL_SIM_HIGH:
            reasons.append(f"sim={sim:.2f}")
        if aid in current_set and aid not in hybrid_norm:
            reasons.append("LLM")
        tactic = _tactic_score(aid, group, attack_index)
        if tactic > 0:
            reasons.append("tactique")
        elif tactic < 0:
            reasons.append("hors-tactique")
        note = "Reclassement v10 (budget analogique"
        if reasons:
            note += ", " + ", ".join(reasons)
        note += ")."
        high = sim >= config.RETRIEVAL_SIM_HIGH or weight >= 0.8 or aid in analog
        decisions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high else "medium",
                "justification": note,
            }
        )
    return decisions


def _norm_label(raw: str) -> str:
    text = (raw or "").strip().lower().replace("-", " ").replace("_", " ")
    return " ".join(text.split())


def _kind_from_id(capability_id: str) -> str:
    parts = [p.lower().replace("-", "_") for p in (capability_id or "").split(".")]
    for part in parts:
        if part in {"variety", "vector"}:
            return part
    return ""


def is_skip_label(label: str) -> bool:
    return _norm_label(label) in config.HYBRID_V11_SKIP_LABELS


def examples_for_label(
    examples: list[dict],
    group: str,
    label: str,
    capability_id: str = "",
) -> list[dict]:
    """Exemples du même groupe + même label (+ variety/vector si dispo)."""
    group_l = (group or "").strip().lower()
    label_n = _norm_label(label)
    kind = _kind_from_id(capability_id)
    if not group_l or not label_n:
        return []
    matched: list[dict] = []
    for example in examples:
        if (example.get("capability_group") or "").strip().lower() != group_l:
            continue
        if _norm_label(example.get("label") or "") != label_n:
            continue
        if kind:
            example_kind = _kind_from_id(example.get("capability_id") or "")
            if example_kind and example_kind != kind:
                continue
        matched.append(example)
    return matched


def analog_union_ids(
    examples: list[dict],
    attack_index: dict,
    max_examples: int | None = None,
) -> list[str]:
    """Union des IDs des K exemples same-label les plus proches.

    max_examples < 0 : tous les exemples fournis (v12).
    """
    if max_examples is None:
        max_examples = config.HYBRID_V11_ANALOG_EXAMPLES
    pool = examples if max_examples < 0 else examples[: max(0, max_examples)]
    ids: list[str] = []
    seen: set[str] = set()
    for example in pool:
        for mapped in example.get("mapped") or []:
            aid = (mapped.get("attack_id") or "").strip().upper()
            if not aid or aid in seen or aid not in attack_index:
                continue
            ids.append(aid)
            seen.add(aid)
    return ids


def _narrow_family(analog: set[str], attack_index: dict) -> set[str]:
    """Si l'analogue a des enfants, retire le parent (évite parent+famille)."""
    children_by_parent: dict[str, set[str]] = {}
    for aid in analog:
        parent = _parent_id(aid, attack_index)
        if parent:
            children_by_parent.setdefault(parent, set()).add(aid)
    narrowed: set[str] = set()
    for aid in analog:
        parent = _parent_id(aid, attack_index)
        if parent is None and aid in children_by_parent:
            continue
        narrowed.add(aid)
    return narrowed


def analog_budget_n_v11(
    examples: list[dict],
    attack_index: dict,
    group: str,
    label: str = "",
    capability_id: str = "",
) -> int:
    """Taille analogique v11 : union same-label, 0 si Unknown/Other sans analogue."""
    skip = is_skip_label(label)
    same = examples_for_label(examples, group, label, capability_id)
    analog = _narrow_family(set(analog_union_ids(same, attack_index)), attack_index)
    if analog:
        return len(analog)
    if skip:
        return 0
    return 0


def allocate_v11_budgets(
    analog_ns: list[int],
    current_ns: list[int],
    groups: list[str],
    target_global: int,
) -> list[int]:
    """N = taille analogique same-label ; pas de padding si l'analogue est plus petit."""
    n_caps = len(analog_ns)
    if n_caps == 0:
        return []
    desired = [max(0, int(n)) for n in analog_ns]
    analog_sum = sum(desired)
    if analog_sum == 0:
        return [0] * n_caps
    cap = max(0, int(target_global))
    if analog_sum <= cap:
        return desired
    scaled = [n * cap / analog_sum for n in desired]
    budgets = [int(round(value)) for value in scaled]
    drift = cap - sum(budgets)
    while drift != 0:
        if drift > 0:
            order = sorted(
                range(n_caps),
                key=lambda i: (
                    0 if groups[i] in config.HYBRID_V10_GROW_SCOPES else 1,
                    scaled[i] - budgets[i],
                    -analog_ns[i],
                ),
            )
            budgets[order[0]] += 1
            drift -= 1
        else:
            order = sorted(
                [i for i in range(n_caps) if budgets[i] > 0],
                key=lambda i: (
                    0 if groups[i] in config.HYBRID_V10_SHRINK_SCOPES else 1,
                    -budgets[i],
                ),
            )
            if not order:
                break
            budgets[order[0]] -= 1
            drift += 1
    return budgets


def _family_allows_v11(
    aid: str,
    selected: list[str],
    analog: set[str],
    attack_index: dict,
) -> bool:
    """Refuse parent si un enfant est déjà pris / dans l'analogue, et les sœurs hors analogue."""
    parent = _parent_id(aid, attack_index)
    analog_children: dict[str, set[str]] = {}
    for analog_id in analog:
        analog_parent = _parent_id(analog_id, attack_index)
        if analog_parent:
            analog_children.setdefault(analog_parent, set()).add(analog_id)

    if parent:
        if parent in analog_children and aid not in analog_children[parent]:
            return False
        if parent in selected:
            return False
        return True

    selected_children = [sid for sid in selected if _parent_id(sid, attack_index) == aid]
    if selected_children:
        return False
    if aid in analog_children:
        return False
    return True


def rerank_v11(
    current_ids: list[str],
    hybrid_ids: set[str],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    group: str = "",
    label: str = "",
    capability_id: str = "",
    n_target: int | None = None,
) -> list[dict]:
    """V11 : same-label, union analogique, famille stricte, pas de pad hors-tactique."""
    same = examples_for_label(examples, group, label, capability_id)
    analog = _narrow_family(set(analog_union_ids(same, attack_index)), attack_index)
    support_w = weighted_example_support(same, attack_index)
    if n_target is None:
        n_target = analog_budget_n_v11(
            examples, attack_index, group, label, capability_id
        )
    n_target = max(0, int(n_target))
    if n_target == 0 or not analog:
        return []

    sims: dict[str, float] = {}
    pool: set[str] = set(analog)
    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        sims[aid] = max(sim, sims.get(aid, 0.0))
        if aid in analog or aid in support_w or sim >= config.RETRIEVAL_SIM_HIGH:
            pool.add(aid)
    for aid in analog:
        sims.setdefault(aid, 0.0)

    current_set = {aid.strip().upper() for aid in current_ids if aid}

    def score(aid: str) -> tuple[float, float]:
        sim = sims.get(aid, 0.0)
        value = 0.0
        value += 2.2 * support_w.get(aid, 0.0)
        if aid in analog:
            value += 3.0
        if sim >= config.RETRIEVAL_SIM_HIGH:
            value += 1.5
        elif sim >= config.RETRIEVAL_SIM_MED:
            value += 0.5
        value += _tactic_score(aid, group, attack_index)
        if aid in current_set:
            value += 0.2
        return (value, sim)

    ranked = sorted(pool, key=score, reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for aid in ranked:
        if aid in seen:
            continue
        if aid not in analog and _tactic_score(aid, group, attack_index) < 0:
            continue
        if not _family_allows_v11(aid, selected, analog, attack_index):
            continue
        selected.append(aid)
        seen.add(aid)
        if len(selected) >= n_target:
            break

    decisions: list[dict] = []
    for aid in selected:
        sim = sims.get(aid, 0.0)
        weight = support_w.get(aid, 0.0)
        reasons = []
        if aid in analog:
            reasons.append("same-label")
        if weight > 0:
            reasons.append(f"support={weight:.2f}")
        if sim >= config.RETRIEVAL_SIM_HIGH:
            reasons.append(f"sim={sim:.2f}")
        tactic = _tactic_score(aid, group, attack_index)
        if tactic > 0:
            reasons.append("tactique")
        elif tactic < 0:
            reasons.append("hors-tactique")
        note = "Reclassement v11 (same-label"
        if reasons:
            note += ", " + ", ".join(reasons)
        note += ")."
        high = aid in analog or weight >= 0.8 or sim >= config.RETRIEVAL_SIM_HIGH
        decisions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high else "medium",
                "justification": note,
            }
        )
    return decisions


def analog_budget_n_v12(
    examples: list[dict],
    attack_index: dict,
    group: str,
    label: str = "",
    capability_id: str = "",
) -> int:
    """Taille analogique v12 : 0 si Unknown/Other, sinon union de tous les same-label."""
    if is_skip_label(label):
        return 0
    same = examples_for_label(examples, group, label, capability_id)
    analog = set(analog_union_ids(same, attack_index, max_examples=-1))
    return len(analog)


def _family_allows_v12(
    aid: str,
    selected: list[str],
    analog: set[str],
    attack_index: dict,
) -> bool:
    """Garde le parent s'il est analogique, même avec des enfants ; refuse les sœurs hors analogue."""
    parent = _parent_id(aid, attack_index)
    analog_children: dict[str, set[str]] = {}
    for analog_id in analog:
        analog_parent = _parent_id(analog_id, attack_index)
        if analog_parent:
            analog_children.setdefault(analog_parent, set()).add(analog_id)

    if parent:
        if parent in analog_children and aid not in analog:
            return False
        return True

    if aid in analog:
        return True
    selected_children = [sid for sid in selected if _parent_id(sid, attack_index) == aid]
    if selected_children:
        return False
    if aid in analog_children:
        return False
    return True


def rerank_v12(
    current_ids: list[str],
    hybrid_ids: set[str],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    group: str = "",
    label: str = "",
    capability_id: str = "",
    n_target: int | None = None,
) -> list[dict]:
    """V12 : same-label union complète, parent conservé, skip Unknown, pas de pad."""
    if is_skip_label(label):
        return []
    same = examples_for_label(examples, group, label, capability_id)
    analog = set(analog_union_ids(same, attack_index, max_examples=-1))
    support_w = weighted_example_support(same, attack_index)
    if n_target is None:
        n_target = analog_budget_n_v12(
            examples, attack_index, group, label, capability_id
        )
    n_target = max(0, int(n_target))
    if n_target == 0 or not analog:
        return []

    sims: dict[str, float] = {}
    pool: set[str] = set(analog)
    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        sims[aid] = max(sim, sims.get(aid, 0.0))
        if aid in analog or aid in support_w or sim >= config.RETRIEVAL_SIM_HIGH:
            pool.add(aid)
    for aid in analog:
        sims.setdefault(aid, 0.0)

    current_set = {aid.strip().upper() for aid in current_ids if aid}

    def score(aid: str) -> tuple[float, float]:
        sim = sims.get(aid, 0.0)
        value = 0.0
        value += 2.2 * support_w.get(aid, 0.0)
        if aid in analog:
            value += 3.0
        if sim >= config.RETRIEVAL_SIM_HIGH:
            value += 1.5
        elif sim >= config.RETRIEVAL_SIM_MED:
            value += 0.5
        value += _tactic_score(aid, group, attack_index)
        if aid in current_set:
            value += 0.2
        return (value, sim)

    ranked = sorted(pool, key=score, reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for aid in ranked:
        if aid in seen:
            continue
        if aid not in analog and _tactic_score(aid, group, attack_index) < 0:
            continue
        if not _family_allows_v12(aid, selected, analog, attack_index):
            continue
        selected.append(aid)
        seen.add(aid)
        if len(selected) >= n_target:
            break

    decisions: list[dict] = []
    for aid in selected:
        sim = sims.get(aid, 0.0)
        weight = support_w.get(aid, 0.0)
        reasons = []
        if aid in analog:
            reasons.append("same-label")
        if weight > 0:
            reasons.append(f"support={weight:.2f}")
        if sim >= config.RETRIEVAL_SIM_HIGH:
            reasons.append(f"sim={sim:.2f}")
        tactic = _tactic_score(aid, group, attack_index)
        if tactic > 0:
            reasons.append("tactique")
        note = "Reclassement v12 (same-label union"
        if reasons:
            note += ", " + ", ".join(reasons)
        note += ")."
        high = aid in analog or weight >= 0.8 or sim >= config.RETRIEVAL_SIM_HIGH
        decisions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high else "medium",
                "justification": note,
            }
        )
    return decisions


def analog_budget_n_v13(
    examples: list[dict],
    attack_index: dict,
    group: str,
    label: str = "",
    capability_id: str = "",
) -> int:
    """Taille analogique v13 : union same-label, y compris Unknown/Other."""
    same = examples_for_label(examples, group, label, capability_id)
    analog = set(analog_union_ids(same, attack_index, max_examples=-1))
    return len(analog)


def rerank_v13(
    current_ids: list[str],
    hybrid_ids: set[str],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    group: str = "",
    label: str = "",
    capability_id: str = "",
    n_target: int | None = None,
) -> list[dict]:
    """V13 : union same-label y compris Unknown/Other, parent conservé, pas de pad."""
    same = examples_for_label(examples, group, label, capability_id)
    analog = set(analog_union_ids(same, attack_index, max_examples=-1))
    support_w = weighted_example_support(same, attack_index)
    if n_target is None:
        n_target = analog_budget_n_v13(
            examples, attack_index, group, label, capability_id
        )
    n_target = max(0, int(n_target))
    if n_target == 0 or not analog:
        return []

    sims: dict[str, float] = {}
    pool: set[str] = set(analog)
    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        sims[aid] = max(sim, sims.get(aid, 0.0))
        if aid in analog or aid in support_w or sim >= config.RETRIEVAL_SIM_HIGH:
            pool.add(aid)
    for aid in analog:
        sims.setdefault(aid, 0.0)

    current_set = {aid.strip().upper() for aid in current_ids if aid}

    def score(aid: str) -> tuple[float, float]:
        sim = sims.get(aid, 0.0)
        value = 0.0
        value += 2.2 * support_w.get(aid, 0.0)
        if aid in analog:
            value += 3.0
        if sim >= config.RETRIEVAL_SIM_HIGH:
            value += 1.5
        elif sim >= config.RETRIEVAL_SIM_MED:
            value += 0.5
        value += _tactic_score(aid, group, attack_index)
        if aid in current_set:
            value += 0.2
        return (value, sim)

    ranked = sorted(pool, key=score, reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for aid in ranked:
        if aid in seen:
            continue
        if aid not in analog and _tactic_score(aid, group, attack_index) < 0:
            continue
        if not _family_allows_v12(aid, selected, analog, attack_index):
            continue
        selected.append(aid)
        seen.add(aid)
        if len(selected) >= n_target:
            break

    decisions: list[dict] = []
    for aid in selected:
        sim = sims.get(aid, 0.0)
        weight = support_w.get(aid, 0.0)
        reasons = []
        if aid in analog:
            reasons.append("same-label")
        if weight > 0:
            reasons.append(f"support={weight:.2f}")
        if sim >= config.RETRIEVAL_SIM_HIGH:
            reasons.append(f"sim={sim:.2f}")
        tactic = _tactic_score(aid, group, attack_index)
        if tactic > 0:
            reasons.append("tactique")
        note = "Reclassement v13 (same-label union"
        if reasons:
            note += ", " + ", ".join(reasons)
        note += ")."
        high = aid in analog or weight >= 0.8 or sim >= config.RETRIEVAL_SIM_HIGH
        decisions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high else "medium",
                "justification": note,
            }
        )
    return decisions


# ---------------------------------------------------------------------------
# v14 : corpus same-label + remap ATT&CK (mises à jour de version) + discovery
# ---------------------------------------------------------------------------

_CORPUS_EXAMPLES: list[dict] | None = None
_NAME_TOKEN_INDEX: dict[str, set[str]] | None = None
_NAME_TOKEN_INDEX_KEY: int | None = None


def _name_tokens(raw: str) -> set[str]:
    import re

    text = (raw or "").lower()
    if ":" in text:
        text = text.split(":", 1)[1]
    parts = re.findall(r"[a-z0-9]+", text)
    stop = {"or", "and", "the", "of", "a", "an", "to", "on", "for", "in", "host"}
    return {p for p in parts if p not in stop and len(p) > 1}


def _attack_name_token_index(attack_index: dict) -> dict[str, set[str]]:
    global _NAME_TOKEN_INDEX, _NAME_TOKEN_INDEX_KEY
    key = id(attack_index)
    if _NAME_TOKEN_INDEX is not None and _NAME_TOKEN_INDEX_KEY == key:
        return _NAME_TOKEN_INDEX
    index = {
        aid: _name_tokens(getattr(tech, "name", "") or "")
        for aid, tech in attack_index.items()
    }
    _NAME_TOKEN_INDEX = index
    _NAME_TOKEN_INDEX_KEY = key
    return index


def remap_attack_id(
    attack_id: str,
    attack_name: str,
    attack_index: dict,
    min_jacc: float | None = None,
) -> str | None:
    """Projette un ID ATT&CK historique vers le catalogue cible (exact / nom / parent)."""
    min_jacc = (
        config.HYBRID_V14_REMAP_MIN_JACC if min_jacc is None else float(min_jacc)
    )
    aid = (attack_id or "").strip().upper()
    if not aid:
        return None
    if aid in attack_index:
        return aid

    parent = aid.split(".", 1)[0] if "." in aid else ""
    query_tokens = _name_tokens(attack_name)
    if query_tokens:
        best_id = None
        best_score = 0.0
        for cand, cand_tokens in _attack_name_token_index(attack_index).items():
            if not cand_tokens:
                continue
            inter = len(query_tokens & cand_tokens)
            if not inter:
                continue
            jacc = inter / len(query_tokens | cand_tokens)
            coverage = inter / len(query_tokens)
            score = max(jacc, coverage * 0.95)
            if parent and (cand == parent or cand.startswith(parent + ".")):
                score += 0.05
            if score > best_score:
                best_score = score
                best_id = cand
        if best_id is not None and best_score >= min_jacc:
            return best_id

    if parent and parent in attack_index:
        return parent
    return None


def load_corpus_examples() -> list[dict]:
    """Tous les exemples experts (hors version cible), format retrieve_examples."""
    global _CORPUS_EXAMPLES
    if _CORPUS_EXAMPLES is not None:
        return _CORPUS_EXAMPLES
    import datasets

    rows: list[dict] = []
    for ex in datasets.load_expert_examples():
        rows.append(
            {
                "source_version": ex.source_version,
                "capability_id": ex.capability_id,
                "capability_group": ex.capability_group,
                "label": ex.label,
                "mapped": list(ex.mapped or []),
                "mapped_summary": ex.mapped_summary(),
                # Similarité max : ce sont des matches same-label exacts du corpus.
                "distance": 0.0,
            }
        )
    _CORPUS_EXAMPLES = rows
    return rows


def corpus_examples_for_label(
    group: str,
    label: str,
    capability_id: str = "",
) -> list[dict]:
    return examples_for_label(
        load_corpus_examples(), group, label, capability_id
    )


def analog_union_ids_remapped(
    examples: list[dict],
    attack_index: dict,
    max_examples: int = -1,
) -> list[str]:
    """Union des IDs same-label, remappés vers le catalogue ATT&CK cible."""
    pool = examples if max_examples < 0 else examples[: max(0, max_examples)]
    ids: list[str] = []
    seen: set[str] = set()
    for example in pool:
        for mapped in example.get("mapped") or []:
            remapped = remap_attack_id(
                mapped.get("attack_id") or "",
                mapped.get("attack_name") or "",
                attack_index,
            )
            if not remapped or remapped in seen:
                continue
            ids.append(remapped)
            seen.add(remapped)
    return ids


def analog_budget_n_v14(
    examples: list[dict],
    attack_index: dict,
    group: str,
    label: str = "",
    capability_id: str = "",
) -> int:
    """Budget v14 : union corpus/retrieval same-label après remap."""
    same = examples_for_label(examples, group, label, capability_id)
    return len(analog_union_ids_remapped(same, attack_index, max_examples=-1))


def discovery_retrieval_decisions(
    candidates: list[dict],
    attack_index: dict,
    group: str = "",
    max_n: int | None = None,
    min_sim: float | None = None,
) -> list[dict]:
    """Découverte conservative : top techniques retrieval à similarité haute."""
    max_n = config.HYBRID_V14_DISCOVERY_MAX if max_n is None else max_n
    min_sim = config.HYBRID_V14_DISCOVERY_SIM if min_sim is None else min_sim
    ranked: list[tuple[float, str]] = []
    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        if sim < min_sim:
            continue
        if _tactic_score(aid, group, attack_index) < 0:
            continue
        ranked.append((sim, aid))
    ranked.sort(reverse=True)

    decisions: list[dict] = []
    seen: set[str] = set()
    for sim, aid in ranked:
        if aid in seen:
            continue
        decisions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if sim >= config.RETRIEVAL_SIM_HIGH else "medium",
                "justification": (
                    f"Découverte v14 (retrieval sim={sim:.2f}"
                    f"{', tactique' if _tactic_score(aid, group, attack_index) > 0 else ''})."
                ),
            }
        )
        seen.add(aid)
        if len(decisions) >= max_n:
            break
    return decisions


def rerank_v14(
    current_ids: list[str],
    hybrid_ids: set[str],
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    group: str = "",
    label: str = "",
    capability_id: str = "",
    n_target: int | None = None,
) -> list[dict]:
    """V14 : same-label corpus/retrieval + remap version ATT&CK, parent conservé."""
    del hybrid_ids  # API stable avec les autres rerank_*
    same = examples_for_label(examples, group, label, capability_id)
    analog = set(analog_union_ids_remapped(same, attack_index, max_examples=-1))
    support_w: dict[str, float] = {}
    for example in same:
        sim = _example_similarity(example)
        for mapped in example.get("mapped") or []:
            remapped = remap_attack_id(
                mapped.get("attack_id") or "",
                mapped.get("attack_name") or "",
                attack_index,
            )
            if remapped:
                support_w[remapped] = support_w.get(remapped, 0.0) + sim

    if n_target is None:
        n_target = len(analog)
    n_target = max(0, int(n_target))
    if n_target == 0 or not analog:
        return []

    sims: dict[str, float] = {}
    pool: set[str] = set(analog)
    for cand in candidates:
        aid = (cand.get("attack_id") or "").strip().upper()
        if not aid or aid not in attack_index:
            continue
        sim = _candidate_similarity(cand)
        sims[aid] = max(sim, sims.get(aid, 0.0))
        if aid in analog or aid in support_w or sim >= config.RETRIEVAL_SIM_HIGH:
            pool.add(aid)
    for aid in analog:
        sims.setdefault(aid, 0.0)

    current_set = {aid.strip().upper() for aid in current_ids if aid}

    def score(aid: str) -> tuple[float, float]:
        sim = sims.get(aid, 0.0)
        value = 0.0
        value += 2.2 * support_w.get(aid, 0.0)
        if aid in analog:
            value += 3.0
        if sim >= config.RETRIEVAL_SIM_HIGH:
            value += 1.5
        elif sim >= config.RETRIEVAL_SIM_MED:
            value += 0.5
        value += _tactic_score(aid, group, attack_index)
        if aid in current_set:
            value += 0.2
        return (value, sim)

    ranked = sorted(pool, key=score, reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for aid in ranked:
        if aid in seen:
            continue
        if aid not in analog and _tactic_score(aid, group, attack_index) < 0:
            continue
        if not _family_allows_v12(aid, selected, analog, attack_index):
            continue
        selected.append(aid)
        seen.add(aid)
        if len(selected) >= n_target:
            break

    decisions: list[dict] = []
    for aid in selected:
        sim = sims.get(aid, 0.0)
        weight = support_w.get(aid, 0.0)
        reasons = []
        if aid in analog:
            reasons.append("same-label")
        if weight > 0:
            reasons.append(f"support={weight:.2f}")
        if sim >= config.RETRIEVAL_SIM_HIGH:
            reasons.append(f"sim={sim:.2f}")
        if _tactic_score(aid, group, attack_index) > 0:
            reasons.append("tactique")
        note = "Reclassement v14 (same-label remap"
        if reasons:
            note += ", " + ", ".join(reasons)
        note += ")."
        high = aid in analog or weight >= 0.8 or sim >= config.RETRIEVAL_SIM_HIGH
        decisions.append(
            {
                "attack_id": aid,
                "mapping_type": "related_to",
                "confidence": "high" if high else "medium",
                "justification": note,
            }
        )
    return decisions


if __name__ == "__main__":
    import datasets

    cap = datasets.load_veris_capabilities()[0]
    print("Capacité :", cap.capability_id)
    print("\nCandidats ATT&CK :")
    for c in retrieve_techniques(cap.query_text(), top_k=5):
        print(f"  {c['attack_id']:12} {c['name']}  (d={c['distance']:.3f})")
    print("\nExemples experts :")
    for e in retrieve_examples(cap.query_text(), top_m=3):
        print(f"  [{e['source_version']}] {e['label']} -> {e['mapped_summary'][:80]}")
