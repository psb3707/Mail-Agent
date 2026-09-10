"""프롬프트 시스템 — 관리 Agent의 프롬프트 중앙화.

관리 Agent가 쓰는 시스템 프롬프트·도구 설명·출력 형식·예시를 한곳에 모아
오케스트레이터(지시-010)가 쉽게 조립하도록 제공한다.

설계: docs/specs/2026-09-10-manager-agent-skeleton.md (4 컴포넌트)
원칙:
- 프롬프트 언어는 한국어.
- 이 모듈은 **함수·상수만** 제공하며 orchestrator/manager를 수정하지 않는다.
  지시-010이 이 모듈을 import해서 사용한다 (계약만 정의).
"""
from __future__ import annotations

from typing import Any

# --- 시스템 프롬프트 -------------------------------------------------------

SYSTEM_PROMPT: str = (
    "당신은 사내 메일함을 건(件) 단위로 정리해 주는 메일 관리 Agent입니다. "
    "사용자와 채팅으로 대화하며 메일 관리(검색·요약·알림 정리·답장 초안)를 돕습니다. "
    "규칙으로는 판단할 수 없는 것(같은 건인가·최신본인가)은 도구 조회 결과를 근거로 설명하고, "
    "추측만으로 답하지 마십시오."
)

# --- JSON 출력 형식 안내 ----------------------------------------------------

JSON_FORMAT_GUIDE: str = (
    '도구를 호출해야 하면 다음 JSON을 반환하십시오: '
    '{"tool": "도구이름", "arguments": {"인자명": 값}}. '
    '도구 호출 없이 답할 수 있으면 다음 JSON을 반환하십시오: {"reply": "사용자에게 할 답변"}. '
    "JSON 외의 다른 텍스트는 포함하지 마십시오."
)

# --- 폴백 응답 -------------------------------------------------------------

FALLBACK_REPLY: str = "죄송합니다. 지금은 답변을 만들지 못했습니다. 잠시 후 다시 시도해 주세요."

# --- 조립 함수 -------------------------------------------------------------


def build_tool_prompt(
    skill_descriptions: list[dict[str, Any]],
    history: list[dict[str, str]],
) -> str:
    """도구 선택 프롬프트를 조립한다.

    스킬(도구) 목록 + 대화 이력 + JSON 출력 형식 지시를 하나의 지시문으로 만든다.

    - skill_descriptions: 각 도구의 {name, description(, parameters?)} dict 목록
    - history: [{"role": "user"|"assistant", "content": str}, ...] 대화 이력
    """
    lines: list[str] = ["다음 도구 중 하나를 골라 JSON으로 호출하십시오."]
    for skill in skill_descriptions:
        name = skill.get("name", "?")
        desc = skill.get("description", "")
        lines.append(f"- {name}: {desc}")
    lines.append("")
    if history:
        lines.append("대화 이력:")
        for turn in history:
            role = turn.get("role", "?")
            content = turn.get("content", "")
            lines.append(f"[{role}] {content}")
        lines.append("")
    lines.append("호출 형식:")
    lines.append(JSON_FORMAT_GUIDE)
    return "\n".join(lines)


def build_result_prompt(
    last_result: str,
    history: list[dict[str, str]],
) -> str:
    """도구 결과를 보고 '계속 or 종료'를 결정하는 프롬프트.

    - last_result: 직전 도구 실행 결과 (문자열)
    - history: [{"role", "content"}, ...] 대화 이력
    """
    lines: list[str] = [
        "직전 도구 실행 결과를 바탕으로, 추가로 호출할 도구가 있으면 JSON으로, "
        "없으면 사용자에게 답할 최종 응답을 JSON으로 반환하십시오.",
        "",
        f"직전 도구 결과:\n{last_result}",
    ]
    if history:
        lines.append("")
        lines.append("대화 이력:")
        for turn in history:
            role = turn.get("role", "?")
            content = turn.get("content", "")
            lines.append(f"[{role}] {content}")
    lines.append("")
    lines.append("호출 형식:")
    lines.append(JSON_FORMAT_GUIDE)
    return "\n".join(lines)
