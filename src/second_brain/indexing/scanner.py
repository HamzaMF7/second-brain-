"""Parcours d'un dossier : fichiers candidats à l'indexation, sans lire leur contenu."""

import os
import stat
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from second_brain.config import ScanConfig


class SkipReason(StrEnum):
    EXCLUDED_DIR = "dossier exclu"
    SYMLINK = "lien symbolique"
    TEMPORARY = "fichier temporaire"
    UNSUPPORTED = "format non supporté"
    TOO_LARGE = "fichier trop gros"
    UNREADABLE = "illisible"


@dataclass(frozen=True, slots=True)
class ScannedFile:
    path: Path  # absolu
    size: int  # octets
    mtime_ns: int  # nanosecondes : comparaison exacte avec la base


@dataclass(slots=True)
class ScanResult:
    files: list[ScannedFile] = field(default_factory=list)  # triés par chemin
    skipped: Counter[SkipReason] = field(default_factory=Counter)


def scan(
    root: Path, is_supported: Callable[[Path], bool], config: ScanConfig | None = None
) -> ScanResult:
    """Liste récursivement les fichiers supportés de `root`.

    Seules les métadonnées sont lues (lstat), jamais le contenu. Les liens symboliques ne
    sont pas suivis : ils pourraient mener hors du dossier choisi, ou former une boucle.
    """
    config = config or ScanConfig()
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Pas un dossier : {root}")

    result = ScanResult()

    def on_error(_: OSError) -> None:
        result.skipped[SkipReason.UNREADABLE] += 1

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
        # Modifier dirnames en place décide des sous-dossiers que os.walk visitera.
        kept = []
        for name in dirnames:
            if name in config.excluded_dirs:
                result.skipped[SkipReason.EXCLUDED_DIR] += 1
            elif os.path.islink(os.path.join(dirpath, name)):
                result.skipped[SkipReason.SYMLINK] += 1
            else:
                kept.append(name)
        dirnames[:] = kept

        for name in filenames:
            path = Path(dirpath, name)
            reason, scanned = _check_file(path, is_supported, config)
            if reason is not None:
                result.skipped[reason] += 1
            elif scanned is not None:
                result.files.append(scanned)

    result.files.sort(key=lambda f: f.path)
    return result


def _check_file(
    path: Path, is_supported: Callable[[Path], bool], config: ScanConfig
) -> tuple[SkipReason | None, ScannedFile | None]:
    """Renvoie soit une raison d'ignorer le fichier, soit le fichier retenu."""
    try:
        st = path.lstat()  # lstat : métadonnées du lien lui-même, sans le suivre
    except OSError:
        return SkipReason.UNREADABLE, None
    if stat.S_ISLNK(st.st_mode):
        return SkipReason.SYMLINK, None
    if not stat.S_ISREG(st.st_mode):
        return None, None  # socket, tube nommé… : ni retenu, ni compté
    if path.name.startswith(config.temp_prefixes):
        return SkipReason.TEMPORARY, None
    if not is_supported(path):
        return SkipReason.UNSUPPORTED, None
    if st.st_size > config.max_file_size:
        return SkipReason.TOO_LARGE, None
    return None, ScannedFile(path=path, size=st.st_size, mtime_ns=st.st_mtime_ns)
