from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .registry import load_registry


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip())


def _positive_intent_spans(text: str, intent: str) -> list[tuple[int, int]]:
    phrase = _normalize(intent)
    spans = []
    for match in re.finditer(re.escape(phrase), text):
        prefix = text[max(0, match.start() - 20) : match.start()]
        negated = re.search(r"(?:do not|don't|not|no|without|不要|不需要|无需|别|不)\s*[\W_]*$", prefix)
        if not negated:
            spans.append(match.span())
    return spans


def _intent_score(text: str, intents: list[str]) -> int:
    score = 0
    for intent in intents:
        phrase = _normalize(intent)
        if phrase and _positive_intent_spans(text, phrase):
            score += max(1, len(phrase))
    return score


def _workflow_matches(text: str, recipe: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    first_id, second_id = recipe["required_skills"]
    first_spans = [span for intent in by_id[first_id]["intents"] for span in _positive_intent_spans(text, intent)]
    second_spans = [span for intent in by_id[second_id]["intents"] for span in _positive_intent_spans(text, intent)]
    connector = re.compile(r"(?:\b(?:and|then|plus|followed by)\b|[,&+;，；、]|再|然后|并|和|加|及)")
    return any(left[0] < right[0] and connector.search(text[left[1] : right[0]]) for left in first_spans for right in second_spans)


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
    scores = {skill["id"]: score for score, _, skill in ranked}
    by_id = {skill["id"]: skill for skill in registry["skills"]}
    active_stage_matches = {skill_id for skill_id in ("geo-discover", "geo-diagnose", "geo-content") if scores.get(skill_id, 0) > 0}
    matched_recipes = [recipe for recipe in registry["workflows"] if set(recipe["required_skills"]) <= active_stage_matches and _workflow_matches(normalized, recipe, by_id)]
    workflow = None
    if len(matched_recipes) == 1 and active_stage_matches == set(matched_recipes[0]["required_skills"]):
        workflow = {"id": matched_recipes[0]["id"], "steps": [dict(step) for step in matched_recipes[0]["steps"]]}
    elif len(matched_recipes) == 2 and active_stage_matches == {"geo-discover", "geo-diagnose", "geo-content"}:
        workflow = {
            "id": "brand-baseline-lite+content-campaign",
            "recipes": [recipe["id"] for recipe in matched_recipes],
            "steps": [
                {"id": "discover", "skill_id": "geo-discover", "depends_on": []},
                {"id": "diagnose", "skill_id": "geo-diagnose", "depends_on": ["discover"]},
                {"id": "content", "skill_id": "geo-content", "depends_on": ["discover"]},
            ],
        }
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

    if workflow is not None:
        selected = next(skill for skill in registry["skills"] if skill["id"] == "geo-discover")
        alternatives = []

    runnable = selected["status"] == "active" and bool(selected["entry"])
    if runnable:
        suggestion = None
    else:
        suggestion = selected.get("nearest_active", "geo-discover")
        reason += f" Stage status is {selected['status']}; no runnable entry is registered."

    result = {
        "protocol_version": registry["protocol_version"],
        "skill_id": selected["id"],
        "status": selected["status"],
        "runnable": runnable,
        "entry": selected["entry"],
        "reason": reason,
        "suggestion": suggestion,
        "alternatives": alternatives,
    }
    if workflow is not None and runnable:
        result["workflow"] = workflow
        result["reason"] = f"Matched exact multi-intent recipe {workflow['id']}."
    return result
