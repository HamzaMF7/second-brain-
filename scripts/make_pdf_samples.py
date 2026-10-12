"""Génère un petit corpus de PDF inventés pour comparer les bibliothèques d'extraction.

Usage : uv run python scripts/make_pdf_samples.py [--out samples/pdf]

Chaque PDF reproduit une difficulté d'extraction connue (colonnes, césures, en-têtes,
ligatures, espaces insécables, image sans texte). Tout le contenu est inventé.
Limite : ce sont des imitations produites avec PyMuPDF. Elles ne remplacent pas de vrais
PDF issus de Word, de LaTeX ou d'un scanner, qui ont leurs propres bizarreries.
"""

import argparse
import itertools
import random
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pymupdf

A4 = pymupdf.paper_rect("a4")
SLIDE = pymupdf.Rect(0, 0, 960, 540)  # format 16:9
LEADING = 1.3  # interligne, en multiple de la taille de police
VOWELS = set("aeiouyàâäéèêëîïôöùûüœ")
INSEPARABLE = {"bl", "br", "ch", "cl", "cr", "dr", "fl", "fr", "gl", "gn", "gr", "ph", "pl"}
INSEPARABLE |= {"pr", "th", "tr", "vr"}
CREATOR = "scripts/make_pdf_samples.py (corpus de test inventé)"


# --- Polices -----------------------------------------------------------------------------


@dataclass(frozen=True)
class FontBook:
    serif: pymupdf.Font
    serif_bold: pymupdf.Font
    sans: pymupdf.Font
    sans_bold: pymupdf.Font


def system_font(pattern: str, fallback: str) -> pymupdf.Font:
    """Police système via fontconfig ; police intégrée à MuPDF si introuvable."""
    try:
        path = subprocess.run(
            ["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, check=True
        ).stdout
        return pymupdf.Font(fontfile=path)
    except (OSError, subprocess.SubprocessError, RuntimeError):
        return pymupdf.Font(fallback)


def load_fonts() -> FontBook:
    return FontBook(
        serif=system_font("Liberation Serif", "tiro"),
        serif_bold=system_font("Liberation Serif:bold", "tibo"),
        sans=system_font("Liberation Sans", "helv"),
        sans_bold=system_font("Liberation Sans:bold", "hebo"),
    )


# --- Texte : nettoyage, typographie, césure -----------------------------------------------


def clean(text: str) -> str:
    """Fusionne les retours à la ligne du code source (garde les espaces insécables)."""
    return re.sub(r"[ \t\n]+", " ", text).strip()


def with_ligatures(text: str, font: pymupdf.Font) -> str:
    """Remplace fi/fl par des glyphes ligaturés, comme le font LaTeX ou InDesign."""
    for pair, ligature in (("fi", "ﬁ"), ("fl", "ﬂ")):
        if font.has_glyph(ord(ligature)):
            text = text.replace(pair, ligature)
    return text


def word_typography(text: str) -> str:
    """Typographie française d'un traitement de texte : ’ et espaces insécables."""
    text = text.replace("'", "’").replace("« ", "« ")
    return re.sub(r" ([:;?!»])", " \\1", text)


def hyphenation_points(word: str) -> list[int]:
    """Positions de coupure plausibles en français (règle simplifiée des syllabes)."""
    points = []
    for i in range(3, len(word) - 2):
        before, here, after = word[i - 1].lower(), word[i].lower(), word[i + 1].lower()
        if not (before.isalpha() and here.isalpha() and after.isalpha()):
            continue
        if before in VOWELS and here not in VOWELS and after in VOWELS:
            points.append(i)  # voyelle | consonne-voyelle : ca-fé
        elif (
            before not in VOWELS
            and here not in VOWELS
            and word[i - 2].lower() in VOWELS
            and before + here not in INSEPARABLE
        ):
            points.append(i)  # consonne | consonne : struc-ture
    return points


def wrap(
    text: str, font: pymupdf.Font, size: float, width: float, hyphenate: bool = False
) -> list[str]:
    """Découpe en lignes de largeur `width`, avec césure éventuelle des mots trop longs."""

    def fits(candidate: str) -> bool:
        return font.text_length(candidate, fontsize=size) <= width

    lines: list[str] = []
    current = ""
    for word in text.split(" "):  # pas split() : il couperait aussi sur les insécables
        candidate = f"{current} {word}" if current else word
        if fits(candidate):
            current = candidate
            continue
        rest = word
        split = None
        if hyphenate and current:
            points = reversed(hyphenation_points(word))
            split = next((i for i in points if fits(f"{current} {word[:i]}-")), None)
        if split:
            lines.append(f"{current} {word[:split]}-")
            rest = word[split:]
        elif current:
            lines.append(current)
        current = rest
    if current:
        lines.append(current)
    return lines


# --- Mise en page ------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    text: str
    font: pymupdf.Font
    size: float
    space_before: float = 0.0
    toc: bool = False  # titre à reprendre dans le sommaire


Placed = tuple[int, pymupdf.Point, Line]  # (numéro de page, position de la ligne, ligne)
Frames = Iterator[tuple[int, pymupdf.Rect]]


def paragraph(
    text: str,
    font: pymupdf.Font,
    size: float,
    width: float,
    *,
    hyphenate: bool = False,
    space_before: float = 0.0,
) -> list[Line]:
    wrapped = wrap(clean(text), font, size, width, hyphenate)
    return [Line(t, font, size, space_before if i == 0 else 0.0) for i, t in enumerate(wrapped)]


def page_frames(first_page: int, rect: pymupdf.Rect, first_top: float | None = None) -> Frames:
    """Un cadre par page, à partir de `first_page` (le premier peut commencer plus bas)."""
    for page in itertools.count(first_page):
        top = first_top if page == first_page and first_top is not None else rect.y0
        yield page, pymupdf.Rect(rect.x0, top, rect.x1, rect.y1)


def column_frames(
    columns: list[tuple[float, float]], first_top: float, top: float, bottom: float
) -> Frames:
    """Les colonnes de chaque page, de gauche à droite, page après page."""
    for page in itertools.count():
        for x0, x1 in columns:
            yield page, pymupdf.Rect(x0, first_top if page == 0 else top, x1, bottom)


def place(lines: Iterable[Line], frames: Frames) -> list[Placed]:
    """Remplit les cadres les uns après les autres, comme un traitement de texte."""
    page, rect = next(frames)
    y = rect.y0
    placed: list[Placed] = []
    for line in lines:
        step = line.size * LEADING + (line.space_before if y > rect.y0 else 0.0)
        if y + step > rect.y1:
            page, rect = next(frames)
            y = rect.y0
            step = line.size * LEADING
        y += step
        placed.append((page, pymupdf.Point(rect.x0, y), line))
    return placed


def render(
    doc: pymupdf.Document, placed: list[Placed], size: pymupdf.Rect, reading_order: bool = True
) -> None:
    """Écrit les lignes. reading_order=False : ligne à ligne à travers les colonnes."""
    if not reading_order:
        placed = sorted(placed, key=lambda p: (p[0], round(p[1].y), p[1].x))
    writers: dict[int, pymupdf.TextWriter] = {}
    for page_no, pos, line in placed:
        while doc.page_count <= page_no:
            doc.new_page(width=size.width, height=size.height)
        if page_no not in writers:
            writers[page_no] = pymupdf.TextWriter(doc[page_no].rect)
        writers[page_no].append(pos, line.text, font=line.font, fontsize=line.size)
    for page_no, writer in writers.items():
        writer.write_text(doc[page_no])


def add_running_text(
    doc: pymupdf.Document,
    font: pymupdf.Font,
    size: float,
    header: str | None,
    footer: str,
    first_page: int = 0,
) -> None:
    """En-tête à gauche et pied de page centré ({n} et {total} remplacés)."""
    for index in range(first_page, doc.page_count):
        page = doc[index]
        writer = pymupdf.TextWriter(page.rect)
        if header:
            writer.append((70, 40), header, font=font, fontsize=size)
        text = footer.format(n=index + 1, total=doc.page_count)
        x = (page.rect.width - font.text_length(text, fontsize=size)) / 2
        writer.append((x, page.rect.height - 30), text, font=font, fontsize=size)
        writer.write_text(page)


def dotted(left: str, right: str, font: pymupdf.Font, size: float, width: float) -> str:
    """Ligne de sommaire avec points de conduite : « Titre ........ 3 »."""
    free = width - font.text_length(f"{left}  {right}", fontsize=size)
    dots = max(int(free / font.text_length(".", fontsize=size)), 3)
    return f"{left} {'.' * dots} {right}"


# --- 1. Article en deux colonnes ---------------------------------------------------------

ARTICLE_TITLE = "Recherche hybride dans les documents personnels : une étude exploratoire"
ARTICLE_AUTHORS = (
    "Alice Martin, Camille Dubois — Laboratoire fictif d'informatique documentaire, Valcourt"
)
ARTICLE_ABSTRACT = """
Résumé — Retrouver un document personnel à partir d'un souvenir approximatif reste difficile
avec une recherche par mots-clés. Nous comparons trois approches sur un corpus inventé de mille
deux cents documents : une recherche lexicale BM25, une recherche vectorielle fondée sur des
embeddings multilingues et une fusion des deux par rangs réciproques. La fusion améliore le
rappel sur les questions reformulées sans dégrader les requêtes exactes.
"""
ARTICLE_SECTIONS = [
    (
        "1. Introduction",
        [
            """Les utilisateurs accumulent des milliers de fichiers dont ils oublient le nom mais
            rarement le contenu. Une personne se souvient d'avoir comparé deux bases de données,
            sans savoir si ce comparatif se trouve dans un rapport, une présentation ou une note
            rapide. Les moteurs de recherche des systèmes d'exploitation privilégient le nom du
            fichier et quelques métadonnées, ce qui laisse de côté l'essentiel de l'information.
            Notre question est simple : quelle combinaison de techniques retrouve le bon document
            dans les cinq premiers résultats ?""",
        ],
    ),
    (
        "2. Méthode",
        [
            """Le corpus contient des rapports, des notes de cours et des présentations rédigés en
            français et en anglais. Chaque document est découpé en passages d'environ trois cents
            mots qui respectent les frontières de sections. Pour la recherche lexicale, nous
            utilisons l'index plein texte de SQLite avec suppression des diacritiques. Pour la
            recherche vectorielle, chaque passage est transformé en un vecteur de trois cent
            quatre-vingt-quatre dimensions par un modèle multilingue exécuté localement.""",
            """Nous avons rédigé cent vingt questions réparties en quatre catégories : formulations
            exactes, reformulations, questions ouvertes et requêtes multilingues. Pour chaque
            question, un annotateur indique le ou les documents attendus. Les métriques retenues
            sont le rappel à cinq, le rappel à dix et le rang réciproque moyen.""",
        ],
    ),
    (
        "3. Résultats",
        [
            """La recherche lexicale obtient d'excellents résultats sur les formulations exactes
            mais s'effondre sur les reformulations, où les mots de la question diffèrent de ceux
            du document. La recherche vectorielle présente le profil inverse : elle comprend les
            paraphrases mais confond parfois des documents proches. La fusion par rangs
            réciproques combine les deux listes sans calibrer leurs scores et obtient le meilleur
            rappel global, avec un gain particulièrement net sur les questions multilingues.""",
        ],
    ),
    (
        "4. Discussion",
        [
            """Ces résultats doivent être interprétés avec prudence. Le corpus est petit, les
            questions ont été écrites par les auteurs eux-mêmes et la taille des passages n'a pas
            été optimisée. Une évaluation sur des documents réels, avec des questions formulées
            plusieurs semaines après la lecture, serait plus représentative de l'usage
            quotidien.""",
        ],
    ),
    (
        "5. Conclusion",
        [
            """Pour un moteur de recherche personnel, local et respectueux de la vie privée, la
            combinaison d'un index lexical et d'un index vectoriel dans une seule base de données
            constitue un compromis robuste. Les travaux futurs porteront sur le reclassement des
            résultats et sur la détection automatique des documents numérisés sans couche de
            texte.""",
        ],
    ),
]


def build_article(fonts: FontBook) -> pymupdf.Document:
    """Deux colonnes écrites ligne à ligne : l'ordre du fichier n'est pas l'ordre de lecture."""
    doc = pymupdf.open()
    x0, x1 = 57.0, 538.0
    head_lines = (
        paragraph(ARTICLE_TITLE, fonts.serif_bold, 17, x1 - x0)
        + paragraph(ARTICLE_AUTHORS, fonts.serif, 10, x1 - x0, space_before=6)
        + paragraph(ARTICLE_ABSTRACT, fonts.serif, 9.5, x1 - x0, hyphenate=True, space_before=14)
    )
    head = place(head_lines, page_frames(0, pymupdf.Rect(x0, 70, x1, 400)))

    col_width = (x1 - x0 - 18) / 2
    body: list[Line] = []
    for heading, paragraphs in ARTICLE_SECTIONS:
        body += paragraph(heading, fonts.serif_bold, 10, col_width, space_before=8)
        for text in paragraphs:
            body += paragraph(text, fonts.serif, 9.5, col_width, hyphenate=True, space_before=3)
    columns = [(x0, x0 + col_width), (x1 - col_width, x1)]
    body_top = head[-1][1].y + 20
    placed = head + place(body, column_frames(columns, body_top, 70, 780))

    render(doc, placed, A4, reading_order=False)
    add_running_text(
        doc, fonts.serif, 8, "Revue fictive d'informatique documentaire · vol. 3, n° 2", "{n}"
    )
    return doc


# --- 2. Long rapport en français ---------------------------------------------------------

REPORT_TITLE = "Rapport annuel 2025"
REPORT_SUBTITLE = "Médiathèque fictive de Valcourt — Programme de numérisation des archives"
REPORT_CHAPTERS: list[tuple[str, list[str]]] = [
    (
        "1. Synthèse",
        [
            """L'année deux mille vingt-cinq marque une étape décisive pour le programme de
            numérisation des archives municipales. Près de quarante-deux mille pages ont été
            numérisées, contrôlées puis indexées, soit une progression considérable par rapport
            à l'exercice précédent. Cette accélération s'explique principalement par la
            réorganisation du flux de traitement, la professionnalisation des équipes et
            l'acquisition d'un second scanner à plat destiné aux documents fragiles.""",
            """Au-delà des volumes, la fiabilité des métadonnées constitue le principal acquis de
            l'année. Chaque fichier numérisé est désormais accompagné d'une fiche descriptive
            normalisée qui précise sa provenance, sa date approximative, son niveau de
            confidentialité et son état de conservation. Cette classification facilite
            considérablement les recherches documentaires effectuées par le public et par les
            services administratifs.""",
        ],
    ),
    (
        "2. Contexte et objectifs",
        [
            """Les archives municipales de Valcourt rassemblent des registres de délibérations,
            des plans d'urbanisme, des correspondances administratives et des photographies
            couvrant près de deux siècles d'histoire locale. Une partie importante de ces
            documents présente des signes de dégradation : encres pâlies, papiers acides,
            reliures fragilisées. La numérisation répond donc simultanément à un objectif de
            conservation et à un objectif d'accessibilité.""",
            """Le programme poursuit trois objectifs prioritaires : sécuriser les fonds les plus
            menacés, offrir une consultation en ligne des documents libres de droits et constituer
            un index plein texte interrogeable, y compris pour les documents manuscrits transcrits
            par des bénévoles. La réflexion engagée cette année sur l'interopérabilité des formats
            prépare l'intégration future au portail départemental.""",
        ],
    ),
    ("3. Activité mensuelle", []),  # paragraphes générés par monthly_activity()
    (
        "4. Difficultés rencontrées",
        [
            """Plusieurs difficultés ont ralenti le programme au second semestre. Le remplacement
            du logiciel de gestion documentaire a nécessité une migration des métadonnées plus
            longue que prévu, en raison d'incohérences historiques dans la saisie des dates et des
            noms de lieux. Par ailleurs, la reconnaissance automatique des caractères donne des
            résultats insuffisants sur les documents manuscrits et sur les imprimés anciens
            utilisant des caractères gothiques.""",
            """La question de la confidentialité a également fait l'objet de discussions
            approfondies. Certains registres contiennent des informations nominatives qui ne
            peuvent être communiquées avant l'expiration des délais légaux. Un circuit de
            validation spécifique a été mis en place afin que ces documents restent consultables
            sur place mais ne soient jamais diffusés en ligne.""",
        ],
    ),
    (
        "5. Perspectives pour 2026",
        [
            """Pour deux mille vingt-six, la priorité portera sur l'amélioration de la recherche
            plein texte et sur la mise en ligne progressive des fonds photographiques. Une étude
            de faisabilité examinera l'intérêt d'un moteur de recherche capable de comprendre des
            questions formulées en langage naturel, afin que les usagers puissent retrouver un
            document à partir d'un simple souvenir de son contenu.""",
        ],
    ),
]
MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août"]
MONTHS += ["Septembre", "Octobre", "Novembre", "Décembre"]
FONDS = [
    "des registres de délibérations",
    "du fonds photographique",
    "des plans d'urbanisme",
    "de la correspondance administrative",
    "des registres paroissiaux",
    "des archives scolaires",
]
COMMENTS = [
    "un niveau conforme aux objectifs fixés",
    "en légère amélioration par rapport au mois précédent",
    "en hausse en raison de documents particulièrement difficiles à manipuler",
    "ce qui confirme la stabilisation des procédures",
]
EVENTS = [
    "Deux bénévoles supplémentaires ont rejoint l'atelier de transcription.",
    "Une journée de formation sur la manipulation des documents fragiles a réuni les agents.",
    "Le serveur de stockage a fait l'objet d'une maintenance planifiée sans interruption.",
    "Une exposition temporaire a présenté une sélection de cartes postales anciennes.",
    "Les procédures de sauvegarde ont été vérifiées par un prestataire indépendant.",
    "Un partenariat avec le lycée professionnel a permis d'accueillir trois stagiaires.",
]


def monthly_activity() -> list[tuple[str, str]]:
    """Un paragraphe par mois, varié mais reproductible (graine fixe)."""
    rng = random.Random(2025)
    result = []
    for month in MONTHS:
        rate = f"{rng.uniform(1.5, 6.5):.1f}".replace(".", ",")
        text = (
            f"En {month.lower()}, l'équipe a numérisé {rng.randint(2800, 4200)} pages issues "
            f"principalement {rng.choice(FONDS)}. Le taux de reprise après contrôle qualité "
            f"s'établit à {rate} %, {rng.choice(COMMENTS)}. {rng.choice(EVENTS)}"
        )
        result.append((month, text))
    return result


def build_report(fonts: FontBook) -> pymupdf.Document:
    """Couverture, sommaire, césures, ligatures, en-têtes et pieds de page répétés."""
    doc = pymupdf.open()
    frame = pymupdf.Rect(70, 80, 525, 780)
    width = frame.width

    def lig(text: str) -> str:
        return with_ligatures(clean(text), fonts.serif)

    cover = place(
        paragraph(REPORT_TITLE, fonts.serif_bold, 28, width)
        + paragraph(REPORT_SUBTITLE, fonts.serif, 15, width, space_before=12)
        + paragraph(
            "Document de travail — diffusion restreinte", fonts.serif, 11, width, space_before=40
        ),
        page_frames(0, pymupdf.Rect(70, 300, 525, 780)),
    )

    body: list[Line] = []
    for chapter, paragraphs in REPORT_CHAPTERS:
        body.append(Line(lig(chapter), fonts.serif_bold, 14, space_before=20, toc=True))
        if not paragraphs:
            for month, text in monthly_activity():
                body += paragraph(month, fonts.serif_bold, 11.5, width, space_before=10)
                body += paragraph(lig(text), fonts.serif, 11.5, width, hyphenate=True)
        for text in paragraphs:
            body += paragraph(lig(text), fonts.serif, 11.5, width, hyphenate=True, space_before=7)
    body_placed = place(body, page_frames(2, frame))

    toc: list[Line] = [Line("Sommaire", fonts.serif_bold, 16)]
    for page_no, _, line in body_placed:
        if line.toc:
            entry = dotted(line.text, str(page_no + 1), fonts.serif, 11.5, width)
            toc.append(Line(entry, fonts.serif, 11.5, space_before=8))
    toc_placed = place(toc, page_frames(1, pymupdf.Rect(70, 120, 525, 780)))

    render(doc, cover + toc_placed + body_placed, A4)
    add_running_text(
        doc,
        fonts.serif,
        8.5,
        "Médiathèque fictive de Valcourt — Rapport annuel 2025 — Usage interne",
        "page {n} / {total}",
        first_page=1,
    )
    return doc


# --- 3. Slides exportées en PDF ----------------------------------------------------------


def build_slides(fonts: FontBook) -> pymupdf.Document:
    """Format paysage, peu de texte par page, zones de texte éparpillées, schéma."""
    doc = pymupdf.open()
    blue = (0.15, 0.3, 0.55)

    def slide(title: str | None) -> tuple[pymupdf.Page, pymupdf.TextWriter]:
        page = doc.new_page(width=SLIDE.width, height=SLIDE.height)
        writer = pymupdf.TextWriter(page.rect)
        if title:
            writer.append((60, 90), title, font=fonts.sans_bold, fontsize=34)
        return page, writer

    def centered(
        writer: pymupdf.TextWriter, cx: float, y: float, text: str, font: pymupdf.Font, size: float
    ) -> None:
        writer.append(
            (cx - font.text_length(text, fontsize=size) / 2, y), text, font=font, fontsize=size
        )

    page, w = slide(None)
    centered(w, 480, 240, "Indexer ses documents en local", fonts.sans_bold, 44)
    centered(w, 480, 295, "Atelier fictif — novembre 2025", fonts.sans, 22)
    w.write_text(page)

    page, w = slide("Pourquoi une recherche locale ?")
    bullets = [
        "Retrouver une idée, pas un nom de fichier",
        "Aucun document ne quitte la machine",
        "Fonctionne sans connexion",
    ]
    for i, bullet in enumerate(bullets):
        w.append((80, 180 + i * 55), f"• {bullet}", font=fonts.sans, fontsize=26)
    w.write_text(page)

    page, w = slide("Le pipeline d'indexation")
    labels = ["Fichiers", "Extraction", "Découpage", "Index"]
    for i, label in enumerate(labels):
        box = pymupdf.Rect(60 + i * 225, 210, 230 + i * 225, 290)
        page.draw_rect(box, color=blue, width=2)
        centered(w, box.x0 + box.width / 2, 258, label, fonts.sans, 22)
        if i < len(labels) - 1:
            page.draw_line((box.x1 + 5, 250), (box.x1 + 50, 250), color=blue, width=2)
            page.draw_line((box.x1 + 40, 243), (box.x1 + 50, 250), color=blue, width=2)
            page.draw_line((box.x1 + 40, 257), (box.x1 + 50, 250), color=blue, width=2)
    centered(w, 480, 400, "Chaque étape est remplaçable", fonts.sans, 22)
    w.write_text(page)

    page, w = slide("Deux façons de chercher")
    for x, heading, items in (
        (80, "Lexicale (BM25)", ["mots exacts", "rapide", "explicable"]),
        (520, "Vectorielle", ["sens proche", "multilingue", "plus coûteuse"]),
    ):
        w.append((x, 180), heading, font=fonts.sans_bold, fontsize=26)
        for i, item in enumerate(items):
            w.append((x + 10, 235 + i * 45), f"– {item}", font=fonts.sans, fontsize=22)
    w.write_text(page)

    page, w = slide("Résultats sur 120 questions")
    for i, (value, label) in enumerate(
        (("0,62", "BM25"), ("0,71", "Vecteurs"), ("0,83", "Hybride"))
    ):
        cx = 160 + i * 320
        centered(w, cx, 280, value, fonts.sans_bold, 64)
        centered(w, cx, 330, label, fonts.sans, 22)
    centered(w, 480, 430, "Rappel@5, questions inventées", fonts.sans, 18)
    w.write_text(page)

    page, w = slide(None)
    centered(w, 480, 285, "Questions ?", fonts.sans_bold, 48)
    w.write_text(page)

    add_running_text(doc, fonts.sans, 12, None, "Indexer ses documents en local · {n}/{total}")
    return doc


# --- 4. Document façon export Word -------------------------------------------------------

WORD_BEFORE_TABLE: list[tuple[str, str]] = [  # (style, texte)
    ("title", "Compte rendu de réunion"),
    ("subtitle", "Projet fictif : refonte de l'intranet documentaire"),
    ("body", "Date : 14 octobre 2025 — Lieu : salle Condorcet, deuxième étage"),
    (
        "body",
        """Participants : Léa Bernard (cheffe de projet), Hugo Petit (développeur), Inès Moreau
        (documentaliste), Paul Garnier (responsable sécurité)""",
    ),
    ("h1", "1. Points abordés"),
    (
        "body",
        """• L'équipe a présenté l'état d'avancement du moteur de recherche interne : l'indexation
        des documents partagés fonctionne, mais les PDF numérisés ne sont pas encore pris en
        compte.""",
    ),
    (
        "body",
        """• Les temps de réponse sont jugés satisfaisants : moins d'une seconde pour la plupart des
        requêtes.""",
    ),
    (
        "body",
        """Inès Moreau rappelle que les utilisateurs cherchent souvent « le document dont on a
        parlé en réunion » plutôt qu'un titre précis. Elle propose de tester la recherche avec des
        questions réelles collectées auprès des services.""",
    ),
    ("h1", "2. Décisions et actions"),
    ("body", "Les actions suivantes ont été décidées :"),
]
WORD_TABLE = [
    ["Action", "Responsable", "Échéance"],
    [
        "Constituer un jeu de 50 questions de test à partir des demandes réelles",
        "Inès Moreau",
        "31 octobre",
    ],
    [
        "Mesurer le rappel de la recherche actuelle sur ce jeu de questions",
        "Hugo Petit",
        "7 novembre",
    ],
    [
        "Vérifier que les journaux ne contiennent aucun extrait de document",
        "Paul Garnier",
        "7 novembre",
    ],
    ["Préparer une démonstration pour le comité de direction", "Léa Bernard", "21 novembre"],
]
WORD_AFTER_TABLE: list[tuple[str, str]] = [
    ("h1", "3. Points de vigilance"),
    (
        "body",
        """Paul Garnier souligne que certains dossiers partagés contiennent des données
        personnelles. L'indexation devra respecter les droits d'accès existants : un utilisateur ne
        doit jamais voir, même sous forme d'extrait, un document qu'il ne pourrait pas ouvrir.""",
    ),
    ("h1", "4. Prochaine réunion"),
    (
        "body",
        """La prochaine réunion aura lieu le 21 novembre à 10 h, dans la même salle. Ordre du
        jour : résultats de la première évaluation et démonstration.""",
    ),
]


def build_word_like(fonts: FontBook) -> pymupdf.Document:
    """Typographie de traitement de texte (’, insécables), tableau, en-tête et pied de page."""
    doc = pymupdf.open()
    frame = pymupdf.Rect(72, 90, 523, 770)  # marges de 2,5 cm
    styles = {
        "title": (fonts.sans_bold, 20, 0.0),
        "subtitle": (fonts.sans_bold, 13, 6.0),
        "h1": (fonts.sans_bold, 14, 16.0),
        "body": (fonts.sans, 11, 6.0),
    }

    def lines(blocks: list[tuple[str, str]]) -> list[Line]:
        result: list[Line] = []
        for style, text in blocks:
            font, size, space = styles[style]
            result += paragraph(
                word_typography(clean(text)), font, size, frame.width, space_before=space
            )
        return result

    before = place(lines(WORD_BEFORE_TABLE), page_frames(0, frame))
    render(doc, before, A4)

    page_no, last_pos, _ = before[-1]
    cells, rects, bottom = table(
        WORD_TABLE, [251, 120, 80], frame.x0, last_pos.y + 12, fonts, page_no
    )
    for rect in rects:
        doc[page_no].draw_rect(rect, color=(0, 0, 0), width=0.5)
    render(doc, cells, A4)

    after = place(lines(WORD_AFTER_TABLE), page_frames(page_no, frame, first_top=bottom + 6))
    render(doc, after, A4)
    add_running_text(
        doc, fonts.sans, 9, "Projet fictif – Compte rendu interne", "Page {n} sur {total}"
    )
    return doc


def table(
    rows: list[list[str]],
    col_widths: list[float],
    x0: float,
    top: float,
    fonts: FontBook,
    page_no: int,
    size: float = 10,
) -> tuple[list[Placed], list[pymupdf.Rect], float]:
    """Place le texte des cellules ligne par ligne ; renvoie aussi les bordures et le bas."""
    pad = 4.0
    placed: list[Placed] = []
    rects: list[pymupdf.Rect] = []
    y = top
    for r, row in enumerate(rows):
        font = fonts.sans_bold if r == 0 else fonts.sans
        cells = [
            wrap(word_typography(c), font, size, w - 2 * pad)
            for c, w in zip(row, col_widths, strict=True)
        ]
        height = max(len(c) for c in cells) * size * LEADING + 2 * pad
        x = x0
        for cell_lines, w in zip(cells, col_widths, strict=True):
            rects.append(pymupdf.Rect(x, y, x + w, y + height))
            for i, text in enumerate(cell_lines):
                pos = pymupdf.Point(x + pad, y + pad + size + i * size * LEADING)
                placed.append((page_no, pos, Line(text, font, size)))
            x += w
        y += height
    return placed, rects, y


# --- 5. PDF scanné et 6. PDF mixte -------------------------------------------------------

LETTER = [
    ("Association fictive des lecteurs de Valcourt", 0.0),
    ("12 rue des Tilleuls, 00000 Valcourt", 0.0),
    ("Valcourt, le 3 mars 2025", 30.0),
    ("Objet : demande de consultation des registres de délibérations", 24.0),
    ("Madame, Monsieur,", 24.0),
    (
        """Notre association souhaite consulter les registres de délibérations du conseil municipal
        pour la période allant de 1890 à 1910, dans le cadre d'une exposition consacrée à
        l'arrivée du chemin de fer à Valcourt.""",
        12.0,
    ),
    (
        """Nous avons bien noté que certains de ces registres sont fragiles et ne peuvent être
        manipulés que sous la surveillance d'un agent. Si une version numérisée existe, nous
        serions heureux de pouvoir la consulter en priorité afin de limiter les manipulations des
        originaux.""",
        12.0,
    ),
    (
        """Nous restons à votre disposition pour convenir d'un rendez-vous et vous remercions par
        avance de l'attention que vous porterez à notre demande.""",
        12.0,
    ),
    ("Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées.", 12.0),
    ("Claire Lefèvre, présidente", 30.0),
]
LETTER_ANNEX = [
    "Annexe : registres demandés",
    "• Registre des délibérations, 1890–1895",
    "• Registre des délibérations, 1896–1900",
    "• Registre des délibérations, 1901–1905",
    "• Registre des délibérations, 1906–1910",
    "• Plan cadastral du quartier de la gare, 1898",
]


def build_letter(fonts: FontBook) -> pymupdf.Document:
    """Le courrier « papier », avant numérisation."""
    doc = pymupdf.open()
    frame = pymupdf.Rect(80, 90, 515, 780)
    letter: list[Line] = []
    for text, space in LETTER:
        letter += paragraph(text, fonts.serif, 12, frame.width, space_before=space)
    annex = [Line(t, fonts.serif, 12, space_before=10) for t in LETTER_ANNEX]
    render(doc, place(letter, page_frames(0, frame)) + place(annex, page_frames(1, frame)), A4)
    return doc


def scanned_images(source: pymupdf.Document, dpi: int = 150) -> list[pymupdf.Pixmap]:
    """Rend chaque page en image grise, légèrement de travers comme sur un scanner."""
    zoom = dpi / 72
    matrix = pymupdf.Matrix(zoom, zoom).prerotate(0.7)
    return [page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY) for page in source]


def build_scanned(fonts: FontBook) -> pymupdf.Document:
    """Uniquement des images : aucune couche de texte à extraire."""
    doc = pymupdf.open()
    for pixmap in scanned_images(build_letter(fonts)):
        page = doc.new_page(width=A4.width, height=A4.height)
        page.insert_image(page.rect, pixmap=pixmap)
    return doc


def build_mixed(fonts: FontBook) -> pymupdf.Document:
    """Pages de texte encadrant une page numérisée : un cas réel fréquent."""
    doc = pymupdf.open()
    frame = pymupdf.Rect(72, 90, 523, 770)
    note = paragraph("Note de transmission", fonts.sans_bold, 16, frame.width) + paragraph(
        """Vous trouverez ci-après la copie numérisée du courrier reçu de l'Association fictive
        des lecteurs de Valcourt. Le courrier original est conservé au secrétariat.""",
        fonts.sans,
        11,
        frame.width,
        space_before=10,
    )
    follow_up = paragraph("Suite à donner", fonts.sans_bold, 16, frame.width) + paragraph(
        """Proposer un rendez-vous à l'association en avril. Vérifier au préalable que les
        registres de 1890 à 1910 ont bien été numérisés et que leur état permet une consultation
        sur place.""",
        fonts.sans,
        11,
        frame.width,
        space_before=10,
    )
    render(doc, place(note, page_frames(0, frame)) + place(follow_up, page_frames(2, frame)), A4)
    scan = scanned_images(build_letter(fonts))[0]
    doc[1].insert_image(doc[1].rect, pixmap=scan)
    return doc


# --- Programme principal -----------------------------------------------------------------

SAMPLES: list[tuple[str, str, Callable[[FontBook], pymupdf.Document]]] = [
    ("article-deux-colonnes.pdf", ARTICLE_TITLE, build_article),
    ("rapport-annuel-long.pdf", f"{REPORT_TITLE} — {REPORT_SUBTITLE}", build_report),
    ("slides-presentation.pdf", "Indexer ses documents en local", build_slides),
    ("compte-rendu-facon-word.pdf", "Compte rendu de réunion", build_word_like),
    ("courrier-scanne.pdf", "Courrier numérisé", build_scanned),
    ("dossier-mixte-texte-et-scan.pdf", "Note de transmission", build_mixed),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=Path("samples/pdf"), help="dossier de sortie")
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()
    for filename, title, build in SAMPLES:
        doc = build(fonts)
        doc.set_metadata({"title": title, "author": "Auteur fictif", "creator": CREATOR})
        doc.subset_fonts()
        path = out / filename
        doc.save(path, garbage=3, deflate=True)
        print(f"{path}  {doc.page_count} page(s)  {path.stat().st_size / 1024:.0f} Ko")
    return 0


if __name__ == "__main__":
    sys.exit(main())
