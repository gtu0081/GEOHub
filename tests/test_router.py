from yao_geo.router import route


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
