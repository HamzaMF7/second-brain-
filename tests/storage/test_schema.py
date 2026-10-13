"""Le schéma initial impose les règles de la section 7 du CLAUDE.md."""

import sqlite3
from pathlib import Path

import pytest

from second_brain.storage.db import open_database

INSERT_DOCUMENT = (
    "INSERT INTO documents"
    " (path, filename, extension, size, mtime, content_hash, status, indexed_at)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)


def add_document(
    conn: sqlite3.Connection, path: str = "/notes/a.md", status: str = "indexed"
) -> int:
    with conn:
        cursor = conn.execute(
            INSERT_DOCUMENT,
            (
                path,
                "a.md",
                ".md",
                120,
                1_700_000_000_123_456_789,
                "abc",
                status,
                "2026-10-13T10:00:00Z",
            ),
        )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def add_chunk(conn: sqlite3.Connection, document_id: int, index: int) -> None:
    with conn:
        conn.execute(
            "INSERT INTO chunks (document_id, chunk_index, text) VALUES (?, ?, ?)",
            (document_id, index, f"passage {index}"),
        )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return open_database(tmp_path / "a.db")


def test_supprimer_un_document_supprime_ses_chunks(conn: sqlite3.Connection) -> None:
    kept = add_document(conn, "/notes/garde.md")
    deleted = add_document(conn, "/notes/supprime.md")
    add_chunk(conn, kept, 0)
    add_chunk(conn, deleted, 0)
    add_chunk(conn, deleted, 1)

    with conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (deleted,))

    assert conn.execute("SELECT document_id FROM chunks").fetchall() == [(kept,)]


def test_chunk_sans_document_est_refuse(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_chunk(conn, document_id=999, index=0)


def test_chemin_unique(conn: sqlite3.Connection) -> None:
    add_document(conn, "/notes/a.md")

    with pytest.raises(sqlite3.IntegrityError):
        add_document(conn, "/notes/a.md")


def test_index_de_chunk_unique_par_document(conn: sqlite3.Connection) -> None:
    document_id = add_document(conn)
    add_chunk(conn, document_id, 0)

    with pytest.raises(sqlite3.IntegrityError):
        add_chunk(conn, document_id, 0)


def test_statut_inconnu_est_refuse(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_document(conn, status="en_cours")


def test_tables_strictes_refusent_un_mauvais_type(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute(
            INSERT_DOCUMENT,
            ("/a.md", "a.md", ".md", "grand", 0, None, "indexed", "2026-10-13T10:00:00Z"),
        )


def test_mtime_en_nanosecondes_est_conserve_exactement(conn: sqlite3.Connection) -> None:
    add_document(conn)

    assert conn.execute("SELECT mtime FROM documents").fetchone() == (1_700_000_000_123_456_789,)


def test_document_en_erreur_peut_ne_pas_avoir_de_hash(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            INSERT_DOCUMENT,
            ("/a.pdf", "a.pdf", ".pdf", 10, 0, None, "error", "2026-10-13T10:00:00Z"),
        )
