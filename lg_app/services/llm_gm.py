from __future__ import annotations

import os
from typing import Dict, List, Optional

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from . import utils, game_engine
from .schemas import Game

SYSTEM_PROMPT = (
    "Tu es le maître du jeu du Loup-Garou. Narre les événements avec suspense, "
    "reste concis et clair. Donne des instructions aux joueurs pour la phase en cours "
    "sans révéler d'informations secrètes sauf si la phase l'exige."
)

DEFAULT_MODEL = os.getenv("MODEL_NAME", "gemini-1.5-pro")
_GEMINI_CONFIGURED = False


def _has_gemini_key() -> bool:
    global _GEMINI_CONFIGURED
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return False
    if not _GEMINI_CONFIGURED:
        genai.configure(api_key=api_key)
        _GEMINI_CONFIGURED = True
    return True


def _render_players(players: List[Dict]) -> str:
    fragments = []
    for player in players:
        status = player.get("status", "alive")
        role = player.get("role") if player.get("role") not in {None, "hidden"} else "?"
        fragments.append(f"{player.get('name')} ({status}, rôle: {role})")
    return ", ".join(fragments) if fragments else "Aucun joueur"


def _mock_narration(context: Dict) -> str:
    phase = context.get("phase", "inconnue")
    players = context.get("players", [])
    last_event = context.get("last_event", "Pas de nouvel événement.")
    return (
        f"[Narration mock] Phase actuelle: {phase}. Joueurs: {_render_players(players)}. "
        f"Dernier événement: {last_event}"
    )


def _build_user_message(context: Dict) -> str:
    phase = context.get("phase")
    last_events = context.get("recent_events", [])
    alive_players = [
        f"{player['name']} ({player.get('role', '?')})"
        for player in context.get("players", [])
        if player.get("status") == "alive"
    ]
    dead_players = [
        player["name"]
        for player in context.get("players", [])
        if player.get("status") == "dead"
    ]

    lines = [
        f"Phase en cours: {phase}",
        f"Joueurs vivants: {', '.join(alive_players) if alive_players else 'aucun'}",
        f"Joueurs éliminés: {', '.join(dead_players) if dead_players else 'aucun'}",
    ]

    if last_events:
        rendered_events = "\n".join(f"- {event}" for event in last_events[-3:])
        lines.append("Événements récents:")
        lines.append(rendered_events)
    else:
        lines.append("Aucun événement récent.")

    if phase == "night_seer":
        lines.append("Action attendue: inviter la Voyante à sonder un joueur.")
    elif phase == "night_wolves":
        lines.append("Action attendue: inviter les Loups-garous à choisir une cible.")
    elif phase == "night_witch":
        lines.append("Action attendue: rappeler à la Sorcière ses potions disponibles.")
    elif phase == "day":
        lines.append("Action attendue: annoncer les événements de la nuit et lancer les discussions.")
    elif phase == "ended":
        winner = context.get("winner", "inconnu")
        lines.append(f"Fin de partie: annoncer la victoire de {winner}.")
    else:
        lines.append("Action attendue: accueillir les joueurs et préparer la suite.")

    return "\n".join(lines)


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
)
def _call_gemini(prompt: str) -> str:
    model = genai.GenerativeModel(
        model_name=DEFAULT_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 300,
        },
    )
    if not response or not response.text:
        raise RuntimeError("Réponse vide du modèle.")
    return response.text.strip()


def narrate(prompt_context: Dict) -> str:
    if not _has_gemini_key():
        return _mock_narration(prompt_context)

    try:
        user_prompt = _build_user_message(prompt_context)
        return _call_gemini(user_prompt)
    except Exception:
        return _mock_narration(prompt_context)


def context_from_game(game: Optional[Game]) -> Dict:
    if not game:
        return {
            "phase": "inactive",
            "players": [],
            "recent_events": [],
            "last_event": "Aucune partie active.",
        }

    players_payload = []
    for player in game.players:
        players_payload.append(
            {
                "id": player.id,
                "name": player.name,
                "status": player.status,
                "role": player.role if player.status == "dead" or game.phase == "ended" else "hidden",
            }
        )

    recent_events = [utils.format_event(event) for event in game.history[-5:]] if game.history else []  # type: ignore[name-defined]
    last_event = recent_events[-1] if recent_events else "Pas de nouvel événement."
    over, winner = game_engine.is_game_over(game)  # type: ignore[name-defined]

    context = {
        "phase": game.phase,
        "players": players_payload,
        "recent_events": recent_events,
        "last_event": last_event,
        "potions": {
            "heal_used": game.potions.heal_used,
            "poison_used": game.potions.poison_used,
        },
    }
    if over:
        context["winner"] = winner
    return context
