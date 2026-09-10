"""Claude 호출 + 캐시 폴백 (장면 3·4 공용).

원칙: 라이브 호출이 기본, 캐시는 네트워크/API 장애 시 자동 폴백으로만.
"""
import os

_CLIENT = None
_CACHE = {}   # cache_key → 답변 (런타임 인메모리, DB 아님)

try:
    import anthropic
    _api_key = os.environ.get("ANTHROPIC_API_KEY")
    if _api_key:
        _CLIENT = anthropic.Anthropic(api_key=_api_key)
except Exception:
    _CLIENT = None


def llm_call(prompt: str, cache_key: str = "") -> str:
    """Claude 호출. 성공 시 캐시 저장, 실패 시 캐시 히트/기본 메시지 폴백."""
    if cache_key and cache_key in _CACHE:
        return _CACHE[cache_key]

    if _CLIENT is not None:
        try:
            resp = _CLIENT.messages.create(
                model=_get_model(),
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = resp.content[0].text
            if cache_key:
                _CACHE[cache_key] = answer
            return answer
        except Exception:
            pass  # 폴백

    if cache_key:
        if cache_key in _CACHE:
            return _CACHE[cache_key]
        # cache_key가 지정된 호출의 실패/캐시 미스 → 기본 메시지 폴백 (지시 002 완료 조건)
        return "LLM 호출에 실패했습니다. 잠시 후 다시 시도해 주세요."
    # cache_key가 없는 호출은 명시적으로 실패를 알린다 (호출부가 자체 처리)
    raise RuntimeError("LLM 호출 실패 (캐시 없음)")


def _get_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")