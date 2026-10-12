"""Extracteur pour les fichiers texte brut."""

from pathlib import Path

from second_brain.extraction.base import DocumentExtractor
from second_brain.extraction.decoding import read_text
from second_brain.extraction.models import ExtractedDocument, Page


class TextExtractor(DocumentExtractor):
    """Un fichier .txt devient une seule page, sans titre ni sections."""

    def supports(self, extension: str) -> bool:
        return extension == ".txt"

    def extract(self, path: Path) -> ExtractedDocument:
        decoded = read_text(path)
        return ExtractedDocument(
            path=path,
            title=None,
            pages=(Page(number=1, text=decoded.text),),
            metadata={"encoding": decoded.encoding},
        )
