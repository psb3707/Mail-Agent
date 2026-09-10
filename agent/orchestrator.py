"""오케스트레이터 — LLM이 JSON으로 도구를 선택하고 하네스가 실행하는 멀티스텝 루프.

도구 호출 JSON 규약 (LLM이 반환):
    {"tool": "get_case_emails", "arguments": {"case_id": "c-m0001"}}   # 도구 호출
    {"reply": "최종 답변 텍스트"}                                       # 종료

루프:
    사용자 메시지
      → LLM: 도구 선택(JSON)
      → 하네스: 실행 → 결과
      → 결과를 컨텍스트에 기록 (context.add_step)
      → LLM: "계속 도구 호출 or 최종 응답"
      → (반복, 최대 max_steps) → 최종 응답

원칙:
- 라이브 LLM 호출이 기본 (app/llm 규약: llm_call(prompt, cache_key="") -> str)
- LLM 실패/비JSON → 규칙 기반 폴백 (기존 manager의 키워드 라우팅 재사용)
- 저장은 인메모리 (DB 금지)
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from agent.context import ConversationContext
from agent.harness import ToolHarness

# LLM 규약 (app/llm과 동일): callable(prompt: str, cache_key: str = "") -> str
LlmCall = Callable[..., str]

# 도구 이름 → 사용자 메시지에서 인자를 뽑는 규칙 (폴백용)
_ID_PATTERNS = {
    "get_case_emails": r"c-[a-z0-9]+",
    "get_attachment_text": r"a\d+",
}

# 메시지 키워드 → 기본 도구 (폴백 라우팅)
_KEYWORD_TOOL = [
    (("건", "트리", "분류"), "get_tree"),
    (("타임라인", "메일", "이메일"), "get_case_emails"),
    (("첨부", "내용", "본문"), "get_attachment_text"),
]


class Orchestrator:
    """멀티스텝 도구 호출 루프 오케스트레이터.

    - harness: ToolHarness — 등록된 스킬 목록·실행을 담당
    - llm_call: LLM 호출 (라이브 기본; 실패 시 규칙 폴백)
    - context: ConversationContext — 대화+도구 이력 (선택)
    - max_steps: 최대 루프 횟수 (기본 4, 초과 시 강제 종료)
    """

    def __init__(
        self,
        harness: ToolHarness,
        llm_call: LlmCall | None = None,
        context: ConversationContext | None = None,
        max_steps: int = 4,
    ):
        self.harness = harness
        self.llm_call = llm_call
        self.context = context or ConversationContext()
        self.max_steps = max(1, max_steps)

    # --- 공개 루프 -----------------------------------------------------------

    def run(self, message: str) -> str:
        """에이전트 루프 실행 → 최종 응답 문자열 반환 (항상 문자열)."""
        self.context.add_user(message)

        last_result = ""
        for _ in range(self.max_steps):
            decision = self._ask_llm(message, last_result)

            if "reply" in decision:
                reply = str(decision.get("reply", "")).strip()
                if reply:
                    self.context.add_agent(reply)
                    return reply
                # 빈 reply → 무한 루프 방지, 마지막 결과 요약으로 종료

            tool = decision.get("tool")
            if tool and self.harness.has(tool):
                args = decision.get("arguments") or {}
                try:
                    result = self.harness.execute(tool, args)
                except Exception as exc:  # 하네스 실행 중 오류 → 결과로 기록 후 계속
                    result = f"(도구 오류: {exc})"
                self.context.add_step(tool, result)
                last_result = self._render_result(tool, result)
                continue

            # tool이 없거나 미등록이면 reply가 없었으므로 폴백으로 종료
            break

        fallback = self._rule_fallback(message)
        self.context.add_agent(fallback)
        return fallback

    # --- 내부: LLM 호출 + JSON 파싱 ------------------------------------------

    def _ask_llm(self, message: str, last_result: str) -> dict[str, Any]:
        """LLM에게 도구 선택을 묻고 JSON dict로 파싱한다. 실패 시 규칙 폴백."""
        prompt = self._tool_prompt(message, last_result)
        if self.llm_call is not None:
            try:
                raw = self.llm_call(prompt)
                parsed = self._parse_json(raw)
                if parsed is not None:
                    return parsed
            except Exception:
                pass  # 폴백
        return self._rule_decision(message)

    def _tool_prompt(self, message: str, last_result: str) -> str:
        """도구 선택 프롬프트 — 스킬 목록 + 대화/도구 이력 + JSON 출력 형식 지시."""
        skills = self.harness.list_skills()
        lines: list[str] = ["사용자 메시지에 답하기 위해 다음 도구 중 하나를 JSON으로 호출하십시오."]
        for s in skills:
            lines.append(f"- {s['name']}: {s['description']}")
        lines.append("")
        lines.append("대화·도구 이력:")
        lines.append(self.context.summary())
        if last_result:
            lines.append(f"직전 도구 결과: {last_result}")
        lines.append("")
        lines.append(
            '{"tool": "도구이름", "arguments": {...}} 또는 '
            '도구 없이 답할 수 있으면 {"reply": "답변"} — JSON 외 텍스트 금지.'
        )
        return "\n".join(lines)

    def _parse_json(self, raw: str) -> dict[str, Any] | None:
        """LLM 출력에서 JSON dict를 추출한다. 실패/형식 오류면 None."""
        if not raw or not isinstance(raw, str):
            return None
        text = raw.strip()
        # ```json ... ``` 코드 펜스 제거
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        # JSON 이외 텍스트 → reply 객체로 간주 (LLM이 그냥 답한 경우)
        if not text.startswith("{") and text.strip():
            return {"reply": text}
        return None

    def _render_result(self, tool: str, result: Any) -> str:
        """도구 실행 결과를 다음 LLM 입력용 요약 문자열로."""
        if isinstance(result, dict):
            if tool == "get_tree":
                cases = result.get("cases", [])
                return "건 트리: " + " / ".join(
                    c.get("title", c.get("id", "?")) for c in cases[:5]
                )
            return json.dumps(result, ensure_ascii=False)[:400]
        if isinstance(result, list):
            lines = [f"- {m.get('sent_at', '')[:10]} {m.get('subject', '')}" for m in result[:5]]
            return "건 타임라인:\n" + "\n".join(lines) if lines else "(결과 없음)"
        return str(result)[:400] if result else "(결과 없음)"

    # --- 규칙 폴백 (LLM 없이도 동작) -----------------------------------------

    def _rule_decision(self, message: str) -> dict[str, Any]:
        """LLM 없이 키워드로 도구/인자를 결정한다. (기존 manager의 _pick_tool 계승)"""
        low = message.lower()
        for keywords, tool in _KEYWORD_TOOL:
            if any(k in low for k in keywords):
                args: dict[str, Any] = {}
                pat = _ID_PATTERNS.get(tool)
                if pat:
                    m = re.search(pat, low)
                    if m:
                        args[
                            "case_id" if tool == "get_case_emails" else "attachment_id"
                        ] = m.group(0)
                return {"tool": tool, "arguments": args}
        return {"reply": _FALLBACK_GUIDE}

    def _rule_fallback(self, message: str) -> str:
        """규칙 폴백으로 최종 응답 텍스트를 만든다 (루프 실패 시)."""
        decision = self._rule_decision(message)
        if "reply" in decision:
            return str(decision["reply"])
        tool = decision["tool"]
        args = decision.get("arguments") or {}
        try:
            result = self.harness.execute(tool, args)
            self.context.add_step(tool, result)
            return self._render_result(tool, result)
        except Exception as exc:
            return f"요청을 처리하지 못했습니다. (오류: {exc})"


_FALLBACK_GUIDE = (
    "메일 관리 Agent입니다. '건 트리', 'c-m0001 타임라인', 'a001 첨부 내용'처럼 "
    "물어보시면 분류된 건과 메일을 안내해 드립니다."
)