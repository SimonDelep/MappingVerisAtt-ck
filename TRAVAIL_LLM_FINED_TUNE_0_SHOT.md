# Travail réalisé - Finalisation des parties Fine-Tune et LLM Zero-Shot

## Contexte général

Ce travail a été réalisé dans le cadre du projet de mapping automatique entre les référentiels **VERIS** et **MITRE ATT&CK**.

L'objectif du projet est de générer automatiquement des correspondances entre des éléments VERIS, appelés *capabilities*, et des techniques ou sous-techniques MITRE ATT&CK.

Le dépôt de référence contenait déjà une structure de projet, des données, des exemples de résultats, des scripts de comparaison et certaines parties liées au RAG. En revanche, les parties liées au **fine-tuning**, au **LLM zero-shot** et à l'évaluation de plusieurs configurations nécessitaient d'être complétées, testées, corrigées et documentées.

Mon travail a donc consisté à finaliser deux axes principaux :

1. une approche locale supervisée, appelée ici **FINE_TUNE** ;
2. une approche basée sur un **LLM déjà entraîné / instruction-tuned**, utilisé en zero-shot via l'API Together.

Ces deux axes ont ensuite été comparés aux mappings experts à l'aide des scripts d'évaluation du projet.

---

## Branche de travail

Afin de ne pas impacter le travail des autres membres du groupe, tout le travail a été réalisé sur une branche dédiée :

```text
finalisation-kanban
```

L'objectif de cette branche est de permettre au groupe de consulter le travail réalisé, les fichiers ajoutés, les résultats obtenus et les choix techniques effectués, sans modifier directement la branche principale du projet.

Cette branche peut ensuite être relue, discutée ou utilisée pour ouvrir une Pull Request.

---

## Données utilisées

Les scripts s'appuient sur les données déjà présentes dans le projet, notamment dans le dossier :

```text
data_for_work/attack-19.1_veris-1.4.1/
```

Les fichiers principaux utilisés sont :

```text
veris_1.4.1.json
attack_19.1.json
mapping_des_experts.json
```

Ces fichiers contiennent :

- les capabilities VERIS ;
- les techniques MITRE ATT&CK ;
- les mappings experts servant de référence ;
- les versions des référentiels utilisés.

Les résultats générés sont ensuite comparés aux mappings experts avec les scripts présents dans :

```text
Resultat/
```

Le script principal de comparaison utilisé est :

```text
Resultat/compare_veris_mappings_v2.py
```

---

# Partie 1 - Modèle local supervisé / Fine-Tune léger

## Objectif

La première partie consistait à mettre en place une solution locale capable de prédire automatiquement les techniques MITRE ATT&CK associées à chaque capability VERIS.

L'objectif n'était pas d'entraîner un grand modèle de langage, mais de proposer une approche supervisée locale, rapide, reproductible et adaptée au volume limité de données disponibles.

Cette approche permet d'obtenir un modèle :

- entraînable localement ;
- indépendant d'une API externe ;
- reproductible ;
- rapide à exécuter ;
- facilement comparable aux approches RAG et LLM zero-shot.

---

## Fichier principal créé

Le fichier principal ajouté pour cette partie est :

```text
Solution/Solution_FINE_TUNE/run_mapping.py
```

Ce script réalise l'ensemble du pipeline local :

1. chargement des données VERIS ;
2. chargement des données MITRE ATT&CK ;
3. chargement des mappings experts ;
4. construction d'un jeu d'entraînement ;
5. entraînement d'un modèle supervisé local ;
6. génération des mappings VERIS vers MITRE ;
7. export des résultats au format JSON attendu par le comparateur.

---

## Modèle utilisé

Le modèle local repose sur une approche simple mais efficace :

```text
TF-IDF + One-vs-Rest + Logistic Regression
```

Plus précisément :

- les textes des capabilities VERIS sont transformés en vecteurs avec TF-IDF ;
- le problème est traité comme une classification multi-label ;
- chaque capability VERIS peut être associée à plusieurs techniques MITRE ;
- une stratégie One-vs-Rest est utilisée ;
- une régression logistique est entraînée pour prédire les techniques MITRE les plus probables.

Cette solution a été retenue car elle est adaptée au contexte du projet :

- peu de données annotées disponibles ;
- besoin d'une solution rapide ;
- besoin d'un résultat reproductible ;
- pas de dépendance à un GPU ;
- entraînement simple à relancer ;
- bonne intégration avec le format JSON attendu.

---

## Pourquoi ne pas avoir entraîné un grand LLM ?

Un vrai fine-tuning d'un grand modèle de langage aurait été beaucoup plus lourd.

Il aurait nécessité :

- un volume de données annotées beaucoup plus important ;
- une infrastructure GPU ou cloud ;
- un budget calcul plus élevé ;
- un temps d'entraînement important ;
- une gestion plus complexe des prompts et des formats de sortie ;
- un risque d'overfitting à cause du faible nombre d'exemples disponibles.

Dans le contexte de ce projet, le choix d'un modèle local supervisé était donc plus réaliste et plus pertinent.

Le terme le plus exact pour cette partie est :

```text
modèle local supervisé / fine-tune léger
```

et non :

```text
grand LLM fine-tuné
```

---

## Hyperparamètres testés

Le script permet de faire varier deux paramètres importants :

```text
threshold
top-k
```

Le paramètre `threshold` correspond au score minimal nécessaire pour conserver une prédiction.

Le paramètre `top-k` correspond au nombre maximal de techniques MITRE conservées pour une capability VERIS.

Plusieurs configurations ont été testées :

```text
FINE_TUNE
FINE_TUNE_T003_K10
FINE_TUNE_T003_K15
FINE_TUNE_T004_K10
FINE_TUNE_T0045_K15
FINE_TUNE_T005_K10
FINE_TUNE_T005_K15
FINE_TUNE_T005_K20
FINE_TUNE_T0055_K15
FINE_TUNE_T010_K10
```

Ces tests ont permis d'observer l'impact du seuil et du top-k sur la précision, le rappel et le F1.

---

## Résultats du modèle local

La meilleure configuration obtenue est :

```text
FINE_TUNE_T005_K20
```

Avec les paramètres suivants :

```text
threshold = 0.05
top-k = 20
```

Résultat global :

```text
Precision = 37.4 %
Rappel    = 46.1 %
F1        = 41.3 %
Jaccard   = 26.0 %
```

Progression observée :

```text
FINE_TUNE initial   → F1 = 16.9 %
FINE_TUNE_T005_K10  → F1 = 36.3 %
FINE_TUNE_T005_K15  → F1 = 39.7 %
FINE_TUNE_T005_K20  → F1 = 41.3 %
```

Le passage de `top-k=10` à `top-k=20` a permis d'augmenter le rappel tout en conservant une précision correcte.

---

## Analyse du modèle local

Le modèle local supervisé est le meilleur résultat réel obtenu dans ce travail.

Il dépasse :

- les variantes LLM zero-shot ;
- les tests Qwen et DeepSeek ;
- le RAG attack-only ;
- le RAG avec exemples.

Cela montre que, pour une tâche très spécialisée comme le mapping VERIS vers MITRE ATT&CK, une approche supervisée locale peut mieux fonctionner qu'un LLM généraliste utilisé sans entraînement spécifique.

Le résultat reste imparfait, mais il est cohérent avec la difficulté de la tâche. Le mapping entre VERIS et MITRE demande souvent une interprétation fine entre deux référentiels différents, avec des termes proches mais pas toujours équivalents.

---

# Partie 2 - LLM déjà entraîné / instruction-tuned utilisé en zero-shot

## Objectif

La deuxième partie consistait à utiliser un LLM déjà entraîné par un fournisseur, sans réentraînement local, pour générer automatiquement des mappings VERIS vers MITRE ATT&CK.

Cette approche correspond à une utilisation :

```text
zero-shot
```

Cela signifie que le modèle n'est pas entraîné spécifiquement sur nos mappings. Il reçoit un prompt contenant les données VERIS, des candidats MITRE et les instructions de génération, puis il produit une réponse JSON.

---

## Fichier principal créé

Le fichier principal ajouté pour cette partie est :

```text
Solution/Solution_FINE_TUNE/run_mapping_llm.py
```

Ce script permet :

1. de charger les données VERIS et MITRE ;
2. de construire un prompt pour chaque groupe de capabilities ;
3. de sélectionner des candidats MITRE pertinents ;
4. d'appeler l'API Together ;
5. de gérer les réponses JSON imparfaites ;
6. de normaliser les sorties du LLM ;
7. de générer les fichiers JSON comparables aux experts.

---

## Modèle principal retenu

Le modèle retenu est :

```text
meta-llama/Llama-3.3-70B-Instruct-Turbo
```

Il est utilisé via l'API Together.

Il s'agit d'un modèle déjà instruction-tuned par le fournisseur, mais il n'a pas été entraîné spécifiquement par nous sur les données VERIS ou MITRE.

Formulation correcte :

```text
LLM déjà entraîné / instruction-tuned utilisé en zero-shot
```

Formulation à éviter :

```text
LLM que nous avons fine-tuné nous-mêmes
```

---

## Modèles testés

Plusieurs modèles disponibles via l'API Together ont été testés ou explorés :

```text
Llama 3.3 70B Instruct Turbo
Qwen/Qwen3.7-Max
DeepSeek-V4-Pro
```

L'objectif était de vérifier si un autre modèle déjà entraîné pouvait mieux fonctionner que Llama dans notre pipeline.

---

## Impasse avec Qwen

Qwen semblait intéressant car il proposait un très grand contexte et pouvait théoriquement gérer beaucoup de données.

Cependant, il a posé plusieurs problèmes pratiques :

```text
streaming obligatoire
blocage sur certains contenus cybersécurité
data_inspection_failed
sorties non exploitables
```

Le modèle a généré des fichiers, mais ceux-ci ne contenaient pas de mappings exploitables par le comparateur.

Résultat :

```text
FINE_TUNED_LLM_QWEN37_BATCH5
F1 = 0.0 %
```

Qwen a donc été écarté.

---

## Impasse avec DeepSeek

DeepSeek a également été testé.

Le modèle s'exécutait mieux que Qwen au niveau de l'appel API, mais les résultats générés n'ont pas produit de paires exploitables dans notre format de comparaison.

Résultat :

```text
FINE_TUNED_LLM_DEEPSEEKV4_BATCH5_K10
F1 = 0.0 %
```

DeepSeek a donc aussi été écarté pour cette version du projet.

---

## Optimisation de Llama sans entraînement

Llama a été conservé car il était le seul LLM zero-shot testé à produire des mappings exploitables.

Plusieurs réglages ont été testés :

```text
batch-size
top-k-attack
```

Le `batch-size` correspond au nombre de capabilities VERIS envoyées dans un même appel au LLM.

Le `top-k-attack` correspond au nombre de techniques MITRE candidates fournies au modèle.

L'objectif était de trouver un équilibre entre :

- quantité d'information fournie au modèle ;
- qualité de la réponse JSON ;
- nombre de mappings proposés ;
- temps d'exécution ;
- stabilité du pipeline.

---

## Résultats Llama

Première configuration :

```text
FINE_TUNED_LLM_BATCH5
batch-size = 5
top-k-attack = 15
F1 = 5.1 %
```

Deuxième configuration :

```text
FINE_TUNED_LLM_LLAMA_B3_K25
batch-size = 3
top-k-attack = 25
F1 = 8.9 %
```

Troisième configuration :

```text
FINE_TUNED_LLM_LLAMA_B2_K30
batch-size = 2
top-k-attack = 30
F1 = 9.3 %
```

La meilleure configuration Llama est donc :

```text
FINE_TUNED_LLM_LLAMA_B2_K30
```

Avec :

```text
Precision = 17.0 %
Rappel    = 6.4 %
F1        = 9.3 %
Jaccard   = 4.9 %
```

---

## Analyse des résultats Llama

Llama a pu être amélioré sans entraînement, uniquement grâce au réglage des paramètres d'inférence.

La réduction du batch-size et l'augmentation du nombre de candidats MITRE ont amélioré les performances :

```text
F1 = 5.1 %  →  8.9 %  →  9.3 %
```

Cependant, le score reste faible.

Cela montre que le LLM généraliste n'arrive pas à retrouver efficacement les mappings experts sans spécialisation.

Les raisons principales sont :

- tâche très spécifique ;
- vocabulaire proche mais pas toujours équivalent entre VERIS et MITRE ;
- besoin d'un mapping exact ;
- difficulté à choisir les bons IDs ATT&CK ;
- tendance du LLM à produire des associations plausibles mais pas forcément identiques aux experts ;
- contraintes strictes du format JSON attendu.

---

# Scripts de réparation et normalisation

Pendant les tests LLM, plusieurs problèmes de format JSON sont apparus.

Certains modèles retournaient :

- du JSON invalide ;
- du texte autour du JSON ;
- des clés différentes de celles attendues ;
- des chaînes de caractères à la place d'objets JSON ;
- des listes de mappings non normalisées ;
- des réponses vides ou non exploitables.

Pour fiabiliser le pipeline, plusieurs scripts de réparation ou de normalisation ont été créés.

---

## Fichiers de correction ajoutés

Selon les tests réalisés, les fichiers suivants ont été créés :

```text
Solution/Solution_FINE_TUNE/normalize_llm_outputs.py
Solution/Solution_FINE_TUNE/repair_llama_output.py
Solution/Solution_FINE_TUNE/fix_bad_llama_entries.py
Solution/Solution_FINE_TUNE/fix_bad_llm_entries.py
```

Ces scripts ont servi à :

- convertir les sorties LLM vers le format attendu ;
- réparer les entrées mal structurées ;
- éviter les crashes du comparateur ;
- transformer certaines réponses texte en objets JSON valides ;
- gérer les cas où le LLM renvoyait une simple chaîne au lieu d'un objet.

---

## Exemple de problème rencontré

Le comparateur attend des entrées sous cette forme :

```json
{
  "veris_id": "action.malware.vector.Remote injection",
  "veris_category": "action.malware",
  "veris_label": "Remote injection",
  "no_mapping_found": false,
  "mitre_mappings": []
}
```

Mais certains LLM retournaient parfois seulement :

```json
"action.malware.vector.Remote injection"
```

Ce format faisait planter le comparateur.

Les scripts de réparation ont donc permis de convertir ces sorties en objets valides.

---

# Résultats comparatifs finaux

## Meilleur modèle local supervisé

```text
FINE_TUNE_T005_K20
Precision = 37.4 %
Rappel    = 46.1 %
F1        = 41.3 %
Jaccard   = 26.0 %
```

## Meilleur LLM zero-shot

```text
FINE_TUNED_LLM_LLAMA_B2_K30
Precision = 17.0 %
Rappel    = 6.4 %
F1        = 9.3 %
Jaccard   = 4.9 %
```

## Meilleur RAG

```text
RAG_with_examples
Precision = 18.9 %
Rappel    = 49.7 %
F1        = 27.4 %
Jaccard   = 15.9 %
```

---

# Comparaison des approches

## Modèle local supervisé

Points forts :

- meilleur F1 global ;
- rapide à entraîner ;
- reproductible ;
- pas de dépendance à une API externe ;
- résultats stables ;
- adapté au petit volume de données ;
- simple à relancer avec différents hyperparamètres.

Limites :

- modèle simple ;
- ne comprend pas réellement le contexte comme un LLM ;
- dépend fortement des mappings experts disponibles ;
- peut produire des faux positifs quand le top-k augmente.

---

## LLM zero-shot

Points forts :

- facile à tester avec une API ;
- pas d'entraînement local ;
- capable de générer des justifications textuelles ;
- flexible si le prompt est bien construit.

Limites :

- score faible ;
- sorties JSON parfois instables ;
- dépendance à une API ;
- coût et temps d'exécution ;
- difficulté à produire des mappings exacts ;
- certains modèles bloquent le contenu cybersécurité ;
- nécessite beaucoup de normalisation.

---

## RAG

Points forts :

- meilleur rappel que le LLM zero-shot ;
- peut exploiter des exemples ;
- plus pertinent qu'un LLM seul.

Limites :

- beaucoup de faux positifs ;
- précision plus faible ;
- dépend du choix des candidats récupérés ;
- nécessite une bonne stratégie de retrieval.

---

# Choix final

Le meilleur résultat global est obtenu par :

```text
FINE_TUNE_T005_K20
```

Cette configuration doit être considérée comme le meilleur résultat final pour la partie modèle local supervisé.

Le meilleur résultat LLM zero-shot est :

```text
FINE_TUNED_LLM_LLAMA_B2_K30
```

Cette configuration doit être considérée comme le meilleur résultat final pour la partie LLM déjà entraîné / instruction-tuned via Together.

---

# Fichiers importants à conserver

## Code principal

```text
Solution/Solution_FINE_TUNE/run_mapping.py
Solution/Solution_FINE_TUNE/run_mapping_llm.py
Solution/Solution_FINE_TUNE/README.md
TRAVAIL_LANCELOT.md
```

## Scripts de normalisation / réparation

```text
Solution/Solution_FINE_TUNE/normalize_llm_outputs.py
Solution/Solution_FINE_TUNE/repair_llama_output.py
Solution/Solution_FINE_TUNE/fix_bad_llama_entries.py
Solution/Solution_FINE_TUNE/fix_bad_llm_entries.py
```

## Résultats finaux

```text
Resultat/Resultat_FINE_TUNE/veris-1.4.1_attack-19.1-enterprise_FINE_TUNE_T005_K20
Resultat/Resultat_FINE_TUNE/veris-1.4.1_attack-19.1-enterprise_FINE_TUNED_LLM_LLAMA_B2_K30
```

---

# Fichiers à ne pas commiter

Les fichiers suivants ne doivent pas être ajoutés au dépôt :

```text
dev.env
.env
Resultat/debug_prompt_errors/
Solution/Solution_FINE_TUNE/model/
__pycache__/
*.pyc
```

Le fichier `dev.env` contient la clé API Together et ne doit jamais être poussé sur Git.

Le modèle `.pkl` peut être régénéré en relançant le script, donc il n'est pas nécessaire de le versionner.

---

# Commandes principales

## Lancer le modèle local final

```powershell
python Solution/Solution_FINE_TUNE/run_mapping.py --threshold 0.05 --top-k 20 --output-name FINE_TUNE_T005_K20
```

## Lancer le meilleur LLM zero-shot

```powershell
python Solution/Solution_FINE_TUNE/run_mapping_llm.py --model meta-llama/Llama-3.3-70B-Instruct-Turbo --batch-size 2 --top-k-attack 30 --output-name FINE_TUNED_LLM_LLAMA_B2_K30
```

## Lancer la comparaison

```powershell
Get-ChildItem Resultat -Recurse -Filter manifest.json | Remove-Item -Force
python Resultat/compare_veris_mappings_v2.py
```

---

# Nettoyage conseillé avant commit

Les dossiers de test ou d'échec peuvent être déplacés hors comparaison pour éviter de polluer le classement final.

```powershell
New-Item -ItemType Directory -Force Resultat_HORS_COMPARAISON\Models_Failed | Out-Null
New-Item -ItemType Directory -Force Resultat_HORS_COMPARAISON\Tests_Limites | Out-Null
New-Item -ItemType Directory -Force Resultat_HORS_COMPARAISON\Exemples | Out-Null
```

Dossiers à déplacer si présents :

```text
FINE_TUNED_LLM_QWEN37_BATCH5
FINE_TUNED_LLM_DEEPSEEKV4_BATCH5_K10
TEST_DEEPSEEKV4_LIMIT5
*_Exemple
```

---

# Sécurité Git

Avant de pousser le travail sur le dépôt commun, il faut vérifier que les fichiers sensibles ne sont pas suivis par Git.

Vérification :

```powershell
git ls-files dev.env .env
```

Si Git affiche `dev.env` ou `.env`, les retirer de l'index sans les supprimer du PC :

```powershell
git rm --cached dev.env .env
```

Le `.gitignore` doit contenir au minimum :

```gitignore
dev.env
.env
Resultat/debug_prompt_errors/
Solution/Solution_FINE_TUNE/model/
__pycache__/
*.pyc
```

---

# Commandes Git conseillées

Vérifier la branche :

```powershell
git branch --show-current
```

La branche attendue est :

```text
finalisation-kanban
```

Ajouter les fichiers importants :

```powershell
git add Solution/Solution_FINE_TUNE/run_mapping.py
git add Solution/Solution_FINE_TUNE/run_mapping_llm.py
git add Solution/Solution_FINE_TUNE/README.md
git add Solution/Solution_FINE_TUNE/normalize_llm_outputs.py
git add Solution/Solution_FINE_TUNE/repair_llama_output.py
git add Solution/Solution_FINE_TUNE/fix_bad_llama_entries.py
git add Solution/Solution_FINE_TUNE/fix_bad_llm_entries.py
git add TRAVAIL_LANCELOT.md
git add .gitignore
```

Ajouter les meilleurs résultats :

```powershell
git add Resultat/Resultat_FINE_TUNE/veris-1.4.1_attack-19.1-enterprise_FINE_TUNE_T005_K20
git add Resultat/Resultat_FINE_TUNE/veris-1.4.1_attack-19.1-enterprise_FINE_TUNED_LLM_LLAMA_B2_K30
```

Vérifier ce qui va être commit :

```powershell
git status
```

Faire le commit :

```powershell
git commit -m "Ajout finalisation fine-tune local et LLM zero-shot"
```

Pousser sur la branche personnelle :

```powershell
git push -u origin finalisation-kanban
```

Cette commande pousse uniquement la branche `finalisation-kanban` et n'impacte pas directement la branche principale.

---

# Conclusion personnelle

Le travail réalisé a permis de finaliser et d'améliorer les parties liées au fine-tune et aux LLM zero-shot.

La principale conclusion est que le modèle local supervisé est le plus performant dans le contexte de ce projet. Même s'il est plus simple qu'un grand LLM, il est mieux adapté à la tâche car il apprend directement à partir des mappings experts.

Les LLM zero-shot restent intéressants pour générer des propositions ou des justifications, mais ils sont beaucoup moins performants pour produire un mapping exact et comparable aux experts.

Le meilleur résultat final obtenu est donc :

```text
FINE_TUNE_T005_K20
F1 = 41.3 %
```

Le meilleur résultat LLM zero-shot obtenu est :

```text
FINE_TUNED_LLM_LLAMA_B2_K30
F1 = 9.3 %
```

Ce travail montre que, pour une tâche de mapping structurée et très spécialisée comme VERIS vers MITRE ATT&CK, une approche supervisée locale simple mais bien réglée peut dépasser un LLM généraliste utilisé sans entraînement spécifique.