from pathlib import Path

import pytest

from second_brain.extraction.base import DocumentExtractor
from second_brain.extraction.errors import ExtractionError, UnsupportedFormatError
from second_brain.extraction.markdown import MarkdownExtractor
from second_brain.extraction.models import ExtractedDocument, Page
from second_brain.extraction.pdf import PdfExtractor
from second_brain.extraction.registry import ExtractorRegistry, default_registry
from second_brain.extraction.text import TextExtractor


class FakeExtractor(DocumentExtractor):
    """Extracteur factice : ne lit aucun fichier, renvoie un texte fixe."""

    def __init__(self, extensions: set[str], label: str = "fake") -> None:
        self.extensions = extensions
        self.label = label

    def supports(self, extension: str) -> bool:
        return extension in self.extensions

    def extract(self, path: Path) -> ExtractedDocument:
        return ExtractedDocument(path=path, title=None, pages=(Page(1, self.label),))


def test_renvoie_l_extracteur_qui_supporte_l_extension() -> None:
    markdown = FakeExtractor({".md"})
    text = FakeExtractor({".txt"})
    registry = ExtractorRegistry([markdown, text])

    assert registry.for_path(Path("notes/idee.txt")) is text


def test_l_extension_est_insensible_a_la_casse() -> None:
    pdf = FakeExtractor({".pdf"})
    registry = ExtractorRegistry([pdf])

    assert registry.for_path(Path("Rapport.PDF")) is pdf


def test_le_premier_extracteur_compatible_l_emporte() -> None:
    first = FakeExtractor({".md"}, label="first")
    second = FakeExtractor({".md"}, label="second")
    registry = ExtractorRegistry([first, second])

    assert registry.for_path(Path("a.md")) is first


def test_format_non_supporte_leve_une_erreur_explicite() -> None:
    registry = ExtractorRegistry([FakeExtractor({".md"})])

    with pytest.raises(UnsupportedFormatError) as excinfo:
        registry.for_path(Path("tableur.xlsx"))

    assert excinfo.value.extension == ".xlsx"
    assert ".xlsx" in str(excinfo.value)


def test_fichier_sans_extension_n_est_pas_supporte() -> None:
    registry = ExtractorRegistry([FakeExtractor({".md"})])

    with pytest.raises(UnsupportedFormatError):
        registry.for_path(Path("README"))


def test_registre_vide_ne_supporte_rien() -> None:
    with pytest.raises(UnsupportedFormatError):
        ExtractorRegistry([]).for_path(Path("a.md"))


def test_format_non_supporte_est_une_erreur_d_extraction() -> None:
    assert issubclass(UnsupportedFormatError, ExtractionError)


def test_le_contrat_ne_peut_pas_etre_instancie() -> None:
    with pytest.raises(TypeError):
        DocumentExtractor()  # type: ignore[abstract]


def test_registre_par_defaut_couvre_les_formats_v0() -> None:
    registry = default_registry()

    assert isinstance(registry.for_path(Path("a.pdf")), PdfExtractor)
    assert isinstance(registry.for_path(Path("a.md")), MarkdownExtractor)
    assert isinstance(registry.for_path(Path("a.markdown")), MarkdownExtractor)
    assert isinstance(registry.for_path(Path("a.txt")), TextExtractor)


def test_supports_indique_si_un_extracteur_existe() -> None:
    registry = ExtractorRegistry([FakeExtractor({".md"})])

    assert registry.supports(Path("notes/A.MD"))
    assert not registry.supports(Path("tableur.xlsx"))
    assert not registry.supports(Path("README"))
