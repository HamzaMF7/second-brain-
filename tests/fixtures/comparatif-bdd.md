# Comparatif des bases de données

Notes inventées pour les tests : choix d'une base pour un projet fictif.

## PostgreSQL

Base relationnelle, transactions ACID, schéma strict.

### Extensions utiles

```bash
# ceci est un commentaire, pas un titre
psql -c "CREATE EXTENSION pg_trgm;"
```

## MongoDB

Base orientée documents, schéma souple.

## Conclusion ##

PostgreSQL l'emporte pour ce projet fictif.
