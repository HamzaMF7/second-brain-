import os
from pathlib import Path

import pymupdf
import pytest

from second_brain.config import ExtractionConfig
from second_brain.extraction.errors import (
    CorruptedDocumentError,
    EncryptedDocumentError,
    ExtractionError,
)
from second_brain.extraction.pdf import PdfExtractor


def make_pdf(path: Path, pages: list[str], title: str = "") -> Path:
    """PDF inventé : une page par chaîne (vide = page blanche)."""
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    doc.set_metadata({"title": title})
    doc.save(path)
    return path


def make_scanned_pdf(path: Path, page_count: int) -> Path:
    """PDF dont les pages ne contiennent qu'une image, comme un scan."""
    doc = pymupdf.open()
    image = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
    image.clear_with(200)
    for _ in range(page_count):
        page = doc.new_page()
        page.insert_image(page.rect, pixmap=image)
    doc.save(path)
    return path


PARAGRAPH = "Notes inventées sur la numérisation des archives de Valcourt.\n" * 3


def test_supporte_uniquement_pdf() -> None:
    extractor = PdfExtractor()

    assert extractor.supports(".pdf")
    assert not extractor.supports(".md")


def test_une_page_par_page_du_pdf(tmp_path: Path) -> None:
    pages = [f"{name} page.\n{PARAGRAPH}" for name in ("Première", "Deuxième", "Troisième")]
    path = make_pdf(tmp_path / "a.pdf", pages)

    doc = PdfExtractor().extract(path)

    assert [p.number for p in doc.pages] == [1, 2, 3]
    assert "Deuxième page" in doc.pages[1].text
    assert doc.path == path
    assert doc.sections == ()
    assert doc.is_scanned is False


def test_le_titre_vient_des_metadonnees(tmp_path: Path) -> None:
    with_title = make_pdf(tmp_path / "a.pdf", [PARAGRAPH], title="Rapport fictif")
    without_title = make_pdf(tmp_path / "b.pdf", [PARAGRAPH])

    assert PdfExtractor().extract(with_title).title == "Rapport fictif"
    assert PdfExtractor().extract(without_title).title is None


def test_pdf_scanne_est_marque_sans_planter(tmp_path: Path) -> None:
    doc = PdfExtractor().extract(make_scanned_pdf(tmp_path / "scan.pdf", 2))

    assert doc.is_scanned is True
    assert len(doc.pages) == 2
    assert doc.text.strip() == ""


def test_un_peu_de_texte_parasite_reste_un_scan(tmp_path: Path) -> None:
    # Un numéro de page ou un filigrane sur un scan ne doit pas tromper la détection.
    path = make_pdf(tmp_path / "a.pdf", ["page 1", "page 2"])

    assert PdfExtractor().extract(path).is_scanned is True


def test_un_vrai_texte_n_est_pas_un_scan(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "a.pdf", [PARAGRAPH, PARAGRAPH])

    assert PdfExtractor().extract(path).is_scanned is False


def test_le_seuil_est_configurable(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "a.pdf", [PARAGRAPH])
    strict = PdfExtractor(ExtractionConfig(scan_threshold_chars_per_page=10_000))

    assert strict.extract(path).is_scanned is True


def test_pdf_mixte_n_est_pas_un_scan_si_la_moyenne_suffit(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "a.pdf", [PARAGRAPH, "", PARAGRAPH])

    doc = PdfExtractor().extract(path)

    assert doc.is_scanned is False
    assert doc.pages[1].text.strip() == ""


def test_ligatures_developpees(tmp_path: Path) -> None:
    font = pymupdf.Font("tiro")
    if not font.has_glyph(0xFB01):
        pytest.skip("police sans glyphe de ligature")
    doc = pymupdf.open()
    page = doc.new_page()
    writer = pymupdf.TextWriter(page.rect)
    writer.append((72, 72), "la ﬁabilité du ﬂux", font=font)
    writer.write_text(page)
    doc.save(tmp_path / "a.pdf")

    text = PdfExtractor().extract(tmp_path / "a.pdf").text

    assert "fiabilité du flux" in text


def test_pdf_corrompu_leve_une_erreur_sans_contenu(tmp_path: Path) -> None:
    path = tmp_path / "corrompu.pdf"
    path.write_bytes(b"secret: pas un vrai PDF")

    with pytest.raises(CorruptedDocumentError) as excinfo:
        PdfExtractor().extract(path)

    assert "corrompu.pdf" in str(excinfo.value)
    assert "secret" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None  # l'erreur MuPDF (qui peut citer des octets) est coupée


def test_pdf_protege_par_mot_de_passe(tmp_path: Path) -> None:
    path = tmp_path / "protege.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), PARAGRAPH)
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")

    with pytest.raises(EncryptedDocumentError, match="protege.pdf"):
        PdfExtractor().extract(path)


def test_fichier_absent(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="absent.pdf"):
        PdfExtractor().extract(tmp_path / "absent.pdf")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignore les permissions")
def test_pdf_sans_droit_de_lecture_n_est_pas_signale_comme_corrompu(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "interdit.pdf", [PARAGRAPH])
    path.chmod(0)
    try:
        with pytest.raises(ExtractionError, match="Lecture impossible : interdit.pdf") as excinfo:
            PdfExtractor().extract(path)
        assert not isinstance(excinfo.value, CorruptedDocumentError)
    finally:
        path.chmod(0o644)
