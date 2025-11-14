# Loup-Garou – Maître du jeu LLM

Application Streamlit en français où un agent Gemini agit comme maître du jeu conversationnel pour orchestrer une partie de Loup-Garou. Toute l'état est persistant dans MongoDB pour survivre aux rafraîchissements de page.

## Prérequis

- Python 3.11 ou supérieur
- MongoDB accessible (local ou distant)
- `uv` recommandé pour la gestion d'environnement
- (Optionnel) Clé API Gemini (`GOOGLE_API_KEY`)
- LangChain installé localement (géré via `uv sync`)

## Installation

```bash
cd lg_app
uv sync
uv run streamlit run app.py
```

Sans `pyproject.toml` synchronisé, vous pouvez initialiser manuellement :

```bash
uv init
uv add streamlit pymongo pydantic python-dotenv google-generativeai tenacity uuid6
uv run streamlit run app.py
```

## Configuration

1. Copiez le fichier `.env.example` en `.env`.
2. Renseignez l'URI MongoDB (`MONGODB_URI`) ainsi que le nom de base (`DB_NAME`).
3. Fournissez `GOOGLE_API_KEY` et `MODEL_NAME` si vous souhaitez activer la narration via Gemini. Sans clé, un narrateur mock prendra le relais.

## Démarrage

```bash
uv run streamlit run app.py
```

L'application propose :

- Création ou rejoint de salon directement via le chatbot (commands en langage naturel).
- Gestion des joueurs et déroulé complet des phases Nuit (Voyante → Loups → Sorcière) puis Jour, entièrement pilotés par un agent LangChain + Gemini.
- Historique dédié des événements et résumé d'état mis à jour en temps réel.
- Gestion des potions de la Sorcière, morts, et détection automatique de la fin de partie.
- Outils d'administration (réinitialisation, forçage de phase, suppression de joueur).

## Notes de test

- Scénario recommandé : 6 à 8 joueurs pour couvrir l'ensemble des rôles spéciaux.
- Vérifiez l'enchaînement complet de nuit : Voyante → Loups → Sorcière → Jour.
- Confirmez que les morts sont bien retirés des sélections et que la victoire est détectée (village si plus de loups, loups si parité).
- Sans clé Gemini, le narrateur mock affiche des textes fixes mais cohérents avec l'état, mais l'agent LangChain ne pourra pas interpréter automatiquement les commandes.

## Utilisation du chatbot

- Demande « crée une partie » pour obtenir un code salon unique.
- Inscris les joueurs avec des phrases naturelles : « ajoute Alice et Bob ».
- Pendant la nuit, formule les actions : « la voyante regarde Paul », « les loups attaquent Jeanne », « la sorcière sauve Paul ».
- Pour passer les phases : « réveille le village », « lance une nouvelle nuit », « montre l'état de la partie ».
