"""관리 Agent 오케스트레이터 — 에이전트 루프.

대화 맥락 → 도구 선택 → 분류AI 어댑터 호출 → 응답 생성.
LLM(라이브 기본)이 도구를 선택하는 진짜 루프는 총괄PM 지시 후 `_pick_tool`을
LLM 호출로 교체한다. 골격 단계에서는 규칙(키워드) 기반 선택을 스텁으로 둔다.
"""
from __future__ import annotations

from typing import Any, Callable

from agent.classifier_adapter import ClassifierAdapter
from agent.context import ConversationContext
from agent.responder import render_tool_result

# LLM 규약 (app/llm과 동일): callable(prompt: str, cache_key: str = "") -> str
LlmCall = Callable[..., str]


class ManagerAgent:
    """챗 방식 관리 Agent 골격."""

    def __init__(
        self,
        classifier: ClassifierAdapter | None = None,
        context: ConversationContext | None = None,
        llm_call: LlmCall | None = None,
    ):
        self.classifier = classifier or ClassifierAdapter()
        self.context = context or ConversationContext()
        # 라이브 LLM이 기본 — 없으면(골격 단계) 규칙 선택으로 동작
        self.llm_call = llm_call

    def _pick_tool(self, message: str) -> str:
        """자연어 메시지에서 수행할 도구 선택 (스텁).

        규칙 기반 라우팅:
        - '건'/'트리'/'분류' → tree
        - '타임라인'/'메일'/'건의 메일' → case_emails
        - '첨부'/'내용' → attachment_text
        - 그 외 → reply (일반 응답)
        LLM 연동 시 이 함수를 라이브 호출로 교체한다.
        """
        if self.llm_call is not None:
            tool = self.llm_call(
                "사용자 메시지에 적절한 도구를 하나 고르시오. "
                "선택지: tree, case_emails, attachment_text, reply\n"
                f"메시지: {message}\n도구:"
            ).strip()
            if tool in {"tree", "case_emails", "attachment_text", "reply"}:
                return tool
        if any(k in message for k in ("건", "트리", "분류")):
            return "tree"
        if any(k in message for k in ("타임라인", "메일", "이메일")):
            return "case_emails"
        if any(k in message for k in ("첨부", "내용", "본문")):
            return "attachment_text"
        return "reply"

    def run(self, message: str) -> str:
        """에이전트 루프 1턴: 메시지 → 도구 → 결과 → 응답."""
        self.context.add_user(message)

        tool = self._pick_tool(message)
        result: Any

        if tool == "tree":
            result = self.classifier.get_tree()
        elif tool == "case_emails":
            case_id = self._extract_case_id(message)
            result = self.classifier.get_case_emails(case_id)
        elif tool == "attachment_text":
            aid = self._extract_attachment_id(message)
            result = self.classifier.get_attachment_text(aid)
        else:
            result = self._make_reply(message)

        answer = render_tool_result(tool, result)
        self.context.add_agent(answer)
        return answer

    def _extract_case_id(self, message: str) -> str:
        """메시지에서 case id(c-xxxx) 추출. 없으면 기본값."""
        import re

        m = re.search(r"c-[a-z0-9]+", message.lower())
        return m.group(0) if m else "c-m0001"

    def _extract_attachment_id(self, message: str) -> str:
        """메시지에서 첨부 id(a\\d+) 추출. 없으면 기본값."""
        import re

        m = re.search(r"a\d+", message.lower())
        return m.group(0) if m else "a001"

    def _make_reply(self, message: str) -> str:
        """일반 응답 — 골격 단계에서는 안내 문구."""
        return (
            "관리 Agent 골격입니다. '건 트리', 'c-m0001 타임라인', 'a001 첨부 내용' "
            "처럼 물어보세요. (실제 LLM 답변은 총괄PM 지시 후 연결)"
        )