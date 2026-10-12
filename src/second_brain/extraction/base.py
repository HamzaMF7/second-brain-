"""Contrat commun à tous les extracteurs (pattern Strategy)."""

from abc import ABC, abstractmethod
from pathlib import Path

from second_brain.extraction.models import ExtractedDocument


class DocumentExtractor(ABC):
    """Transforme un fichier d'un format donné en ExtractedDocument."""

    @abstractmethod
    def supports(self, extension: str) -> bool:
        """Indique si l'extension (minuscules, avec le point : '.pdf') est prise en charge."""

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDocument:
        """Extrait le document. Lève une ExtractionError en cas d'échec."""
