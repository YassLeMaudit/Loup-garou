from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional

ROLE_SEER = "seer"
ROLE_WITCH = "witch"
ROLE_WOLF = "wolf"
ROLE_VILLAGER = "villager"


def _wolf_count(player_count: int) -> int:
    if player_count <= 6:
        return 1
    if player_count <= 9:
        return 2
    return 3


def role_distribution(player_count: int) -> Dict[str, int]:
    if player_count < 5:
        raise ValueError("Au moins 5 joueurs sont requis pour lancer une partie.")

    distribution: Dict[str, int] = {
        ROLE_SEER: 1,
        ROLE_WITCH: 0,
        ROLE_WOLF: _wolf_count(player_count),
    }

    if player_count >= 6:
        distribution[ROLE_WITCH] = 1

    villagers = player_count - sum(distribution.values())
    if villagers < 0:
        raise ValueError("Le nombre de joueurs est insuffisant pour la distribution demandée.")

    distribution[ROLE_VILLAGER] = villagers
    return distribution


def assign_roles(player_ids: Iterable[str], seed: Optional[int] = None) -> Dict[str, str]:
    ids: List[str] = list(player_ids)
    count = len(ids)
    distribution = role_distribution(count)

    bag: List[str] = []
    for role, amount in distribution.items():
        bag.extend([role] * amount)

    rng = random.Random(seed)
    rng.shuffle(ids)
    rng.shuffle(bag)

    assignments = {player_id: bag[index] for index, player_id in enumerate(ids)}
    return assignments
