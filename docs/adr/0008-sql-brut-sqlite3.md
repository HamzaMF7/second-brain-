# 0008 — Accès aux données en SQL brut avec sqlite3

- Date : 2026-10-13
- Statut : Accepté

## Contexte

L'étape 2 crée la couche `storage/` : schéma, migrations, insertion et purge des documents et de leurs chunks. Il faut choisir comment le code Python parle à SQLite.

Contraintes :
- SQLite est la base unique (ADR 0002), et le cœur du projet repose sur deux fonctionnalités propres à SQLite : **FTS5** (`chunks_fts`, recherche BM25) et **sqlite-vec** (`chunk_vectors`). Ce sont des tables virtuelles.
- Un document est indexé dans une seule transaction ; les clés étrangères doivent être activées (`PRAGMA foreign_keys = ON`) à chaque connexion.
- Toute évolution de schéma passe par une migration numérotée.
- Projet d'apprentissage (phase 1), qui deviendra peut-être un produit avec une API FastAPI (V1).

## Options étudiées

- **A. `sqlite3` brut (bibliothèque standard)** : aucune dépendance, contrôle total (transactions, PRAGMA, `executemany`), un seul langage pour les tables classiques, FTS5 et sqlite-vec. Mais plus de code répétitif (conversion ligne ↔ dataclass à la main), discipline des paramètres liés (`?`) à tenir, migrations à écrire soi-même.
- **B. SQLModel (ORM, SQLAlchemy + Pydantic)** : moins de code répétitif, modèles réutilisables pour FastAPI, injection SQL impossible par construction. Mais trois dépendances, typage délicat sous mypy strict, et **aucune prise en charge de FTS5 ni de sqlite-vec** : la recherche, les triggers et les tables virtuelles resteraient en SQL brut, d'où deux styles dans le même module.
- **C. SQLAlchemy Core (sans ORM)** : requêtes construites en Python, plus structuré que le SQL brut. Même dépendance lourde que B et même absence de prise en charge de FTS5 et sqlite-vec.

## Décision

Accès aux données en **SQL brut avec le module `sqlite3`** de la bibliothèque standard, regroupé dans `storage/`.

## Justification

- La partie qu'un ORM simplifierait (deux tables classiques, `documents` et `chunks`) est petite ; celle qu'il ne couvre pas (FTS5, sqlite-vec, triggers) est le cœur du projet. Un seul style de code partout.
- Objectif d'apprentissage : maîtriser SQL et SQLite de bout en bout (transactions, clés étrangères, index, plans d'exécution).
- Aucune dépendance nouvelle ; typage simple sous mypy strict.

## Conséquences

- **Toutes les requêtes passent par des paramètres liés (`?`)** ; jamais de f-string ni de concaténation pour insérer une valeur dans du SQL. À vérifier en relecture.
- Une seule fonction ouvre les connexions et applique les PRAGMA (`foreign_keys = ON`, au minimum) ; aucun autre module n'appelle `sqlite3.connect`.
- Le SQL reste confiné à `storage/` : les autres modules manipulent des dataclasses, pas des lignes SQL.
- Migrations : fichiers `storage/migrations/NNN_description.sql` appliqués dans l'ordre par une petite fonction, avec la version courante dans `schema_version`.
- Conversion ligne ↔ dataclass écrite à la main et testée.
- En V1, les schémas de l'API FastAPI seront des modèles Pydantic distincts des tables. À réévaluer si ce double modèle devient coûteux.
