# 0001 — Python pour le cœur, CLI avant API et interface

- Date : 2026-10-08
- Statut : Accepté

## Contexte

La partie la plus incertaine du projet est la qualité de la recherche (extraction, chunking, embeddings, fusion, reranking). C'est elle qu'il faut pouvoir expérimenter vite. Le projet est d'abord un projet d'apprentissage, puis un outil personnel, puis peut-être un produit desktop.

## Options étudiées

- **Python** : écosystème IA et documentaire le plus riche, prototypage rapide. Moins adapté à une distribution desktop légère.
- **TypeScript / Node.js** : même langage que la future interface. Bibliothèques IA et documentaires moins pratiques.
- **Rust** : performances, faible mémoire, idéal pour un produit desktop. Expérimentation IA beaucoup plus lente.
- **C# / .NET** : robuste et typé. Écosystème IA moderne moins direct.

Pour l'interface en V0 : CLI, API FastAPI + interface web, ou application Tauri directement.

## Décision

Python 3.12 (géré avec uv) pour tout le cœur. En V0, **uniquement une CLI** ; l'API FastAPI arrive en V1, l'application Tauri en phase produit.

## Justification

- Python maximise la vitesse d'expérimentation sur la partie incertaine.
- Une CLI suffit pour indexer, rechercher et évaluer ; une interface en V0 détournerait le temps de la qualité de recherche.
- La logique vit dans des modules indépendants de la couche d'entrée : CLI, API puis desktop les réutilisent sans réécriture.

## Conséquences

- Aucune logique métier dans `cli.py` (et plus tard dans les routes FastAPI).
- Si Python devient un goulot d'étranglement (indexation de gros volumes), une brique pourra être réécrite en Rust derrière la même interface.
- Le packaging desktop d'un backend Python reste un défi : voir ADR 0002 et 0004, qui limitent son poids.
