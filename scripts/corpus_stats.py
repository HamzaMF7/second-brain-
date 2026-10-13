"""Statistiques d'un dossier à partir des seules métadonnées (aucun contenu n'est lu).

Usage : uv run python scripts/corpus_stats.py <dossier> [--top N]
"""

import argparse
import heapq
import os
import stat
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from second_brain.config import ScanConfig

# Mêmes exclusions que l'indexation (CLAUDE.md, section 8).
_SCAN = ScanConfig()
EXCLUDED_DIRS = _SCAN.excluded_dirs
TEMP_PREFIXES = _SCAN.temp_prefixes
MAX_FILE_SIZE = _SCAN.max_file_size
V0_EXTENSIONS = {".pdf", ".md", ".txt"}
NO_EXTENSION = "(sans extension)"


@dataclass
class Stats:
    count_by_ext: Counter[str] = field(default_factory=Counter)
    size_by_ext: Counter[str] = field(default_factory=Counter)
    largest: list[tuple[int, str]] = field(default_factory=list)  # tas min (taille, chemin)
    total_size: int = 0
    excluded_dirs: int = 0
    temp_files: int = 0
    too_large: int = 0
    symlinks: int = 0
    unreadable: int = 0


def human_size(size: float) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "o" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"


def scan(root: Path, top: int) -> Stats:
    stats = Stats()

    def on_error(_: OSError) -> None:
        stats.unreadable += 1

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
        # Modifier dirnames en place empêche os.walk de descendre dans ces dossiers.
        kept = [d for d in dirnames if d not in EXCLUDED_DIRS]
        stats.excluded_dirs += len(dirnames) - len(kept)
        dirnames[:] = kept

        for name in filenames:
            path = Path(dirpath, name)
            try:
                # lstat : métadonnées du lien lui-même, sans le suivre ni ouvrir le fichier.
                st = path.lstat()
            except OSError:
                stats.unreadable += 1
                continue
            if stat.S_ISLNK(st.st_mode):
                stats.symlinks += 1
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            if name.startswith(TEMP_PREFIXES):
                stats.temp_files += 1
                continue

            ext = path.suffix.lower() or NO_EXTENSION
            stats.count_by_ext[ext] += 1
            stats.size_by_ext[ext] += st.st_size
            stats.total_size += st.st_size
            if st.st_size > MAX_FILE_SIZE:
                stats.too_large += 1

            entry = (st.st_size, str(path.relative_to(root)))
            if len(stats.largest) < top:
                heapq.heappush(stats.largest, entry)
            else:
                heapq.heappushpop(stats.largest, entry)

    return stats


def print_report(root: Path, stats: Stats) -> None:
    total_files = stats.count_by_ext.total()
    print(f"Dossier : {root}")
    print(f"Fichiers : {total_files}   Taille totale : {human_size(stats.total_size)}\n")

    print(f"{'Extension':<18} {'Fichiers':>9} {'Taille':>11}  V0")
    for ext, count in stats.count_by_ext.most_common():
        v0 = "oui" if ext in V0_EXTENSIONS else ""
        print(f"{ext:<18} {count:>9} {human_size(stats.size_by_ext[ext]):>11}  {v0}")

    v0_files = sum(stats.count_by_ext[e] for e in V0_EXTENSIONS)
    v0_size = sum(stats.size_by_ext[e] for e in V0_EXTENSIONS)
    print(f"\nIndexables en V0 (PDF, MD, TXT) : {v0_files} fichiers, {human_size(v0_size)}")

    print(f"\nPlus gros fichiers (top {len(stats.largest)}) :")
    for size, rel_path in sorted(stats.largest, reverse=True):
        print(f"{human_size(size):>11}  {rel_path}")

    print("\nIgnorés ou signalés :")
    print(f"  dossiers exclus (.git, node_modules…) : {stats.excluded_dirs}")
    print(f"  fichiers temporaires (~$*, .~lock*)   : {stats.temp_files}")
    print(f"  liens symboliques (non suivis)        : {stats.symlinks}")
    print(f"  illisibles (permissions…)             : {stats.unreadable}")
    print(f"  fichiers > 50 Mo (comptés ci-dessus)  : {stats.too_large}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("folder", type=Path, help="dossier à analyser")
    parser.add_argument("--top", type=int, default=10, help="nombre de plus gros fichiers (10)")
    args = parser.parse_args()

    root: Path = args.folder.expanduser().resolve()
    if not root.is_dir():
        print(f"Erreur : {root} n'est pas un dossier.", file=sys.stderr)
        return 1

    print_report(root, scan(root, max(args.top, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
