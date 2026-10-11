# Prompts Claude Code — V0

> À placer dans `docs/prompts-v0.md`.
> Ordre d'exécution = ordre du fichier. Une case = une session ou une tâche.
> Règles : nouvelle session (`/clear`) à chaque nouvelle tâche · mode plan (Shift+Tab) pour les prompts marqués 🧭 · relis chaque diff avant de commiter · `/fin-tache` après chaque tâche.
> Les prompts marqués ✍️ sont des tâches que **tu codes toi-même** : Claude Code ne fait que les tests et la relecture.

---

## Étape 0 — Environnement et corpus

- [ ] **0.1 🧭 Setup du projet**
  > Lis CLAUDE.md. Je démarre l'étape 0. Propose la configuration minimale d'un projet Python 3.12 avec uv, ruff, mypy (strict sur src/) et pytest, avec la structure de dossiers décrite en section 5 et un point d'entrée CLI `second-brain`. Explique le rôle de chaque fichier de configuration avant de les créer. Ne crée aucun module métier pour l'instant.

- [ ] **0.2 CLI squelette**
  > Ajoute une CLI avec Typer (ou propose argparse si tu juges que c'est mieux pour moi, en expliquant pourquoi) exposant les commandes vides `index`, `search`, `extract`, `chunks`. Chacune affiche « pas encore implémenté ». Ajoute un test qui vérifie que `--help` fonctionne.

- [ ] **0.3 .gitignore et CI**
  > Crée un .gitignore adapté (Python, uv, .env, *.db, corpus/) et une CI GitHub Actions qui lance ruff, mypy et pytest sur chaque push. Explique-moi chaque étape du workflow.

- [ ] **0.4 Inventaire du corpus**
  > Écris un script `scripts/corpus_stats.py` qui parcourt un dossier passé en argument et affiche : nombre de fichiers par extension, taille totale, plus gros fichiers. Il ne doit lire aucun contenu, seulement les métadonnées. Je vais le lancer sur mon corpus.

- [ ] **0.5 Clôture** → `/fin-etape 0`

---

## Étape 1 — Extraction

- [ ] **1.1 🧭 Concepts**
  > Avant de coder : explique-moi pourquoi extraire du texte d'un PDF est difficile (colonnes, en-têtes, césures, PDF scannés), et ce qu'est le pattern Strategy appliqué à des extracteurs par format. Termine par 3 questions pour vérifier que j'ai compris.

- [ ] **1.2 Modèles de données**
  > Crée les modèles `ExtractedDocument` et `Page` dans `src/second_brain/extraction/models.py` (champs : path, title, text, pages, sections détectées, metadata, is_scanned). Propose dataclass ou Pydantic avec les compromis, puis attends mon choix.

- [ ] **1.3 Interface et registre**
  > Crée l'interface `DocumentExtractor` (section 5 du CLAUDE.md) et un registre qui renvoie le bon extracteur selon l'extension, ou lève une erreur explicite si le format n'est pas supporté. Tests d'abord.

- [ ] **1.4 TXT et Markdown**
  > Implémente `TextExtractor` et `MarkdownExtractor`. Le Markdown doit conserver la hiérarchie des titres pour le futur chunking. Gère les encodages (UTF-8, Latin-1) et normalise en Unicode NFC. Crée des fixtures inventées dans tests/fixtures/.

- [ ] **1.5 🧭 Comparatif PDF**
  > Écris `scripts/compare_pdf_libs.py` qui extrait 5 PDF avec PyMuPDF puis pypdf et affiche pour chacun : temps, nombre de caractères, 300 premiers caractères. Rappelle-moi aussi les licences des deux bibliothèques et ce que ça implique pour un futur produit. Ne choisis pas à ma place.

- [ ] **1.6 ADR bibliothèque PDF** → `/adr choix de la bibliothèque PDF`

- [ ] **1.7 Extracteur PDF**
  > Implémente `PdfExtractor` avec la bibliothèque choisie dans l'ADR 0007 (bibliothèque PDF). Une Page par page du PDF. Détecte les PDF scannés (moins de N caractères par page en moyenne, N configurable) et marque-les `is_scanned=True` sans planter.

- [ ] **1.8 Commande extract**
  > Branche la commande `second-brain extract <fichier>` : affiche le titre, le nombre de pages, si le document est scanné, et les 500 premiers caractères.

- [ ] **1.9 Test sur le corpus**
  > Écris `scripts/extract_all.py` qui extrait tout le corpus et produit un rapport : succès, échecs (avec type d'erreur, sans contenu), PDF scannés. Je veux zéro plantage : chaque erreur doit être capturée et rapportée.

- [ ] **1.10 Clôture** → `/fin-etape 1`

---

## Étape 2 — Stockage et indexation

- [ ] **2.1 🧭 Concepts**
  > Explique-moi l'indexation incrémentale : pourquoi comparer mtime et taille avant de calculer un hash, et les 5 cas (nouveau, modifié, inchangé, supprimé, déplacé). Puis explique les transactions SQLite et ON DELETE CASCADE avec un exemple. 3 questions de vérification à la fin.

- [ ] **2.2 🧭 SQL brut ou ORM**
  > Montre-moi la même insertion d'un document et de ses chunks en sqlite3 brut puis en SQLModel. Liste les compromis pour un projet d'apprentissage qui deviendra un produit. Je déciderai. → puis `/adr SQL brut ou ORM`

- [ ] **2.3 Schéma et migrations**
  > Implémente le schéma de la section 7 du CLAUDE.md (sans chunks_fts ni chunk_vectors pour l'instant) avec un système de migrations minimal basé sur `schema_version`. Active `PRAGMA foreign_keys`. Tests : base vide → migrée ; migration rejouée → sans effet.

- [ ] **2.4 Scanner**
  > Crée `indexing/scanner.py` : parcours récursif d'un dossier avec les exclusions de la section 8, renvoie pour chaque fichier supporté son chemin, sa taille et son mtime. Aucune lecture de contenu. Tests avec un dossier temporaire.

- [ ] **2.5 Détection des changements (tests d'abord)**
  > Écris d'abord les tests de `indexing/changes.py` pour les 5 cas : nouveau, modifié, inchangé (mtime identique), inchangé (mtime changé mais hash identique), supprimé. Montre-les-moi avant d'implémenter.
  > *(puis)* Implémente le code pour faire passer ces tests.

- [ ] **2.6 Pipeline d'indexation**
  > Crée `indexing/pipeline.py` qui, pour chaque changement détecté, extrait et enregistre le document dans une seule transaction. À ce stade un document = un seul chunk. Erreur sur un fichier → statut `error` en base, le pipeline continue. Logs sans aucun contenu.

- [ ] **2.7 Commande index**
  > Branche `second-brain index <dossier>` avec une barre de progression et un résumé final : ajoutés, modifiés, supprimés, inchangés, erreurs, durée.

- [ ] **2.8 Vérification**
  > Lance l'indexation deux fois sur tests/fixtures et vérifie que la deuxième ne retraite rien. Ajoute un test d'intégration qui le prouve. Puis indique-moi comment ouvrir la base avec DB Browser for SQLite pour l'inspecter.

- [ ] **2.9 Clôture** → `/fin-etape 2`

---

## Étape 3 — BM25 (FTS5)

- [ ] **3.1 🧭 Concepts**
  > Explique-moi l'index inversé, puis TF-IDF, puis BM25 avec un calcul chiffré sur 3 mini-documents et une requête de 2 mots. Explique le rôle des paramètres k1 et b. Puis pourquoi le tokenizer `unicode61 remove_diacritics 2` et pas `porter` pour du français.

- [ ] **3.2 Table FTS5**
  > Ajoute une migration qui crée `chunks_fts` (FTS5 external content sur chunks.text) et les triggers de synchronisation INSERT/UPDATE/DELETE. Test : supprimer un document le fait disparaître de la recherche.

- [ ] **3.3 Retriever lexical**
  > Crée l'interface `Retriever` et le modèle `SearchResult` (section 5), puis `search/lexical.py` : requête FTS5, score BM25, extrait via `snippet()`. Attention : FTS5 renvoie des scores négatifs (plus petit = meilleur), explique comment tu le gères.

- [ ] **3.4 Prétraitement des requêtes**
  > Ajoute un prétraitement : minuscules, retrait des mots vides français et anglais, échappement des caractères spéciaux FTS5 (guillemets, tirets, `*`), combinaison des termes en OR. Tests avec des requêtes piégeuses : « où parle-t-on de C++ ? », « API-472 », une requête vide.

- [ ] **3.5 Commande search**
  > Branche `second-brain search "<requête>"` : rang, nom de fichier, score, extrait avec termes surlignés (couleur terminal), temps de réponse.

- [ ] **3.6 Échecs de BM25**
  > Je vais tester 10 requêtes sur mon corpus. Aide-moi à noter dans docs/journal.md celles qui échouent et à les classer par cause (synonyme, reformulation, autre langue, autre).

- [ ] **3.7 Clôture** → `/fin-etape 3`

---

## Étape 4 — Évaluation

- [ ] **4.1 🧭 Concepts**
  > Explique-moi Recall@k et MRR avec un exemple chiffré de 3 questions. Puis le biais qui apparaît quand on écrit les questions en lisant les documents. Ne me donne pas le code des métriques : je vais les écrire.

- [ ] **4.2 Format des questions**
  > Crée `eval/questions.yaml` avec le format de la section 11 du CLAUDE.md et 3 exemples, plus un chargeur qui valide le fichier (types autorisés, fichiers attendus existants dans l'index). Je rédigerai les questions moi-même.

- [ ] **4.3 ✍️ Tests des métriques**
  > Je vais écrire moi-même `recall_at_k` et `mrr` dans `eval/metrics.py`. Écris uniquement les tests, avec cas limites : aucun résultat, plusieurs documents attendus, doublons, attendu absent de l'index. Ne code pas les fonctions.

- [ ] **4.4 ✍️ Relecture des métriques** → `/relecture eval/metrics.py`

- [ ] **4.5 Script d'évaluation**
  > Crée `eval/run_eval.py` : prend un nom de retriever, lance toutes les questions, regroupe les chunks par document, calcule Recall@5, Recall@10 et MRR globaux et par type, affiche un tableau et sauvegarde un JSON daté avec la configuration complète dans eval/results/.

- [ ] **4.6 Baseline** → `/eval lexical`

- [ ] **4.7 Clôture** → `/fin-etape 4` (ajouter les chiffres BM25 au README)

---

## Étape 5 — Chunking

- [ ] **5.1 🧭 Concepts**
  > Explique-moi pourquoi découper les documents, la limite de tokens des modèles d'embeddings, et compare 3 stratégies (taille fixe, récursive, par structure) avec leurs compromis pour des PDF et du Markdown en français.

- [ ] **5.2 Interface et chunker**
  > Crée l'interface `Chunker` et le modèle `Chunk` (texte, page, section, position, token_count). Implémente un chunker récursif qui respecte la structure : titres Markdown, pages PDF, puis paragraphes, puis phrases. Taille et chevauchement configurables, comptés en tokens. Tests sur les fixtures.

- [ ] **5.3 Préfixe de contexte**
  > Ajoute une option qui préfixe le texte indexé de chaque chunk par « titre du document > section ». Le texte affiché dans les résultats reste le texte d'origine.

- [ ] **5.4 Intégration**
  > Branche le chunker dans le pipeline d'indexation. Vérifie que la réindexation d'un document remplace bien tous ses anciens chunks. Ajoute la commande `second-brain chunks <fichier>` pour visualiser le découpage.

- [ ] **5.5 Expérience**
  > Lance l'évaluation BM25 avec des chunks de 200, 400 et 800 tokens, avec et sans préfixe. Donne-moi un tableau comparatif et ton interprétation, sans conclure à ma place. → `/eval lexical` pour chaque configuration

- [ ] **5.6 ADR** → `/adr stratégie et taille de chunk`

- [ ] **5.7 Clôture** → `/fin-etape 5`

---

## Étape 6 — Embeddings et recherche vectorielle

- [ ] **6.1 🧭 Concepts**
  > Explique-moi ce qu'est un embedding, la similarité cosinus avec un exemple en 3 dimensions, la différence bi-encodeur / cross-encodeur, et pourquoi ONNX plutôt que PyTorch pour notre cas. Mentionne le piège des préfixes query:/passage: des modèles e5.

- [ ] **6.2 🧭 Choix des candidats**
  > Propose-moi 2 ou 3 modèles d'embeddings multilingues disponibles dans fastembed, avec : dimension, limite de tokens, taille, langues, préfixes requis. Vérifie la liste réellement disponible dans la version installée plutôt que de te fier à ta mémoire.

- [ ] **6.3 Interface Embedder**
  > Crée l'interface `Embedder` (section 5) et une implémentation fastembed configurable par nom de modèle. Gère les préfixes automatiquement selon le modèle. Calcul par lots. Test avec 3 phrases : deux proches, une éloignée.

- [ ] **6.4 Stockage vectoriel**
  > Installe sqlite-vec et ajoute une migration pour `chunk_vectors` (avec `model_id`). Explique comment l'extension se charge dans sqlite3 et ce qui se passe si elle est absente. Les vecteurs doivent être purgés avec leur chunk.

- [ ] **6.5 Indexation des vecteurs**
  > Intègre le calcul des embeddings dans le pipeline, par lots, avec barre de progression. Si `model_id` change dans la config, seuls les vecteurs concernés sont recalculés. Mesure et affiche le temps d'embedding total.

- [ ] **6.6 Retriever sémantique**
  > Crée `search/semantic.py` qui implémente `Retriever` avec sqlite-vec. Ajoute `--mode lexical|semantic` à la commande search.

- [ ] **6.7 Comparaison des modèles**
  > Pour chaque modèle candidat : réindexe, lance l'évaluation, et relève la qualité par type de requête, le temps d'indexation du corpus, la taille de la base et la mémoire utilisée. Tableau final comparé à BM25. → `/eval semantic`

- [ ] **6.8 ADR** → `/adr modèle d'embeddings et stockage vectoriel`

- [ ] **6.9 Clôture** → `/fin-etape 6`

---

## Étape 7 — Recherche hybride

- [ ] **7.1 🧭 Concepts**
  > Explique-moi pourquoi on ne peut pas additionner un score BM25 et une similarité cosinus, puis Reciprocal Rank Fusion avec un exemple chiffré sur deux listes de 5 documents. Ne me donne pas le code.

- [ ] **7.2 ✍️ Tests RRF**
  > Je vais écrire `rrf()` dans `search/fusion.py`. Écris uniquement les tests : listes vides, document présent dans une seule liste, égalités, paramètre k. Ne code pas la fonction.

- [ ] **7.3 ✍️ Relecture** → `/relecture search/fusion.py`

- [ ] **7.4 Retriever hybride**
  > Crée `search/hybrid.py` : top 30 lexical + top 30 sémantique, fusion avec ma fonction rrf, regroupement des chunks par document (meilleur chunk affiché, nombre de chunks pertinents indiqué). Ajoute `--mode hybrid` et fais-en le mode par défaut.

- [ ] **7.5 Expérience**
  > Évalue l'hybride avec k = 20, 60, 100, plus une variante pondérée. Tableau final : lexical, sémantique, hybride, par type de requête. → `/eval hybrid`

- [ ] **7.6 ADR** → `/adr méthode de fusion`

- [ ] **7.7 README portfolio**
  > Réécris le README pour un recruteur : problème, démo (je fournirai un GIF), architecture (schéma Mermaid), choix techniques avec liens vers les ADR, tableau des résultats d'évaluation, installation, limites connues, prochaines étapes.

- [ ] **7.8 Rétrospective V0**
  > Relis docs/journal.md et docs/adr/. Aide-moi à écrire la rétrospective de la V0 : ce qui a marché, ce qui a été plus dur que prévu, ce que je referais autrement, et ce que les chiffres disent des priorités pour la V1.

- [ ] **7.9 Clôture** → `/fin-etape 7` puis une semaine d'usage réel avant la V1.

---

## Trame V1 / V2 (prompts à écrire après la rétrospective V0)

Même structure pour chaque étape : 🧭 concepts → décision + ADR → tâches petites → évaluation → clôture.

| Étape | Prompt d'ouverture |
|---|---|
| 8. File watcher | « Explique-moi watchdog, le debounce et une file d'attente en tâche de fond, puis propose un plan. » |
| 9. DOCX + filtres | « Ajoute un DocxExtractor sans toucher aux autres modules, puis des filtres dossier/type/date. » |
| 10. API + interface | « Mode plan : FastAPI au-dessus des modules existants, sans logique métier dans les routes. Puis une interface web locale minimale. » |
| 11. Reranker | « Explique cross-encoder vs bi-encoder, propose 2 rerankers multilingues ONNX, mesure gain et latence. » |
| 12. RAG | « Mode plan : Ollama, construction du contexte, prompt anti-hallucination, citations vérifiables. » |
| 13. Éval RAG | « Explique fidélité et exactitude des citations, et les limites d'un LLM juge. » |
| 14. Filtres temporels | « Extraire dates et lieux d'une question en filtres de métadonnées, avec 10 cas de test réels. » |
