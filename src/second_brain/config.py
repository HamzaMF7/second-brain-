"""Configuration centralisée. Chaque réglage a une valeur par défaut documentée."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionConfig:
    # Un PDF dont la moyenne de caractères non blancs par page est inférieure à ce seuil
    # est considéré comme scanné. Une page de slides en compte en général plus de 100 ;
    # un scan peut porter un peu de texte parasite (numéro de page, filigrane).
    scan_threshold_chars_per_page: int = 50
