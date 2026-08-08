from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .registry import load_registry


_NEGATION_RE = re.compile(
    r"(?:\b(?:do\s+not|don['’]?t|dont|must\s+not|should\s+not|cannot|can['’]?t|cant|"
    r"never|without|skip|avoid|no\s+(?:need|desire|wish))\b|"
    r"\bnot\b(?!\s+only\b)|\bno\b(?![-.]?\w)|"
    r"(?:请勿|不需要|不要|无需|无须|不能|不可|别|禁止|拒绝|不想|不必|不准|切勿|"
    r"不做|不进行|不创建|不生成|不开展|跳过|避免|勿|"
    r"不(?=(?:诊断|审计|拓词|挖掘|研究|写|创建|生成|做|进行|开展|发布|测量|抓取))))"
)
_HARD_CLAUSE_RE = re.compile(r"[;；。.!?！？]")
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?:[;；。.!?！？]|(?:,\s*)?\b(?:but|instead|however)(?:\s+please)?\b|"
    r"(?:,\s*)?(?:and\s+)?(?:then|only)\b|"
    r",\s*(?:only|just)\b|(?:，\s*)?(?:但是|但|改为|转而)(?:请)?|"
    r"(?:，\s*)?(?:然后|再|只)|，\s*(?:只|仅|请)|请)"
)
_WORKFLOW_CONNECTOR_RE = re.compile(
    r"(?:\b(?:and|then|plus|followed by|but|instead|however)\b|"
    r"[,&+;，；、]|再|然后|还要|还需|并且|但是|但|改为|转而|并|和|加|及)"
)
_NEGATION_FILLER_RE = re.compile(
    r"\b(?:under|any|circumstances|at|all|ever|in|way|please|just|only|really|want|"
    r"interested|rather)\b|(?:无论如何|在任何情况下|任何形式|都|仅仅|只是)"
)
MAX_ROUTE_CHARACTERS = 8_000
MAX_ROUTE_UTF8_BYTES = 16_384
_ACTION_VERB_PREFIXES = frozenset(
    {
        "build",
        "create",
        "generate",
        "make",
        "produce",
        "refine",
        "write",
        "产出",
        "创建",
        "制作",
        "写",
        "生成",
        "输出",
    }
)
_SEQUENCE_SCOPE_TOKENS = frozenset(
    {"then", "and then", "only", "and only", "just", "然后", "再", "只", "仅", "请"}
)
_ACTION_LEAD_IN_RE = re.compile(r"(?:(?:please|need|want)\s+|(?:请|要|需要)\s*)")


@dataclass(frozen=True)
class ClauseScope:
    start: int
    end: int
    negation_starts: tuple[int, ...]


@dataclass(frozen=True)
class ActionPhraseIndex:
    phrases: frozenset[str]
    start_pattern: re.Pattern[str]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip())


def build_action_phrase_index(registry: dict[str, Any]) -> ActionPhraseIndex:
    """Compile every registered intent plus narrow request verb prefixes."""
    phrases = {
        phrase
        for skill in registry["skills"]
        for intent in skill["intents"]
        if (phrase := _normalize(intent))
    }
    phrases.update(_ACTION_VERB_PREFIXES)
    alternatives = []
    for phrase in sorted(phrases, key=lambda item: (-len(item), item)):
        suffix = r"(?![\w-])" if phrase[-1].isascii() else ""
        alternatives.append(f"(?:{re.escape(phrase)}){suffix}")
    return ActionPhraseIndex(
        phrases=frozenset(phrases),
        start_pattern=re.compile("(?:" + "|".join(alternatives) + ")"),
    )


def _starts_registered_action(text: str, action_index: ActionPhraseIndex) -> bool:
    lead_in = _ACTION_LEAD_IN_RE.match(text)
    start = lead_in.end() if lead_in else 0
    return action_index.start_pattern.match(text, start) is not None


def _connector_starts_scope(
    text: str,
    boundary: re.Match[str],
    scope_start: int,
    negation_spans: tuple[tuple[int, int], ...],
    negation_starts: tuple[int, ...],
    object_prefix: tuple[int, ...],
    action_index: ActionPhraseIndex,
) -> bool:
    token = _normalize(boundary.group().strip(" ,，"))
    right = text[boundary.end() :].lstrip()
    if token in _SEQUENCE_SCOPE_TOKENS:
        if token in {"only", "and only"} and text[max(0, boundary.start() - 4) : boundary.start()].endswith("not "):
            return False
        if not _starts_registered_action(right, action_index):
            return False
    if (
        token.startswith(("however", "instead"))
        and boundary.group().lstrip().startswith((",", "，"))
        and right.startswith((",", "，"))
    ):
        return False
    negation_index = bisect_right(negation_starts, boundary.start() - 1) - 1
    if negation_index < 0 or negation_spans[negation_index][0] < scope_start:
        return True
    after_negation = negation_spans[negation_index][1]
    return object_prefix[boundary.start()] > object_prefix[after_negation]


def _parse_clause_scopes(
    text: str,
    action_index: ActionPhraseIndex,
) -> tuple[ClauseScope, ...]:
    negation_matches = tuple(_NEGATION_RE.finditer(text))
    negation_spans = tuple(match.span() for match in negation_matches)
    negation_starts = tuple(span[0] for span in negation_spans)
    ignored = bytearray(len(text))
    for match in (*negation_matches, *_NEGATION_FILLER_RE.finditer(text)):
        ignored[match.start() : match.end()] = b"\x01" * (match.end() - match.start())
    prefix = [0]
    for index, character in enumerate(text):
        prefix.append(prefix[-1] + int(character.isalpha() and not ignored[index]))
    object_prefix = tuple(prefix)
    boundaries: list[int] = [0]
    scope_start = 0
    for boundary in _CLAUSE_BOUNDARY_RE.finditer(text):
        if _HARD_CLAUSE_RE.fullmatch(boundary.group()) or _connector_starts_scope(
            text,
            boundary,
            scope_start,
            negation_spans,
            negation_starts,
            object_prefix,
            action_index,
        ):
            scope_start = boundary.end()
            boundaries.append(scope_start)
    boundaries.append(len(text) + 1)
    scopes = []
    for start, end in zip(boundaries, boundaries[1:]):
        left = bisect_right(negation_starts, start - 1)
        right = bisect_right(negation_starts, end - 1)
        negations = negation_starts[left:right]
        scopes.append(ClauseScope(start=start, end=end, negation_starts=negations))
    return tuple(scopes)


def _positive_intent_spans(
    text: str,
    intent: str,
    scopes: tuple[ClauseScope, ...],
) -> list[tuple[int, int]]:
    phrase = _normalize(intent)
    scope_starts = tuple(scope.start for scope in scopes)
    spans = []
    for match in re.finditer(re.escape(phrase), text):
        scope = scopes[bisect_right(scope_starts, match.start()) - 1]
        if not any(start < match.start() for start in scope.negation_starts):
            spans.append(match.span())
    return spans


def _analyze_skill_intents(
    text: str,
    intents: list[str],
    scopes: tuple[ClauseScope, ...],
) -> tuple[int, list[tuple[int, int]]]:
    score = 0
    skill_spans: list[tuple[int, int]] = []
    for intent in intents:
        phrase = _normalize(intent)
        spans = _positive_intent_spans(text, phrase, scopes) if phrase else []
        if spans:
            score += max(1, len(phrase))
            skill_spans.extend(spans)
    return score, skill_spans


def _workflow_matches(
    recipe: dict[str, Any],
    spans_by_skill: dict[str, list[tuple[int, int]]],
    connector_spans: tuple[tuple[int, int], ...],
) -> bool:
    first_id, second_id = recipe["required_skills"]
    first_ends = sorted(span[1] for span in spans_by_skill[first_id])
    second_starts = sorted(span[0] for span in spans_by_skill[second_id])
    if not first_ends or not second_starts:
        return False
    return any(
        bisect_right(first_ends, connector_start) > 0
        and bisect_right(second_starts, connector_end - 1) < len(second_starts)
        for connector_start, connector_end in connector_spans
    )


def route(text: str, registry_path: Path | None = None) -> dict[str, Any]:
    """Select the best registry route and expose its implementation status."""
    if len(text) > MAX_ROUTE_CHARACTERS or len(text.encode("utf-8")) > MAX_ROUTE_UTF8_BYTES:
        raise ValueError(
            "Route text exceeds 8000 characters or 16384 UTF-8 bytes"
        )
    normalized = _normalize(text)
    if not normalized:
        raise ValueError("Route text must not be empty")

    registry = load_registry(registry_path)
    action_index = build_action_phrase_index(registry)
    scopes = _parse_clause_scopes(normalized, action_index)
    analyses = {
        skill["id"]: _analyze_skill_intents(normalized, skill["intents"], scopes)
        for skill in registry["skills"]
    }
    ranked = [
        (analyses[skill["id"]][0], index, skill)
        for index, skill in enumerate(registry["skills"])
    ]
    scores = {skill["id"]: score for score, _, skill in ranked}
    spans_by_skill = {skill_id: analysis[1] for skill_id, analysis in analyses.items()}
    connector_spans = tuple(match.span() for match in _WORKFLOW_CONNECTOR_RE.finditer(normalized))
    planned_ranked = [
        item
        for item in ranked
        if item[0] > 0 and item[2]["status"] != "active"
    ]
    active_stage_matches = {
        skill_id
        for skill_id in ("geo-discover", "geo-diagnose", "geo-content")
        if scores.get(skill_id, 0) > 0
    }
    matched_recipes = [] if planned_ranked else [
        recipe
        for recipe in registry["workflows"]
        if set(recipe["required_skills"]) <= active_stage_matches
        and _workflow_matches(recipe, spans_by_skill, connector_spans)
    ]
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
    if planned_ranked:
        ranked = planned_ranked
    elif any(score > 0 and skill["id"] != "geo" for score, _, skill in ranked):
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
