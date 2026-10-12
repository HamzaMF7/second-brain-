"""Lecture des fichiers texte : encodage, fins de ligne, normalisation Unicode."""

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from second_brain.extraction.errors import ExtractionError

# Essayés dans l'ordre. cp1252 est le « Latin-1 » de Windows (il ajoute € œ ’…).
# Latin-1 vient en dernier : il associe un caractère à chacun des 256 octets,
# il ne peut donc pas échouer.
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


@dataclass(frozen=True, slots=True)
class DecodedText:
    text: str
    encoding: str


def read_text(path: Path) -> DecodedText:
    """Lit un fichier texte et renvoie son contenu normalisé avec l'encodage détecté."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ExtractionError(f"Lecture impossible : {path.name}") from exc

    for encoding in ENCODINGS:
        try:
            return DecodedText(normalize(raw.decode(encoding)), encoding)
        except UnicodeDecodeError:
            continue
    raise AssertionError("inatteignable : latin-1 décode tous les octets")


def normalize(text: str) -> str:
    """Fins de ligne en '\\n' et Unicode en NFC ('e' + accent combinant → 'é')."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)
