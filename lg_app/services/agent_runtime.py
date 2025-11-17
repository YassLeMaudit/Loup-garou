from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import db, game_engine, llm_gm, utils
from .game_engine import GameStateError
from .schemas import ChatMessage, Game


class AgentToolError(Exception):
    """Erreur fonctionnelle levée lorsqu'un outil ne peut pas être exécuté."""


@dataclass
class AgentContext:
    user_message: str
    chat_history: List[Dict[str, str]]
    game_code: Optional[str] = None
    game: Optional[Game] = None
    executed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def reload_game(self) -> None:
        if self.game_code:
            self.game = db.get_game(self.game_code)
        else:
            self.game = None


CURRENT_CONTEXT: ContextVar[AgentContext] = ContextVar("lg_agent_context")


def set_current_context(context: AgentContext) -> Token:
    context.reload_game()
    return CURRENT_CONTEXT.set(context)


def reset_current_context(token: Token) -> None:
    CURRENT_CONTEXT.reset(token)


def get_current_context() -> AgentContext:
    try:
        return CURRENT_CONTEXT.get()
    except LookupError as exc:
        raise RuntimeError("Aucun contexte d'agent n'est défini.") from exc


def _ensure_game(context: AgentContext) -> Game:
    if not context.game_code or not context.game:
        raise AgentToolError("Aucune partie active. Crée ou rejoins un salon d'abord.")
    return context.game


def _finalize_state(context: AgentContext, game: Game) -> Game:
    over, winner = game_engine.is_game_over(game)
    if over and game.phase != "ended":
        game.phase = "ended"
        db.log_event(game.code, utils.build_event("game_over", {"winner": winner or "inconnu"}))
    db.upsert_game(game)
    context.game_code = game.code
    context.reload_game()
    return context.game  # type: ignore[return-value]


def tool_create_game(code: Optional[str] = None) -> str:
    context = get_current_context()
    if code:
        candidate = code.strip().upper()
        if not utils.validate_game_code(candidate):
            raise AgentToolError("Le code fourni est invalide. Utilise 6 caractères alphanumériques.")
        generated_code = candidate
    else:
        generated_code = utils.generate_game_code()
    game = db.create_game(generated_code)
    db.log_event(generated_code, utils.build_event("game_created", {"code": generated_code}))
    context.game_code = generated_code
    context.game = game
    context.executed.append(f"Partie créée avec le code {generated_code}.")
    return context.executed[-1]


def tool_join_game(code: str) -> str:
    context = get_current_context()
    normalized = code.strip().upper()
    if not utils.validate_game_code(normalized):
        raise AgentToolError("Le code salon fourni est invalide.")
    game = db.get_game(normalized)
    if not game:
        raise AgentToolError("Aucune partie trouvée avec ce code.")
    context.game_code = normalized
    context.game = game
    message = f"Salon {normalized} rejoint."
    context.executed.append(message)
    return message


def tool_add_player(name: str) -> str:
    context = get_current_context()
    game = _ensure_game(context)
    player_name = name.strip()
    if not player_name:
        raise AgentToolError("Indique un nom de joueur.")
    if utils.find_player_by_name(game.players, player_name):
        raise AgentToolError(f"{player_name} est déjà inscrit.")
    db.add_player(game.code, player_name)
    db.log_event(game.code, utils.build_event("player_added", {"name": player_name}))
    context.reload_game()
    message = f"{player_name} rejoint la partie."
    context.executed.append(message)
    return message


def tool_remove_player(name: str) -> str:
    context = get_current_context()
    game = _ensure_game(context)
    target_name = name.strip()
    if not target_name:
        raise AgentToolError("Quel joueur veux-tu retirer ?")
    player = utils.find_player_by_name(game.players, target_name)
    if not player:
        raise AgentToolError(f"{target_name} n'est pas inscrit.")
    db.remove_player(game.code, player.id)
    db.log_event(game.code, utils.build_event("player_removed", {"name": player.name}))
    context.reload_game()
    message = f"{player.name} a été retiré du salon."
    context.executed.append(message)
    return message


def tool_list_players() -> str:
    context = get_current_context()
    game = _ensure_game(context)
    if not game.players:
        return "Aucun joueur inscrit pour le moment."
    lines = []
    for player in game.players:
        status = "vivant" if player.status == "alive" else "mort"
        role = player.role if game.phase == "ended" or player.status == "dead" else "?"
        lines.append(f"- {player.name} ({status}, rôle: {role})")
    message = "Joueurs inscrits :\n" + "\n".join(lines)
    context.executed.append("Consultation de la liste des joueurs.")
    return message


def tool_assign_roles(seed: Optional[int] = None) -> str:
    context = get_current_context()
    game = _ensure_game(context)
    if len(game.players) < 5:
        raise AgentToolError("Au moins 5 joueurs sont requis pour distribuer les rôles.")
    try:
        assignments = game_engine.assign_roles(game, seed=seed)
    except GameStateError as exc:
        raise AgentToolError(str(exc)) from exc
    db.log_event(
        game.code,
        utils.build_event("roles_assigned", {"players": str(len(assignments))}),
    )
    _finalize_state(context, game)
    message = "Les rôles sont distribués. La nuit commence."
    context.executed.append(message)
    return message


def tool_seer_peek(target_name: str) -> str:
    context = get_current_context()
    game = _ensure_game(context)
    
    # Vérification : on doit être en phase voyante
    if game.phase != "night_seer":
        if game.phase == "lobby":
            raise AgentToolError("Les rôles doivent d'abord être distribués. Utilise 'distribue les rôles'.")
        elif game.phase == "day":
            raise AgentToolError("C'est le jour. La Voyante ne peut agir que la nuit. Lance d'abord une nouvelle nuit.")
        else:
            raise AgentToolError(f"Ce n'est pas le tour de la Voyante. Phase actuelle : {game.phase}. Utilise 'run_night_sequence' pour voir qui doit jouer.")
    
    target = utils.find_player_by_name(game.players, target_name)
    if not target:
        raise AgentToolError(f"{target_name} n'est pas un joueur valide.")
    try:
        role = game_engine.seer_peek(game, target.id)
    except GameStateError as exc:
        raise AgentToolError(str(exc)) from exc
    db.log_event(game.code, utils.build_event("seer_peek", {"target": target.name, "role": role}))
    _finalize_state(context, game)
    message = f"La Voyante découvre que {target.name} est {role}."
    context.executed.append(message)
    return message


def tool_wolves_vote(target_name: str) -> str:
    context = get_current_context()
    game = _ensure_game(context)
    
    # Vérification : on doit être en phase loups
    if game.phase == "night_seer":
        seer = next((p for p in game.players if p.role == "seer" and p.status == "alive"), None)
        if seer:
            raise AgentToolError("La Voyante doit d'abord jouer son tour. Demande à la Voyante de sonder un joueur.")
        else:
            # Si la voyante est morte, on peut forcer le passage à la phase loups
            game.phase = "night_wolves"
            db.set_phase(game.code, "night_wolves")
            context.reload_game()
            game = context.game  # type: ignore[assignment]
    elif game.phase != "night_wolves":
        raise AgentToolError(f"Ce n'est pas le tour des Loups. Phase actuelle : {game.phase}. Utilise 'run_night_sequence' pour voir qui doit jouer.")
    
    target = utils.find_player_by_name(game.players, target_name)
    if not target:
        raise AgentToolError(f"{target_name} est introuvable.")
    if target.status != "alive":
        raise AgentToolError(f"{target.name} est déjà éliminé.")
    try:
        game_engine.wolves_vote(game, target.id)
    except GameStateError as exc:
        raise AgentToolError(str(exc)) from exc
    db.log_event(game.code, utils.build_event("wolves_vote", {"target": target.name}))
    _finalize_state(context, game)
    message = f"Les Loups ciblent {target.name}."
    context.executed.append(message)
    return message


def tool_witch_action(heal: bool = False, poison_target: Optional[str] = None) -> str:
    context = get_current_context()
    game = _ensure_game(context)
    
    # Vérification : on doit être en phase sorcière
    if game.phase == "night_seer":
        raise AgentToolError("La Voyante doit d'abord jouer. Utilise 'run_night_sequence' pour orchestrer la nuit dans l'ordre.")
    elif game.phase == "night_wolves":
        wolves = [p for p in game.players if p.role == "wolf" and p.status == "alive"]
        if wolves:
            raise AgentToolError("Les Loups doivent d'abord attaquer. Demande aux Loups de choisir leur victime.")
        else:
            # Si tous les loups sont morts, on peut forcer le passage à la phase sorcière
            game.phase = "night_witch"
            db.set_phase(game.code, "night_witch")
            context.reload_game()
            game = context.game  # type: ignore[assignment]
    elif game.phase != "night_witch":
        raise AgentToolError(f"Ce n'est pas le tour de la Sorcière. Phase actuelle : {game.phase}. Utilise 'run_night_sequence' pour voir qui doit jouer.")
    poison_id = None
    poisoned_name = None
    if poison_target:
        target = utils.find_player_by_name(game.players, poison_target)
        if not target:
            raise AgentToolError(f"{poison_target} n'est pas un joueur valide.")
        poison_id = target.id
        poisoned_name = target.name
    saved_name = None
    if heal and game.last_killed:
        victim = next((player for player in game.players if player.id == game.last_killed), None)
        if victim:
            saved_name = victim.name
    try:
        killed_id = game_engine.witch_action(game, heal=heal, poison_target_id=poison_id)
    except GameStateError as exc:
        raise AgentToolError(str(exc)) from exc
    if heal:
        db.log_event(game.code, utils.build_event("witch_heal", {"saved": saved_name or "aucun"}))
    if poisoned_name:
        db.log_event(game.code, utils.build_event("witch_poison", {"target": poisoned_name}))
    if killed_id:
        victim = next((player for player in game.players if player.id == killed_id), None)
        if victim:
            db.log_event(game.code, utils.build_event("player_killed", {"name": victim.name}))
    _finalize_state(context, game)
    message = "Action de la Sorcière appliquée."
    context.executed.append(message)
    return message


def tool_advance_to_day() -> str:
    context = get_current_context()
    game = _ensure_game(context)
    if game.phase != "night_witch":
        raise AgentToolError("La fin de nuit ne peut être annoncée qu'après le tour de la Sorcière.")
    try:
        killed_id = game_engine.witch_action(game, heal=False, poison_target_id=None)
    except GameStateError as exc:
        raise AgentToolError(str(exc)) from exc
    if killed_id:
        victim = next((player for player in game.players if player.id == killed_id), None)
        if victim:
            db.log_event(game.code, utils.build_event("player_killed", {"name": victim.name}))
    db.log_event(game.code, utils.build_event("night_finished", {}))
    _finalize_state(context, game)
    message = "Le village se réveille."
    context.executed.append(message)
    return message


def tool_run_night_sequence() -> str:
    """Orchestre automatiquement toute la séquence de nuit avec narration."""
    context = get_current_context()
    game = _ensure_game(context)
    
    if game.phase not in ["night_seer", "night_wolves", "night_witch"]:
        raise AgentToolError("La séquence de nuit ne peut démarrer que pendant une phase de nuit.")
    
    messages = []
    
    # Phase Voyante (si pas déjà passée)
    if game.phase == "night_seer":
        seer = next((p for p in game.players if p.role == "seer" and p.status == "alive"), None)
        if seer:
            messages.append(f"🔮 La nuit commence. La Voyante ({seer.name}) se réveille.")
            messages.append(f"Voyante, qui veux-tu sonder ? (Utilise : 'la voyante regarde [nom]')")
        else:
            messages.append("🔮 La Voyante n'est plus parmi nous...")
            # Passer automatiquement à la phase suivante si la voyante est morte
            game.phase = "night_wolves"
            db.set_phase(game.code, "night_wolves")
            context.reload_game()
            game = context.game  # type: ignore[assignment]
    
    # Phase Loups (si on est à cette phase ou si on vient de passer)
    if game.phase == "night_wolves":
        wolves = [p for p in game.players if p.role == "wolf" and p.status == "alive"]
        if wolves:
            wolf_names = ", ".join(p.name for p in wolves)
            messages.append(f"🐺 Les Loups-garous ({wolf_names}) se réveillent.")
            messages.append(f"Loups, qui voulez-vous dévorer ? (Utilise : 'les loups attaquent [nom]')")
        else:
            messages.append("🐺 Les Loups-garous ont tous été éliminés...")
            # Passer automatiquement à la phase suivante si tous les loups sont morts
            game.phase = "night_witch"
            db.set_phase(game.code, "night_witch")
            context.reload_game()
            game = context.game  # type: ignore[assignment]
    
    # Phase Sorcière (si on est à cette phase ou si on vient de passer)
    if game.phase == "night_witch":
        witch = next((p for p in game.players if p.role == "witch" and p.status == "alive"), None)
        if witch:
            messages.append(f"🧪 La Sorcière ({witch.name}) se réveille.")
            potion_info = []
            if not game.potions.heal_used and game.last_killed:
                victim = next((p for p in game.players if p.id == game.last_killed), None)
                if victim:
                    potion_info.append(f"Les loups ont attaqué {victim.name}. Tu peux le/la sauver avec ta potion de soin.")
            if not game.potions.poison_used:
                potion_info.append("Tu disposes encore de ta potion de poison.")
            if potion_info:
                messages.append("Sorcière : " + " ".join(potion_info))
                messages.append("(Utilise : 'la sorcière sauve [nom]' ou 'la sorcière empoisonne [nom]' ou passe ton tour)")
        else:
            messages.append("🧪 La Sorcière n'est plus parmi nous...")
            # Si la sorcière est morte, on peut avancer directement au jour
            messages.append("Toutes les phases de nuit sont terminées. Utilise 'réveille le village' pour passer au jour.")
    
    return "\n".join(messages)


def tool_start_next_night() -> str:
    context = get_current_context()
    game = _ensure_game(context)
    try:
        game_engine.start_next_night(game)
    except GameStateError as exc:
        raise AgentToolError(str(exc)) from exc
    db.log_event(game.code, utils.build_event("night_started", {}))
    _finalize_state(context, game)
    message = "Une nouvelle nuit tombe sur le village."
    context.executed.append(message)
    return message


def tool_game_status() -> str:
    context = get_current_context()
    game = _ensure_game(context)
    context.reload_game()
    game = context.game  # type: ignore[assignment]
    alive = [player.name for player in game.players if player.status == "alive"]
    dead = [player.name for player in game.players if player.status == "dead"]
    status = (
        f"Phase actuelle : {game.phase}.\n"
        f"Vivants : {', '.join(alive) if alive else 'aucun'}.\n"
        f"Morts : {', '.join(dead) if dead else 'aucun'}.\n"
        f"Potions - soin utilisé : {game.potions.heal_used}, poison utilisé : {game.potions.poison_used}."
    )
    context.executed.append("Statut de la partie consulté.")
    return status


TOOL_FUNCTIONS = {
    "create_game": tool_create_game,
    "join_game": tool_join_game,
    "add_player": tool_add_player,
    "remove_player": tool_remove_player,
    "list_players": tool_list_players,
    "assign_roles": tool_assign_roles,
    "seer_peek": tool_seer_peek,
    "wolves_vote": tool_wolves_vote,
    "witch_action": tool_witch_action,
    "run_night_sequence": tool_run_night_sequence,
    "advance_to_day": tool_advance_to_day,
    "start_next_night": tool_start_next_night,
    "game_status": tool_game_status,
}


@dataclass
class AgentResponse:
    reply: str
    game_code: Optional[str]
    chat_history: List[Dict[str, str]]
    errors: List[str]
    executed_actions: List[str]
    game_snapshot: Optional[Game]


def persist_interaction(context: AgentContext, assistant_reply: str) -> AgentResponse:
    updated_history: List[Dict[str, str]]
    snapshot: Optional[Game] = None

    if context.game_code:
        db.append_chat_message(
            context.game_code,
            ChatMessage(role="user", content=context.user_message),
        )
        db.append_chat_message(
            context.game_code,
            ChatMessage(role="assistant", content=assistant_reply),
        )
        snapshot = db.get_game(context.game_code)
        persisted = snapshot.chat_history if snapshot else []
        updated_history = [
            {"role": message.role, "content": message.content} for message in persisted
        ]
    else:
        updated_history = context.chat_history.copy()

        updated_history.append({"role": "user", "content": context.user_message})
        updated_history.append({"role": "assistant", "content": assistant_reply})

    return AgentResponse(
        reply=assistant_reply,
        game_code=context.game_code,
        chat_history=updated_history,
        errors=context.errors,
        executed_actions=context.executed,
        game_snapshot=snapshot,
    )
