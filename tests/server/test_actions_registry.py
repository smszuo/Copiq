"""architecture.md section 15.1 -- parameter normalization."""
from __future__ import annotations

import pytest

from copiq_server.application.actions import (
    InvalidParametersError,
    PromptNotFoundError,
    PromptRenderError,
    UnknownActionError,
    build_prompt,
    get_action,
    load_template,
    normalize_parameters,
    postprocess_result,
    resolve_prompt_version,
)


def test_unknown_action_raises():
    with pytest.raises(UnknownActionError):
        get_action("nonsense")


def test_unknown_parameter_raises():
    spec = get_action("simplify")
    with pytest.raises(InvalidParametersError):
        normalize_parameters(spec, {"bogus": "x"}, default_target_language="zh-CN")


def test_default_target_language_applied_when_omitted():
    spec = get_action("translate")
    normalized = normalize_parameters(spec, None, default_target_language="zh-CN")
    assert normalized["targetLanguage"] == "zh-cn"


def test_target_language_is_lowercased_for_stable_cache_keys():
    spec = get_action("translate")
    a = normalize_parameters(spec, {"targetLanguage": "ZH-CN"}, default_target_language="ja-JP")
    b = normalize_parameters(spec, {"targetLanguage": "zh-cn"}, default_target_language="ja-JP")
    assert a == b


def test_diagram_defaults_to_auto():
    spec = get_action("diagram")
    normalized = normalize_parameters(spec, None, default_target_language="zh-CN")
    assert normalized["diagramType"] == "auto"


def test_diagram_type_is_validated():
    spec = get_action("diagram")
    with pytest.raises(InvalidParametersError):
        normalize_parameters(spec, {"diagramType": "pie chart please"}, default_target_language="zh-CN")


def test_diagram_type_is_lowercased():
    spec = get_action("diagram")
    normalized = normalize_parameters(spec, {"diagramType": "FLOWCHART"}, default_target_language="zh-CN")
    assert normalized["diagramType"] == "flowchart"


def test_diagram_prompt_names_the_mermaid_keyword_when_type_is_specific():
    spec = get_action("diagram")
    normalized = normalize_parameters(spec, {"diagramType": "sequence"}, default_target_language="zh-CN")
    prompt = build_prompt(spec, normalized, version=spec.prompt_version, prompts_dir=None)
    assert "sequenceDiagram" in prompt


def test_diagram_prompt_lets_the_model_choose_when_type_is_auto():
    spec = get_action("diagram")
    normalized = normalize_parameters(spec, {"diagramType": "auto"}, default_target_language="zh-CN")
    prompt = build_prompt(spec, normalized, version=spec.prompt_version, prompts_dir=None)
    assert "flowchart for a process" in prompt


def test_postprocess_extracts_fenced_mermaid_block():
    spec = get_action("diagram")
    raw = "Sure, here's the diagram:\n```mermaid\nflowchart TD\n  A --> B\n```\nHope that helps!"
    assert postprocess_result(spec, raw) == "flowchart TD\n  A --> B"


def test_postprocess_falls_back_to_raw_when_no_fence_present():
    spec = get_action("diagram")
    raw = "  flowchart TD\n  A --> B  "
    assert postprocess_result(spec, raw) == "flowchart TD\n  A --> B"


def test_postprocess_is_a_no_op_for_other_actions():
    spec = get_action("translate")
    raw = "```mermaid\nnot actually relevant here\n```"
    assert postprocess_result(spec, raw) == raw


# --- architecture.md section 18.2: prompt configurability ---------------


def test_resolve_prompt_version_uses_default_when_unlisted():
    spec = get_action("translate")
    assert resolve_prompt_version(spec, {}) == "v1"
    assert resolve_prompt_version(spec, {"diagram": "v2"}) == "v1"


def test_resolve_prompt_version_honors_override():
    spec = get_action("translate")
    assert resolve_prompt_version(spec, {"translate": "v2-formal"}) == "v2-formal"


def test_load_template_falls_back_to_bundled_when_no_override_dir():
    text = load_template("simplify", "v1", None)
    assert "simpler English" in text


def test_load_template_falls_back_when_override_dir_lacks_this_file(tmp_path):
    (tmp_path / "translate").mkdir()
    (tmp_path / "translate" / "v2-other-action-only.txt").write_text("irrelevant")
    text = load_template("simplify", "v1", tmp_path)
    assert "simpler English" in text


def test_load_template_prefers_override_when_present(tmp_path):
    action_dir = tmp_path / "translate"
    action_dir.mkdir()
    (action_dir / "v1.txt").write_text("Custom override prompt: {target_language}")
    text = load_template("translate", "v1", tmp_path)
    assert text == "Custom override prompt: {target_language}"


def test_load_template_raises_clearly_when_version_does_not_exist_anywhere(tmp_path):
    with pytest.raises(PromptNotFoundError):
        load_template("translate", "v99-typo", tmp_path)


def test_build_prompt_with_custom_template_from_override_dir(tmp_path):
    action_dir = tmp_path / "simplify"
    action_dir.mkdir()
    (action_dir / "v1.txt").write_text("Simplify this, casually: no placeholders needed here.")
    spec = get_action("simplify")
    normalized = normalize_parameters(spec, None, default_target_language="zh-CN")
    prompt = build_prompt(spec, normalized, version="v1", prompts_dir=tmp_path)
    assert prompt == "Simplify this, casually: no placeholders needed here."


def test_build_prompt_raises_clear_error_for_stray_unescaped_braces(tmp_path):
    action_dir = tmp_path / "simplify"
    action_dir.mkdir()
    # A custom prompt author including a raw JSON example without escaping
    # {{ }} -- a realistic mistake now that prompts are operator-editable.
    (action_dir / "v1.txt").write_text('Example output: {"key": "value"}')
    spec = get_action("simplify")
    normalized = normalize_parameters(spec, None, default_target_language="zh-CN")
    with pytest.raises(PromptRenderError, match="key"):
        build_prompt(spec, normalized, version="v1", prompts_dir=tmp_path)


def test_explain_defaults_to_the_target_language_prompt():
    """architecture.md section 20 -- explain answers entirely in
    targetLanguage, which is prompt version v2; v1 stays bundled for rows
    already cached under it."""
    spec = get_action("explain")
    assert resolve_prompt_version(spec, {}) == "v2"

    normalized = normalize_parameters(spec, None, default_target_language="zh-CN")
    prompt = build_prompt(spec, normalized, version="v2", prompts_dir=None)
    assert prompt.count("zh-cn") >= 2  # the translation line *and* the explanation
    assert "{" not in prompt

    assert resolve_prompt_version(spec, {"explain": "v1"}) == "v1"
    assert load_template("explain", "v1", None)
