# Journal de bord

> Une entrée par fin d'étape : ce qui a été fait, appris, ce qui a été difficile, les chiffres.

## 2026-10-12 — Étape 1 : extraction

**Fait**
- Modèles `ExtractedDocument` / `Page` / `Section` (dataclasses immuables), avec `Section.offset`
  pour que le futur chunking sache où commence chaque section.
- Pattern Strategy : interface `DocumentExtractor`, registre `ExtractorRegistry`,
  `default_registry()` comme unique endroit qui liste les formats.
- Extracteurs TXT et Markdown : encodage UTF-8 → cp1252 → Latin-1, normalisation NFC,
  titres Markdown hors blocs de code.
- Corpus de 6 PDF inventés (colonnes, césures, ligatures, slides, export façon Word, scan, mixte)
  et comparatif PyMuPDF / pypdf → ADR 0007 : PyMuPDF.
- `PdfExtractor` : une page par page, ligatures développées, détection des scans
  (< 50 caractères/page en moyenne), erreurs typées sans contenu.
- Commande `second-brain extract` et script `extract_all.py` (rapport sans contenu).
- 56 tests.

**Appris**
- Un PDF est un format de dessin : ordre de lecture, mots et lignes sont reconstruits.
- Un encodage transforme des octets en caractères ; UTF-8 est strict, donc essayé en premier ;
  Latin-1 accepte tout, donc en dernier.
- NFC : un même « é » peut s'écrire de deux façons ; sans normalisation, la recherche échoue en silence.
- `raise ... from None` coupe la chaîne d'exceptions, utile quand le message d'origine peut
  contenir du contenu.
- Ordre des `except` : le plus spécifique d'abord.
- Licences : l'AGPL est contaminante à la distribution, pas à l'usage personnel.

**Difficile**
- Aucune bibliothèque ne remet deux colonnes dans l'ordre ; `TEXT_DEHYPHENATE` de MuPDF
  n'a eu aucun effet.
- Trois fois, un test était faux et le code juste : vérifier qui a tort avant de corriger.
- Un PDF sans permission était signalé « corrompu » : MuPDF masquait la vraie cause.

**Chiffres**
- Corpus inventé : PyMuPDF 5 à 15× plus rapide que pypdf ; pypdf colle des lignes
  (`Conclusionsouvient`). Pas encore d'évaluation de recherche (étape 4).

## 2026-10-13 — Étape 2 : stockage et indexation

**Fait**
- ADR 0008 : SQL brut avec `sqlite3`, confiné à `storage/`.
- Schéma initial (tables `STRICT`) et migrations numérotées `NNN_nom.sql`, une transaction
  chacune, historique dans `schema_version`.
- Scanner : exclusions de la section 8 centralisées dans `ScanConfig`, liens symboliques
  non suivis, aucune lecture de contenu.
- Détection des changements pure (nouveau, modifié, touché, inchangé, supprimé), testée sans
  base ; hash SHA-256 seulement si nécessaire ; documents en erreur retentés.
- Pipeline : un document = une transaction ; erreur → statut `error`, le pipeline continue ;
  logs sans contenu, vérifiés par un test.
- Commande `second-brain index` : progression, résumé, `--verbose`, base dans
  `~/.local/share/second-brain/`.
- Test d'intégration : le deuxième passage ne fait aucune extraction, aucun hash, aucune écriture.
- 138 tests.

**Appris**
- L'entonnoir mtime/taille → hash → extraction : chaque étage évite le suivant.
- Transactions : tout ou rien, et un seul fsync par document au lieu d'un par ligne.
- `ON DELETE CASCADE` ne marche qu'avec `PRAGMA foreign_keys = ON`, à chaque connexion,
  et ne couvre pas les tables virtuelles (FTS5, sqlite-vec).
- `ON CONFLICT DO UPDATE` garde l'id ; `INSERT OR REPLACE` le change.
- `dirnames[:] = ...` pour piloter `os.walk` ; `lstat` pour repérer un lien sans le suivre.
- Un espion qui enveloppe un extracteur prouve qu'aucun travail n'est refait :
  compter les « inchangés » ne suffit pas.

**Difficile**
- Deux pièges silencieux de `sqlite3` : PRAGMA ignoré dans une transaction, et DDL non
  annulé dans le mode par défaut de Python. Découverts en testant avant de concevoir.
- Typer 0.27 n'utilise plus Click : il a fallu un `Protocol` plutôt qu'un type privé.

**Chiffres**
- Fixtures : 2 documents ajoutés au 1er passage, 2 inchangés au 2e, 0 relecture de fichier.
  Pas encore d'évaluation de recherche (étape 4).
