import os
from pathlib import Path

import pytest

from second_brain.config import ScanConfig
from second_brain.indexing.scanner import ScannedFile, SkipReason, scan


def supported(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".txt", ".pdf"}


def write(path: Path, content: str = "contenu inventé") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_liste_recursivement_les_fichiers_supportes_avec_taille_et_mtime(tmp_path: Path) -> None:
    a = write(tmp_path / "a.md", "12345")
    b = write(tmp_path / "sous" / "dossier" / "b.TXT")

    result = scan(tmp_path, supported)

    assert result.files == [
        ScannedFile(path=a, size=5, mtime_ns=a.stat().st_mtime_ns),
        ScannedFile(path=b, size=b.stat().st_size, mtime_ns=b.stat().st_mtime_ns),
    ]


def test_les_chemins_sont_absolus_et_tries(tmp_path: Path) -> None:
    for name in ("c.md", "a.md", "b/z.md", "b/a.md"):
        write(tmp_path / name)

    files = scan(tmp_path, supported).files

    assert all(f.path.is_absolute() for f in files)
    assert [f.path for f in files] == sorted(f.path for f in files)


def test_format_non_supporte_est_ignore_et_compte(tmp_path: Path) -> None:
    write(tmp_path / "a.md")
    write(tmp_path / "tableur.xlsx")
    write(tmp_path / "sans_extension")

    result = scan(tmp_path, supported)

    assert [f.path.name for f in result.files] == ["a.md"]
    assert result.skipped[SkipReason.UNSUPPORTED] == 2


@pytest.mark.parametrize("excluded", [".git", "node_modules", "__pycache__", ".venv"])
def test_dossiers_exclus_ne_sont_pas_parcourus(tmp_path: Path, excluded: str) -> None:
    write(tmp_path / excluded / "profond" / "cache.md")
    write(tmp_path / "garde.md")

    result = scan(tmp_path, supported)

    assert [f.path.name for f in result.files] == ["garde.md"]
    assert result.skipped[SkipReason.EXCLUDED_DIR] == 1


def test_un_dossier_exclu_est_exclu_a_toute_profondeur(tmp_path: Path) -> None:
    write(tmp_path / "projet" / "node_modules" / "lib.md")

    assert scan(tmp_path, supported).files == []


def test_fichiers_temporaires_ignores(tmp_path: Path) -> None:
    write(tmp_path / "~$rapport.md")
    write(tmp_path / ".~lock.notes.md#")
    write(tmp_path / "vrai.md")

    result = scan(tmp_path, supported)

    assert [f.path.name for f in result.files] == ["vrai.md"]
    assert result.skipped[SkipReason.TEMPORARY] == 2


def test_fichier_trop_gros_ignore_mais_la_limite_exacte_est_acceptee(tmp_path: Path) -> None:
    write(tmp_path / "limite.md", "x" * 10)
    write(tmp_path / "gros.md", "x" * 11)

    result = scan(tmp_path, supported, ScanConfig(max_file_size=10))

    assert [f.path.name for f in result.files] == ["limite.md"]
    assert result.skipped[SkipReason.TOO_LARGE] == 1


def test_liens_symboliques_ne_sont_pas_suivis(tmp_path: Path) -> None:
    outside = tmp_path / "ailleurs"
    write(outside / "secret.md")
    root = tmp_path / "racine"
    write(root / "vrai.md")
    (root / "lien_fichier.md").symlink_to(outside / "secret.md")
    (root / "lien_dossier").symlink_to(outside, target_is_directory=True)

    result = scan(root, supported)

    assert [f.path.name for f in result.files] == ["vrai.md"]
    assert result.skipped[SkipReason.SYMLINK] == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignore les permissions")
def test_aucun_contenu_n_est_lu(tmp_path: Path) -> None:
    # Un fichier sans droit de lecture est quand même listé : seules ses métadonnées comptent.
    path = write(tmp_path / "interdit.md")
    path.chmod(0)
    try:
        assert [f.path for f in scan(tmp_path, supported).files] == [path]
    finally:
        path.chmod(0o644)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignore les permissions")
def test_dossier_illisible_est_compte_sans_planter(tmp_path: Path) -> None:
    locked = tmp_path / "verrouille"
    write(locked / "a.md")
    write(tmp_path / "b.md")
    locked.chmod(0)
    try:
        result = scan(tmp_path, supported)
    finally:
        locked.chmod(0o755)

    assert [f.path.name for f in result.files] == ["b.md"]
    assert result.skipped[SkipReason.UNREADABLE] == 1


def test_racine_qui_n_est_pas_un_dossier(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        scan(write(tmp_path / "a.md"), supported)
