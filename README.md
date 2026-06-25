# Mapping VERIS Attack

[INSERER DESCRIPTION DU PROJET]

## Objectif du projet

Créer un pipeline qui fasse le mapping entre Veris et Att&ck dans les deux sens, selon les critères d'évaluation suivant:
-> Précision
-> Consommation de ressources

Récolter les data disponible dans :
-> La base de données VCBD
-> Mitre att&ck -> Base de donné publique

Nous experimenterons plusieurs moyens pour faire le mapping, avec soit une LLM fine tuné, ou avec des prompts zéro shot bidirectionnels
Nous essayerons aussi de mettre en place un RAG pour faire le mapping afin d'évaluer les perfomances

Nous ferons a la fin un bilan des 3 techniques, les comparer au niveau de la précision et de la consommation de ressources

## Outils utilisés
- Python
- BDD MITRE ATT&CK
- Framework VERIS
- LLM zero shot -> Modele generique (LLM Publique), afin de faire le mapping
- LLM fine tuné -> Modele entrainer pour le cas du Mapping seulement


