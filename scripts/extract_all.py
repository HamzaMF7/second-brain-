"""Extrait tout un dossier et produit un rapport (succès, échecs, PDF scannés).

Usage : uv run python scripts/extract_all.py <dossier> [--near N]

Aucun contenu de document n'est affiché : seulement des chemins, des types d'erreur et
des chiffres. Le script ne doit jamais s'arrêter sur un fichier : chaque erreur est
capturée et rapportée.
"""

import argparse
import os
import stat
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from second_brain.config import ExtractionConfig
from second_brain.extraction.errors import ExtractionError, UnsupportedFormatError
from second_brain.extraction.models import ExtractedDocument
from second_brain.extraction.registry import ExtractorRegistry, default_registry

# Mêmes exclusions que scripts/corpus_stats.py (CLAUDE.md, section 8).
# À centraliser quand l'indexation (étape 2) parcourra les dossiers.
EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
TEMP_PREFIXES = ("~$", ".~lock")
MAX_FILE_SIZE = 50 * 1024 * 1024
SLOWEST_COUNT = 5


@dataclass
class Report:
    ok: Counter[str] = field(default_factory=Counter)  # par extension
    scanned: list[str] = field(default_factory=list)
    failures: list[tuple[str, str, str]] = field(default_factory=list)  # (chemin, type, message)
    unexpected: list[tuple[str, str]] = field(default_factory=list)  # (chemin, type)
    unsupported: Counter[str] = field(default_factory=Counter)
    skipped: Counter[str] = field(default_factory=Counter)  # raison → nombre
    encodings: Counter[str] = field(default_factory=Counter)
    timings: list[tuple[float, str]] = field(default_factory=list)
    pdf_density: list[tuple[float, str, int]] = field(default_factory=list)  # (moy, chemin, vides)

    @property
    def attempted(self) -> int:
        return self.ok.total() + len(self.failures) + len(self.unexpected)


def iter_files(root: Path, report: Report) -> list[Path]:
    """Fichiers à traiter, triés, en appliquant les exclusions par défaut."""
    files: list[Path] = []

    def on_error(_: OSError) -> None:
        report.skipped["dossier illisible"] += 1

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath, name)
            try:
                st = path.lstat()
            except OSError:
                report.skipped["métadonnées illisibles"] += 1
                continue
            if stat.S_ISLNK(st.st_mode):
                report.skipped["lien symbolique"] += 1
            elif not stat.S_ISREG(st.st_mode):
                continue
            elif name.startswith(TEMP_PREFIXES):
                report.skipped["fichier temporaire"] += 1
            elif st.st_size > MAX_FILE_SIZE:
                report.skipped["plus de 50 Mo"] += 1
            else:
                files.append(path)
    return files


def visible_chars_per_page(doc: ExtractedDocument) -> tuple[float, int]:
    """Moyenne de caractères non blancs par page, et nombre de pages vides."""
    counts = [len("".join(page.text.split())) for page in doc.pages]
    empty = sum(count == 0 for count in counts)
    return (sum(counts) / len(counts) if counts else 0.0), empty


def process(path: Path, rel: str, registry: ExtractorRegistry, report: Report) -> None:
    extension = path.suffix.lower() or "(sans extension)"
    try:
        extractor = registry.for_path(path)
    except UnsupportedFormatError:
        report.unsupported[extension] += 1
        return

    start = time.perf_counter()
    try:
        doc = extractor.extract(path)
    except ExtractionError as exc:  # échec prévu : notre message ne contient pas de contenu
        report.failures.append((rel, type(exc).__name__, str(exc)))
        return
    except Exception as exc:  # bug à corriger : on n'affiche que le type, jamais le message
        report.unexpected.append((rel, type(exc).__name__))
        return
    finally:
        report.timings.append((time.perf_counter() - start, rel))

    report.ok[extension] += 1
    if doc.is_scanned:
        report.scanned.append(rel)
    if "encoding" in doc.metadata:
        report.encodings[doc.metadata["encoding"]] += 1
    if extension == ".pdf":
        average, empty = visible_chars_per_page(doc)
        report.pdf_density.append((average, rel, empty))


def print_report(root: Path, report: Report, config: ExtractionConfig, near: int) -> None:
    total_time = sum(t for t, _ in report.timings)
    print(f"\nDossier : {root}")
    print(f"Fichiers traités : {report.attempted}   durée totale : {total_time:.1f} s")

    print(f"\n{'Format':<10} {'Succès':>7} {'dont scannés':>13}")
    scanned_by_ext = Counter(Path(rel).suffix.lower() for rel in report.scanned)
    for ext, count in report.ok.most_common():
        print(f"{ext:<10} {count:>7} {scanned_by_ext[ext]:>13}")

    print(f"\nÉchecs prévus (ExtractionError) : {len(report.failures)}")
    for error_type, count in Counter(t for _, t, _ in report.failures).most_common():
        print(f"  {error_type} : {count}")
    for _, _, message in report.failures:
        print(f"    {message}")

    print(f"\nÉchecs inattendus (bugs à corriger) : {len(report.unexpected)}")
    for rel, error_type in report.unexpected:
        print(f"  {error_type} : {rel}")

    print(
        f"\nPDF scannés (moins de {config.scan_threshold_chars_per_page} car./page) : "
        f"{len(report.scanned)}"
    )
    for rel in report.scanned:
        print(f"  {rel}")

    print(f"\nPDF les plus proches du seuil (pour valider le réglage, top {near}) :")
    print(f"  {'car./page':>9} {'pages vides':>11}  fichier")
    for average, rel, empty in sorted(report.pdf_density)[:near]:
        print(f"  {average:>9.0f} {empty:>11}  {rel}")

    if report.encodings:
        print("\nEncodages détectés (TXT, MD) :")
        for encoding, count in report.encodings.most_common():
            print(f"  {encoding} : {count}")

    print(f"\nPlus lents (top {SLOWEST_COUNT}) :")
    for seconds, rel in sorted(report.timings, reverse=True)[:SLOWEST_COUNT]:
        print(f"  {seconds * 1000:>8.0f} ms  {rel}")

    print("\nIgnorés :")
    for ext, count in report.unsupported.most_common():
        print(f"  format non supporté {ext} : {count}")
    for reason, count in report.skipped.most_common():
        print(f"  {reason} : {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("folder", type=Path, help="dossier à extraire")
    parser.add_argument("--near", type=int, default=10, help="PDF proches du seuil à lister (10)")
    args = parser.parse_args()

    root: Path = args.folder.expanduser().resolve()
    if not root.is_dir():
        print(f"Erreur : {root} n'est pas un dossier.", file=sys.stderr)
        return 1

    config = ExtractionConfig()
    registry = default_registry(config)
    report = Report()
    files = iter_files(root, report)
    for i, path in enumerate(files, start=1):
        process(path, str(path.relative_to(root)), registry, report)
        if i % 50 == 0 or i == len(files):
            print(f"\r{i}/{len(files)} fichiers", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    print_report(root, report, config, max(args.near, 0))
    return 1 if report.unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
