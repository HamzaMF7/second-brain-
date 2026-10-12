"""Erreurs d'extraction. Les messages ne contiennent jamais de contenu de document."""


class ExtractionError(Exception):
    """Base de toutes les erreurs d'extraction."""


class CorruptedDocumentError(ExtractionError):
    """Le fichier n'a pas pu être lu comme un document valide du format attendu."""


class EncryptedDocumentError(ExtractionError):
    """Le document est protégé par un mot de passe."""


class UnsupportedFormatError(ExtractionError):
    """Aucun extracteur ne prend en charge cette extension."""

    def __init__(self, extension: str) -> None:
        self.extension = extension
        super().__init__(f"Format non supporté : {extension or '(sans extension)'}")
