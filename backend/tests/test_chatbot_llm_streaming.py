import json

import pytest

from backend.services.chatbot.llm_client import ChatbotLLMClient


class FakeStreamResponse:
    status_code = 200

    def iter_lines(self, decode_unicode=True):
        chunks = [
            {"choices": [{"delta": {"content": "첫 "}, "finish_reason": None}], "usage": None},
            {"choices": [{"delta": {"content": "답변"}, "finish_reason": "stop"}], "usage": None},
            {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}},
        ]
        for chunk in chunks:
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}"
        yield "data: [DONE]"


def test_stream_reply_emits_openai_text_deltas(monkeypatch):
    client = ChatbotLLMClient()
    client.api_key = "test"
    monkeypatch.setattr(client, "_consume_shared_usage", lambda *args: None)
    monkeypatch.setattr(
        "backend.services.chatbot.llm_client.requests.post",
        lambda *args, **kwargs: FakeStreamResponse(),
    )
    deltas = []

    result = client.stream_reply(
        system_prompt="system",
        user_message="질문",
        user_id="user-1",
        auth_header="Bearer test",
        function_schemas=[],
        history=[],
        on_delta=deltas.append,
    )

    assert deltas == ["첫 ", "답변"]
    assert result["reply"] == "첫 답변"
    assert result["usage"]["total_tokens"] == 12


def test_stream_reply_accumulates_tool_call_argument_deltas(monkeypatch):
    class FakeToolStreamResponse:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            chunks = [
                {"choices": [{"delta": {"tool_calls": [{
                    "index": 0,
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "get_portfolio_summary", "arguments": "{\"broker_"},
                }]}, "finish_reason": None}]},
                {"choices": [{"delta": {"tool_calls": [{
                    "index": 0,
                    "function": {"arguments": "env\":\"REAL\"}"},
                }]}, "finish_reason": "tool_calls"}]},
            ]
            for chunk in chunks:
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}"
            yield "data: [DONE]"

    client = ChatbotLLMClient()
    client.api_key = "test"
    monkeypatch.setattr(client, "_consume_shared_usage", lambda *args: None)
    monkeypatch.setattr(
        "backend.services.chatbot.llm_client.requests.post",
        lambda *args, **kwargs: FakeToolStreamResponse(),
    )

    result = client.stream_reply(
        system_prompt="system",
        user_message="자산 알려줘",
        user_id="user-1",
        auth_header="Bearer test",
        function_schemas=[],
        history=[],
        on_delta=lambda text: None,
    )

    assert result["tool_calls"] == [{
        "id": "call-1",
        "type": "function",
        "function": {
            "name": "get_portfolio_summary",
            "arguments": "{\"broker_env\":\"REAL\"}",
        },
    }]


def test_stream_reply_rejects_error_event_after_partial_delta(monkeypatch):
    class FakeErrorStreamResponse:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"부분 "}}]}'
            yield 'data: {"error":{"message":"secret provider detail"}}'

    client = ChatbotLLMClient()
    client.api_key = "test"
    monkeypatch.setattr(client, "_consume_shared_usage", lambda *args: None)
    monkeypatch.setattr(
        "backend.services.chatbot.llm_client.requests.post",
        lambda *args, **kwargs: FakeErrorStreamResponse(),
    )
    deltas = []

    with pytest.raises(RuntimeError) as raised:
        client.stream_reply(
            system_prompt="system",
            user_message="질문",
            user_id="user-1",
            auth_header="Bearer test",
            function_schemas=[],
            history=[],
            on_delta=deltas.append,
        )

    assert deltas == ["부분 "]
    assert "secret provider detail" not in str(raised.value)


def test_stream_reply_rejects_eof_without_done(monkeypatch):
    class FakeEarlyEofResponse:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"미완성"}}]}'

    client = ChatbotLLMClient()
    client.api_key = "test"
    monkeypatch.setattr(client, "_consume_shared_usage", lambda *args: None)
    monkeypatch.setattr(
        "backend.services.chatbot.llm_client.requests.post",
        lambda *args, **kwargs: FakeEarlyEofResponse(),
    )

    with pytest.raises(RuntimeError, match="비정상 종료"):
        client.stream_reply(
            system_prompt="system",
            user_message="질문",
            user_id="user-1",
            auth_header="Bearer test",
            function_schemas=[],
            history=[],
            on_delta=lambda text: None,
        )


def test_stream_reply_prioritizes_tool_mode_for_mixed_delta(monkeypatch):
    class FakeMixedStreamResponse:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            chunk = {
                "choices": [{
                    "delta": {
                        "content": "중간 설명",
                        "tool_calls": [{
                            "index": 0,
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "get_portfolio_summary",
                                "arguments": "{}",
                            },
                        }],
                    },
                    "finish_reason": "tool_calls",
                }],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}"
            yield "data: [DONE]"

    client = ChatbotLLMClient()
    client.api_key = "test"
    monkeypatch.setattr(client, "_consume_shared_usage", lambda *args: None)
    monkeypatch.setattr(
        "backend.services.chatbot.llm_client.requests.post",
        lambda *args, **kwargs: FakeMixedStreamResponse(),
    )
    deltas = []

    result = client.stream_reply(
        system_prompt="system",
        user_message="자산 알려줘",
        user_id="user-1",
        auth_header="Bearer test",
        function_schemas=[],
        history=[],
        on_delta=deltas.append,
    )

    assert deltas == []
    assert result["tool_calls"][0]["function"]["name"] == "get_portfolio_summary"


def test_stream_reply_http_error_does_not_expose_provider_body(monkeypatch):
    class FakeHttpErrorResponse:
        status_code = 429
        text = "secret provider body"

    client = ChatbotLLMClient()
    client.api_key = "test"
    monkeypatch.setattr(client, "_consume_shared_usage", lambda *args: None)
    monkeypatch.setattr(
        "backend.services.chatbot.llm_client.requests.post",
        lambda *args, **kwargs: FakeHttpErrorResponse(),
    )

    with pytest.raises(RuntimeError) as raised:
        client.stream_reply(
            system_prompt="system",
            user_message="질문",
            user_id="user-1",
            auth_header="Bearer test",
            function_schemas=[],
            history=[],
            on_delta=lambda text: None,
        )

    assert "HTTP 429" in str(raised.value)
    assert "secret provider body" not in str(raised.value)
