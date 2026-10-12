"""Point d'entrée de la ligne de commande second-brain."""

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from second_brain.extraction.errors import ExtractionError
from second_brain.extraction.registry import default_registry

PREVIEW_CHARS = 500  # longueur de l'aperçu affiché par `extract`

app = typer.Typer(
    help="Mémoire personnelle locale interrogeable en langage naturel.",
    no_args_is_help=True,
    add_completion=False,
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(version("second-brain"))
        raise typer.Exit()


@app.callback()
def main(
    show_version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Affiche la version et quitte.",
        ),
    ] = False,
) -> None:
    """Options globales, communes à toutes les sous-commandes."""


def _not_implemented() -> None:
    typer.echo("pas encore implémenté", err=True)
    raise typer.Exit(code=1)


@app.command()
def index() -> None:
    """Indexe un dossier (étape 2)."""
    _not_implemented()


@app.command()
def search() -> None:
    """Recherche dans les documents indexés (étape 3)."""
    _not_implemented()


@app.command()
def extract(
    path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Fichier à extraire."),
    ],
) -> None:
    """Affiche le titre, les pages et le début du texte extrait d'un fichier."""
    try:
        doc = default_registry().for_path(path).extract(path)
    except ExtractionError as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Fichier   : {path.name}")
    typer.echo(f"Titre     : {doc.title or '(aucun)'}")
    typer.echo(f"Pages     : {len(doc.pages)}")
    typer.echo(f"Scanné    : {'oui' if doc.is_scanned else 'non'}")
    text = doc.text
    typer.echo(f"\n--- {min(len(text), PREVIEW_CHARS)} premiers caractères sur {len(text)} ---")
    typer.echo(text[:PREVIEW_CHARS])


@app.command()
def chunks() -> None:
    """Affiche les chunks d'un document (étape 5)."""
    _not_implemented()
