"""Point d'entrée de la ligne de commande second-brain."""

import logging
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Protocol

import typer

from second_brain.config import default_database_path
from second_brain.extraction.errors import ExtractionError
from second_brain.extraction.registry import default_registry
from second_brain.indexing.pipeline import index_folder
from second_brain.storage.db import open_database

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
def index(
    folder: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, readable=True, help="Dossier à indexer."),
    ],
    db: Annotated[
        Path | None,
        typer.Option(
            "--db",
            envvar="SECOND_BRAIN_DB",
            help="Fichier de la base (défaut : ~/.local/share/second-brain/index.db).",
        ),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Journalise chaque fichier traité.")
    ] = False,
) -> None:
    """Indexe un dossier : ajoute, met à jour et purge les documents."""
    db_path = db or default_database_path()
    conn = open_database(db_path)
    try:
        with _verbose_logging(verbose), ExitStack() as stack:
            bars: list[_Updatable] = []

            def on_progress(done: int, total: int) -> None:
                if not bars:  # le total n'est connu qu'après le scan
                    bars.append(
                        stack.enter_context(
                            typer.progressbar(length=total, label="Indexation", file=sys.stderr)
                        )
                    )
                bars[0].update(1)

            report = index_folder(conn, folder, default_registry(), on_progress=on_progress)
    finally:
        conn.close()

    scanned = f"  (dont {report.scanned_pdfs} PDF scanné(s))" if report.scanned_pdfs else ""
    touched = f"  (dont {report.touched} : métadonnées seules)" if report.touched else ""
    skipped = ", ".join(f"{reason} : {n}" for reason, n in report.skipped.most_common())
    lines = [
        ("Dossier", str(folder.resolve())),
        ("Base", str(db_path)),
        ("Ajoutés", f"{report.added}{scanned}"),
        ("Modifiés", str(report.modified)),
        ("Supprimés", str(report.deleted)),
        ("Inchangés", f"{report.unchanged + report.touched}{touched}"),
        ("Erreurs", str(report.errors) + ("  (détails : --verbose)" if report.errors else "")),
        ("Ignorés", f"{report.skipped.total()}" + (f"  ({skipped})" if skipped else "")),
        ("Durée", f"{report.seconds:.1f} s"),
    ]
    for label, value in lines:
        typer.echo(f"{label:<12}: {value}")


class _Updatable(Protocol):
    """Ce que la commande utilise de la barre de progression de Typer."""

    def update(self, n_steps: int) -> None: ...


@contextmanager
def _verbose_logging(enabled: bool) -> Iterator[None]:
    """Affiche les logs du paquet sur stderr le temps d'une commande."""
    if not enabled:
        yield
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger = logging.getLogger("second_brain")
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


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
