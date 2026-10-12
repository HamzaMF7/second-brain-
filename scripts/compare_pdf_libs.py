"""Compare l'extraction de texte de PyMuPDF et pypdf sur quelques PDF.

Usage : uv run python scripts/compare_pdf_libs.py <fichier.pdf | dossier>... [--limit N]

Le script affiche un aperçu du texte extrait : à lancer uniquement dans ton terminal,
ne pas copier la sortie dans un fichier commité.
"""

import argparse
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pypdf

EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
PAGE_SEPARATOR = "\n\n"  # même séparateur que ExtractedDocument.text
PREVIEW_CHARS = 300
EMPTY_PAGE_CHARS = 20  # une page avec moins de caractères est comptée comme vide


@dataclass
class Result:
    seconds: float
    pages: list[str]

    @property
    def text(self) -> str:
        return PAGE_SEPARATOR.join(self.pages)


def extract_pymupdf(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]


def extract_pypdf(path: Path) -> list[str]:
    reader = pypdf.PdfReader(path)
    return [page.extract_text() for page in reader.pages]


LIBRARIES: dict[str, Callable[[Path], list[str]]] = {
    "PyMuPDF": extract_pymupdf,
    "pypdf": extract_pypdf,
}


def run(extract: Callable[[Path], list[str]], path: Path) -> Result:
    start = time.perf_counter()
    pages = extract(path)
    return Result(seconds=time.perf_counter() - start, pages=pages)


def find_pdfs(inputs: list[Path]) -> Iterator[Path]:
    for item in inputs:
        if item.is_file() and item.suffix.lower() == ".pdf":
            yield item
        elif item.is_dir():
            for path in sorted(item.rglob("*")):
                in_excluded = any(part in EXCLUDED_DIRS for part in path.parts)
                if path.is_file() and path.suffix.lower() == ".pdf" and not in_excluded:
                    yield path


def preview(text: str) -> str:
    # '⏎' rend visibles les retours à la ligne (utile pour repérer césures et colonnes).
    shown = text[:PREVIEW_CHARS].replace("\n", "⏎ ")
    return textwrap.indent(textwrap.fill(shown, width=96), "    ")


def print_comparison(path: Path) -> None:
    print("=" * 100)
    print(f"{path.name}  ({path.stat().st_size / 1024:.0f} Ko)")
    for name, extract in LIBRARIES.items():
        print(f"\n  [{name}]")
        try:
            result = run(extract, path)
        except Exception as exc:  # comparatif : on rapporte toute erreur sans s'arrêter
            print(f"    échec : {type(exc).__name__}")
            continue
        empty = sum(len(p.strip()) < EMPTY_PAGE_CHARS for p in result.pages)
        print(
            f"    temps : {result.seconds * 1000:.0f} ms   pages : {len(result.pages)}"
            f"   pages vides : {empty}   caractères : {len(result.text)}"
        )
        print(preview(result.text))
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("inputs", type=Path, nargs="+", help="fichiers PDF ou dossiers")
    parser.add_argument("--limit", type=int, default=5, help="nombre maximal de PDF (5)")
    args = parser.parse_args()

    pdfs = [p for _, p in zip(range(max(args.limit, 0)), find_pdfs(args.inputs), strict=False)]
    if not pdfs:
        print("Erreur : aucun PDF trouvé.", file=sys.stderr)
        return 1
    for path in pdfs:
        print_comparison(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
