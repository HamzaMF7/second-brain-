"""Ouverture de la base SQLite : seul endroit du code qui appelle sqlite3.connect (ADR 0008)."""

import sqlite3
from pathlib import Path

from second_brain.storage.migrator import migrate


def connect(path: Path) -> sqlite3.Connection:
    """Connexion avec clés étrangères actives, en mode transactionnel.

    PRAGMA foreign_keys est ignoré à l'intérieur d'une transaction : on l'exécute en
    autocommit, puis on passe en autocommit=False, où toute écriture se fait dans une
    transaction validée par `with conn:` (COMMIT) ou annulée en cas d'exception (ROLLBACK).
    """
    conn = sqlite3.connect(path, autocommit=True)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.autocommit = False
    return conn


def open_database(path: Path) -> sqlite3.Connection:
    """Ouvre la base (en créant son dossier si besoin) et applique les migrations manquantes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    migrate(conn)
    return conn
