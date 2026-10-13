-- Schéma initial (CLAUDE.md, section 7), sans chunks_fts ni chunk_vectors.
-- STRICT : SQLite refuse une valeur du mauvais type au lieu de la convertir en silence.
-- Pas de BEGIN/COMMIT ici : migrator.py exécute chaque fichier dans sa transaction.

CREATE TABLE folders (
    id      INTEGER PRIMARY KEY,
    path    TEXT    NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
) STRICT;

CREATE TABLE documents (
    id           INTEGER PRIMARY KEY,
    path         TEXT    NOT NULL UNIQUE,
    filename     TEXT    NOT NULL,
    extension    TEXT    NOT NULL,
    size         INTEGER NOT NULL,             -- octets
    mtime        INTEGER NOT NULL,             -- nanosecondes (st_mtime_ns) : comparaison exacte
    content_hash TEXT,                         -- NULL si le fichier n'a pas pu être lu
    status       TEXT    NOT NULL CHECK (status IN ('indexed', 'scanned', 'error')),
    error        TEXT,                         -- type d'erreur et nom de fichier, jamais de contenu
    indexed_at   TEXT    NOT NULL              -- ISO 8601 UTC
) STRICT;

-- Retrouver un document par son hash : détection des fichiers déplacés ou renommés.
CREATE INDEX documents_content_hash ON documents (content_hash);

CREATE TABLE chunks (
    id          INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    page        INTEGER,
    section     TEXT,
    token_count INTEGER,
    -- Aussi l'index sur document_id dont ON DELETE CASCADE a besoin pour ne pas
    -- parcourir toute la table à chaque suppression.
    UNIQUE (document_id, chunk_index)
) STRICT;
