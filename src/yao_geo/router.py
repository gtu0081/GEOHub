from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .registry import load_registry


_NEGATION_RE = re.compile(
    r"(?:\b(?:do\s+not|don['’]?t|dont|must\s+not|should\s+not|cannot|can['’]?t|cant|"
    r"never|without|no\s+(?:need|desire|wish))\b|"
    r"(?:请勿|不需要|不要|无需|无须|不能|不可|别|禁止|拒绝|不想|不必|不准|切勿|"
    r"不做|不进行|不创建|不生成|不开展|勿|"
    r"不(?=(?:诊断|审计|拓词|挖掘|研究|写|创建|生成|做|进行|开展|发布|测量|抓取))))"
)
_HARD_CLAUSE_RE = re.compile(r"[;；。.!?！？]")
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?:[;；。.!?！？]|(?:,\s*)?\b(?:but|instead|however)(?:\s+please)?\b|"
    r",\s*(?:only|just)\b|(?:，\s*)?(?:但是|但|改为|转而)(?:请)?|"
    r"，\s*(?:只|仅|请)|(?:请|只)\s*$)"
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip())


def _contains_registered_intent(text: str, all_intents: tuple[str, ...]) -> bool:
    return any(phrase and phrase in text for phrase in all_intents)


def _negated_scope_has_object(text: str, all_intents: tuple[str, ...]) -> bool:
    if _contains_registered_intent(text, all_intents):
        return True
    remainder = re.sub(
        r"\b(?:under\s+any\s+circumstances|at\s+all|ever|in\s+any\s+way|please|just|only|really)\b|"
        r"(?:无论如何|在任何情况下|任何形式|都|仅仅|只是)",
        " ",
        text,
    )
    return bool(re.search(r"[a-z\u3400-\u9fff]", remainder))


def _connector_starts_scope(
    text: str,
    boundary: re.Match[str],
    scope_start: int,
    all_intents: tuple[str, ...],
) -> bool:
    token = boundary.group().strip(" ,，").casefold()
    right = text[boundary.end() :].lstrip()
    if (
        token.startswith(("however", "instead"))
        and boundary.group().lstrip().startswith((",", "，"))
        and right.startswith((",", "，"))
    ):
        return False
    scope = text[scope_start : boundary.start()]
    negations = list(_NEGATION_RE.finditer(scope))
    if not negations:
        return True
    after_negation = scope[negations[-1].end() :]
    return _negated_scope_has_object(after_negation, all_intents)


def _positive_intent_spans(
    text: str,
    intent: str,
    all_intents: tuple[str, ...] = (),
) -> list[tuple[int, int]]:
    phrase = _normalize(intent)
    spans = []
    for match in re.finditer(re.escape(phrase), text):
        prefix = text[: match.start()]
        boundaries = []
        scope_start = 0
        for boundary in _CLAUSE_BOUNDARY_RE.finditer(prefix):
            if _HARD_CLAUSE_RE.fullmatch(boundary.group()) or _connector_starts_scope(
                prefix,
                boundary,
                scope_start,
                all_intents,
            ):
                boundaries.append(boundary)
                scope_start = boundary.end()
        clause_prefix = prefix[boundaries[-1].end() :] if boundaries else prefix
        negated = _NEGATION_RE.search(clause_prefix) or re.search(r"不\s*$", clause_prefix)
        if not negated:
            spans.append(match.span())
    return spans


def _intent_score(text: str, intents: list[str], all_intents: tuple[str, ...]) -> int:
    score = 0
    for intent in intents:
        phrase = _normalize(intent)
        if phrase and _positive_intent_spans(text, phrase, all_intents):
            score += max(1, len(phrase))
    return score


def _workflow_matches(
    text: str,
    recipe: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    all_intents: tuple[str, ...],
) -> bool:
    first_id, second_id = recipe["required_skills"]
    first_spans = [span for intent in by_id[first_id]["intents"] for span in _positive_intent_spans(text, intent, all_intents)]
    second_spans = [span for intent in by_id[second_id]["intents"] for span in _positive_intent_spans(text, intent, all_intents)]
    connector = re.compile(r"(?:\b(?:and|then|plus|followed by)\b|[,&+;，；、]|再|然后|还要|还需|并且|并|和|加|及)")
    return any(left[0] < right[0] and connector.search(text[left[1] : right[0]]) for left in first_spans for right in second_spans)


def route(text: str, registry_path: Path | None = None) -> dict[str, Any]:
    """Select the best registry route and expose its implementation status."""
    normalized = _normalize(text)
    if not normalized:
        raise ValueError("Route text must not be empty")

    registry = load_registry(registry_path)
    all_intents = tuple(
        _normalize(intent)
        for skill in registry["skills"]
        for intent in skill["intents"]
        if _normalize(intent)
    )
    ranked = [
        (_intent_score(normalized, skill["intents"], all_intents), index, skill)
        for index, skill in enumerate(registry["skills"])
    ]
    scores = {skill["id"]: score for score, _, skill in ranked}
    by_id = {skill["id"]: skill for skill in registry["skills"]}
    active_stage_matches = {skill_id for skill_id in ("geo-discover", "geo-diagnose", "geo-content") if scores.get(skill_id, 0) > 0}
    matched_recipes = [recipe for recipe in registry["workflows"] if set(recipe["required_skills"]) <= active_stage_matches and _workflow_matches(normalized, recipe, by_id, all_intents)]
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
    if not runnable:
        result["required_inputs"] = list(selected["required_inputs"])
        result["closest_v0_artifact"] = selected["closest_v0_artifact"]
    if workflow is not None and runnable:
        result["workflow"] = workflow
        result["reason"] = f"Matched exact multi-intent recipe {workflow['id']}."
    return result
