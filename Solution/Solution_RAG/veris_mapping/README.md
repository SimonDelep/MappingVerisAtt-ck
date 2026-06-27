# RAG — Mapping VERIS → MITRE ATT&CK

Solution **RAG** (Retrieval-Augmented Generation) du projet SIEM. Elle reproduit
automatiquement le mapping expert entre les capacités **VERIS** et les techniques
**MITRE ATT&CK**, puis écrit **7 fichiers JSON** (un par *capability group*) au
format `veris_to_mitre` attendu par `Resultat/compare_veris_mappings_v2.py`.

L'architecture réutilise le squelette du RAG d'exemple (`../Rag_project`), avec
**deux fournisseurs interchangeables** :

| `RAG_PROVIDER` | Embeddings | Génération par défaut | Clés requises |
|---|---|---|---|
| `local` (**défaut**) | `sentence-transformers` | `retrieval` (similarité) | aucune |
| `azure` | Azure OpenAI | `llm` (Azure) | `dev.env` |

ChromaDB sert de base vectorielle locale dans les deux cas. Le backend de
génération est réglable via `RAG_GENERATOR` : `retrieval` (sans LLM),
`local_llm` (LLM local via `transformers`) ou `llm` (Azure).

---

## Principe

Contrairement à PROMPT (LLM seul) et FINE_TUNE (modèle entraîné), ce RAG **ancre
chaque décision dans du contexte récupéré** via deux corpus vectoriels :

1. **`attack_techniques`** — le catalogue ATT&CK cible (les *candidats*).
2. **`expert_examples`** — les mappings experts des **autres** versions
   (9.0 / 12.1 / 16.1), agrégés par capacité, comme *exemples analogiques*.

> ⚠️ **Anti-fuite** : le mapping expert de la version cible (1.4.1 / 19.1) n'est
> **jamais** indexé. Seules les versions antérieures servent d'exemples
> (`config.list_example_work_dirs()` exclut explicitement la version cible).

### Flux pour une capacité VERIS

```
capacité VERIS (groupe + libellé + description)
        │
        ├─► retrieve : top-k techniques ATT&CK candidates
        ├─► retrieve : top-m exemples experts (variante "with_examples")
        ▼
   prompt LLM (capacité + candidats + exemples) → JSON {mappings:[{attack_id,...}]}
        │
        ├─► validation : on rejette les IDs hors catalogue (anti-hallucination)
        ├─► enrichissement : noms/sous-techniques/tactiques tirés du catalogue
        ▼
   entrée veris_to_mitre → regroupée par capability_group → 7 fichiers JSON
```

Le LLM ne renvoie que l'**identifiant** ATT&CK, le `mapping_type`, la `confidence`
et une `justification`. Les libellés et tactiques proviennent du catalogue local,
ce qui garantit des sorties propres et comparables.

---

## Deux variantes comparées

| Mode | Corpus de récupération | Dossier de sortie |
|---|---|---|
| `attack_only` | ATT&CK seul | `Resultat/Resultat_RAG/veris-1.4.1_attack-19.1-enterprise_RAG_attack_only/` |
| `with_examples` | ATT&CK + exemples experts | `Resultat/Resultat_RAG/veris-1.4.1_attack-19.1-enterprise_RAG_with_examples/` |

Les deux variantes partagent la **même ingestion** (les deux collections sont
indexées une fois) ; seul le *retrieval* change. Elles sont ensuite classées
côte à côte par `compare_veris_mappings_v2.py`.

---

## Structure

| Fichier | Rôle |
|---|---|
| `config.py` | Versions cible, chemins, Azure, ChromaDB, top_k/top_m. |
| `datasets.py` | Chargement VERIS / ATT&CK / exemples experts. |
| `embeddings.py` | Embeddings Azure OpenAI (par lots). |
| `vectorstore.py` | ChromaDB : 2 collections (cosine). |
| `ingest.py` | Indexe ATT&CK + exemples experts. |
| `retrieve.py` | Récupère candidats techniques + exemples. |
| `prompt.py` | Prompt système/utilisateur + schéma JSON. |
| `generate_mapping.py` | Pipeline complet → 7 fichiers par variante. |
| `selftest_offline.py` | Smoke-test hors-ligne (embeddings + LLM bouchonnés). |

---

## Prérequis

```bash
pip install -r requirements.txt
```

**Mode local (défaut)** : aucune clé. Le modèle `sentence-transformers` se
télécharge automatiquement au premier lancement (~80 Mo).

**Mode Azure (optionnel)** : renseigner `dev.env` (voir `SIEM/dev.env.example`)
et mettre `RAG_PROVIDER=azure`. Attention : `AZURE_OPENAI_*_MODEL` sont les noms
de **déploiement**, pas de modèle.

---

## Utilisation

Toutes les commandes se lancent depuis ce dossier (`veris_mapping/`).

```bash
# 0. (optionnel) vérifier le câblage sans réseau
python selftest_offline.py

# 1. valider la config + les fichiers de données
python config.py

# 2. ingestion (une seule fois) : ATT&CK + exemples experts
python ingest.py

# 3. génération des deux variantes
python generate_mapping.py --mode both
#   ou une seule : --mode attack_only   /   --mode with_examples
#   test rapide  : --limit 5

# 4. évaluation vs experts (depuis SIEM/Resultat)
python ../../../Resultat/compare_veris_mappings_v2.py --solutions Resultat_RAG
```

---

## Résultats (mode local, generator `retrieval`)

Évaluation v2 contre les experts (1.4.1 / 19.1) :

| Variante | Précision | Rappel | F1 |
|---|---:|---:|---:|
| `RAG_with_examples` | 18.9 % | 49.7 % | **27.4 %** |
| `RAG_attack_only` | 7.2 % | 15.4 % | 9.8 % |

> Les exemples experts (autres versions) apportent un gain majeur en rappel.
> Le backend `retrieval` privilégie le rappel au détriment de la précision ;
> passer en `local_llm` ou `llm` (Azure) filtre mieux les candidats et
> augmente la précision. Les seuils `RAG_RETRIEVAL_SIM_*` permettent aussi
> d'arbitrer précision/rappel.

---

## Paramètres de réglage (`dev.env` ou variables d'env)

| Variable | Défaut | Effet |
|---|---|---|
| `RAG_TOP_K_TECHNIQUES` | 20 | Candidats ATT&CK récupérés par capacité. |
| `RAG_TOP_M_EXAMPLES` | 5 | Exemples experts injectés (mode `with_examples`). |
| `RAG_GENERATION_TEMPERATURE` | 0.1 | Déterminisme de la génération. |
| `RAG_EMBEDDING_BATCH_SIZE` | 64 | Taille des lots d'embeddings. |

> **Note recall** : certaines capacités VERIS sont mappées par les experts vers
> *toutes* les sous-techniques d'une famille (ex. T1546.\*). Avec un `top_k`
> limité, le RAG ne voit pas tous ces candidats : augmenter `RAG_TOP_K_TECHNIQUES`
> améliore le rappel au prix de prompts plus longs.

---

## Format de sortie

Identique aux exemples de `Resultat/Resultat_RAG/...` :

```json
{
  "metadata": {"veris_version": "1.4.1", "mitre_attack_version": "19.1", "scope": "action.hacking"},
  "veris_to_mitre": [
    {
      "veris_id": "hacking.variety.backdoor",
      "veris_category": "Hacking",
      "veris_label": "Backdoor",
      "no_mapping_found": false,
      "mitre_mappings": [
        {
          "technique_id": "T1098", "technique_name": "Account Manipulation",
          "sub_technique_id": "T1098.007", "sub_technique_name": "Additional Local or Domain Groups",
          "tactic(s)": ["persistence", "privilege-escalation"],
          "mapping_type": "related_to", "confidence": "high",
          "confidence_score": 1.0, "justification": "..."
        }
      ],
      "ambiguous": false, "notes": ""
    }
  ]
}
```
