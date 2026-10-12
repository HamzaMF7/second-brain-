"""Extracteur PDF fondé sur PyMuPDF (ADR 0007)."""

from pathlib import Path

import pymupdf

from second_brain.config import ExtractionConfig
from second_brain.extraction.base import DocumentExtractor
from second_brain.extraction.decoding import normalize
from second_brain.extraction.errors import (
    CorruptedDocumentError,
    EncryptedDocumentError,
    ExtractionError,
)
from second_brain.extraction.models import ExtractedDocument, Page

# Réglages par défaut de MuPDF, sans conserver les ligatures : « ﬁ » devient « fi ».
TEXT_FLAGS = pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_LIGATURES

# Métadonnées PDF conservées (clé PyMuPDF → clé stockée). Jamais de contenu.
METADATA_KEYS = {
    "author": "author",
    "creator": "creator",
    "producer": "producer",
    "creationDate": "creation_date",
    "modDate": "modification_date",
}

# MuPDF écrit ses erreurs sur stderr, parfois avec des octets du fichier : on les coupe.
pymupdf.TOOLS.mupdf_display_errors(False)
pymupdf.TOOLS.mupdf_display_warnings(False)


class PdfExtractor(DocumentExtractor):
    """Une Page par page du PDF ; marque les PDF scannés au lieu d'échouer."""

    def __init__(self, config: ExtractionConfig | None = None) -> None:
        self.config = config or ExtractionConfig()

    def supports(self, extension: str) -> bool:
        return extension == ".pdf"

    def extract(self, path: Path) -> ExtractedDocument:
        # On lit les octets nous-mêmes : sinon MuPDF transforme une erreur de lecture
        # (fichier absent, permissions) en FileDataError, confondue avec un PDF corrompu.
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractionError(f"Lecture impossible : {path.name}") from exc

        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass:
                    raise EncryptedDocumentError(f"PDF protégé par mot de passe : {path.name}")
                pages = tuple(
                    Page(number=i, text=normalize(page.get_text(flags=TEXT_FLAGS)))
                    for i, page in enumerate(pdf, start=1)
                )
                metadata = pdf.metadata or {}
        except ExtractionError:
            raise
        except (RuntimeError, ValueError) as exc:
            # `from None` : le message MuPDF peut citer des octets du fichier.
            raise CorruptedDocumentError(
                f"PDF illisible : {path.name} ({type(exc).__name__})"
            ) from None

        return ExtractedDocument(
            path=path,
            title=(metadata.get("title") or "").strip() or None,
            pages=pages,
            metadata={
                new: metadata[old] for old, new in METADATA_KEYS.items() if metadata.get(old)
            },
            is_scanned=self._looks_scanned(pages),
        )

    def _looks_scanned(self, pages: tuple[Page, ...]) -> bool:
        """Moyenne de caractères non blancs par page sous le seuil configuré."""
        if not pages:
            return False
        visible = sum(len("".join(page.text.split())) for page in pages)
        return visible / len(pages) < self.config.scan_threshold_chars_per_page
