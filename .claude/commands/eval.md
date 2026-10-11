---
description: Lancer l'évaluation et comparer avec les résultats précédents
argument-hint: <lexical|semantic|hybrid> [description de la configuration]
---
Lance l'évaluation pour : $ARGUMENTS

1. Exécute `uv run python eval/run_eval.py` avec le retriever indiqué et la configuration actuelle.
2. Affiche Recall@5, Recall@10 et MRR, globaux et par type de requête.
3. Compare avec le résultat précédent le plus pertinent dans eval/results/ (même retriever ou baseline BM25) : tableau avant / après avec les écarts.
4. Liste les 5 questions les plus mal classées avec le rang obtenu, et propose une hypothèse pour chacune.
5. Ne modifie aucun code et ne tire pas de conclusion définitive : donne ton interprétation, je décide.