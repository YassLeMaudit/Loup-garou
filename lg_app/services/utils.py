from __future__ import annotations

import random
import string
from typing import Dict, Iterable, List, Optional

from .schemas import Event, Player

GAME_CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_game_code(length: int = 6) -> str:
    rng = random.SystemRandom()
    return "".join(rng.choice(GAME_CODE_ALPHABET) for _ in range(length))


def validate_game_code(code: str) -> bool:
    return len(code) == 6 and all(char in GAME_CODE_ALPHABET for char in code.upper())


def alive_players(players: Iterable[Player]) -> List[Player]:
    return [player for player in players if player.status == "alive"]


def count_role(players: Iterable[Player], role: str) -> int:
    return sum(1 for player in players if player.role == role)


def count_wolves(players: Iterable[Player]) -> int:
    return count_role(players, "wolf")


def find_player_by_name(players: Iterable[Player], name: str) -> Optional[Player]:
    target = name.strip().lower()
    for player in players:
        if player.name.strip().lower() == target:
            return player
    return None


def to_public_player(player: Player, reveal_role: bool = False) -> Dict[str, str]:
    data = {
        "id": player.id,
        "name": player.name,
        "status": player.status,
    }
    if reveal_role:
        data["role"] = player.role
    else:
        data["role"] = "hidden"
    return data


def build_event(event_type: str, payload: Dict[str, str]) -> Event:
    return Event(type=event_type, payload=payload)


def format_event(event: Event) -> str:
    base = event.type.replace("_", " ").capitalize()
    details = ", ".join(f"{key}: {value}" for key, value in event.payload.items())
    return f"{base} ({details})" if details else base
