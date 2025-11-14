from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
from uuid6 import uuid7

from .schemas import Event, Game, Player, ChatMessage


def _get_mongo_uri() -> str:
    return os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def _get_db_name() -> str:
    return os.getenv("DB_NAME", "lg_db")


@lru_cache
def get_client() -> MongoClient:
    return MongoClient(_get_mongo_uri())


def get_collection() -> Collection:
    db = get_client()[_get_db_name()]
    collection = db["games"]
    collection.create_index("code", unique=True)
    return collection


def _serialize_game(game: Game) -> Dict:
    return game.model_dump(mode="python")


def _deserialize_game(document: Dict) -> Game:
    data = dict(document)
    data.pop("_id", None)
    return Game.model_validate(data)


def create_game(code: str) -> Game:
    collection = get_collection()
    game = Game(code=code)
    try:
        collection.insert_one(_serialize_game(game))
    except DuplicateKeyError as exc:
        raise ValueError("Un salon avec ce code existe deja.") from exc
    return game


def get_game(code: str) -> Optional[Game]:
    collection = get_collection()
    document = collection.find_one({"code": code})
    if not document:
        return None
    return _deserialize_game(document)


def upsert_game(game: Game) -> Game:
    collection = get_collection()
    collection.update_one(
        {"code": game.code},
        {"$set": _serialize_game(game)},
        upsert=True,
    )
    return game


def add_player(code: str, name: str) -> str:
    player = Player(id=str(uuid7()), name=name)
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$push": {"players": player.model_dump(mode="python")}},
    )
    return player.id


def remove_player(code: str, player_id: str) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$pull": {"players": {"id": player_id}}},
    )


def list_players(code: str) -> List[Player]:
    game = get_game(code)
    if not game:
        return []
    return game.players


def set_role(code: str, player_id: str, role: str) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code, "players.id": player_id},
        {"$set": {"players.$.role": role}},
    )


def bulk_assign_roles(code: str, assignments: Dict[str, str]) -> None:
    game = get_game(code)
    if not game:
        raise ValueError("Partie introuvable.")
    player_map = {player.id: player for player in game.players}
    for player_id, role in assignments.items():
        if player_id in player_map:
            player_map[player_id].role = role
    game.players = list(player_map.values())
    upsert_game(game)


def set_status(code: str, player_id: str, status: str) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code, "players.id": player_id},
        {"$set": {"players.$.status": status}},
    )


def set_phase(code: str, phase: str) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$set": {"phase": phase}},
    )


def set_last_killed(code: str, player_id: Optional[str]) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$set": {"last_killed": player_id}},
    )


def clear_last_killed(code: str) -> None:
    set_last_killed(code, None)


def set_potion_used(code: str, kind: str) -> None:
    if kind not in {"heal", "poison"}:
        raise ValueError("Type de potion invalide.")
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$set": {f"potions.{kind}_used": True}},
    )


def log_event(code: str, event: Event) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$push": {"history": event.model_dump(mode="python")}},
    )


def append_chat_message(code: str, message: ChatMessage) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$push": {"chat_history": message.model_dump(mode="python")}},
    )


def overwrite_chat_history(code: str, messages: List[ChatMessage]) -> None:
    collection = get_collection()
    collection.update_one(
        {"code": code},
        {"$set": {"chat_history": [msg.model_dump(mode="python") for msg in messages]}},
    )
