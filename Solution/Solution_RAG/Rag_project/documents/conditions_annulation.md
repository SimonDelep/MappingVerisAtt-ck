# Conditions d’annulation — NordTrail Gear

**Version :** 1.0  
**Date de mise à jour :** 15 mai 2026  
**Document :** Politique client — Annulation de commande  
**Entreprise :** NordTrail Gear  

---

## 1. Objectif du document

Ce document définit les règles d’annulation des commandes passées sur la boutique en ligne NordTrail Gear.

Il sert de référence pour :

- le service client ;
- l’assistant RAG ;
- les agents chargés de traiter les demandes d’annulation ;
- les outils simulés de gestion de commande.

L’objectif est de déterminer clairement si une commande peut être annulée, modifiée ou si elle doit être traitée comme un retour après réception.

---

## 2. Principe général

Une commande peut être annulée uniquement si elle n’a pas encore été expédiée.

Dès qu’une commande est remise au transporteur, elle ne peut plus être annulée directement par NordTrail Gear.

Dans ce cas, le client devra attendre la réception du colis, puis effectuer une demande de retour si les conditions de retour sont respectées.

---

## 3. Statuts de commande

| Statut de commande | Annulation possible | Explication |
|---|---|---|
| Paiement en attente | Oui | La commande n’est pas encore validée |
| Paiement validé | Oui | Annulation possible si la préparation n’a pas commencé |
| En préparation | Possible sous conditions | Annulation possible uniquement si le colis n’est pas encore emballé |
| Emballée | Non, sauf exception | Le colis est déjà prêt à partir |
| Expédiée | Non | La commande est remise au transporteur |
| Livrée | Non | Le client doit passer par une demande de retour |
| Retournée | Non applicable | La commande suit déjà une procédure de retour |
| Annulée | Non applicable | La commande est déjà annulée |

---

## 4. Annulation avant préparation

Si la commande est encore au statut **paiement validé** et que la préparation n’a pas commencé, l’annulation est acceptée automatiquement.

Dans ce cas :

- la commande est annulée ;
- le client reçoit une confirmation par courriel ;
- le remboursement est déclenché automatiquement ;
- aucun frais d’annulation n’est appliqué.

Le remboursement est effectué sur le moyen de paiement initial.

---

## 5. Annulation pendant la préparation

Si la commande est au statut **en préparation**, l’annulation n’est pas garantie.

| Situation | Décision |
|---|---|
| Préparation commencée mais colis non emballé | Annulation possible |
| Colis emballé mais non remis au transporteur | Annulation exceptionnelle possible |
| Colis déjà en zone d’expédition | Annulation refusée |
| Colis déjà remis au transporteur | Annulation impossible |

Dans les cas limites, le service client doit consulter l’état exact de la commande avant de répondre au client.

---

## 6. Annulation après expédition

Une commande expédiée ne peut plus être annulée.

Le client doit attendre la livraison du colis.

Après réception, il peut faire une demande de retour si :

- le produit est éligible au retour ;
- le délai de retour est respecté ;
- le produit n’a pas été utilisé de manière incompatible avec la politique de retour ;
- le produit est retourné complet, propre et dans son emballage d’origine si nécessaire.

L’assistant ne doit jamais promettre une annulation directe si la commande est déjà expédiée.

---

## 7. Refus du colis à la livraison

Le client peut refuser le colis lors de la livraison, mais cette action n’est pas considérée comme une annulation standard.

Si le colis est refusé :

- il est généralement retourné à NordTrail Gear ;
- le remboursement peut être déclenché après réception et contrôle du colis ;
- les frais de livraison initiaux peuvent être retenus ;
- des frais de retour peuvent être déduits si le transporteur les facture.

Le refus du colis ne garantit donc pas un remboursement intégral.

---

## 8. Modification de commande

Une modification de commande est possible uniquement si la commande n’est pas encore expédiée.

Les modifications possibles avant expédition sont :

- correction d’adresse ;
- changement de taille ;
- changement de couleur ;
- retrait d’un produit ;
- ajout d’un produit si le paiement complémentaire est possible ;
- changement du mode de livraison si la commande n’a pas encore été préparée.

Une fois la commande expédiée, aucune modification directe n’est possible.

---

## 9. Modification d’adresse

Si le client signale une erreur d’adresse avant l’expédition, le service client peut corriger l’adresse.

Si la commande est déjà expédiée, NordTrail Gear ne garantit pas la modification.

Dans ce cas, le client peut :

- contacter directement le transporteur ;
- attendre une tentative de livraison ;
- attendre le retour éventuel du colis à l’expéditeur.

Si le colis revient à NordTrail Gear à cause d’une adresse incorrecte fournie par le client, les frais de livraison initiaux ne sont pas remboursés.

---

## 10. Annulation partielle

Si la commande contient plusieurs produits, il peut être possible d’annuler uniquement un produit.

L’annulation partielle est possible si :

- le produit concerné n’a pas encore été préparé ;
- le produit n’a pas été expédié séparément ;
- le système de commande permet de séparer la ligne de commande ;
- l’annulation ne bloque pas le reste de la commande.

Si un produit est déjà expédié, il ne peut pas être annulé individuellement.

---

## 11. Produits non annulables

Certains produits ne peuvent pas être annulés si leur préparation spécifique a commencé.

Cela concerne notamment :

- les produits personnalisés ;
- les produits commandés spécialement auprès d’un fournisseur ;
- les packs promotionnels déjà assemblés ;
- les produits faisant partie d’une opération limitée ;
- les commandes déjà transmises à un entrepôt externe.

Dans ces cas, l’annulation peut être refusée même si le colis n’est pas encore physiquement expédié.

---

## 12. Commandes avec promotion

Si une commande bénéficiant d’une promotion est annulée partiellement, le montant remboursé peut être recalculé.

Exemple :  
Un client bénéficie de 20 € de réduction à partir de 100 € d’achat.  
S’il annule un produit et que le total restant passe sous 100 €, la réduction peut être annulée ou ajustée.

Le remboursement correspond alors au montant réellement dû après recalcul de la promotion.

---

## 13. Commandes avec livraison offerte

Si une annulation partielle fait passer le montant de la commande sous le seuil de livraison offerte, les frais de livraison peuvent être réappliqués.

Exemple :  
La livraison est offerte à partir de 80 €.  
Le client commande pour 95 €, puis annule un produit de 25 €.  
Le total restant est de 70 €.  
Les frais de livraison peuvent être déduits du remboursement.

---

## 14. Délais de remboursement après annulation

Lorsque l’annulation est acceptée, le remboursement est généralement déclenché sous **2 à 5 jours ouvrés**.

| Moyen de paiement | Délai estimé |
|---|---|
| Carte bancaire | 2 à 7 jours ouvrés |
| PayPal | 1 à 3 jours ouvrés |
| Carte cadeau | Crédit immédiat ou sous 24 h |
| Virement bancaire | 3 à 10 jours ouvrés |

Le service client ne doit pas garantir une date bancaire exacte.

---

## 15. Annulation par NordTrail Gear

NordTrail Gear peut annuler une commande dans certains cas :

- produit en rupture de stock ;
- erreur manifeste de prix ;
- suspicion de fraude ;
- paiement non validé ;
- adresse incomplète ou incohérente ;
- impossibilité de livraison dans la zone demandée ;
- problème technique lors de la validation de commande.

Dans ce cas, le client est informé par courriel et remboursé si un paiement a déjà été effectué.

---

## 16. Rupture de stock après commande

Il peut arriver qu’un produit affiché disponible soit finalement indisponible au moment de la préparation.

Dans ce cas, NordTrail Gear peut proposer :

- l’annulation du produit concerné ;
- l’expédition du reste de la commande ;
- un produit équivalent ;
- un avoir ;
- un remboursement complet si le client ne souhaite pas de remplacement.

Le client ne doit pas être forcé d’accepter un produit de remplacement.

---

## 17. Cas de suspicion de fraude

Une commande peut être bloquée ou annulée si certains signaux sont détectés :

- adresse incohérente ;
- paiement refusé ou suspect ;
- plusieurs commandes similaires en peu de temps ;
- litiges répétés sur le même compte ;
- incohérence entre adresse de facturation et adresse de livraison.

Ces cas doivent être escaladés vers un agent humain.

L’assistant RAG ne doit pas accuser le client de fraude.

---

## 18. Réponses types

### Commande annulable

Bonjour,

Votre commande peut encore être annulée car elle n’a pas été expédiée. Nous allons procéder à l’annulation et déclencher le remboursement sur votre moyen de paiement initial.

Cordialement,  
Service client NordTrail Gear

---

### Commande déjà expédiée

Bonjour,

Votre commande a déjà été expédiée. Elle ne peut donc plus être annulée directement.

Vous pouvez attendre la réception du colis puis effectuer une demande de retour, sous réserve que les conditions de retour soient respectées.

Cordialement,  
Service client NordTrail Gear

---

### Commande en préparation

Bonjour,

Votre commande est actuellement en préparation. L’annulation n’est pas garantie à ce stade. Nous allons vérifier si le colis peut encore être stoppé avant expédition.

Cordialement,  
Service client NordTrail Gear

---

## 19. Règles importantes pour l’assistant RAG

L’assistant doit :

- vérifier le statut de commande avant de confirmer une annulation ;
- ne jamais promettre une annulation si la commande est expédiée ;
- distinguer annulation, modification et retour ;
- demander le numéro de commande si absent ;
- préciser que les délais bancaires dépendent du prestataire de paiement ;
- escalader vers un humain en cas de fraude, litige ou cas ambigu.

---

## 20. Résumé opérationnel

| Situation | Décision |
|---|---|
| Paiement en attente | Annulation possible |
| Paiement validé | Annulation possible si préparation non commencée |
| En préparation | Vérification nécessaire |
| Emballée | Annulation rarement possible |
| Expédiée | Annulation impossible |
| Livrée | Retour uniquement |
| Adresse incorrecte avant expédition | Correction possible |
| Adresse incorrecte après expédition | Modification non garantie |
| Produit personnalisé | Annulation souvent impossible |
| Suspicion de fraude | Escalade obligatoire |
