from importlib.metadata import version
from pathlib import Path

import pymupdf
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


# --- extract ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_affiche_titre_pages_scan_et_apercu() -> None:
    result = runner.invoke(app, ["extract", str(FIXTURES / "comparatif-bdd.md")])

    assert result.exit_code == 0
    assert "Comparatif des bases de données" in result.stdout
    assert "Pages     : 1" in result.stdout
    assert "Scanné    : non" in result.stdout
    assert "PostgreSQL" in result.stdout


def test_extract_sans_titre(tmp_path: Path) -> None:
    result = runner.invoke(app, ["extract", str(FIXTURES / "idees.txt")])

    assert result.exit_code == 0
    assert "Titre     : (aucun)" in result.stdout


def test_extract_limite_l_apercu_a_500_caracteres(tmp_path: Path) -> None:
    path = tmp_path / "long.txt"
    path.write_text("a" * 500 + "MARQUEUR_APRES_500", encoding="utf-8")

    result = runner.invoke(app, ["extract", str(path)])

    assert result.exit_code == 0
    assert "a" * 500 in result.stdout
    assert "MARQUEUR_APRES_500" not in result.stdout
    assert "500 premiers caractères sur 518" in result.stdout


def test_extract_signale_un_pdf_scanne(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)

    result = runner.invoke(app, ["extract", str(path)])

    assert result.exit_code == 0
    assert "Scanné    : oui" in result.stdout


def test_extract_format_non_supporte(tmp_path: Path) -> None:
    path = tmp_path / "tableur.xlsx"
    path.write_bytes(b"")

    result = runner.invoke(app, ["extract", str(path)])

    assert result.exit_code == 1
    assert "Format non supporté : .xlsx" in result.stderr


def test_extract_pdf_corrompu_sans_contenu(tmp_path: Path) -> None:
    path = tmp_path / "corrompu.pdf"
    path.write_bytes(b"secret: pas un PDF")

    result = runner.invoke(app, ["extract", str(path)])

    assert result.exit_code == 1
    assert "corrompu.pdf" in result.stderr
    assert "secret" not in result.output


def test_extract_fichier_absent(tmp_path: Path) -> None:
    result = runner.invoke(app, ["extract", str(tmp_path / "absent.md")])

    assert result.exit_code == 2
