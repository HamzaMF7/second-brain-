"""Tests d'intégration du pipeline : vrais fichiers, vrais extracteurs, vraie base SQLite."""

import logging
import os
import sqlite3
from pathlib import Path

import pymupdf
import pytest

from second_brain.extraction.registry import default_registry
from second_brain.indexing.pipeline import IndexReport, index_folder
from second_brain.storage.db import open_database

SECRET = "CONTENU_CONFIDENTIEL_42"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return open_database(tmp_path / "index.db")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "notes"
    folder.mkdir()
    return folder


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(conn: sqlite3.Connection, root: Path) -> IndexReport:
    return index_folder(conn, root, default_registry())


def documents(conn: sqlite3.Connection) -> dict[str, tuple[str, str | None]]:
    """nom de fichier → (statut, texte du chunk ou None)."""
    rows = conn.execute(
        "SELECT d.filename, d.status, c.text FROM documents d"
        " LEFT JOIN chunks c ON c.document_id = d.id ORDER BY d.filename"
    ).fetchall()
    return {name: (status, text) for name, status, text in rows}


def chunk_ids(conn: sqlite3.Connection) -> list[int]:
    return [chunk_id for (chunk_id,) in conn.execute("SELECT id FROM chunks ORDER BY id")]


def test_premier_passage_indexe_les_nouveaux_fichiers(conn: sqlite3.Connection, root: Path) -> None:
    write(root / "a.md", "# Titre\n\nPostgreSQL contre MongoDB")
    write(root / "sous" / "b.txt", "Idées en vrac")

    report = run(conn, root)

    assert report.added == 2
    assert documents(conn) == {
        "a.md": ("indexed", "# Titre\n\nPostgreSQL contre MongoDB"),
        "b.txt": ("indexed", "Idées en vrac"),
    }
    assert conn.execute("SELECT path FROM folders").fetchall() == [(str(root),)]


def test_second_passage_ne_retraite_rien(conn: sqlite3.Connection, root: Path) -> None:
    write(root / "a.md", "texte")
    run(conn, root)
    before = chunk_ids(conn)

    report = run(conn, root)

    assert (report.added, report.modified, report.touched, report.deleted) == (0, 0, 0, 0)
    assert report.unchanged == 1
    assert chunk_ids(conn) == before  # chunks non réécrits


def test_fichier_modifie_est_reindexe_sous_le_meme_id(conn: sqlite3.Connection, root: Path) -> None:
    path = write(root / "a.md", "version 1")
    run(conn, root)
    (old_id,) = conn.execute("SELECT id FROM documents").fetchone()

    write(path, "version 2, plus longue")
    report = run(conn, root)

    assert report.modified == 1
    assert documents(conn)["a.md"] == ("indexed", "version 2, plus longue")
    assert conn.execute("SELECT id FROM documents").fetchone() == (old_id,)


def test_fichier_touche_met_a_jour_le_mtime_sans_reindexer(
    conn: sqlite3.Connection, root: Path
) -> None:
    path = write(root / "a.md", "texte")
    run(conn, root)
    before = chunk_ids(conn)
    new_mtime_ns = path.stat().st_mtime_ns + 5_000_000_000
    os.utime(path, ns=(new_mtime_ns, new_mtime_ns))

    report = run(conn, root)

    assert report.touched == 1
    assert chunk_ids(conn) == before
    assert conn.execute("SELECT mtime FROM documents").fetchone() == (new_mtime_ns,)
    assert run(conn, root).unchanged == 1  # le passage suivant le voit inchangé


def test_fichier_supprime_est_purge(conn: sqlite3.Connection, root: Path) -> None:
    path = write(root / "a.md", "texte")
    write(root / "b.md", "garde")
    run(conn, root)

    path.unlink()
    report = run(conn, root)

    assert report.deleted == 1
    assert list(documents(conn)) == ["b.md"]
    assert conn.execute("SELECT count(*) FROM chunks").fetchone() == (1,)


def test_erreur_sur_un_fichier_n_arrete_pas_le_pipeline(
    conn: sqlite3.Connection, root: Path
) -> None:
    (root / "corrompu.pdf").write_bytes(b"pas un PDF")
    write(root / "a.md", "texte")

    report = run(conn, root)

    assert (report.added, report.errors) == (1, 1)
    status, text = documents(conn)["corrompu.pdf"]
    assert (status, text) == ("error", None)
    (error,) = conn.execute("SELECT error FROM documents WHERE status = 'error'").fetchone()
    assert "corrompu.pdf" in error


def test_document_modifie_qui_echoue_perd_ses_anciens_chunks(
    conn: sqlite3.Connection, root: Path
) -> None:
    path = root / "doc.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "Texte du PDF inventé. " * 10)
    pdf.save(path)
    run(conn, root)

    path.write_bytes(b"maintenant corrompu")
    run(conn, root)

    assert documents(conn)["doc.pdf"] == ("error", None)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignore les permissions")
def test_document_en_erreur_est_retente_au_passage_suivant(
    conn: sqlite3.Connection, root: Path
) -> None:
    path = write(root / "a.txt", "texte")
    path.chmod(0)
    try:
        assert run(conn, root).errors == 1
    finally:
        path.chmod(0o644)

    report = run(conn, root)  # mtime inchangé, mais le document était en erreur

    assert report.modified == 1
    assert documents(conn)["a.txt"] == ("indexed", "texte")


def test_pdf_scanne_enregistre_sans_chunk(conn: sqlite3.Connection, root: Path) -> None:
    pdf = pymupdf.open()
    pdf.new_page()
    pdf.save(root / "scan.pdf")

    report = run(conn, root)

    assert report.scanned_pdfs == 1
    assert documents(conn)["scan.pdf"] == ("scanned", None)


def test_indexer_un_dossier_ne_supprime_pas_les_documents_d_un_autre(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    write(tmp_path / "notes" / "a.md", "a")
    write(tmp_path / "notes-old" / "b.md", "b")
    run(conn, tmp_path / "notes-old")

    report = run(conn, tmp_path / "notes")

    assert report.deleted == 0
    assert sorted(documents(conn)) == ["a.md", "b.md"]


def test_progression_signalee_pour_chaque_fichier_traite(
    conn: sqlite3.Connection, root: Path
) -> None:
    for name in ("a.md", "b.md", "c.md"):
        write(root / name, name)
    calls: list[tuple[int, int]] = []

    index_folder(
        conn, root, default_registry(), on_progress=lambda done, total: calls.append((done, total))
    )

    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_les_logs_ne_contiennent_aucun_contenu(
    conn: sqlite3.Connection, root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write(root / "secret.md", f"# {SECRET}\n\n{SECRET}")
    (root / "corrompu.pdf").write_bytes(SECRET.encode())

    with caplog.at_level(logging.DEBUG):
        run(conn, root)

    assert "secret.md" in caplog.text  # le nom de fichier est autorisé
    assert SECRET not in caplog.text
    (error,) = conn.execute("SELECT error FROM documents WHERE status = 'error'").fetchone()
    assert SECRET not in error


def test_rapport_compte_les_fichiers_ignores(conn: sqlite3.Connection, root: Path) -> None:
    write(root / "a.md", "texte")
    write(root / "tableur.xlsx", "")

    report = run(conn, root)

    assert sum(report.skipped.values()) == 1
    assert report.seconds >= 0
