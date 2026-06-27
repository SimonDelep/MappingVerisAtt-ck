"""Chargement des référentiels VERIS / ATT&CK et des exemples experts.

- VERIS cible   : capacités à mapper (les "questions").
- ATT&CK        : techniques candidates + index par identifiant.
- Exemples      : mappings experts des *anciennes* versions (jamais la cible),
                  agrégés par capacité pour servir d'exemples analogiques.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import config


def load_json(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


# ==================== VERIS (cible) ====================
@dataclass
class VerisCapability:
    capability_id: str
    capability_group: str
    value: str  # libellé court
    description: str

    def query_text(self) -> str:
        """Texte utilisé pour interroger les corpus vectoriels."""
        desc = self.description or self.value
        return f"VERIS {self.capability_group} : {self.value}. {desc}"


def load_veris_capabilities() -> list[VerisCapability]:
    data = load_json(config.VERIS_FILE)
    caps = [
        VerisCapability(
            capability_id=item["capability_id"],
            capability_group=item["capability_group"],
            value=item.get("value", ""),
            description=item.get("description", ""),
        )
        for item in data.get("capabilities", [])
    ]
    return caps


# ==================== ATT&CK (candidats) ====================
@dataclass
class AttackTechnique:
    attack_id: str
    name: str
    description: str
    tactics: list[str] = field(default_factory=list)
    is_subtechnique: bool = False
    parent_id: str | None = None

    def document_text(self) -> str:
        tactics = ", ".join(self.tactics) if self.tactics else "n/a"
        return (
            f"{self.attack_id} {self.name}\n"
            f"Tactiques : {tactics}\n"
            f"{self.description}"
        )


def load_attack_techniques() -> list[AttackTechnique]:
    data = load_json(config.ATTACK_FILE)
    return [
        AttackTechnique(
            attack_id=t["attack_id"],
            name=t.get("name", ""),
            description=t.get("description", ""),
            tactics=t.get("tactics", []),
            is_subtechnique=bool(t.get("is_subtechnique")),
            parent_id=t.get("parent_id"),
        )
        for t in data.get("techniques", [])
    ]


def build_attack_index() -> dict[str, AttackTechnique]:
    return {t.attack_id: t for t in load_attack_techniques()}


# ==================== Exemples experts (anciennes versions) ====================
@dataclass
class ExpertExample:
    """Une capacité VERIS d'une ancienne version et son mapping expert agrégé."""

    source_version: str
    capability_id: str
    capability_group: str
    label: str
    description: str
    mapped: list[dict]  # [{"attack_id", "attack_name"}]

    def document_text(self) -> str:
        desc = self.description or self.label
        return f"VERIS {self.capability_group} : {self.label}. {desc}"

    def mapped_summary(self) -> str:
        if not self.mapped:
            return "(aucune technique mappée)"
        return "; ".join(
            f"{m['attack_id']} {m['attack_name']}".strip() for m in self.mapped
        )


def _label_from_capability_id(capability_id: str) -> str:
    parts = capability_id.split(".")
    remainder = parts[2:]  # retire axis.category
    if remainder and remainder[0].lower() in {"variety", "vector"}:
        remainder = remainder[1:]
    return ".".join(remainder) if remainder else capability_id


def load_expert_examples() -> list[ExpertExample]:
    """Charge et agrège les mappings experts de toutes les versions != cible."""
    examples: list[ExpertExample] = []

    for work_dir in config.list_example_work_dirs():
        data = load_json(work_dir / "mapping_des_experts.json")
        version = (
            data.get("metadata", {}).get("mapping_framework_version") or work_dir.name
        )

        # Agrège par capability_id : un exemple = une capacité + ses techniques.
        by_capability: dict[str, ExpertExample] = {}
        for obj in data.get("mapping_objects", []):
            capability_id = obj.get("capability_id", "")
            group = obj.get("capability_group", "")
            if not capability_id:
                continue
            example = by_capability.get(capability_id)
            if example is None:
                example = ExpertExample(
                    source_version=version,
                    capability_id=capability_id,
                    capability_group=group,
                    label=_label_from_capability_id(capability_id),
                    description=obj.get("capability_description", ""),
                    mapped=[],
                )
                by_capability[capability_id] = example

            attack_id = (obj.get("attack_object_id") or "").strip()
            if attack_id:
                example.mapped.append(
                    {
                        "attack_id": attack_id,
                        "attack_name": obj.get("attack_object_name", ""),
                    }
                )

        examples.extend(by_capability.values())

    return examples


if __name__ == "__main__":
    caps = load_veris_capabilities()
    techs = load_attack_techniques()
    examples = load_expert_examples()
    print(f"Capacités VERIS cible : {len(caps)}")
    print(f"Techniques ATT&CK     : {len(techs)}")
    print(f"Exemples experts       : {len(examples)}")
    from collections import Counter

    print("Par groupe (VERIS cible) :", dict(Counter(c.capability_group for c in caps)))
