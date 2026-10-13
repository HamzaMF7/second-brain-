import sqlite3
from pathlib import Path

import pytest

from second_brain.storage.db import connect, open_database
from second_brain.storage.migrator import (
    Migration,
    MigrationError,
    current_version,
    load_migrations,
    migrate,
)


def tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {name for (name,) in rows}


def test_connect_active_les_cles_etrangeres(tmp_path: Path) -> None:
    conn = connect(tmp_path / "a.db")

    assert conn.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_base_vide_est_migree(tmp_path: Path) -> None:
    conn = connect(tmp_path / "a.db")
    assert current_version(conn) == 0

    applied = migrate(conn)

    assert applied == [m.version for m in load_migrations()]
    assert {"schema_version", "folders", "documents", "chunks"} <= tables(conn)
    assert current_version(conn) == load_migrations()[-1].version


def test_migration_rejouee_est_sans_effet(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    migrate(connect(path))

    conn = connect(path)
    applied = migrate(conn)

    assert applied == []
    assert conn.execute("SELECT count(*) FROM schema_version").fetchone() == (
        len(load_migrations()),
    )


def test_open_database_ouvre_et_migre(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "a.db")

    assert "documents" in tables(conn)
    assert conn.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_seules_les_nouvelles_migrations_sont_appliquees(tmp_path: Path) -> None:
    conn = connect(tmp_path / "a.db")
    first = Migration(1, "first", "CREATE TABLE a (x INTEGER) STRICT;")
    second = Migration(2, "second", "CREATE TABLE b (x INTEGER) STRICT;")
    migrate(conn, [first])

    assert migrate(conn, [first, second]) == [2]
    assert {"a", "b"} <= tables(conn)


def test_migration_en_echec_est_annulee_entierement(tmp_path: Path) -> None:
    conn = connect(tmp_path / "a.db")
    good = Migration(1, "good", "CREATE TABLE a (x INTEGER) STRICT;")
    broken = Migration(2, "broken", "CREATE TABLE b (x INTEGER) STRICT; CREATE TABLE (;")

    with pytest.raises(MigrationError, match="002_broken"):
        migrate(conn, [good, broken])

    assert current_version(conn) == 1
    assert "b" not in tables(conn)  # la première instruction de la migration 2 est annulée


def test_base_plus_recente_que_le_code_est_refusee(tmp_path: Path) -> None:
    conn = connect(tmp_path / "a.db")
    migrate(conn, [Migration(1, "a", "SELECT 1;"), Migration(2, "b", "SELECT 1;")])

    with pytest.raises(MigrationError, match="plus récente"):
        migrate(conn, [Migration(1, "a", "SELECT 1;")])


def test_charge_les_fichiers_dans_l_ordre_numerique(tmp_path: Path) -> None:
    (tmp_path / "010_later.sql").write_text("SELECT 10;", encoding="utf-8")
    (tmp_path / "002_early.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignoré", encoding="utf-8")

    migrations = load_migrations(tmp_path)

    assert [(m.version, m.name) for m in migrations] == [(2, "early"), (10, "later")]


@pytest.mark.parametrize("filename", ["1_short.sql", "002-tiret.sql", "002_.sql", "abc_x.sql"])
def test_nom_de_fichier_invalide_est_refuse(tmp_path: Path, filename: str) -> None:
    (tmp_path / filename).write_text("SELECT 1;", encoding="utf-8")

    with pytest.raises(MigrationError, match="nom invalide"):
        load_migrations(tmp_path)


def test_numero_en_double_est_refuse(tmp_path: Path) -> None:
    (tmp_path / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "001_b.sql").write_text("SELECT 1;", encoding="utf-8")

    with pytest.raises(MigrationError, match="en double"):
        load_migrations(tmp_path)


def test_open_database_cree_le_dossier_parent(tmp_path: Path) -> None:
    path = tmp_path / "nouveau" / "dossier" / "a.db"

    open_database(path)

    assert path.exists()
