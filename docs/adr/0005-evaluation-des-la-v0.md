# 0005 — Évaluation chiffrée dès la V0, arbitre des décisions

- Date : 2026-10-08
- Statut : Accepté

## Contexte

Presque tous les choix de la recherche (taille de chunk, modèle, fusion, reranker, prétraitement) ont des effets difficiles à prévoir. Sans mesure, on décide à l'intuition sur quelques requêtes favorables (« ça marche chez moi »). La conception initiale plaçait l'évaluation en fin de projet.

## Options étudiées

- **Évaluation à la fin** : rapide au début, mais toutes les décisions intermédiaires sont prises à l'aveugle.
- **Tests manuels ad hoc** : peu coûteux, mais non reproductibles et biaisés.
- **Jeu d'évaluation dès la V0** : coût initial (rédiger 30 à 50 questions), puis chaque décision se tranche en une commande.

## Décision

Construire le jeu d'évaluation à l'étape 4, juste après la première recherche (BM25). Toute modification qui touche la recherche est évaluée **avant** d'être gardée.

## Justification

- Rend chaque choix défendable et reproductible.
- BM25 sert de baseline : l'apport du vectoriel, de l'hybride et du reranker devient mesurable.
- C'est le cœur de la valeur portfolio : un tableau de résultats et des décisions argumentées par des chiffres.

## Conséquences

- `eval/questions.yaml` : questions typées (`exact`, `reformulation`, `question`, `multilingue`), équilibrées, dont une partie écrite de mémoire pour éviter le biais lexical.
- Métriques : Recall@5, Recall@10, MRR, globales et par type. Je code moi-même les métriques (exercice d'apprentissage).
- Chaque exécution est sauvegardée dans `eval/results/` avec sa configuration complète.
- Chaque recherche ratée en usage réel devient une nouvelle question.
- Le jeu de test contient des chemins vers mes documents personnels : il reste hors du repo public si nécessaire (ou anonymisé pour la démo).
- En V2, ajout de métriques RAG : fidélité, exactitude des citations.
