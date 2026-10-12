from pathlib import Path

import pytest

from second_brain.extraction.decoding import read_text
from second_brain.extraction.errors import ExtractionError


def write_bytes(tmp_path: Path, raw: bytes) -> Path:
    path = tmp_path / "fichier.txt"
    path.write_bytes(raw)
    return path


def test_lit_l_utf8(tmp_path: Path) -> None:
    decoded = read_text(write_bytes(tmp_path, "café".encode()))

    assert decoded.text == "café"
    assert decoded.encoding == "utf-8-sig"


def test_retire_le_bom_utf8(tmp_path: Path) -> None:
    decoded = read_text(write_bytes(tmp_path, b"\xef\xbb\xbfcaf\xc3\xa9"))

    assert decoded.text == "café"


def test_lit_le_cp1252_avec_ses_caracteres_propres(tmp_path: Path) -> None:
    # '’', 'œ' et '€' existent en cp1252 mais pas en Latin-1.
    decoded = read_text(write_bytes(tmp_path, "l’œuvre coûte 5 €".encode("cp1252")))

    assert decoded.text == "l’œuvre coûte 5 €"
    assert decoded.encoding == "cp1252"


def test_latin1_en_dernier_recours(tmp_path: Path) -> None:
    # 0x81 n'est défini ni en UTF-8 ni en cp1252.
    decoded = read_text(write_bytes(tmp_path, b"caf\xe9 \x81"))

    assert decoded.text == "café \x81"
    assert decoded.encoding == "latin-1"


def test_normalise_en_nfc(tmp_path: Path) -> None:
    nfd = "café"  # 'e' + accent aigu combinant : 5 points de code
    decoded = read_text(write_bytes(tmp_path, nfd.encode()))

    assert decoded.text == "café"
    assert len(decoded.text) == 4


def test_normalise_les_fins_de_ligne(tmp_path: Path) -> None:
    decoded = read_text(write_bytes(tmp_path, b"windows\r\nmac\runix\n"))

    assert decoded.text == "windows\nmac\nunix\n"


def test_fichier_illisible_leve_une_erreur_d_extraction(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="absent.txt"):
        read_text(tmp_path / "absent.txt")
