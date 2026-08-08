from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .registry import load_registry


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip())


def _intent_score(text: str, intents: list[str]) -> int:
    score = 0
    for intent in intents:
        phrase = _normalize(intent)
        if phrase and phrase in text:
            score += max(1, len(phrase))
    return score


def route(text: str, registry_path: Path | None = None) -> dict[str, Any]:
    """Select the best registry route and expose its implementation status."""
    normalized = _normalize(text)
    if not normalized:
        raise ValueError("Route text must not be empty")

    registry = load_registry(registry_path)
    ranked = [
        (_intent_score(normalized, skill["intents"]), index, skill)
        for index, skill in enumerate(registry["skills"])
    ]
    if any(score > 0 and skill["id"] != "geo" for score, _, skill in ranked):
        ranked = [item for item in ranked if item[2]["id"] != "geo"]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    top_score = ranked[0][0]
    if top_score == 0:
        selected = next(skill for skill in registry["skills"] if skill["id"] == "geo")
        alternatives: list[str] = []
        reason = "No specific stage matched; using the active GEO umbrella route."
    else:
        selected = ranked[0][2]
        alternatives = [
            item[2]["id"] for item in ranked[1:] if item[0] == top_score and item[0] > 0
        ]
        reason = f"Matched registered intent terms for {selected['id']}."

    runnable = selected["status"] == "active" and bool(selected["entry"])
    if runnable:
        suggestion = None
    else:
        suggestion = "geo-discover"
        reason += f" Stage status is {selected['status']}; no runnable entry is registered."

    return {
        "protocol_version": registry["protocol_version"],
        "skill_id": selected["id"],
        "status": selected["status"],
        "runnable": runnable,
        "entry": selected["entry"],
        "reason": reason,
        "suggestion": suggestion,
        "alternatives": alternatives,
    }
