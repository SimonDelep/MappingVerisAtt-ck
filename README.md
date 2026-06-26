# SIEM — Mapping automatique VERIS → MITRE ATT&CK

Projet UQAC (semestre 2). L'objectif est de **reproduire automatiquement, à l'aide de l'IA, le mapping expert entre le vocabulaire VERIS et le framework MITRE ATT&CK**, puis de mesurer la qualité de ce mapping par rapport au mapping officiel produit par des experts (CTID / MITRE Engenuity *Mappings Explorer*).

Trois approches d'IA sont mises en concurrence :

| Approche | Dossier | Idée |
|---|---|---|
| **FINE_TUNE** | `Solution/Solution_FINE_TUNE` | Modèle entraîné (fine-tuning) sur les mappings existants. |
| **PROMPT** | `Solution/Solution_PROMPT` | LLM piloté uniquement par prompt (zero/few-shot). |
| **RAG** | `Solution/Solution_RAG` | LLM + récupération de contexte (Retrieval-Augmented Generation). |

Chaque approche doit produire, pour une version donnée, **7 fichiers JSON** (un par *capability group* VERIS) au format `veris_to_mitre`. Ces fichiers sont ensuite **comparés au mapping des experts** par les scripts d'évaluation.

---

## 1. Contexte : les deux référentiels

### VERIS
**V**ocabulary for **E**vent **R**ecording and **I**ncident **S**haring : un vocabulaire standardisé pour décrire les incidents de sécurité (le *quoi*). On y trouve des axes (`action`, `attribute`, `value_chain`…), des catégories (`hacking`, `malware`, `social`…), et des sous-catégories (`variety`, `vector`).

### MITRE ATT&CK
Base de connaissance des **techniques et tactiques adverses** (le *comment*). Chaque technique a un identifiant (`T1059`), un nom, une description, des tactiques (kill-chain), et éventuellement des sous-techniques (`T1059.001`).

### Le mapping
Les experts relient une **capacité VERIS** (ex. `action.hacking.variety.SQLi`) à une ou plusieurs **techniques ATT&CK**. C'est exactement ce travail qu'on cherche à automatiser, en confrontant les deux référentiels bruts :

```
verisc-enum.json + verisc-labels.json   (les "questions")
enterprise-attack.json                  (les "candidats")
        │
        ▼
   Solution IA  ──►  mapping VERIS → ATT&CK  ──►  comparaison vs experts
```

### Les 7 *capability groups*
Seuls 7 groupes VERIS « comportementaux » sont mappés vers ATT&CK. Les volumes ci-dessous correspondent à la référence **VERIS 1.4.1 / ATT&CK 19.1** :

| Capability group | Paires VERIS↔ATT&CK | Capacités VERIS |
|---|---:|---:|
| `action.hacking` | 538 | 68 |
| `action.malware` | 405 | 54 |
| `attribute.integrity` | 91 | 13 |
| `attribute.confidentiality` | 73 | 1 |
| `attribute.availability` | 44 | 6 |
| `action.social` | 78 | 23 |
| `value_chain.development` | 25 | 12 |

> `attribute.confidentiality` est un cas particulier : les experts mappent le champ `data_disclosure` lui-même (une seule capacité), et non des valeurs sous `variety`.

---

## 2. Versions supportées

Quatre paires (ATT&CK, VERIS) sont disponibles de bout en bout :

| ATT&CK | VERIS | Référence |
|---|---|---|
| 9.0 | 1.3.5 | `veris-1.3.5_attack-9.0-enterprise` |
| 12.1 | 1.3.7 | `veris-1.3.7_attack-12.1-enterprise` |
| 16.1 | 1.4.0 | `veris-1.4.0_attack-16.1-enterprise` |
| 19.1 | 1.4.1 | `veris-1.4.1_attack-19.1-enterprise` |

La **convention de nommage** `veris-<v>_attack-<a>-enterprise` est utilisée partout (mappings experts, dossiers de résultats) et sert de clé pour relier un résultat à sa référence.

---

## 3. Arborescence du projet

```
SIEM/
├── README.md                         ← ce fichier
│
├── data/                             ← données brutes (sources officielles)
│   ├── raw/
│   │   ├── attack/<version>/enterprise-attack.json     STIX brut ATT&CK
│   │   ├── veris/<version>/verisc-enum.json            énumérations VERIS
│   │   │                   verisc-labels.json          libellés VERIS
│   │   │                   verisc.json                 schéma VERIS complet
│   │   └── mapping/attack-<a>_veris-<v>/               mapping expert (csv/xlsx/yaml/json/stix)
│   └── databases/                    bases SQLite auxiliaires (vocabulaires, mappings)
│
├── data_for_work/                    ← ENTRÉES préparées pour les solutions IA
│   └── attack-<a>_veris-<v>/
│       ├── veris_<v>.json            capacités VERIS en scope (les "questions")
│       ├── attack_<a>.json           techniques ATT&CK (les "candidats")
│       └── mapping_des_experts.json  mapping expert (copie de référence)
│
├── tools/                            ← scripts de préparation des données
│   ├── build_work_inputs.py          data/raw → data_for_work (veris + attack par version)
│   └── build_example_results.py      génère des résultats "parfaits" de référence
│
├── Solution/                         ← code des 3 approches IA (à compléter)
│   ├── Solution_FINE_TUNE/README.md
│   ├── Solution_PROMPT/README.md
│   └── Solution_RAG/README.md
│
└── Resultat/                         ← sorties des solutions + évaluation
    ├── Mapping_des_experts/                      mappings officiels (format CTID)
    │   └── veris-<v>_attack-<a>-enterprise_json.json
    ├── Resultat_FINE_TUNE/<ref>_*/               7 JSON produits par FINE_TUNE
    ├── Resultat_PROMPT/<ref>_*/                  7 JSON produits par PROMPT
    ├── Resultat_RAG/<ref>_*/                     7 JSON produits par RAG
    ├── compare_veris_mappings.py                 évaluation v1 (1 fichier vs 1 référence)
    └── compare_veris_mappings_v2.py              évaluation v2 (lot : 3 solutions × 7 scopes)
```

---

## 4. Le pipeline de bout en bout

### Étape 1 — Préparer les entrées (`tools/build_work_inputs.py`)
Transforme les données brutes en deux fichiers exploitables par l'IA, pour chaque version :

```bash
python tools/build_work_inputs.py
```

- **`veris_<v>.json`** : liste des capacités VERIS dans les 7 groupes, avec `capability_id`, `capability_group`, `value`, `description`.
- **`attack_<a>.json`** : liste des techniques ATT&CK non dépréciées/révoquées, avec `attack_id`, `name`, `description`, `tactics`, `is_subtechnique`, `parent_id`.

### Étape 2 — Produire le mapping (les 3 solutions IA)
Chaque solution (`Solution/Solution_*`) ingère `veris_<v>.json` + `attack_<a>.json` et écrit ses 7 fichiers dans `Resultat/Resultat_<APPROCHE>/<ref>_*/` au format `veris_to_mitre` (voir §5). *(Code des solutions à compléter.)*

### Étape 3 — Évaluer (`Resultat/compare_veris_mappings*.py`)
Comparer les résultats aux mappings experts et calculer les métriques (voir §6).

---

## 5. Format de sortie `veris_to_mitre`

Chaque fichier de résultat (`<capability_group>.json`) suit ce schéma :

```json
{
  "metadata": {
    "veris_version": "1.4.1",
    "mitre_attack_version": "19.1",
    "scope": "action.malware"
  },
  "veris_to_mitre": [
    {
      "veris_id": "malware.variety.ransomware",
      "veris_category": "Malware",
      "veris_label": "variety.Ransomware",
      "no_mapping_found": false,
      "mitre_mappings": [
        {
          "technique_id": "T1486",
          "technique_name": "Data Encrypted for Impact",
          "sub_technique_id": null,
          "sub_technique_name": null,
          "tactic(s)": ["impact"],
          "mapping_type": "related_to",
          "confidence": "high",
          "confidence_score": 1.0,
          "justification": "…"
        }
      ],
      "ambiguous": false,
      "notes": ""
    }
  ]
}
```

Règles clés :
- une entrée par capacité VERIS ;
- `no_mapping_found: true` quand aucune technique ne correspond (et `mitre_mappings: []`) ;
- pour une **sous-technique**, `technique_id` = parent (`T1059`) et `sub_technique_id` = complet (`T1059.001`) ;
- les fichiers experts de référence, eux, sont au **format CTID** (clé `mapping_objects`) — les scripts d'évaluation détectent automatiquement le format.

---

## 6. Évaluation

### v1 — comparaison unitaire (`compare_veris_mappings.py`)
Compare **un** fichier à **une** référence, filtré sur un scope.

```bash
# Compare un résultat au mapping expert, scope action.hacking
python Resultat/compare_veris_mappings.py \
  Resultat/Mapping_des_experts/veris-1.4.1_attack-19.1-enterprise_json.json \
  Resultat/Resultat_RAG/veris-1.4.1_attack-19.1-enterprise_Exemple/action.hacking.json \
  --scope action.hacking

# Toutes catégories + rapport JSON détaillé
python Resultat/compare_veris_mappings.py A.json B.json --scope all -o rapport.json
```

### v2 — comparaison en lot (`compare_veris_mappings_v2.py`)
Parcourt automatiquement les 3 dossiers de solutions, détecte la version via le nom du sous-dossier, retrouve la référence experte correspondante, **valide la présence des 7 fichiers**, calcule un score **global** (7 scopes agrégés) + le **détail par scope**, et affiche un **classement** des solutions.

```bash
# Toutes les solutions
python Resultat/compare_veris_mappings_v2.py

# Une seule solution + rapport JSON
python Resultat/compare_veris_mappings_v2.py --solutions Resultat_RAG -o rapport_v2.json

# Options
#   --base <dir>        racine contenant les Resultat_* et Mapping_des_experts (défaut: dossier Resultat)
#   --experts <dir>     dossier des mappings experts (défaut: <base>/Mapping_des_experts)
#   --solutions A B ...  noms des dossiers de solutions à évaluer
#   -o / --output       rapport JSON détaillé
```

Exemple de sortie (résumé) :

```
Solution : Resultat_RAG
Fichiers : 7/7 scopes presents
  GLOBAL (tous scopes agreges) :
    Precision= 89.7%  Rappel= 61.3%  F1= 72.8%  Jaccard= 57.2%
  PAR CAPABILITY_GROUP :
    action.malware   405  403  403  100.0%  99.5%  99.8%
    ...

CLASSEMENT DES SOLUTIONS (F1 global vs experts)
   # solution            Prec    Rapp     F1    Jacc
   1 Resultat_RAG       89.7%   61.3%  72.8%   57.2%
```

### Définition des métriques
On compare deux **ensembles de paires** `(veris_id, attack_id)` : `A` = experts (référence), `B` = solution.

- **Précision** = |A∩B| / |B| — part des paires proposées qui sont correctes.
- **Rappel** = |A∩B| / |A| — part des paires expertes retrouvées.
- **F1** = moyenne harmonique précision/rappel.
- **Jaccard** = |A∩B| / |A∪B| — similarité globale des deux ensembles.
- **Métriques par capability** : pour chaque capacité commune, recouvrement des techniques, correspondance exacte, rappel/précision moyens.

Les IDs sont **normalisés** avant comparaison (minuscules, casse/espaces/tirets harmonisés) pour éviter les faux négatifs.

---

## 7. Résultats de référence ("parfaits")

`tools/build_example_results.py` génère, à partir du mapping expert, des résultats au format `veris_to_mitre` qui reproduisent **fidèlement** les paires des experts. Ils servent d'exemple de format **et** de borne supérieure (score ≈ 100 %).

```bash
python tools/build_example_results.py
```

> **Quirk connu** : quelques objets du fichier expert portent un `capability_group` (ex. `action.malware`) alors que leur `capability_id` est un identifiant `hacking.*`. En évaluation **par scope**, ces paires apparaissent côté experts mais sont filtrées côté `veris_to_mitre` (filtrage par préfixe du `veris_id`), d'où un rappel légèrement < 100 % sur `action.malware` (99,5 %) et `attribute.integrity` (98,9 %). L'évaluation **globale** (`scope=all`, agrégée) n'est pas affectée.

---

## 8. Prérequis & installation

- **Python 3.10+** (utilise les annotations de type modernes, `X | None`).
- Les scripts d'**évaluation** (`compare_veris_mappings*.py`) et de **préparation** (`tools/*.py`) n'utilisent que la **bibliothèque standard** — aucune dépendance externe.
- Les **solutions IA** (FINE_TUNE / PROMPT / RAG) auront leurs propres dépendances (ex. `torch`, `transformers`, `sentence-transformers`, client LLM…), à déclarer dans chaque dossier `Solution/Solution_*` au moment de leur implémentation.

```bash
python --version   # >= 3.10
```

---

## 9. Démarrage rapide

```bash
# 1) (Re)générer les entrées de travail à partir des données brutes
python tools/build_work_inputs.py

# 2) (Optionnel) Générer les résultats de référence "parfaits"
python tools/build_example_results.py

# 3) Lancer chaque solution IA pour produire ses 7 JSON   (à implémenter)
#    -> Resultat/Resultat_<APPROCHE>/<ref>_*/<capability_group>.json

# 4) Évaluer et classer les 3 solutions
python Resultat/compare_veris_mappings_v2.py
```

---

## 10. Glossaire

| Terme | Signification |
|---|---|
| **Capability / capacité VERIS** | élément VERIS à mapper (ex. `action.hacking.variety.SQLi`). |
| **Capability group** | un des 7 groupes VERIS mappés (un fichier JSON par groupe). |
| **Technique / sous-technique ATT&CK** | `T1059` / `T1059.001`. |
| **Paire** | une liaison `(veris_id, attack_id)`, unité de comparaison. |
| **Format CTID** | format des mappings experts (clé `mapping_objects`). |
| **Format `veris_to_mitre`** | format des résultats des solutions (clé `veris_to_mitre`). |
| **Référence** | identifiant de version `veris-<v>_attack-<a>-enterprise`. |
```

