"""Verify the grammar-constrained request path of LlamaServerClient.

We don't need a real llama-server: httpx.MockTransport intercepts the POST,
captures the JSON body, and returns a canned completion. This proves the
client sends the ``response_format`` json_schema block (which llama-server
compiles to a GBNF grammar -- docs/DE-RISKING.md §3) when and only when a
schema is supplied, and that the scripted fake tolerates the new kwarg.
"""

from __future__ import annotations

import httpx

from src.orchestrator.llm_client import FakeLLMClient, LlamaServerClient


def _client_with_capture():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"hypothesis": "x"}'}}]})

    client = LlamaServerClient(base_url="http://cage.test")
    client.client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://cage.test")
    return client, captured


def test_json_schema_becomes_response_format():
    client, captured = _client_with_capture()
    schema = {"type": "object", "properties": {"hypothesis": {"type": "string"}}}
    out = client.complete("prompt", json_schema=schema)

    assert out == '{"hypothesis": "x"}'
    rf = captured["json"]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["schema"] == schema
    assert rf["json_schema"]["strict"] is True


def test_no_schema_means_no_response_format():
    client, captured = _client_with_capture()
    client.complete("prompt")  # no json_schema
    assert "response_format" not in captured["json"]


def test_seed_is_forwarded_when_given():
    client, captured = _client_with_capture()
    client.complete("prompt", seed=42)
    assert captured["json"]["seed"] == 42


def test_fake_client_accepts_and_ignores_schema():
    fake = FakeLLMClient(script=['{"ok": true}'])
    # Must not raise on the json_schema kwarg (Protocol compatibility).
    out = fake.complete("prompt", json_schema={"type": "object"})
    assert out == '{"ok": true}'
