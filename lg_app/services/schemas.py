from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, field_validator


class PotionState(BaseModel):
    heal_used: bool = False
    poison_used: bool = False


class Player(BaseModel):
    id: str
    name: str
    role: str = "villager"
    status: str = "alive"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le nom du joueur ne peut pas être vide.")
        if len(value) > 40:
            raise ValueError("Le nom du joueur doit contenir 40 caractères maximum.")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        allowed_roles = {"seer", "witch", "wolf", "villager"}
        if value not in allowed_roles:
            raise ValueError(f"Rôle invalide: {value}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed_status = {"alive", "dead"}
        if value not in allowed_status:
            raise ValueError(f"Statut invalide: {value}")
        return value


class Event(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    role: Literal["user", "assistant", "system"]
    content: str


class Game(BaseModel):
    code: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    phase: str = "lobby"
    players: List[Player] = Field(default_factory=list)
    history: List[Event] = Field(default_factory=list)
    last_killed: Optional[str] = None
    potions: PotionState = Field(default_factory=PotionState)
    chat_history: List[ChatMessage] = Field(default_factory=list)

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, value: str) -> str:
        allowed_phases = {
            "lobby",
            "night_seer",
            "night_wolves",
            "night_witch",
            "day",
            "ended",
        }
        if value not in allowed_phases:
            raise ValueError(f"Phase inconnue: {value}")
        return value
