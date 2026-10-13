"""Intégration : deux indexations de tests/fixtures, la seconde ne retraite rien."""

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from second_brain.cli import app
from second_brain.extraction.base import DocumentExtractor
from second_brain.extraction.markdown import MarkdownExtractor
from second_brain.extraction.models import ExtractedDocument
from second_brain.extraction.pdf import PdfExtractor
from second_brain.extraction.registry import ExtractorRegistry
from second_brain.extraction.text import TextExtractor
from second_brain.indexing.changes import sha256_file
from second_brain.indexing.pipeline import index_folder
from second_brain.storage.db import open_database

FIXTURES = Path(__file__).parent / "fixtures"


class CountingExtractor(DocumentExtractor):
    """Enveloppe un vrai extracteur et note chaque extraction (même contrat, pattern Strategy)."""

    def __init__(self, inner: DocumentExtractor, log: list[str]) -> None:
        self.inner = inner
        self.log = log

    def supports(self, extension: str) -> bool:
        return self.inner.supports(extension)

    def extract(self, path: Path) -> ExtractedDocument:
        self.log.append(path.name)
        return self.inner.extract(path)


class Spy:
    """Compte les extractions et les calculs de hash, sans changer leur résultat."""

    def __init__(self) -> None:
        self.extracted: list[str] = []
        self.hashed: list[str] = []
        inner = [PdfExtractor(), MarkdownExtractor(), TextExtractor()]
        self.registry = ExtractorRegistry(CountingExtractor(e, self.extracted) for e in inner)

    def hash_file(self, path: Path) -> str:
        self.hashed.append(path.name)
        return sha256_file(path)


def snapshot(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return conn.execute(
        "SELECT d.id, d.path, d.mtime, d.content_hash, d.status, d.indexed_at, c.id, c.text"
        " FROM documents d LEFT JOIN chunks c ON c.document_id = d.id ORDER BY d.id, c.id"
    ).fetchall()


def test_deuxieme_indexation_des_fixtures_ne_retraite_rien(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "index.db")
    fixture_count = len(list(FIXTURES.iterdir()))

    first_spy = Spy()
    first = index_folder(conn, FIXTURES, first_spy.registry, hash_file=first_spy.hash_file)
    assert first.added == fixture_count
    assert len(first_spy.extracted) == fixture_count
    before = snapshot(conn)

    second_spy = Spy()
    second = index_folder(conn, FIXTURES, second_spy.registry, hash_file=second_spy.hash_file)

    assert (second.added, second.modified, second.touched, second.deleted, second.errors) == (
        0,
        0,
        0,
        0,
        0,
    )
    assert second.unchanged == fixture_count
    assert second_spy.extracted == []  # aucune extraction
    assert second_spy.hashed == []  # aucun fichier lu : mtime et taille suffisent
    assert snapshot(conn) == before  # aucune ligne réécrite


def test_deuxieme_indexation_des_fixtures_par_la_cli(tmp_path: Path) -> None:
    runner = CliRunner()
    args = ["index", str(FIXTURES), "--db", str(tmp_path / "index.db")]
    fixture_count = len(list(FIXTURES.iterdir()))

    runner.invoke(app, args)
    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert "Ajoutés     : 0" in result.stdout
    assert f"Inchangés   : {fixture_count}" in result.stdout
