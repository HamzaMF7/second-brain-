from pathlib import Path

from second_brain.extraction.models import Page
from second_brain.extraction.text import TextExtractor

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_supporte_uniquement_txt() -> None:
    extractor = TextExtractor()

    assert extractor.supports(".txt")
    assert not extractor.supports(".md")


def test_extrait_un_fichier_texte_en_une_page() -> None:
    path = FIXTURES / "idees.txt"

    doc = TextExtractor().extract(path)

    assert doc.path == path
    assert doc.title is None
    assert doc.sections == ()
    assert doc.is_scanned is False
    assert len(doc.pages) == 1
    assert doc.pages[0].number == 1
    assert "café, élève, Noël" in doc.text
    assert doc.metadata == {"encoding": "utf-8-sig"}


def test_fichier_vide_donne_une_page_vide(tmp_path: Path) -> None:
    path = tmp_path / "vide.txt"
    path.write_bytes(b"")

    doc = TextExtractor().extract(path)

    assert doc.pages == (Page(number=1, text=""),)
