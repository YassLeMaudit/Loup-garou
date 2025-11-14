from __future__ import annotations

from typing import Dict, Optional, Tuple

from .roles import assign_roles as roles_assign, ROLE_SEER, ROLE_WITCH, ROLE_WOLF
from .schemas import Game, Player
from .utils import alive_players, count_wolves


class GameStateError(Exception):
    """Raised when a game action is invalid in the current state."""


def assign_roles(game: Game, seed: Optional[int] = None) -> Dict[str, str]:
    if game.phase != "lobby":
        raise GameStateError("Les rôles ne peuvent être attribués qu'en phase de lobby.")
    player_ids = [player.id for player in game.players]
    assignments = roles_assign(player_ids, seed=seed)
    for player in game.players:
        player.role = assignments[player.id]
        player.status = "alive"
    game.phase = "night_seer"
    return assignments


def _get_player(game: Game, player_id: str) -> Player:
    for player in game.players:
        if player.id == player_id:
            return player
    raise GameStateError("Joueur introuvable.")


def _ensure_alive(player: Player) -> None:
    if player.status != "alive":
        raise GameStateError("Cette action nécessite un joueur vivant.")


def seer_peek(game: Game, target_player_id: str) -> str:
    if game.phase != "night_seer":
        raise GameStateError("Ce n'est pas le tour de la voyante.")
    target = _get_player(game, target_player_id)
    _ensure_alive(target)
    game.phase = "night_wolves"
    return target.role


def wolves_vote(game: Game, target_player_id: str) -> str:
    if game.phase != "night_wolves":
        raise GameStateError("Ce n'est pas le tour des loups-garous.")
    target = _get_player(game, target_player_id)
    _ensure_alive(target)
    game.last_killed = target.id
    game.phase = "night_witch"
    return target.id


def witch_action(
    game: Game,
    heal: bool,
    poison_target_id: Optional[str] = None,
) -> Optional[str]:
    if game.phase != "night_witch":
        raise GameStateError("Ce n'est pas le tour de la sorcière.")

    killed_id = game.last_killed

    if heal:
        if game.potions.heal_used:
            raise GameStateError("La potion de soin a déjà été utilisée.")
        if not game.last_killed:
            raise GameStateError("Aucun joueur à sauver.")
        game.last_killed = None
        game.potions.heal_used = True
        killed_id = None

    if poison_target_id:
        if game.potions.poison_used:
            raise GameStateError("La potion de poison a déjà été utilisée.")
        target = _get_player(game, poison_target_id)
        _ensure_alive(target)
        if poison_target_id == killed_id:
            raise GameStateError("Impossible d'empoisonner un joueur déjà ciblé.")
        target.status = "dead"
        killed_id = poison_target_id
        game.potions.poison_used = True

    if killed_id:
        victim = _get_player(game, killed_id)
        victim.status = "dead"

    if game.last_killed:
        victim = _get_player(game, game.last_killed)
        victim.status = "dead"
    game.last_killed = None
    game.phase = "day"
    return killed_id


def start_next_night(game: Game) -> None:
    if game.phase != "day":
        raise GameStateError("La nuit ne peut démarrer qu'après la phase de jour.")
    game.phase = "night_seer"


def is_game_over(game: Game) -> Tuple[bool, Optional[str]]:
    alive = alive_players(game.players)
    wolves = [player for player in alive if player.role == ROLE_WOLF]
    villagers = [player for player in alive if player.role != ROLE_WOLF]

    if not wolves:
        return True, "village"

    if len(wolves) >= len(villagers):
        return True, "wolves"

    return False, None


def living_roles_summary(game: Game) -> Dict[str, int]:
    summary = {"wolves": count_wolves(alive_players(game.players))}
    summary["villagers"] = len(alive_players(game.players)) - summary["wolves"]
    return summary
