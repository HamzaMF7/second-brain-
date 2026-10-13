import sqlite3
from pathlib import Path

import pytest

from second_brain.storage.db import open_database
from second_brain.storage.documents import (
    ChunkRecord,
    DocumentRecord,
    DocumentStatus,
    delete_documents,
    documents_under,
    ensure_folder,
    save_document,
    update_file_metadata,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return open_database(tmp_path / "a.db")


def record(path: str = "/notes/a.md", **overrides: object) -> DocumentRecord:
    values: dict[str, object] = {
        "path": Path(path),
        "size": 10,
        "mtime_ns": 1_000,
        "content_hash": "h1",
        "status": DocumentStatus.INDEXED,
        "error": None,
    }
    values.update(overrides)
    return DocumentRecord(**values)  # type: ignore[arg-type]


def chunk_texts(conn: sqlite3.Connection, document_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT text FROM chunks WHERE document_id = ? ORDER BY chunk_index", (document_id,)
    ).fetchall()
    return [text for (text,) in rows]


def test_save_document_insere_le_document_et_ses_chunks(conn: sqlite3.Connection) -> None:
    document_id = save_document(conn, record(), [ChunkRecord(0, "un"), ChunkRecord(1, "deux")])

    row = conn.execute(
        "SELECT path, filename, extension, size, mtime, content_hash, status, error"
        " FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    assert row == ("/notes/a.md", "a.md", ".md", 10, 1_000, "h1", "indexed", None)
    assert chunk_texts(conn, document_id) == ["un", "deux"]


def test_save_document_remplace_un_document_existant_en_gardant_son_id(
    conn: sqlite3.Connection,
) -> None:
    first = save_document(conn, record(), [ChunkRecord(0, "ancien"), ChunkRecord(1, "ancien 2")])

    second = save_document(conn, record(content_hash="h2", size=20), [ChunkRecord(0, "nouveau")])

    assert second == first
    assert chunk_texts(conn, first) == ["nouveau"]
    assert conn.execute("SELECT count(*) FROM documents").fetchone() == (1,)


def test_save_document_est_tout_ou_rien(conn: sqlite3.Connection) -> None:
    # Deux chunks avec le même index : le second INSERT échoue, rien ne doit rester.
    with pytest.raises(sqlite3.IntegrityError):
        save_document(conn, record(), [ChunkRecord(0, "a"), ChunkRecord(0, "b")])

    assert conn.execute("SELECT count(*) FROM documents").fetchone() == (0,)
    assert conn.execute("SELECT count(*) FROM chunks").fetchone() == (0,)


def test_document_en_erreur_sans_chunk(conn: sqlite3.Connection) -> None:
    document_id = save_document(
        conn,
        record(status=DocumentStatus.ERROR, error="PDF illisible : a.pdf", content_hash=None),
        [],
    )

    assert chunk_texts(conn, document_id) == []


def test_documents_under_ne_renvoie_que_le_dossier_demande(conn: sqlite3.Connection) -> None:
    save_document(conn, record("/notes/a.md"), [])
    save_document(conn, record("/notes/sous/b.md"), [])
    save_document(conn, record("/notes-old/c.md"), [])  # piège d'un LIKE '/notes%'
    save_document(conn, record("/archives/d.md"), [])

    paths = [d.path for d in documents_under(conn, Path("/notes"))]

    assert paths == [Path("/notes/a.md"), Path("/notes/sous/b.md")]


def test_documents_under_renvoie_statut_et_metadonnees(conn: sqlite3.Connection) -> None:
    document_id = save_document(conn, record(status=DocumentStatus.ERROR, error="x"), [])

    (document,) = documents_under(conn, Path("/notes"))

    assert document.id == document_id
    assert (document.size, document.mtime_ns, document.content_hash) == (10, 1_000, "h1")
    assert document.status is DocumentStatus.ERROR


def test_update_file_metadata_ne_touche_pas_aux_chunks(conn: sqlite3.Connection) -> None:
    document_id = save_document(conn, record(), [ChunkRecord(0, "texte")])

    update_file_metadata(conn, document_id, size=10, mtime_ns=2_000)

    assert conn.execute("SELECT mtime FROM documents").fetchone() == (2_000,)
    assert chunk_texts(conn, document_id) == ["texte"]


def test_delete_documents_supprime_aussi_les_chunks(conn: sqlite3.Connection) -> None:
    kept = save_document(conn, record("/notes/a.md"), [ChunkRecord(0, "garde")])
    gone = save_document(conn, record("/notes/b.md"), [ChunkRecord(0, "parti")])

    assert delete_documents(conn, [gone]) == 1

    assert conn.execute("SELECT document_id FROM chunks").fetchall() == [(kept,)]


def test_ensure_folder_est_idempotent(conn: sqlite3.Connection) -> None:
    ensure_folder(conn, Path("/notes"))
    ensure_folder(conn, Path("/notes"))

    assert conn.execute("SELECT path, enabled FROM folders").fetchall() == [("/notes", 1)]
