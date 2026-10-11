---
description: Clôturer une étape du plan (critères de sortie, journal, CLAUDE.md)
argument-hint: <numéro de l'étape>
---
L'étape $ARGUMENTS est terminée. Fais dans l'ordre :

1. Rappelle les critères de sortie de l'étape $ARGUMENTS (voir docs/prompts-v0.md) et vérifie chacun : rempli, partiel ou non rempli, avec la preuve.
2. Vérifie que les ADR prévus pour cette étape existent dans docs/adr/.
3. Propose une entrée pour docs/journal.md : date, ce qui a été fait, ce que j'ai appris, ce qui a été difficile, chiffres d'évaluation s'il y en a. Je la relirai avant que tu l'ajoutes.
4. Mets à jour la section « État actuel » du CLAUDE.md (étape en cours, décisions prises et ouvertes, derniers résultats).
5. Liste ce qui pourrait poser problème pour l'étape suivante.