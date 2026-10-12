"""Extracteur Markdown : texte brut et hiérarchie des titres."""

import re
from pathlib import Path

from second_brain.extraction.base import DocumentExtractor
from second_brain.extraction.decoding import read_text
from second_brain.extraction.models import ExtractedDocument, Page, Section

# Titre ATX : 1 à 6 '#', puis au moins un espace. Les '#' de fermeture sont ignorés.
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
# Ouverture ou fermeture d'un bloc de code : ``` ou ~~~ (3 ou plus).
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


class MarkdownExtractor(DocumentExtractor):
    """Un fichier Markdown devient une seule page ; les titres deviennent des sections."""

    def supports(self, extension: str) -> bool:
        return extension in {".md", ".markdown"}

    def extract(self, path: Path) -> ExtractedDocument:
        decoded = read_text(path)
        sections = parse_headings(decoded.text)
        title = next((s.title for s in sections if s.level == 1), None)
        return ExtractedDocument(
            path=path,
            title=title,
            pages=(Page(number=1, text=decoded.text),),
            sections=sections,
            metadata={"encoding": decoded.encoding},
        )


def parse_headings(text: str) -> tuple[Section, ...]:
    """Renvoie les titres dans l'ordre du document, hors blocs de code."""
    sections: list[Section] = []
    open_fence: str | None = None
    offset = 0
    for line in text.split("\n"):
        line_start = offset
        offset += len(line) + 1  # +1 pour le '\n' retiré par split
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if open_fence is None:
                open_fence = marker
            elif marker[0] == open_fence[0] and len(marker) >= len(open_fence):
                open_fence = None
            continue
        if open_fence is not None:
            continue
        heading = _HEADING.match(line)
        if heading:
            level, title = heading.groups()
            sections.append(Section(title=title, level=len(level), page=None, offset=line_start))
    return tuple(sections)
