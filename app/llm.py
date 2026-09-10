"""OpenRouter 호출 + 캐시 폴백 (장면 3·4 공용, 지시-017).

원칙: 라이브 호출이 기본, 캐시는 네트워크/API 장애 시 자동 폴백으로만.
- API 키: 환경변수 OPENROUTER_API_KEY 또는 워크스페이스 루트의 .env (키 없으면 폴백 동작)
- 모델: OPENROUTER_MODEL (기본 anthropic/claude-sonnet-4-5)
- 엔드포인트: https://openrouter.ai/api/v1/chat/completions (OpenAI-호환)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.request

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "anthropic/claude-sonnet-4-5"

_CACHE: dict[str, str] = {}  # cache_key → 답변 (런타임 인메모리, DB 아님)


def _load_dotenv() -> None:
    """프로젝트 루트의 .env에서 KEY=VALUE를 읽어 환경변수에 반영 (기존 값 우선)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('\"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _api_key() -> str | None:
    return os.environ.get("OPENROUTER_API_KEY") or None


def _get_model() -> str:
    return os.environ.get("OPENROUTER_MODEL", _DEFAULT_MODEL)


def parse_openrouter_response(raw: str) -> str | None:
    """OpenRouter 응답 JSON에서 choices[0].message.content를 추출한다.

    형식: {"choices": [{"message": {"content": "..."}}], ...}
    파싱 실패/필드 누락 시 None (→ 호출부가 폴백).
    """
    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        return content if isinstance(content, str) and content else None
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return None


def call_openrouter(prompt: str, model: str | None = None) -> str:
    """OpenRouter /chat/completions 호출. 실패 시 예외를 던진다 (호출부가 폴백)."""
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 미설정")

    body = json.dumps({
        "model": model or _get_model(),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }).encode("utf-8")

    req = urllib.request.Request(
        _API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")

    answer = parse_openrouter_response(raw)
    if answer is None:
        raise RuntimeError("OpenRouter 응답 형식 오류")
    return answer


def llm_call(prompt: str, cache_key: str = "") -> str:
    """OpenRouter 호출. 성공 시 캐시 저장, 실패 시 캐시 히트/기본 메시지 폴백.

    시그니처 유지: (prompt, cache_key="") -> str — search·versions·orchestrator 소비.
    """
    if cache_key and cache_key in _CACHE:
        return _CACHE[cache_key]

    if _api_key():
        try:
            answer = call_openrouter(prompt)
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
    raise RuntimeError("LLM 호출 실패 (키 없음/캐시 없음)")