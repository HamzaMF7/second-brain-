"""Point d'entrée de la ligne de commande second-brain."""

from importlib.metadata import version
from typing import Annotated

import typer

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
def extract() -> None:
    """Affiche le texte extrait d'un fichier (étape 1)."""
    _not_implemented()


@app.command()
def chunks() -> None:
    """Affiche les chunks d'un document (étape 5)."""
    _not_implemented()
