"""architecture.md section 15, 16, 22, 29 (secret gate)."""
from __future__ import annotations


def _upload(client, content, client_id="c1"):
    r = client.post("/api/clipboard", json={"content": content, "source": "x", "clientId": client_id})
    return r.json()["id"]


def test_translate_action_success(client):
    item_id = _upload(client, "This looks like a race condition.")
    r = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "translate"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["cached"] is False
    assert body["result"]


def test_second_identical_action_is_cached(client, fake_provider):
    item_id = _upload(client, "This avoids introducing unnecessary coupling.")
    r1 = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "translate"})
    r2 = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "translate"})
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is True
    assert r2.json()["result"] == r1.json()["result"]
    # the cache actually prevented a second provider call, not just returned
    # the same string coincidentally (architecture.md section 33)
    assert len(fake_provider.calls) == 1


def test_different_target_language_is_not_cached(client, fake_provider):
    item_id = _upload(client, "This is a test sentence.")
    r1 = client.post(f"/api/clipboard/{item_id}/actions",
                      json={"action": "translate", "parameters": {"targetLanguage": "zh-CN"}})
    r2 = client.post(f"/api/clipboard/{item_id}/actions",
                      json={"action": "translate", "parameters": {"targetLanguage": "ja-JP"}})
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is False
    assert len(fake_provider.calls) == 2


def test_unknown_action_rejected(client):
    item_id = _upload(client, "hello")
    r = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "nonsense"})
    assert r.status_code == 400


def test_unknown_parameter_rejected(client):
    item_id = _upload(client, "hello")
    r = client.post(f"/api/clipboard/{item_id}/actions",
                     json={"action": "simplify", "parameters": {"bogus": "x"}})
    assert r.status_code == 400


def test_action_on_missing_item_404(client):
    r = client.post("/api/clipboard/999999/actions", json={"action": "translate"})
    assert r.status_code == 404


def test_secret_flagged_content_blocks_action_without_ack(client):
    item_id = _upload(client, "token ghp_" + "a" * 36)
    r = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "translate"})
    assert r.status_code == 409


def test_secret_flagged_content_allowed_with_ack(client):
    item_id = _upload(client, "token ghp_" + "a" * 36)
    r = client.post(f"/api/clipboard/{item_id}/actions",
                     json={"action": "translate", "acknowledgeSecret": True})
    assert r.status_code == 200


def test_explain_and_simplify_actions_work(client):
    item_id = _upload(client, "This introduces a subtle race condition.")
    for action in ("explain", "simplify", "explain-simple", "summarize", "breakdown", "breakdown-target", "skeleton", "vocabulary"):
        r = client.post(f"/api/clipboard/{item_id}/actions", json={"action": action})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "completed"


def test_diagram_action_extracts_clean_mermaid_from_a_wrapped_response(client, fake_provider):
    """architecture.md's diagram action -- the *stored* (and cached) result
    is the bare Mermaid source, not whatever wrapper prose the model added,
    since that's what both the CLI and the Web UI's renderer expect."""
    content = "user submits form, server validates, then either saves or rejects"
    fake_provider.responses[content] = (
        "Sure, here's the diagram:\n"
        "```mermaid\n"
        "flowchart TD\n"
        "  A[Submit] --> B{Valid?}\n"
        "  B -->|yes| C[Save]\n"
        "  B -->|no| D[Reject]\n"
        "```\n"
        "Let me know if you'd like changes!"
    )
    item_id = _upload(client, content)

    r = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "diagram"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["result"] == "flowchart TD\n  A[Submit] --> B{Valid?}\n  B -->|yes| C[Save]\n  B -->|no| D[Reject]"
    assert "```" not in body["result"]


def test_diagram_type_parameter_is_accepted(client):
    item_id = _upload(client, "a simple request/response exchange")
    r = client.post(
        f"/api/clipboard/{item_id}/actions",
        json={"action": "diagram", "parameters": {"diagramType": "sequence"}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["parameters"]["diagramType"] == "sequence"


def test_invalid_diagram_type_rejected(client):
    item_id = _upload(client, "hello")
    r = client.post(
        f"/api/clipboard/{item_id}/actions",
        json={"action": "diagram", "parameters": {"diagramType": "pie"}},
    )
    assert r.status_code == 400


def test_configured_prompt_override_reaches_the_provider(client, settings, fake_provider, tmp_path):
    """architecture.md section 18.2, end to end: a [prompts] override
    configured on Settings actually changes what gets sent to the AI
    provider, not just what build_prompt() returns in isolation (covered
    separately in test_actions_registry.py) -- this is the wiring through
    run_action that only an integration test can see."""
    action_dir = tmp_path / "translate"
    action_dir.mkdir()
    (action_dir / "v2-custom.txt").write_text("CUSTOM MARKER PROMPT for {target_language}")
    settings.prompts.dir = str(tmp_path)
    settings.prompts.versions = {"translate": "v2-custom"}

    item_id = _upload(client, "hello world")
    r = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "translate"})
    assert r.status_code == 200, r.text

    assert len(fake_provider.calls) == 1
    assert "CUSTOM MARKER PROMPT" in fake_provider.calls[0].prompt


def test_unconfigured_action_version_falls_back_to_bundled_default(client, settings, fake_provider, tmp_path):
    """Configuring a version for one action must not disturb another
    action that isn't listed in [prompts.versions]."""
    settings.prompts.dir = str(tmp_path)
    settings.prompts.versions = {"diagram": "v2-not-relevant-here"}

    item_id = _upload(client, "hello world")
    r = client.post(f"/api/clipboard/{item_id}/actions", json={"action": "translate"})
    assert r.status_code == 200, r.text
    assert "Translate the text between the markers" in fake_provider.calls[0].prompt
