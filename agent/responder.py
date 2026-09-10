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
        titles = "\n".join("- **" + c.get("title", c.get("id", "?")) + "**" for c in cases)
        return f"지금 메일함에는 **{len(cases)}건의 업무**가 모여 있어요.\n\n## 업무 모아보기\n\n{titles}" if titles else "아직 모아 둔 업무가 없어요."
    if tool == "case_emails":
        if not result:
            return "이 업무에는 아직 확인할 메일이 없어요."
        lines = [f"- {m.get('sent_at', '')[:10]} {m.get('subject', '')}" for m in result]
        return "업무의 흐름을 시간순으로 모았어요.\n\n## 메일 타임라인\n\n" + "\n".join(lines)
    if tool == "attachment_text":
        return f"확인한 첨부 내용이에요.\n\n{result}" if result else "첨부에서 읽을 수 있는 내용을 찾지 못했어요."
    if tool == "reply":
        return str(result)
    return str(result)