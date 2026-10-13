from pathlib import Path

import pytest

from second_brain.config import default_database_path


def test_base_par_defaut_dans_le_dossier_de_donnees_utilisateur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert default_database_path() == Path.home() / ".local/share/second-brain/index.db"


def test_base_par_defaut_respecte_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    assert default_database_path() == tmp_path / "second-brain" / "index.db"
