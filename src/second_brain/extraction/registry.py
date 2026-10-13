"""Choix de l'extracteur selon l'extension du fichier."""

from collections.abc import Iterable
from pathlib import Path

from second_brain.config import ExtractionConfig
from second_brain.extraction.base import DocumentExtractor
from second_brain.extraction.errors import UnsupportedFormatError
from second_brain.extraction.markdown import MarkdownExtractor
from second_brain.extraction.pdf import PdfExtractor
from second_brain.extraction.text import TextExtractor


class ExtractorRegistry:
    """Liste ordonnée d'extracteurs : le premier compatible l'emporte."""

    def __init__(self, extractors: Iterable[DocumentExtractor]) -> None:
        self._extractors = tuple(extractors)

    def for_path(self, path: Path) -> DocumentExtractor:
        """Renvoie l'extracteur adapté à `path`, ou lève UnsupportedFormatError."""
        extractor = self._find(path)
        if extractor is None:
            raise UnsupportedFormatError(path.suffix.lower())
        return extractor

    def supports(self, path: Path) -> bool:
        """Indique si un extracteur prend en charge ce fichier (d'après son extension)."""
        return self._find(path) is not None

    def _find(self, path: Path) -> DocumentExtractor | None:
        extension = path.suffix.lower()
        if not extension:
            return None
        return next((e for e in self._extractors if e.supports(extension)), None)


def default_registry(config: ExtractionConfig | None = None) -> ExtractorRegistry:
    """Registre des formats de la V0 : PDF, Markdown, texte."""
    return ExtractorRegistry([PdfExtractor(config), MarkdownExtractor(), TextExtractor()])
