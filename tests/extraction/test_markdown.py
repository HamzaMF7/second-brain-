from pathlib import Path

from second_brain.extraction.markdown import MarkdownExtractor, parse_headings
from second_brain.extraction.models import Section

FIXTURES = Path(__file__).parent.parent / "fixtures"


def levels_and_titles(sections: tuple[Section, ...]) -> list[tuple[int, str]]:
    return [(s.level, s.title) for s in sections]


def test_supporte_md_et_markdown() -> None:
    extractor = MarkdownExtractor()

    assert extractor.supports(".md")
    assert extractor.supports(".markdown")
    assert not extractor.supports(".txt")


def test_extrait_la_hierarchie_des_titres() -> None:
    doc = MarkdownExtractor().extract(FIXTURES / "comparatif-bdd.md")

    assert doc.title == "Comparatif des bases de données"
    assert levels_and_titles(doc.sections) == [
        (1, "Comparatif des bases de données"),
        (2, "PostgreSQL"),
        (3, "Extensions utiles"),
        (2, "MongoDB"),
        (2, "Conclusion"),
    ]
    assert all(s.page is None for s in doc.sections)


def test_l_offset_pointe_sur_la_ligne_du_titre_dans_le_texte() -> None:
    doc = MarkdownExtractor().extract(FIXTURES / "comparatif-bdd.md")

    for section in doc.sections:
        line = doc.text[section.offset :].split("\n", 1)[0]
        assert line.startswith("#" * section.level + " " + section.title)


def test_offsets_calcules_ligne_par_ligne() -> None:
    text = "intro\n# Un\n\n```\n# code\n```\n## Deux\n"

    assert [s.offset for s in parse_headings(text)] == [6, 27]


def test_conserve_le_texte_brut_en_une_page() -> None:
    doc = MarkdownExtractor().extract(FIXTURES / "comparatif-bdd.md")

    assert len(doc.pages) == 1
    assert doc.text.startswith("# Comparatif des bases de données\n")
    assert "CREATE EXTENSION pg_trgm" in doc.text
    assert doc.metadata == {"encoding": "utf-8-sig"}


def test_ignore_les_titres_dans_les_blocs_de_code() -> None:
    text = "# Vrai\n~~~\n# faux\n```\n# faux aussi\n~~~\n## Vrai aussi\n"

    assert levels_and_titles(parse_headings(text)) == [(1, "Vrai"), (2, "Vrai aussi")]


def test_un_diese_colle_n_est_pas_un_titre() -> None:
    assert parse_headings("#hashtag\n####### sept dièses\n") == ()


def test_sans_titre_de_niveau_1_le_titre_est_absent(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("## Sous-partie\n\ntexte\n", encoding="utf-8")

    doc = MarkdownExtractor().extract(path)

    assert doc.title is None
    assert levels_and_titles(doc.sections) == [(2, "Sous-partie")]
