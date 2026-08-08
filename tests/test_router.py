from copy import deepcopy

import pytest
import yaml

import yao_geo.router as router_module
from yao_geo.paths import repository_root
from yao_geo.registry import load_registry
from yao_geo.router import build_action_phrase_index, route


def test_routes_chinese_discovery_request():
    result = route("帮我做 AI 搜索意图挖掘和问题挖掘")
    assert result["skill_id"] == "geo-discover"
    assert result["runnable"] is True
    assert result["status"] == "active"


def test_readme_chinese_example_routes_to_discovery():
    result = route("帮我挖掘 AI 搜索问题")
    assert result["skill_id"] == "geo-discover"
    assert result["runnable"] is True


def test_routes_english_discovery_request():
    result = route("Run intent mining and query research for our category")
    assert result["skill_id"] == "geo-discover"
    assert result["entry"] == "skills/geo-discover/SKILL.md"


def test_planned_route_is_honest():
    result = route("请给出 GEO strategy 和 roadmap")
    assert result["skill_id"] == "geo-strategy"
    assert result["status"] == "planned"
    assert result["runnable"] is False
    assert result["entry"] is None
    assert result["suggestion"] == "geo-discover"


def test_routes_chinese_website_diagnosis():
    result = route("诊断我们的网站 GEO 差距")
    assert result["skill_id"] == "geo-diagnose"
    assert result["status"] == "active"
    assert result["runnable"] is True
    assert result["entry"] == "skills/geo-diagnose/SKILL.md"


def test_routes_english_brand_and_page_audits():
    for text in ("Run a brand diagnosis for Acme", "Audit this website", "Page audit for our pricing page"):
        result = route(text)
        assert result["skill_id"] == "geo-diagnose"
        assert result["runnable"] is True


def test_unknown_request_falls_back_to_geo():
    result = route("help me choose the next step")
    assert result["skill_id"] == "geo"
    assert result["runnable"] is True


def test_routes_chinese_and_english_content_modes():
    requests = (
        "生成标题候选",
        "写一篇科普解释",
        "做一个中立对比",
        "制作证据榜单",
        "输出页面蓝图",
        "帮我做内容优化",
        "Create an article-friendly draft",
        "Build an explainer and comparison",
    )
    for text in requests:
        result = route(text)
        assert result["skill_id"] == "geo-content"
        assert result["status"] == "active"
        assert result["runnable"] is True
        assert result["entry"] == "skills/geo-content/SKILL.md"


def test_brand_baseline_workflow_is_stable_dag():
    result = route("先做意图挖掘，再做品牌诊断")
    assert result["skill_id"] == "geo-discover"
    assert result["workflow"] == {
        "id": "brand-baseline-lite",
        "steps": [
            {"id": "discover", "skill_id": "geo-discover", "depends_on": []},
            {"id": "diagnose", "skill_id": "geo-diagnose", "depends_on": ["discover"]},
        ],
    }


def test_content_campaign_requires_both_stage_intents():
    single = route("Write an explainer and comparison")
    assert "workflow" not in single
    mixed = route("Discover questions then write an explainer")
    assert mixed["skill_id"] == "geo-discover"
    assert mixed["workflow"]["id"] == "content-campaign"


def test_planned_routes_have_domain_nearest_active_suggestions():
    cases = {
        "strategy": "geo-discover",
        "knowledge base": "geo-content",
        "publish": "geo-content",
        "measure": "geo-diagnose",
    }
    for text, expected in cases.items():
        result = route(text)
        assert result["runnable"] is False
        assert result["suggestion"] == expected


def test_workflows_require_positive_ordered_exact_two_stage_intent():
    negated = route("Do not discover; audit our site")
    assert negated["skill_id"] == "geo-diagnose"
    assert "workflow" not in negated

    reversed_order = route("Audit our site, then discover questions")
    assert "workflow" not in reversed_order

    three_stage = route("Discover questions, audit our site, then write an explainer")
    assert three_stage["workflow"]["id"] == "brand-baseline-lite+content-campaign"
    assert three_stage["workflow"]["recipes"] == ["brand-baseline-lite", "content-campaign"]
    assert three_stage["workflow"]["steps"][-1] == {"id": "content", "skill_id": "geo-content", "depends_on": ["discover"]}

    noun_phrase = route("We need content discovery")
    assert "workflow" not in noun_phrase


def test_negated_planned_intent_does_not_override_active_intent():
    result = route("Do not publish; write content")
    assert result["skill_id"] == "geo-content"
    assert result["runnable"] is True


def test_chinese_not_needed_stage_is_excluded():
    result = route("意图挖掘后不需要发布内容")
    assert result["skill_id"] == "geo-discover"
    assert "workflow" not in result


def test_keyword_expansion_then_article_uses_content_campaign_dag():
    result = route("先拓词再生成文章")
    assert result["skill_id"] == "geo-discover"
    assert result["workflow"]["id"] == "content-campaign"
    assert [step["skill_id"] for step in result["workflow"]["steps"]] == ["geo-discover", "geo-content"]

    negated = route("不要拓词，只生成文章")
    assert negated["skill_id"] == "geo-content"
    assert "workflow" not in negated


def test_planned_route_exposes_inputs_and_closest_v0_artifact():
    result = route("制定 GEO strategy roadmap")
    assert result["status"] == "planned"
    assert result["runnable"] is False
    assert result["required_inputs"]
    assert result["closest_v0_artifact"]


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("No keyword research then publish", "geo-publish"),
        ("No keyword research then strategy", "geo-strategy"),
        ("No content then monitor", "geo-measure"),
        ("Skip website audit then knowledge base", "geo-knowledge"),
        ("Avoid content generation then publish to CMS", "geo-publish"),
        ("No diagnosis then measure AI visibility", "geo-measure"),
        ("Avoid content, then build a roadmap", "geo-strategy"),
        ("不拓词然后发布", "geo-publish"),
        ("不写文章然后策略", "geo-strategy"),
        ("不写文章然后知识库", "geo-knowledge"),
        ("不诊断然后监测", "geo-measure"),
        ("不拓词然后分发", "geo-publish"),
    ),
)
def test_planned_intents_after_negated_sequence_scope_remain_planned(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["status"] == "planned"
    assert result["runnable"] is False
    assert result["entry"] is None
    assert result["required_inputs"]
    assert result["closest_v0_artifact"]
    assert "workflow" not in result


@pytest.mark.parametrize(
    "text",
    (
        "No content then publish and keyword research and website audit",
        "不写文章然后发布并拓词和诊断网站",
        "No content then publish and website audit",
    ),
)
def test_positive_planned_intent_blocks_active_workflow_execution(text):
    result = route(text)
    assert result["skill_id"] == "geo-publish"
    assert result["status"] == "planned"
    assert result["runnable"] is False
    assert result["entry"] is None
    assert result["required_inputs"]
    assert result["closest_v0_artifact"]
    assert "workflow" not in result


def test_long_scope_negations_exclude_only_the_negated_stage():
    cases = (
        ("Do not under any circumstances create an article; audit our website instead", "geo-diagnose"),
        ("I don't want any keyword research at all; write an explainer", "geo-content"),
        ("无论如何都不要进行任何形式的意图挖掘和拓词工作，只需要诊断网站问题", "geo-diagnose"),
    )
    for text, skill_id in cases:
        result = route(text)
        assert result["skill_id"] == skill_id
        assert "workflow" not in result


def test_negated_content_is_excluded_from_positive_multistage_dag():
    result = route(
        "Do not under any circumstances create an article; discover questions, then audit our site"
    )
    assert result["workflow"]["id"] == "brand-baseline-lite"
    assert [step["skill_id"] for step in result["workflow"]["steps"]] == [
        "geo-discover",
        "geo-diagnose",
    ]


def test_positive_intent_after_negated_clause_remains_routable():
    result = route("Don't create an article; do keyword research instead")
    assert result["skill_id"] == "geo-discover"
    assert "workflow" not in result


def test_bare_transition_word_starts_a_positive_clause():
    result = route("Do not create an article however audit the website")
    assert result["skill_id"] == "geo-diagnose"
    assert "workflow" not in result


def test_parenthetical_however_does_not_cancel_negation():
    for text in (
        "Please do not, however, audit the website",
        "Please do not, however, discover questions and audit the website",
    ):
        result = route(text)
        assert result["skill_id"] == "geo"
        assert "workflow" not in result

    transition = route("Do not write, however audit the website")
    assert transition["skill_id"] == "geo-diagnose"
    assert "workflow" not in transition


def test_connector_inside_negation_scope_does_not_start_a_route_or_dag():
    cases = (
        "Please do not, instead, audit the website",
        "Please do not instead discover questions and audit the website",
        "请不要改为诊断网站",
        "请不要改为拓词并诊断网站",
        "不要转而写文章",
    )
    for text in cases:
        result = route(text)
        assert result["skill_id"] == "geo"
        assert "workflow" not in result


def test_connector_after_negated_explicit_intent_starts_positive_scope():
    cases = (
        ("Do not write, instead audit the website", "geo-diagnose"),
        ("不要写文章，改为诊断网站", "geo-diagnose"),
        ("不要诊断网站，转而写文章", "geo-content"),
    )
    for text, expected in cases:
        result = route(text)
        assert result["skill_id"] == expected
        assert "workflow" not in result


def test_modal_and_chinese_prohibitions_exclude_single_and_dag_intents():
    cases = (
        "You must not audit the website",
        "You should not create content",
        "You cannot run keyword research",
        "You can't discover questions and audit the website",
        "请勿诊断网站",
        "勿生成文章",
        "请勿拓词并诊断网站",
    )
    for text in cases:
        result = route(text)
        assert result["skill_id"] == "geo"
        assert "workflow" not in result


def test_chinese_bu_compounds_remain_positive_intents():
    cases = (
        ("不断拓词", "geo-discover", None),
        ("不仅要拓词还要诊断网站", "geo-discover", "brand-baseline-lite"),
        ("帮我做个不错的网站诊断", "geo-diagnose", None),
        ("不同网站 audit", "geo-diagnose", None),
    )
    for text, skill_id, workflow_id in cases:
        result = route(text)
        assert result["skill_id"] == skill_id
        assert result.get("workflow", {}).get("id") == workflow_id


def test_chinese_bu_directly_governing_action_remains_negative():
    for text in ("不诊断网站", "不拓词", "不写文章"):
        result = route(text)
        assert result["skill_id"] == "geo"
        assert "workflow" not in result

    for text in ("不拓词但诊断网站", "不拓词只诊断网站"):
        transition = route(text)
        assert transition["skill_id"] == "geo-diagnose"
        assert "workflow" not in transition


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("不制定策略只诊断网站", "geo-diagnose"),
        ("不构建知识库只写文章", "geo-content"),
        ("不发布只写文章", "geo-content"),
        ("不分发只写文章", "geo-content"),
        ("不监测只诊断网站", "geo-diagnose"),
        ("不衡量只诊断网站", "geo-diagnose"),
    ),
)
def test_bare_bu_uses_registered_planned_action_before_active_scope(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("不再分发只写文章", "geo-content"),
        ("不再发布只写文章", "geo-content"),
        ("不再监测只诊断网站", "geo-diagnose"),
        ("不再衡量只诊断网站", "geo-diagnose"),
        ("不再制定策略只诊断网站", "geo-diagnose"),
        ("不 分发只写文章", "geo-content"),
        ("不 监测只诊断网站", "geo-diagnose"),
    ),
)
def test_bare_bu_absorbs_spacing_and_internal_zai_before_registered_action(
    text,
    skill_id,
):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("不再需要发布只写文章", "geo-content"),
        ("不再继续监测只诊断网站", "geo-diagnose"),
        ("不再想制定策略只诊断网站", "geo-diagnose"),
        ("不再去构建知识库只写文章", "geo-content"),
        ("不 再 要 分发只写文章", "geo-content"),
        ("不再打算衡量只诊断网站", "geo-diagnose"),
        ("不再准备发布只写文章", "geo-content"),
        ("不再需要诊断只写文章", "geo-content"),
        ("不 想 发布只写文章", "geo-content"),
    ),
)
def test_bare_bu_reuses_action_lead_in_before_registered_action(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("不再想要拓词只诊断网站", "geo-diagnose"),
        ("不再想要发布只写文章", "geo-content"),
        ("不再打算继续监测只诊断网站", "geo-diagnose"),
        ("不再需要继续制定策略只诊断网站", "geo-diagnose"),
        ("不再发布，再想要写文章", "geo-content"),
        ("不再监测，再准备去诊断网站", "geo-diagnose"),
    ),
)
def test_action_lead_in_chains_share_negation_and_sequence_scope(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


def test_action_lead_in_chain_is_bounded_to_four_tokens():
    match = router_module._ACTION_LEAD_IN_RE.match("想要打算准备继续发布")
    assert match is not None
    assert match.group() == "想要打算准备"


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("不再打算请拓词只诊断网站", "geo-diagnose"),
        ("不再想请发布只写文章", "geo-content"),
        ("不再需要请监测只诊断网站", "geo-diagnose"),
        ("不要想请发布只写文章", "geo-content"),
        ("不要 想请发布只写文章", "geo-content"),
        ("不要请发布只写文章", "geo-content"),
        ("避免继续监测只诊断网站", "geo-diagnose"),
        ("不再准备去发布只写文章", "geo-content"),
        ("不要打算再发布只写文章", "geo-content"),
        ("不再想只发布只写文章", "geo-content"),
        ("不再想请发布，再写文章", "geo-content"),
    ),
)
def test_negation_span_absorbs_the_recognized_action_lead_in(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


def test_positive_action_lead_in_chain_keeps_planned_precedence():
    result = route("想请发布只诊断网站")
    assert result["skill_id"] == "geo-publish"
    assert result["runnable"] is False


def test_bujin_with_action_lead_in_remains_positive():
    result = route("不仅想发布还要诊断网站")
    assert result["skill_id"] == "geo-publish"
    assert result["status"] == "planned"
    assert result["runnable"] is False


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("不再准备发布，再写文章", "geo-content"),
        ("不再继续监测，再诊断网站", "geo-diagnose"),
    ),
)
def test_later_zai_after_lead_in_negation_starts_positive_scope(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("不发布，再写文章", "geo-content"),
        ("不制定策略，再诊断网站", "geo-diagnose"),
    ),
)
def test_zai_after_negated_action_starts_a_positive_sequence_scope(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


@pytest.mark.parametrize(
    "text,skill_id",
    (
        ("Don't want strategy; audit the website", "geo-diagnose"),
        ("No strategy, then audit the website", "geo-diagnose"),
        ("Don't monitor; write article", "geo-content"),
        ("No monitor, then write article", "geo-content"),
        ("Don't publish; write article", "geo-content"),
        ("No publish, then keyword research", "geo-discover"),
    ),
)
def test_english_planned_negation_keeps_the_active_scope(text, skill_id):
    result = route(text)
    assert result["skill_id"] == skill_id
    assert result["runnable"] is True
    assert "workflow" not in result


def test_positive_planned_intent_still_has_non_runnable_precedence():
    result = route("制定策略只诊断网站")
    assert result["skill_id"] == "geo-strategy"
    assert result["status"] == "planned"
    assert result["runnable"] is False


def test_new_registry_planned_intent_automatically_participates_in_bare_bu_scope(
    tmp_path,
):
    registry = deepcopy(load_registry())
    next(skill for skill in registry["skills"] if skill["id"] == "geo-strategy")[
        "intents"
    ].append("校准路线")
    registry_root = tmp_path / "registry"
    registry_root.mkdir()
    schema_source = repository_root() / "registry" / "skills.schema.json"
    (registry_root / "skills.schema.json").write_text(
        schema_source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for skill in registry["skills"]:
        if skill["entry"]:
            entry = tmp_path / skill["entry"]
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_text("# test entry\n", encoding="utf-8")
    registry_path = registry_root / "skills.yaml"
    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True),
        encoding="utf-8",
    )

    result = route("不校准路线只诊断网站", registry_path)
    assert result["skill_id"] == "geo-diagnose"
    assert result["runnable"] is True


def test_bare_negation_verbs_and_lexical_exceptions_are_clause_local():
    negated = (
        "No keyword research",
        "Not audit the website",
        "Skip content creation",
        "Avoid keyword research and audit the website",
        "跳过拓词并诊断网站",
        "避免写文章",
    )
    for text in negated:
        result = route(text)
        assert result["skill_id"] == "geo"
        assert "workflow" not in result

    positive = (
        ("Not only keyword research but audit the website", "geo-discover", "brand-baseline-lite"),
        ("Run a no-code website audit", "geo-diagnose", None),
        ("Write a no.1 ranking article", "geo-content", None),
        ("No keyword research, just audit the website", "geo-diagnose", None),
    )
    for text, skill_id, workflow_id in positive:
        result = route(text)
        assert result["skill_id"] == skill_id
        assert result.get("workflow", {}).get("id") == workflow_id


def test_standalone_negation_applies_only_to_its_workflow_stage():
    cases = (
        ("No keyword research; audit the website", "geo-diagnose"),
        ("Discover questions; no content generation", "geo-discover"),
        ("I'm not interested in keyword research; write article", "geo-content"),
        ("I'd rather not create content; audit the website", "geo-diagnose"),
    )
    for text, skill_id in cases:
        result = route(text)
        assert result["skill_id"] == skill_id
        assert "workflow" not in result


def test_route_preparses_clause_boundaries_once_for_1k_and_2k_inputs(monkeypatch):
    original_boundary = router_module._CLAUSE_BOUNDARY_RE
    original_negation = router_module._NEGATION_RE
    original_bare_zh = router_module._BARE_ZH_NEGATION_RE
    boundary_calls = 0
    negation_calls = 0
    bare_zh_calls = 0

    class CountingBoundaryPattern:
        def finditer(self, text):
            nonlocal boundary_calls
            boundary_calls += 1
            return original_boundary.finditer(text)

    class CountingNegationPattern:
        def finditer(self, text):
            nonlocal negation_calls
            negation_calls += 1
            return original_negation.finditer(text)

    class CountingBareZhPattern:
        def finditer(self, text):
            nonlocal bare_zh_calls
            bare_zh_calls += 1
            return original_bare_zh.finditer(text)

    monkeypatch.setattr(router_module, "_CLAUSE_BOUNDARY_RE", CountingBoundaryPattern())
    monkeypatch.setattr(router_module, "_NEGATION_RE", CountingNegationPattern())
    monkeypatch.setattr(router_module, "_BARE_ZH_NEGATION_RE", CountingBareZhPattern())
    for target_length in (1_000, 2_000):
        text = ("keyword research and audit the website; " * 100)[:target_length]
        before = (boundary_calls, negation_calls, bare_zh_calls)
        route(text)
        assert boundary_calls - before[0] == 1
        assert negation_calls - before[1] == 1
        assert bare_zh_calls - before[2] == 1


def test_route_rejects_excessive_character_and_utf8_byte_lengths():
    with pytest.raises(ValueError, match="8000 characters|16384 UTF-8 bytes"):
        route("a" * 8_001)
    with pytest.raises(ValueError, match="8000 characters|16384 UTF-8 bytes"):
        route("诊" * 6_000)


def test_workflow_connector_scan_is_single_pass_for_dense_in_limit_input(monkeypatch):
    original = router_module._WORKFLOW_CONNECTOR_RE
    calls = 0

    class CountingWorkflowPattern:
        def finditer(self, text):
            nonlocal calls
            calls += 1
            return original.finditer(text)

    monkeypatch.setattr(router_module, "_WORKFLOW_CONNECTOR_RE", CountingWorkflowPattern())
    text = ("keyword research " * 240) + ("website audit " * 240)
    result = route(text)
    assert calls == 1
    assert "workflow" not in result


def test_sequencing_connectors_end_only_the_prior_negated_stage():
    cases = (
        ("No keyword research, then write explainer", "geo-content"),
        ("Skip keyword research; then write explainer", "geo-content"),
        ("Avoid content, then audit the website", "geo-diagnose"),
        ("跳过拓词，然后写文章", "geo-content"),
        ("避免写文章，然后诊断网站", "geo-diagnose"),
        ("Avoid keyword research and only write content", "geo-content"),
    )
    for text, skill_id in cases:
        result = route(text)
        assert result["skill_id"] == skill_id
        assert "workflow" not in result

    ordinary = route("Explain what happens then in a ranking article")
    assert ordinary["skill_id"] == "geo-content"


def test_chinese_scope_connectors_allow_normalized_spacing_before_action():
    cases = (
        ("跳过拓词，然后 写文章", "geo-content"),
        ("避免写文章，然后 诊断网站", "geo-diagnose"),
        ("跳过拓词再 写文章", "geo-content"),
        ("不拓词只 诊断网站", "geo-diagnose"),
        ("不要写文章请 诊断网站", "geo-diagnose"),
    )
    for text, skill_id in cases:
        result = route(text)
        assert result["skill_id"] == skill_id
        assert "workflow" not in result


@pytest.mark.parametrize(
    "text",
    (
        "No keyword research, then title",
        "Skip keyword research, then explainer",
        "Avoid keyword research and only comparison",
        "No keyword research, then ranking",
        "Skip keyword research, then page blueprint",
        "Avoid keyword research, then refine content",
        "No keyword research, then article-friendly",
        "跳过拓词，然后标题",
        "跳过拓词，然后解释",
        "跳过拓词，然后对比",
        "跳过拓词，然后排名",
        "跳过拓词，然后页面蓝图",
        "跳过拓词，然后内容优化",
        "跳过拓词，然后文章友好",
    ),
)
def test_all_registered_content_modes_start_positive_sequence_scope(text):
    result = route(text)
    assert result["skill_id"] == "geo-content"
    assert "workflow" not in result


def test_action_index_contains_every_registry_intent():
    registry = load_registry()
    index = build_action_phrase_index(registry)
    expected = {
        " ".join(intent.casefold().split())
        for skill in registry["skills"]
        for intent in skill["intents"]
    }
    assert expected <= index.phrases


def test_registry_action_index_is_compiled_once_and_checked_once_per_sequence(monkeypatch):
    original_builder = router_module.build_action_phrase_index
    build_calls = 0
    match_calls = 0

    class CountingStartPattern:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def match(self, text, *args):
            nonlocal match_calls
            match_calls += 1
            return self.wrapped.match(text, *args)

    def counting_builder(registry):
        nonlocal build_calls
        build_calls += 1
        index = original_builder(registry)
        return router_module.ActionPhraseIndex(
            phrases=index.phrases,
            start_pattern=CountingStartPattern(index.start_pattern),
        )

    monkeypatch.setattr(router_module, "build_action_phrase_index", counting_builder)
    text = ("No keyword research, then title; " * 100)[:3_000]
    route(text)
    assert build_calls == 1
    assert match_calls <= text.count("then") + text.count("No")


def test_bare_chinese_request_marker_starts_positive_clause():
    result = route("不要写文章请诊断网站")
    assert result["skill_id"] == "geo-diagnose"
    assert "workflow" not in result


def test_bare_contrast_connector_starts_positive_clause():
    cases = (
        ("Don't create an article but audit the website", "geo-diagnose"),
        ("不要写文章但诊断网站", "geo-diagnose"),
        ("不需要生成内容但请拓词", "geo-discover"),
    )
    for text, skill_id in cases:
        result = route(text)
        assert result["skill_id"] == skill_id
        assert "workflow" not in result
