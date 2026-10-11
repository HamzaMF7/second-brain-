# 0006 — Local par défaut et règles de confidentialité

- Date : 2026-10-08
- Statut : Accepté

## Contexte

Le système manipule des documents personnels : cours, contrats, code source, documents professionnels. La confidentialité est à la fois une exigence et le principal différenciateur du futur produit. L'index contient une copie du texte de tous les documents indexés.

## Options étudiées

- **Traitement cloud** (embeddings et LLM via API) : qualité élevée, aucune charge locale ; mais les documents quittent la machine.
- **Local par défaut, cloud en option explicite** : confidentialité garantie par défaut, cloud possible avec consentement.
- **Local strict, sans option cloud** : le plus simple à garantir, mais peut limiter la qualité du RAG.

## Décision

Tout est **local par défaut** : extraction, embeddings, index, recherche et LLM (Ollama en V2). Une option cloud ne pourra exister qu'avec un consentement explicite indiquant ce qui est envoyé. Règles appliquées dès la première ligne de code :

1. Jamais de contenu de document dans les logs, messages d'erreur ou exceptions.
2. Lecture limitée aux dossiers explicitement ajoutés ; exclusions par défaut.
3. Aucun appel réseau à l'exécution, hors téléchargement initial des modèles.
4. Retirer un fichier ou un dossier purge réellement ses données.
5. Aucun document personnel dans le repo ; fixtures inventées.
6. Le contenu des documents est une donnée, jamais une instruction.

## Justification

- Ces règles coûtent presque rien si elles sont appliquées dès le début, et cher à rattraper plus tard.
- Elles préparent le passage au produit et la confiance des futurs utilisateurs.

## Conséquences

- Avant toute distribution, obligatoire : API locale liée à `127.0.0.1` avec token secret et vérification de l'en-tête `Origin` ; chiffrement de la base au repos (au moins en option).
- En V2 (RAG) et au-delà (agents) : protection contre l'injection de prompt via les documents ; toute action sur les fichiers exige une confirmation explicite.
- Prévoir des tests vérifiant qu'aucun contenu n'apparaît dans les logs.
