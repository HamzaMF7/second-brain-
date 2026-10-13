"""Migrations numérotées du schéma : fichiers `migrations/NNN_nom.sql` appliqués dans l'ordre."""

import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from importlib.resources.abc import Traversable

_FILENAME = re.compile(r"^(\d{3})_([a-z0-9_]*[a-z0-9])\.sql$")

_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT    NOT NULL
) STRICT
"""


class MigrationError(Exception):
    """Migration introuvable, mal nommée, en échec, ou base plus récente que le code."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def label(self) -> str:
        return f"{self.version:03d}_{self.name}"


def load_migrations(directory: Traversable | None = None) -> list[Migration]:
    """Lit les fichiers NNN_nom.sql (par défaut ceux du paquet), triés par numéro."""
    source = directory if directory is not None else files("second_brain.storage") / "migrations"
    found: dict[int, Migration] = {}
    for entry in source.iterdir():
        if not entry.name.endswith(".sql"):
            continue
        match = _FILENAME.match(entry.name)
        if match is None:
            raise MigrationError(
                f"Migration au nom invalide : {entry.name} (attendu : NNN_nom.sql)"
            )
        version = int(match.group(1))
        if version in found:
            raise MigrationError(f"Numéro de migration en double : {version:03d}")
        found[version] = Migration(version, match.group(2), entry.read_text(encoding="utf-8"))
    return [found[version] for version in sorted(found)]


def current_version(conn: sqlite3.Connection) -> int:
    """Dernière migration appliquée ; 0 pour une base vide."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
    ).fetchone()
    if exists is None:
        return 0
    (version,) = conn.execute("SELECT coalesce(max(version), 0) FROM schema_version").fetchone()
    return int(version)


def migrate(conn: sqlite3.Connection, migrations: Sequence[Migration] | None = None) -> list[int]:
    """Applique les migrations manquantes, chacune dans sa propre transaction.

    Renvoie les versions appliquées (liste vide si la base est à jour). La connexion doit
    être en mode transactionnel (`db.connect`) : sinon le DDL ne serait pas annulé en cas
    d'échec. Les fichiers SQL ne doivent donc pas contenir BEGIN ni COMMIT.
    """
    available = sorted(migrations if migrations is not None else load_migrations(), key=_version)
    with conn:
        conn.execute(_SCHEMA_VERSION_TABLE)

    current = current_version(conn)
    latest = available[-1].version if available else 0
    if current > latest:
        raise MigrationError(
            f"Base en version {current}, plus récente que le code (version {latest})"
        )

    applied: list[int] = []
    for migration in available:
        if migration.version <= current:
            continue
        try:
            with conn:  # COMMIT si tout passe, ROLLBACK sinon (y compris le DDL)
                conn.executescript(migration.sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (migration.version, datetime.now(UTC).isoformat(timespec="seconds")),
                )
        except sqlite3.Error as exc:
            raise MigrationError(
                f"Échec de la migration {migration.label} ({type(exc).__name__})"
            ) from exc
        applied.append(migration.version)
    return applied


def _version(migration: Migration) -> int:
    return migration.version
