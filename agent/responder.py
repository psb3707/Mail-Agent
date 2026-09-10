"""응답 생성 — 분류AI 조회 결과를 사용자에게 반환할 텍스트로 정리.

골격 단계에서는 도구 결과를 그대로 요약 문구로 만든다.
(실제 자연어 생성은 app/llm 규약을 재사용해 라이브 호출로 확장한다)
"""
from __future__ import annotations

from typing import Any


def render_tool_result(tool: str, result: Any) -> str:
    """도구 호출 결과를 사용자용 텍스트로 요약한다.

    tool: "tree" | "case_emails" | "attachment_text" | "reply"
    """
    if tool == "tree":
        cases = result.get("cases", []) if isinstance(result, dict) else []
        titles = " / ".join(c.get("title", c.get("id", "?")) for c in cases[:5])
        return f"분류된 건: {titles}" if titles else "분류된 건이 없습니다."
    if tool == "case_emails":
        if not result:
            return "해당 건에 메일이 없습니다."
        lines = [f"- {m.get('sent_at', '')[:10]} {m.get('subject', '')}" for m in result]
        return "건 타임라인:\n" + "\n".join(lines)
    if tool == "attachment_text":
        return f"첨부 내용: {result}" if result else "첨부 내용이 없습니다."
    if tool == "reply":
        return str(result)
    return str(result)