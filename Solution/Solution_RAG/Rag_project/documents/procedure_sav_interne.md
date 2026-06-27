# Procédure SAV interne — NordTrail Gear

**Version :** 1.0  
**Date de mise à jour :** 15 mai 2026  
**Document :** Procédure interne — Service après-vente  
**Entreprise :** NordTrail Gear  
**Usage :** Interne uniquement  

---

## 1. Objectif du document

Cette procédure décrit la manière dont le service après-vente de NordTrail Gear doit traiter les demandes clients.

Elle sert de référence pour :

- les agents du service client ;
- l’assistant RAG ;
- les futurs agents LLM connectés à des outils ;
- les processus d’escalade vers un agent humain.

Le but est de garantir des réponses cohérentes, traçables et conformes aux politiques internes de NordTrail Gear.

---

## 2. Types de demandes SAV

| Type de demande | Exemple client |
|---|---|
| Retour produit | “Je veux retourner mes chaussures.” |
| Échange de taille | “La veste est trop grande.” |
| Produit défectueux | “Ma lampe frontale ne charge plus.” |
| Garantie | “Mon sac à dos s’est déchiré après 3 mois.” |
| Colis endommagé | “Le carton est arrivé ouvert.” |
| Produit manquant | “Il manque un article dans mon colis.” |
| Mauvais produit reçu | “J’ai reçu la mauvaise taille.” |
| Retard de livraison | “Ma commande n’est toujours pas arrivée.” |
| Annulation | “Je veux annuler ma commande.” |
| Remboursement | “Quand vais-je être remboursé ?” |

---

## 3. Informations à récupérer avant traitement

| Information | Obligatoire | Exemple |
|---|---|---|
| Numéro de commande | Oui | NTG-2026-000184 |
| Adresse courriel du client | Oui | client@example.com |
| Nom du produit concerné | Oui si produit spécifique | Chaussures TrailStorm X2 |
| Motif de la demande | Oui | Taille trop petite |
| Date de réception | Oui pour retour ou réclamation | 12 mai 2026 |
| Photos | Selon le cas | Produit abîmé, colis endommagé |
| Numéro de suivi | Oui pour livraison | TRK-94818471 |

Si une information obligatoire manque, l’agent doit la demander avant de prendre une décision définitive.

---

## 4. Règle générale de décision

L’agent doit toujours suivre cet ordre :

```text
Identifier l’intention du client
        ↓
Extraire les informations importantes
        ↓
Consulter les politiques internes
        ↓
Vérifier le statut de commande si nécessaire
        ↓
Décider de l’action possible
        ↓
Répondre clairement au client
        ↓
Citer ou enregistrer la règle utilisée
```

L’agent ne doit pas promettre une solution avant d’avoir vérifié les règles applicables.

---

## 5. Traitement d’une demande de retour

### Étapes

1. Vérifier le numéro de commande.
2. Vérifier la date de réception.
3. Identifier le produit concerné.
4. Vérifier si le délai de retour est respecté.
5. Vérifier si le produit est éligible au retour.
6. Demander des photos si l’état du produit est incertain.
7. Créer une demande de retour si les conditions sont remplies.

### Décision

| Situation | Décision |
|---|---|
| Produit reçu depuis moins de 30 jours | Retour potentiellement possible |
| Produit reçu depuis plus de 30 jours | Retour refusé sauf geste commercial |
| Produit neuf, complet, non utilisé | Retour accepté |
| Produit utilisé en extérieur | Retour refusé ou étude manuelle |
| Produit sale, taché ou incomplet | Retour refusé |
| Produit personnalisé | Retour refusé sauf défaut avéré |

---

## 6. Traitement d’un échange de taille

Un échange de taille est traité comme un retour suivi d’une nouvelle expédition.

L’échange est possible si :

- le produit est encore dans le délai de retour ;
- le produit est propre et non abîmé ;
- l’étiquette est présente si nécessaire ;
- la nouvelle taille est disponible en stock.

### Cas particulier des chaussures

Les chaussures peuvent être essayées en intérieur.  
Elles ne doivent pas présenter de traces d’utilisation extérieure.

Si les semelles présentent de la terre, de l’usure ou des traces visibles, l’échange peut être refusé.

---

## 7. Traitement d’un produit défectueux

Un produit est considéré comme potentiellement défectueux lorsqu’il présente un problème anormal malgré une utilisation conforme.

| Produit | Défaut possible |
|---|---|
| Lampe frontale | Ne charge plus, bouton défectueux |
| Sac à dos | Couture rompue après usage normal |
| Veste imperméable | Fermeture éclair cassée rapidement |
| Chaussures | Semelle décollée après faible usage |
| Sac de couchage | Fermeture bloquée, garnissage défectueux |

### Étapes

1. Demander le numéro de commande.
2. Vérifier la date d’achat.
3. Vérifier la durée de garantie applicable.
4. Demander une description précise du problème.
5. Demander des photos ou vidéos.
6. Vérifier si le problème vient d’un défaut ou d’une mauvaise utilisation.
7. Décider : réparation, remplacement, remboursement, refus ou escalade.

---

## 8. Garantie

La garantie couvre les défauts de fabrication et les pannes anormales.

Elle ne couvre pas :

- l’usure normale ;
- les dommages causés par une mauvaise utilisation ;
- les chocs ;
- les déchirures causées par un objet externe ;
- les produits modifiés par le client ;
- l’entretien incorrect ;
- les dommages liés à un lavage non conforme.

| Situation | Décision |
|---|---|
| Défaut clair pendant la période de garantie | Prise en charge possible |
| Usure normale | Refus |
| Mauvaise utilisation évidente | Refus |
| Cas ambigu | Escalade vers agent humain |
| Produit hors garantie | Refus ou geste commercial éventuel |

L’assistant RAG ne doit pas valider définitivement une garantie dans un cas ambigu.

---

## 9. Colis endommagé

Si le client signale un colis endommagé, l’agent doit demander :

- photo du colis fermé ;
- photo de l’étiquette de transport ;
- photo des produits endommagés ;
- date de réception ;
- numéro de commande.

La réclamation doit être ouverte dans les **48 heures** après réception.

Si le client signale le dommage après ce délai, la demande peut être refusée ou escaladée selon la gravité.

---

## 10. Produit manquant

Si un client déclare qu’un produit est manquant dans son colis, l’agent doit vérifier :

1. le contenu attendu de la commande ;
2. le poids du colis enregistré ;
3. le bon de préparation ;
4. les éventuelles livraisons partielles ;
5. les photos du colis reçu.

| Situation | Décision |
|---|---|
| Livraison partielle prévue | Informer le client du second colis |
| Erreur de préparation confirmée | Expédier le produit manquant |
| Preuves insuffisantes | Demander informations complémentaires |
| Suspicion de fraude | Escalade obligatoire |

---

## 11. Mauvais produit reçu

Si le client reçoit le mauvais produit, l’agent doit demander :

- numéro de commande ;
- photo du produit reçu ;
- photo de l’étiquette produit ;
- photo du bon de livraison si disponible.

Si l’erreur vient de NordTrail Gear, le client ne doit pas payer les frais de retour.

Solutions possibles :

- expédition du bon produit ;
- remboursement ;
- échange ;
- avoir si le client accepte.

---

## 12. Retard de livraison

Une commande est considérée comme en retard lorsque le délai maximal estimé est dépassé de plus de **2 jours ouvrés**.

L’agent doit :

1. vérifier le statut du suivi ;
2. vérifier la date d’expédition ;
3. vérifier le transporteur ;
4. déterminer si une enquête est nécessaire ;
5. répondre sans promettre un remboursement automatique.

Un retard simple ne justifie pas automatiquement un remboursement total.

---

## 13. Annulation de commande

L’agent doit vérifier le statut exact de la commande.

| Statut | Action |
|---|---|
| Paiement validé | Annulation possible si préparation non commencée |
| En préparation | Vérification nécessaire |
| Emballée | Annulation rarement possible |
| Expédiée | Annulation impossible |
| Livrée | Retour uniquement |

Si la commande est expédiée, l’agent doit expliquer que le client devra passer par la procédure de retour après réception.

---

## 14. Remboursement

Le remboursement dépend du cas :

| Cas | Remboursement |
|---|---|
| Annulation avant expédition | Remboursement complet |
| Retour produit accepté | Remboursement du produit |
| Refus colis sans faute NordTrail Gear | Frais de livraison potentiellement retenus |
| Produit défectueux confirmé | Remboursement, remplacement ou réparation |
| Produit utilisé hors conditions | Remboursement refusé |

L’agent doit éviter les promesses de dates exactes. Les délais bancaires dépendent du prestataire de paiement.

---

## 15. Escalade vers agent humain

L’assistant RAG doit recommander une escalade dans les cas suivants :

- client agressif ou menaçant ;
- suspicion de fraude ;
- litige sur un montant élevé ;
- produit de valeur supérieure à 250 € ;
- réclamation déjà refusée une fois ;
- garantie ambiguë ;
- problème médical ou sécurité physique ;
- cas non couvert par les politiques internes ;
- demande juridique ;
- incohérence entre documents et statut de commande.

---

## 16. Niveau de priorité

| Priorité | Cas |
|---|---|
| Basse | Question générale, suivi simple |
| Moyenne | Retour, échange, annulation avant expédition |
| Haute | Colis livré non reçu, produit manquant, mauvais produit |
| Critique | Produit dangereux, menace juridique, suspicion fraude |

---

## 17. Ton des réponses

Les réponses doivent être :

- polies ;
- directes ;
- précises ;
- sans promesse non vérifiée ;
- basées sur les règles internes ;
- orientées solution.

L’agent ne doit pas :

- accuser le client ;
- inventer une politique ;
- garantir un remboursement sans vérification ;
- contredire les documents internes ;
- masquer une limite réelle.

---

## 18. Exemple de réponse interne structurée

```text
Intention : demande de retour
Commande : NTG-2026-000184
Produit : TrailStorm X2
Statut : livrée
Date de réception : 10 mai 2026
Analyse : délai de retour respecté, mais produit utilisé en extérieur
Décision : retour non automatique, étude manuelle nécessaire
Action : demander photos des semelles et de l’état général
```

---

## 19. Résumé opérationnel

| Demande | Action principale |
|---|---|
| Retour | Vérifier délai, état, éligibilité |
| Échange | Vérifier délai, état, stock |
| Garantie | Vérifier défaut, date, usage |
| Colis endommagé | Demander photos sous 48 h |
| Produit manquant | Vérifier préparation et livraison partielle |
| Mauvais produit | Demander photos, corriger si erreur confirmée |
| Retard | Vérifier suivi, ouvrir enquête si nécessaire |
| Annulation | Vérifier statut de commande |
| Fraude ou litige | Escalade obligatoire |
