# PROMPT POUR CODEX — GÉNÉRER L’APP “Loup-Garou avec LLM maître du jeu” (Streamlit + MongoDB)
#
# Objectif : Créer une application Streamlit où un LLM est le maître du jeu du Loup-Garou.
# Les joueurs sont saisis, les rôles sont attribués aléatoirement, chaque joueur révèle sa
# carte individuellement, puis le LLM orchestre les phases de nuit (Voyante → Loups-garous → Sorcière)
# et le jour. État persistant en MongoDB.
#
# Contraintes techniques
#
# * Langage : Python 3.11+.
# * UI : Streamlit (une seule app `app.py`).
# * DB : MongoDB (via `pymongo`).
# * LLM : Gemini (si `GOOGLE_API_KEY` présent), sinon fallback narrateur “mock”.
# * Gestion env : compatible `uv` (fournir `pyproject.toml`).
# * State management : stocker tout l’état serveur en Mongo (pas dans `st.session_state`
#   sauf cache éphémère d’ID de partie).
# * Sécurité minimale : aucune donnée sensible en clair dans l’UI, variables d’env pour
#   secrets/URIs, validation basique des inputs.
# * I18N : interface en français.
#
# Livrables attendus
#
# Crée la structure suivante et remplis tous les fichiers :
#
# lg_app/
#   app.py
#   services/
#     db.py
#     game_engine.py
#     llm_gm.py
#     roles.py
#     schemas.py
#     utils.py
#   assets/
#     cards.css
#   README.md
#   pyproject.toml
#   .env.example
#
# Détails de chaque composant
#
# 1) `pyproject.toml`
#
# * Dépendances :
#
#   * `streamlit`, `pymongo`, `pydantic`, `python-dotenv`, `openai` (facultatif à l’exécution si pas d’API key),
#     `tenacity` (pour retry LLM), `uuid6`.
# * Scripts (optionnels) :
#
#   * `start = "streamlit run app.py"`
#
# 2) `.env.example`
#
# * Variables attendues :
#
#   * `MONGODB_URI=mongodb://localhost:27017`
#   * `DB_NAME=lg_db`
#   * `GOOGLE_API_KEY=`
#   * `MODEL_NAME=gemini-1.5-pro` (ou équivalent)
# * Charger `.env` au démarrage si présent.
#
# 3) Schémas & rôles (`services/schemas.py`, `services/roles.py`)
#
# * `Game` :
#
#   * `code: str` (code salon unique, ex: 6 chars), `created_at: datetime`,
#   * `phase: str` ∈ {`lobby`,`night_seer`,`night_wolves`,`night_witch`,`day`,`ended`},
#   * `players: [PlayerRef]`, `history: [Event]`, `last_killed: Optional[str`
#   * `potions: {heal_used: bool, poison_used: bool}`
# * `Player` :
#
#   * `id: str`, `name: str`, `role: str` ∈ {`seer`,`witch`,`wolf`,`villager`},
#     `status: str` ∈ {`alive`,`dead`}
# * `Event` : `timestamp, type, payload`
# * `roles.py` :
#
#   * Génération aléatoire des rôles en fonction du nombre de joueurs (règles simples :
#     5-6 joueurs → 1 loup, 7-9 → 2 loups, ≥10 → 3 loups; 1 voyante, 1 sorcière si ≥6).
#
# 4) Accès DB (`services/db.py`)
#
# * Fonctions :
#
#   * `create_game(code)`, `get_game(code)`, `upsert_game(game)`, `add_player(code, name) → player_id`,
#   * `list_players(code)`, `set_role(code, player_id, role)`, `bulk_assign_roles(code, assignments)`,
#   * `set_status(code, player_id, status)`, `set_phase(code, phase)`,
#   * `set_last_killed(code, player_id)`, `clear_last_killed(code)`,
#   * `set_potion_used(code, kind)`, `log_event(code, event)`.
# * Index : `{code: 1}` unique.
#
# 5) Moteur de jeu (`services/game_engine.py`)
#
# * Logique pure (sans UI) pour enchaîner les phases :
#
#   * `assign_roles(game, players)`
# * Nuit :
#
#   * `seer_peek(game, target_player_id) → role`
#   * `wolves_vote(game, target_player_id) → killed_id`
#   * `witch_action(game, heal: bool, poison_target_id: Optional[str]) → killed_id_after_witch`
# * Jour :
#
#   * (MVP) pas de vote des villageois ; simplement narration + passage à la nuit suivante.
#
# * Règles :
#
#   * La Sorcière dispose de deux potions uniques : guérison (peut annuler `last_killed` de
#     cette nuit) et poison (tuer un joueur vivant).
#   * Un joueur `dead` ne peut plus être appelé dans les phases.
#
# * Fonctions utilitaires pour vérifier fin de partie :
#
#   * `is_game_over(game) → (bool, winner: str|None)` ; victoire Loups si #loups >= #village,
#     sinon Village si #loups == 0.
#
# 6) LLM maître de jeu (`services/llm_gm.py`)
#
# * `narrate(prompt_context: dict) → str`
#
#   * Construit un message système “Tu es le maître du jeu du Loup-Garou…” et un message utilisateur
#     avec l’état (phase, joueurs vivants/morts, événements récents).
#   * Si pas de `GOOGLE_API_KEY`, retourner une narration mock cohérente (texte fixe + interpolation).
# * Courts prompts pour :
#
#   * accueil/lobby, passage à la nuit, appel Voyante/Loups/Sorcière, annonce des morts, début du jour,
#     fin de partie.
# * Rate-limit/retry avec `tenacity`.
#
# 7) Utilitaires (`services/utils.py`)
#
# * Génération code partie (`ABC123`), validation entrées, formatage d’événements, calcul du nombre de loups.
# * Masquage des rôles dans l’UI sauf pour la carte révélée du joueur courant.
#
# 8) UI Streamlit (`app.py`)
#
# * Thème simple + CSS `assets/cards.css` pour cartes cliquables (une carte par joueur).
# * Écrans :
#
#   1. Accueil / Créer ou rejoindre une partie
#
#      * Input “Code partie” + bouton “Créer” (génère code) ou “Rejoindre”.
#      * Saisie des joueurs (ajout/suppression). Listing en temps réel (`st.autorefresh`
#        léger ou re-run bouton).
#   2. Attribution & Révélation des cartes
#
#      * Bouton “Attribuer les rôles” (utilise `assign_roles`).
#      * Grille de cartes : cliquer sur une carte ouvre un `st.modal` qui affiche le rôle du joueur
#        (visible uniquement sur ce poste).
#   3. Phase de Nuit (séquentielle)
#
#      * Narration LLM (ou mock) en haut.
#      * Voyante : selectbox des joueurs vivants → bouton “Révéler” → affiche rôle du ciblé uniquement
#        sur l’écran (ne pas persister cette info visible).
#      * Loups : radio/select + bouton “Valider le vote” → set `last_killed`.
#      * Sorcière :
#
#        * Si potion de soin dispo et `last_killed` défini → bouton “Sauver {nom}`”.
#        * Potion de poison : select joueur vivant (≠ `last_killed` si déjà sauvé) → bouton “Empoisonner”.
#      * À la fin de la nuit : appliquer morts (`status=dead`) et `clear_last_killed`.
#   4. Jour
#
#      * Afficher morts de la nuit, narration LLM.
#      * (MVP) Bouton “Passer à la nuit suivante”.
#   5. Fin de partie
#
#      * Afficher vainqueur (Loups/Village), récap des événements.
#
# * Boutons d’admin rapides (dans un `st.sidebar`) : réinitialiser partie, forcer phase, supprimer joueur (debug).
#
# 9) CSS (`assets/cards.css`)
#
# * Style cartes : recto (dos générique), verso (role), survol/click, layout responsive.
#
# 10) README.md (instructions)
#
# * Installation (uv) :
#
#   uv init
#   uv add streamlit pymongo pydantic python-dotenv openai tenacity uuid6
#   uv run streamlit run app.py
#
#   ou, avec `pyproject.toml` fourni :
#
#   uv sync
#   uv run streamlit run app.py
#
# * MongoDB : lancer localement (`mongodb://localhost:27017`) ou via Docker, préciser la variable `MONGODB_URI`.
# * ENV : copier `.env.example` en `.env`.
# * Scénario de test : 6–8 joueurs, vérifier enchaînement Voyante → Loups → Sorcière, états “dead”, fin de partie.
# * Sans GOOGLE_API_KEY : narration mock activée automatiquement.
#
# Critères d’acceptation
#
# * Création/rejoindre partie par code, ajout de joueurs, attribution aléatoire reproductible (seed optionnelle).
# * Révélation individuelle des cartes par clic.
# * Phases Nuit/ Jour pilotées par UI + narration LLM/mock.
# * Voyante peut sonder 1 joueur/nuit (rôle révélé à l’écran, non persistant).
# * Loups votent et tuent 1 joueur/nuit (flag `last_killed` puis `dead`).
# * Sorcière : 1 soin total, 1 poison total sur toute la partie.
# * Les joueurs `dead` ne sont plus sélectionnables ni appelés par le LLM.
# * Persistance intégrale en MongoDB ; rechargement de la page ne casse pas la partie.
# * Fin de partie détectée correctement et affichée.
# * Code propre, typé, modulaires services, commentaires là où nécessaire.
