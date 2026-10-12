"""Modèles produits par les extracteurs, communs à tous les formats."""

from dataclasses import dataclass, field
from pathlib import Path

PAGE_SEPARATOR = "\n\n"


@dataclass(frozen=True, slots=True)
class Page:
    """Une page du document. Un MD ou un TXT n'a qu'une page (number=1)."""

    number: int  # 1-based, comme l'affiche un lecteur PDF
    text: str


@dataclass(frozen=True, slots=True)
class Section:
    """Un titre détecté dans le document, utilisé plus tard par le chunking."""

    title: str
    level: int  # 1 pour '#', 2 pour '##'…
    page: int | None  # page où la section commence ; None si le format n'a pas de pages
    offset: int  # position du début de la ligne de titre dans ExtractedDocument.text


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """Résultat d'une extraction, indépendant du format source."""

    path: Path
    title: str | None
    pages: tuple[Page, ...]
    sections: tuple[Section, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
    is_scanned: bool = False

    @property
    def text(self) -> str:
        """Texte complet, calculé à partir des pages (source de vérité unique)."""
        return PAGE_SEPARATOR.join(page.text for page in self.pages)
