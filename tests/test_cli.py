from importlib.metadata import version

from typer.testing import CliRunner

from second_brain.cli import app

runner = CliRunner()


def test_version_affiche_la_version_du_paquet() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == version("second-brain")


def test_help_liste_les_commandes() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    # Espaces autour du nom : sinon « index » serait trouvé dans « indexés ».
    for command in ("index", "search", "extract", "chunks"):
        assert f" {command} " in result.stdout
