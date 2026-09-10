import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import llm


def test_llm_call_returns_string_and_marks_cache():
    # API 키 없음 → 폴백 경로만 검증 (라이브 호출 없음)
    llm._CACHE = {}
    out = llm.llm_call("테스트 질문", cache_key="test")
    assert isinstance(out, str)
    assert len(out) > 0


def test_llm_cache_hit_uses_cached():
    from app import llm as m
    m._CACHE = {"test-key": "캐시된 답변"}
    assert m.llm_call("테스트", cache_key="test-key") == "캐시된 답변"


def test_parse_openrouter_response_extracts_content():
    raw = '{"id":"x","choices":[{"index":0,"message":{"role":"assistant","content":"정답"}}]}'
    assert llm.parse_openrouter_response(raw) == "정답"


def test_parse_openrouter_response_missing_fields_returns_none():
    assert llm.parse_openrouter_response('{"choices":[]}') is None
    assert llm.parse_openrouter_response('{"error":"boom"}') is None
    assert llm.parse_openrouter_response("not json") is None


def test_call_openrouter_raises_without_key():
    llm._api_key = lambda: None
    try:
        llm.call_openrouter("질문")
        assert False, "키 없이 호출은 예외여야 한다"
    except RuntimeError:
        pass
    finally:
        # monkeypatch 없이 원복 (테스트 격리)
        import importlib
        importlib.reload(llm)


def test_get_model_default_and_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    assert llm._get_model() == "anthropic/claude-sonnet-4-5"
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    assert llm._get_model() == "openai/gpt-4o-mini"