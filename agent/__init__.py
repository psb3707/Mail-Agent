"""관리 Agent(메일 관리 도우미) 골격 패키지.

설계: docs/specs/2026-09-10-manager-agent-skeleton.md
원칙:
- 분류AI 본체는 동료 PC가 같은 레포에 구현한다. 여기는 그 **경계(어댑터·목)**만 둔다.
- 라이브 LLM 호출이 기본, 캐시는 폴백 전용 (기존 app/llm 규약 재사용).
- 저장은 인메모리 — DB/SQLite 금지.
"""

from agent.prompts import (
    FALLBACK_REPLY,
    JSON_FORMAT_GUIDE,
    SYSTEM_PROMPT,
    build_result_prompt,
    build_tool_prompt,
)
from agent.manager import ManagerAgent

__all__ = [
    "SYSTEM_PROMPT",
    "JSON_FORMAT_GUIDE",
    "FALLBACK_REPLY",
    "build_tool_prompt",
    "build_result_prompt",
    "ManagerAgent",
]