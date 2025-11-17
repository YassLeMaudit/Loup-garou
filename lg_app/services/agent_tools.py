from __future__ import annotations

from typing import Dict, List

ToolSpec = Dict[str, object]

TOOL_DEFINITIONS: List[ToolSpec] = [
    {
        "name": "create_game",
        "description": "Crée un nouveau salon avec un code unique optionnel.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code personnalisé de 6 caractères alphanumériques (facultatif).",
                }
            },
        },
    },
    {
        "name": "join_game",
        "description": "Rejoint un salon existant via son code.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code salon de 6 caractères.",
                }
            },
            "required": ["code"],
        },
    },
    {
        "name": "add_player",
        "description": "Ajoute un joueur vivant dans le salon courant.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nom du joueur à ajouter.",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "remove_player",
        "description": "Supprime un joueur du salon courant.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nom du joueur à retirer.",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_players",
        "description": "Affiche la liste des joueurs et leur statut.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "assign_roles",
        "description": "Distribue aléatoirement les rôles et passe à la première nuit.",
        "parameters": {
            "type": "object",
            "properties": {
                "seed": {
                    "type": "integer",
                    "description": "Graine optionnelle pour reproduire l'attribution.",
                }
            },
        },
    },
    {
        "name": "seer_peek",
        "description": "Permet à la voyante de sonder un joueur vivant pendant la phase appropriée.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_name": {
                    "type": "string",
                    "description": "Nom du joueur à sonder.",
                }
            },
            "required": ["target_name"],
        },
    },
    {
        "name": "wolves_vote",
        "description": "Les loups choisissent une cible vivante pendant leur phase.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_name": {
                    "type": "string",
                    "description": "Nom du joueur attaqué.",
                }
            },
            "required": ["target_name"],
        },
    },
    {
        "name": "witch_action",
        "description": "La sorcière peut sauver la victime ou empoisonner un autre joueur.",
        "parameters": {
            "type": "object",
            "properties": {
                "heal": {
                    "type": "boolean",
                    "description": "Vrai pour utiliser la potion de soin sur la cible des loups.",
                },
                "poison_target": {
                    "type": "string",
                    "description": "Nom du joueur à empoisonner (optionnel).",
                },
            },
        },
    },
    {
        "name": "run_night_sequence",
        "description": "Orchestre automatiquement toute la séquence de nuit : appel de la voyante, puis des loups, puis de la sorcière. Utilise cet outil au lieu d'appeler chaque phase individuellement.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "advance_to_day",
        "description": "Annonce la fin de la nuit, applique les morts restants et passe au jour.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "start_next_night",
        "description": "Lance une nouvelle nuit après la phase de jour.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "game_status",
        "description": "Résume la phase actuelle, les joueurs vivants/morts et l'état des potions.",
        "parameters": {"type": "object", "properties": {}},
    },
]

TOOL_MAP: Dict[str, ToolSpec] = {spec["name"]: spec for spec in TOOL_DEFINITIONS}


def describe_tools() -> str:
    lines = []
    for spec in TOOL_DEFINITIONS:
        params = spec.get("parameters", {})
        requirement = ", ".join(params.get("required", [])) if params else ""
        lines.append(
            f"- **{spec['name']}** : {spec['description']}."
            + (f" Champs requis : {requirement}." if requirement else "")
        )
    return "\n".join(lines)
