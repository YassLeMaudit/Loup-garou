from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

from services import db, llm_gm, langchain_agent
from services.schemas import Game

load_dotenv()

st.set_page_config(
    page_title="Loup-Garou – Chatbot Maître du Jeu",
    page_icon="🧙",
    layout="wide",
)

CSS_PATH = Path(__file__).parent / "assets" / "cards.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

SESSION_DEFAULTS = {
    "game_code": None,
    "chat_messages": [],
}

for key, value in SESSION_DEFAULTS.items():
    st.session_state.setdefault(key, value)


def _load_game(game_code: Optional[str]) -> Optional[Game]:
    if not game_code:
        return None
    return db.get_game(game_code)


def _sync_chat_from_game(game: Game) -> List[Dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in game.chat_history]


def _reset_game(game: Game) -> None:
    db.upsert_game(Game(code=game.code))
    db.overwrite_chat_history(game.code, [])
    st.session_state["chat_messages"] = []


def _render_sidebar(game: Optional[Game]) -> None:
    st.sidebar.header("Administration")
    if game:
        st.sidebar.success(f"Code partie : {game.code}")
        st.sidebar.markdown(f"**Phase :** {game.phase}")
        alive = [player.name for player in game.players if player.status == "alive"]
        dead = [player.name for player in game.players if player.status == "dead"]
        st.sidebar.markdown("**Vivants :** " + (", ".join(alive) if alive else "aucun"))
        st.sidebar.markdown("**Morts :** " + (", ".join(dead) if dead else "aucun"))
        st.sidebar.markdown(
            f"**Potions** – soin utilisé : {game.potions.heal_used}, poison utilisé : {game.potions.poison_used}"
        )
        if st.sidebar.button("Réinitialiser la partie"):
            _reset_game(game)
            st.rerun()
        if st.sidebar.button("Quitter la partie"):
            st.session_state["game_code"] = None
            st.session_state["chat_messages"] = []
            st.rerun()
    else:
        st.sidebar.info("Aucune partie active. Utilise le chatbot pour créer ou rejoindre un salon.")


def _render_history_tab(game: Optional[Game]) -> None:
    if not game or not game.history:
        st.write("Aucun événement pour le moment.")
        return
    st.write("Historique des actions :")
    for event in game.history:
        st.markdown(f"- {event.timestamp.strftime('%H:%M:%S')} · {event.type} · {event.payload}")


def _render_status_panel(game: Optional[Game]) -> None:
    st.markdown("### État actuel")
    if not game:
        st.info("Pas de partie en cours. Demande au maître du jeu de créer ou rejoindre un salon.")
        return
    context = llm_gm.context_from_game(game)
    st.json(context)


def _chat_interface(game: Optional[Game]) -> None:
    chat_messages: List[Dict[str, str]] = st.session_state.get("chat_messages", [])
    if game:
        # Synchroniser avec l'historique persistant si nécessaire
        persisted = _sync_chat_from_game(game)
        if len(persisted) > len(chat_messages):
            chat_messages = persisted
            st.session_state["chat_messages"] = chat_messages

    for message in chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Parle au maître du jeu…")
    if not prompt:
        return

    response = langchain_agent.process_message(
        st.session_state.get("game_code"),
        chat_messages,
        prompt.strip(),
    )
    st.session_state["game_code"] = response.game_code
    st.session_state["chat_messages"] = response.chat_history
    if response.game_code:
        st.session_state["game_snapshot"] = response.game_snapshot

    st.rerun()


def main() -> None:
    st.title("Loup-Garou – Maître du Jeu Conversational")
    current_game = _load_game(st.session_state.get("game_code"))
    _render_sidebar(current_game)

    tabs = st.tabs(["Chat", "Historique", "État"])
    with tabs[0]:
        _chat_interface(current_game)
    with tabs[1]:
        _render_history_tab(current_game)
    with tabs[2]:
        _render_status_panel(current_game)


if __name__ == "__main__":
    main()
