import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import llm


def test_llm_call_returns_string_and_marks_cache():
    # 실제 API 호출 없이: 캐시 폴백 경로만 검증
    llm._CLIENT = None  # 클라이언트 없음 → 폴백
    out = llm.llm_call("테스트 질문", cache_key="test")
    assert isinstance(out, str)
    assert len(out) > 0


def test_llm_cache_hit_uses_cached():
    llm._CLIENT = None
    from app import llm as m
    m._CACHE = {"test-key": "캐시된 답변"}
    assert m.llm_call("테스트", cache_key="test-key") == "캐시된 답변"