import dataclasses
from pathlib import Path

import pytest

from second_brain.extraction.models import ExtractedDocument, Page, Section


def make_doc(*pages: Page) -> ExtractedDocument:
    return ExtractedDocument(path=Path("notes.md"), title=None, pages=pages)


def test_text_concatene_les_pages_separees_par_une_ligne_vide() -> None:
    doc = make_doc(Page(number=1, text="Première page."), Page(number=2, text="Deuxième page."))

    assert doc.text == "Première page.\n\nDeuxième page."


def test_text_d_une_seule_page_est_le_texte_de_la_page() -> None:
    doc = make_doc(Page(number=1, text="Tout le contenu."))

    assert doc.text == "Tout le contenu."


def test_text_d_un_document_sans_page_est_vide() -> None:
    assert make_doc().text == ""


def test_valeurs_par_defaut() -> None:
    doc = make_doc()

    assert doc.sections == ()
    assert doc.metadata == {}
    assert doc.is_scanned is False


def test_metadata_par_defaut_n_est_pas_partagee_entre_documents() -> None:
    first, second = make_doc(), make_doc()

    first.metadata["author"] = "Alice"

    assert second.metadata == {}


def test_les_modeles_sont_immuables() -> None:
    doc = make_doc(Page(number=1, text="a"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        doc.is_scanned = True  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        doc.pages[0].text = "b"  # type: ignore[misc]


def test_section_d_un_markdown_n_a_pas_de_page() -> None:
    section = Section(title="PostgreSQL vs MongoDB", level=2, page=None, offset=0)

    assert section.page is None
