# 0007 — Bibliothèque d'extraction PDF

- Date : 2026-10-12
- Statut : Accepté

## Contexte

Le PDF est le format le plus délicat de la V0 : c'est un format de dessin, sans notion de mot, de ligne ni d'ordre de lecture. La qualité du texte extrait conditionne directement BM25 (mots collés ou coupés = tokens inexistants) et les embeddings (phrases mélangées = vecteurs moins pertinents).

Contraintes : exécution locale, documents français et anglais, CLI maintenant, application desktop distribuable plus tard (phase 2). L'extracteur reste derrière l'interface `DocumentExtractor` : changer de bibliothèque plus tard ne touche qu'une classe.

Mesures faites avec `scripts/compare_pdf_libs.py` sur un corpus de 6 PDF inventés générés par `scripts/make_pdf_samples.py` (deux colonnes, rapport long avec césures et ligatures, slides, export façon Word, scan, PDF mixte). Ce corpus imite les pièges connus mais pas les bizarreries des vrais outils (Word, LaTeX, scanners).

| Critère | PyMuPDF 1.28 | pypdf 6.20 |
|---|---|---|
| Temps par fichier (corpus de test) | 4 à 9 ms | 36 à 123 ms (5 à 15× plus lent) |
| Séparation des lignes | conserve un `\n` entre les lignes | colle parfois deux lignes : `quotidien.Les`, `Conclusionsouvient` |
| Deux colonnes écrites ligne à ligne | colonnes mélangées (y compris avec `sort=True`) | colonnes mélangées |
| Ligatures `ﬁ` / `ﬂ` | conservées telles quelles | conservées telles quelles |
| Césures, en-têtes répétés, insécables | non traités | non traités |
| PDF scanné / page scannée | 0 caractère, détectable | 0 caractère, détectable |
| Fichier corrompu | `FileDataError` | `PdfStreamError` + avertissements sur stderr |
| Taille installée | 64 Mo (moteur C MuPDF compilé) | 3,9 Mo (Python pur) |
| Licence | AGPL-3.0 ou licence commerciale Artifex | BSD-3-Clause |

## Options étudiées

- **PyMuPDF** : rapide, ne colle pas les lignes, outils avancés (blocs, positions, rendu en image utile pour un futur OCR). Mais licence AGPL : distribuer un produit qui l'intègre impose de publier tout le produit sous licence compatible AGPL, ou d'acheter une licence commerciale. Paquet lourd.
- **pypdf** : licence permissive, Python pur, léger, simple à packager. Mais plus lent et colle parfois des lignes, ce qui crée des tokens faux pour BM25.
- Non mesurées, pour mémoire : **pdfplumber** (MIT, basé sur pdfminer.six, bon sur les tableaux, lent) et **pypdfium2** (Apache/BSD, moteur PDF de Chrome, rapide).

## Décision

**PyMuPDF**, derrière l'interface `DocumentExtractor` (classe `PdfExtractor`).

## Justification

- **Qualité du texte** : pypdf colle des lignes (`Conclusionsouvient`), ce qui crée des tokens inexistants pour BM25 ; PyMuPDF conserve la séparation. La qualité de recherche passe avant le reste (principe 2).
- **Vitesse** : 5 à 15 fois plus rapide sur le corpus de test, sensible lors de l'indexation complète d'un corpus.
- **Outils pour la suite** : extraction par blocs et positions (piste pour l'ordre des colonnes), rendu de page en image (piste pour un futur OCR).
- **Licence** : en phase 1 (usage personnel, non distribué), l'AGPL n'impose aucune contrainte. Le coût de la licence n'apparaît qu'au moment de distribuer, et l'interface `DocumentExtractor` limite le changement éventuel à une seule classe.

## Conséquences

Quelle que soit l'option :
- Ces traitements nous reviennent : recoller les césures, retirer en-têtes et pieds de page répétés, ligatures (NFKC ou remplacement ciblé), ordre des colonnes.
- Détection des PDF scannés par nombre de caractères par page (tâche 1.7), valable avec les deux bibliothèques.
- La bibliothèque choisie passe dans les dépendances principales ; l'autre est retirée du groupe `dev`.

Propres à PyMuPDF :
- **Point de réévaluation obligatoire avant toute distribution (phase 2)** : soit publier Second Brain sous licence compatible AGPL, soit acheter une licence commerciale Artifex, soit remplacer `PdfExtractor` (pypdfium2 en premier candidat, à mesurer). Cet ADR sera alors remplacé.
- Paquet de 64 Mo à prendre en compte dans le packaging desktop.
- Vérifier sur de vrais PDF du corpus (tâche 1.9) que les constats faits sur le corpus inventé tiennent.
