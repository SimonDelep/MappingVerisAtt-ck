# Solution FINE_TUNE

## Objectif

Ce dossier contient la solution développée pour la partie **FINE_TUNE** du projet de mapping automatique entre **VERIS** et **MITRE ATT&CK**.

L’objectif est de générer automatiquement des mappings entre les capacités VERIS et les techniques MITRE ATT&CK, puis de comparer ces résultats avec les mappings experts fournis dans le projet.

Dans le cadre de cette implémentation, deux approches ont été explorées :

1. un **modèle local supervisé**, entraîné sur les mappings experts ;
2. une expérimentation complémentaire avec un **LLM déjà instruction-tuned**, utilisé en zero-shot via l’API Together.

La meilleure approche finale retenue pour la partie FINE_TUNE est le modèle local supervisé.

---

## Données utilisées

Les données utilisées proviennent du dossier :

```text
data_for_work/attack-19.1_veris-1.4.1/
```

Ce dossier contient :

```text
veris_1.4.1.json
attack_19.1.json
mapping_des_experts.json
```

Rôle des fichiers :

* `veris_1.4.1.json` : contient les capacités VERIS à mapper ;
* `attack_19.1.json` : contient les techniques et sous-techniques MITRE ATT&CK candidates ;
* `mapping_des_experts.json` : contient les mappings experts utilisés comme référence d’entraînement et d’évaluation.

Les résultats générés doivent respecter le format `veris_to_mitre` attendu par les scripts d’évaluation du projet.

---

## Capability groups traités

Le projet attend un fichier JSON par capability group VERIS.

Les 7 scopes traités sont :

```text
action.hacking
action.malware
action.social
attribute.availability
attribute.confidentiality
attribute.integrity
value_chain.development
```

Chaque exécution génère donc les fichiers suivants :

```text
action.hacking.json
action.malware.json
action.social.json
attribute.availability.json
attribute.confidentiality.json
attribute.integrity.json
value_chain.development.json
```

---

## Approche principale : modèle local supervisé

Le fichier principal de cette approche est :

```text
run_mapping.py
```

Ce script entraîne un modèle local supervisé à partir des mappings experts.

Le modèle utilisé est :

```text
TF-IDF + One-vs-Rest + Logistic Regression
```

### Principe

Chaque capacité VERIS est transformée en texte à partir de plusieurs informations :

* identifiant VERIS ;
* capability group ;
* label ;
* description éventuelle.

Ce texte est ensuite vectorisé avec TF-IDF.

Le problème est traité comme une classification multi-label, car une capacité VERIS peut correspondre à plusieurs techniques MITRE ATT&CK.

La stratégie One-vs-Rest permet de prédire plusieurs techniques possibles pour une même entrée VERIS.

---

## Pourquoi ce choix ?

Un vrai fine-tuning de grand LLM avec LoRA ou QLoRA n’a pas été retenu dans cette version.

Les raisons principales sont :

* volume de données annotées limité ;
* absence de nécessité d’un GPU pour l’approche locale ;
* meilleure reproductibilité ;
* entraînement rapide ;
* pipeline plus simple à intégrer ;
* format de sortie plus stable ;
* comparaison directe avec les mappings experts.

Cette approche correspond donc à un **fine-tune léger local**, et non à un fine-tuning complet d’un grand LLM.

---

## Hyperparamètres

Le script utilise deux paramètres importants :

```text
--threshold
--top-k
```

### `--threshold`

Le `threshold` définit le score minimal nécessaire pour conserver une prédiction.

Exemple :

```powershell
--threshold 0.05
```

Un seuil élevé rend le modèle plus strict.
Un seuil faible rend le modèle plus permissif.

### `--top-k`

Le `top-k` définit le nombre maximal de techniques MITRE conservées pour chaque capacité VERIS.

Exemple :

```powershell
--top-k 20
```

Un top-k faible limite les prédictions.
Un top-k élevé permet de retrouver plus de mappings experts, mais peut aussi ajouter des faux positifs.

---

## Meilleure configuration locale

La meilleure configuration obtenue est :

```text
FINE_TUNE_T005_K20
```

Commande :

```powershell
python Solution/Solution_FINE_TUNE/run_mapping.py --threshold 0.05 --top-k 20 --output-name FINE_TUNE_T005_K20
```

Résultats :

```text
Precision = 37.4 %
Rappel    = 46.1 %
F1        = 41.3 %
Jaccard   = 26.0 %
```

Cette configuration est retenue car elle offre le meilleur équilibre entre précision et rappel.

---

## Résultats des principales configurations

| Configuration      | Threshold | Top-k | Précision | Rappel |     F1 |
| ------------------ | --------: | ----: | --------: | -----: | -----: |
| FINE_TUNE          |      0.20 |     5 |    58.9 % |  9.8 % | 16.9 % |
| FINE_TUNE_T010_K10 |      0.10 |    10 |    68.0 % | 18.7 % | 29.4 % |
| FINE_TUNE_T005_K10 |      0.05 |    10 |    35.4 % | 37.2 % | 36.3 % |
| FINE_TUNE_T005_K15 |      0.05 |    15 |    36.7 % | 43.1 % | 39.7 % |
| FINE_TUNE_T005_K20 |      0.05 |    20 |    37.4 % | 46.1 % | 41.3 % |

Le modèle initial était trop strict.
La baisse du seuil et l’augmentation du top-k ont permis d’améliorer le rappel et le F1.

---

## Expérimentation complémentaire : LLM zero-shot

Le fichier suivant a été ajouté pour tester un LLM déjà instruction-tuned via Together :

```text
run_mapping_llm.py
```

Le modèle principalement retenu est :

```text
meta-llama/Llama-3.3-70B-Instruct-Turbo
```

Ce modèle n’a pas été réentraîné par nous.
Il est utilisé en zero-shot via l’API Together.

Cette expérimentation permet de comparer :

* le modèle local supervisé ;
* un LLM généraliste déjà instruction-tuned ;
* les approches RAG et PROMPT du projet.

---

## Commande du meilleur LLM zero-shot

```powershell
python Solution/Solution_FINE_TUNE/run_mapping_llm.py --model meta-llama/Llama-3.3-70B-Instruct-Turbo --batch-size 2 --top-k-attack 30 --output-name FINE_TUNED_LLM_LLAMA_B2_K30
```

Résultats :

```text
Precision = 17.0 %
Rappel    = 6.4 %
F1        = 9.3 %
Jaccard   = 4.9 %
```

Le LLM zero-shot est exploitable, mais reste nettement inférieur au modèle local supervisé.

---

## Modèles LLM testés

Plusieurs modèles ont été testés via Together :

```text
Llama 3.3 70B Instruct Turbo
Qwen
DeepSeek
```

### Llama

Llama est le seul modèle LLM zero-shot qui a produit des mappings exploitables dans le pipeline.

### Qwen

Qwen a été écarté à cause de problèmes de streaming obligatoire, de blocage sur certains contenus cybersécurité et de sorties non exploitables.

### DeepSeek

DeepSeek a également été écarté car les fichiers produits ne donnaient pas de mappings exploitables par le comparateur.

---

## Scripts de normalisation et de réparation

Les LLM ne produisent pas toujours un JSON strictement valide.

Pour corriger certains résultats sans relancer des appels API longs, des scripts de réparation ont été ajoutés :

```text
normalize_llm_outputs.py
fix_bad_llm_entries.py
```

Ces scripts servent à :

* convertir des sorties LLM vers le format attendu ;
* réparer des entrées mal structurées ;
* éviter les erreurs du comparateur ;
* transformer des chaînes de caractères en objets JSON valides ;
* normaliser les clés utilisées par le LLM.

Ils ne servent pas à inventer des mappings.
Ils servent uniquement à rendre les fichiers générés exploitables par les scripts d’évaluation.

---

## Évaluation

Les résultats sont évalués avec :

```powershell
python Resultat/compare_veris_mappings_v2.py
```

Avant l’évaluation, il est conseillé de supprimer les fichiers `manifest.json`, qui peuvent perturber le comparateur :

```powershell
Get-ChildItem Resultat -Recurse -Filter manifest.json | Remove-Item -Force
python Resultat/compare_veris_mappings_v2.py
```

Les métriques utilisées sont :

* précision ;
* rappel ;
* F1 ;
* Jaccard.

Le F1 est utilisé comme métrique principale, car il mesure l’équilibre entre précision et rappel.

---

## Comparaison finale

| Méthode                | Précision | Rappel |     F1 | Jaccard |
| ---------------------- | --------: | -----: | -----: | ------: |
| FINE_TUNE_T005_K20     |    37.4 % | 46.1 % | 41.3 % |  26.0 % |
| RAG_with_examples      |    18.9 % | 49.7 % | 27.4 % |  15.9 % |
| RAG_attack_only        |     7.2 % | 15.4 % |  9.8 % |   5.2 % |
| Llama zero-shot B2_K30 |    17.0 % |  6.4 % |  9.3 % |   4.9 % |

Le meilleur résultat global est obtenu par :

```text
FINE_TUNE_T005_K20
```

---

## Prérequis

Installer les dépendances nécessaires :

```powershell
pip install -r Solution/Solution_FINE_TUNE/requirements.txt
```

Le fichier `requirements.txt` doit contenir au minimum :

```text
scikit-learn
python-dotenv
together
```

Pour utiliser l’API Together, il faut créer un fichier local non versionné :

```text
dev.env
```

Avec :

```text
TOGETHER_API_KEY=...
TOGETHER_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo
```


---

## Sorties générées

Le modèle local final génère :

```text
Resultat/Resultat_FINE_TUNE/veris-1.4.1_attack-19.1-enterprise_FINE_TUNE_T005_K20/
```

Le LLM zero-shot final génère :

```text
Resultat/Resultat_FINE_TUNE/veris-1.4.1_attack-19.1-enterprise_FINE_TUNED_LLM_LLAMA_B2_K30/
```

Chaque dossier contient les 7 fichiers JSON attendus par le projet.

---

## Conclusion

La partie FINE_TUNE a été finalisée avec une approche locale supervisée.

Le meilleur résultat est obtenu avec :

```text
FINE_TUNE_T005_K20
F1 = 41.3 %
```

Ce résultat montre qu’un modèle local simple, mais entraîné directement sur les mappings experts, est plus performant qu’un LLM généraliste utilisé sans entraînement spécifique.

L’approche Llama zero-shot reste utile comme expérience comparative, mais elle n’est pas retenue comme meilleure méthode.

LoRA ou QLoRA pourraient être testés dans une amélioration future, mais n’ont pas été utilisés dans cette version du projet.

