"""관리 Agent — 챗 방식 메일 관리 도우미 (오케스트레이터 기반).

대화 맥락 → 오케스트레이터(도구 선택 → 하네스 실행 → 응답) → 사용자 응답.
지시-010 리팩터: 기존 1턴 루프(`_pick_tool`·직접 도구 호출)를 `Orchestrator.run()`으로 대체.
LLM(라이브 기본)이 JSON으로 도구를 선택하고, 실패 시 규칙 폴백으로 동작한다.
"""
from __future__ import annotations

from typing import Callable

from agent.classifier_adapter import ClassifierAdapter
from agent.context import ConversationContext
from agent.harness import ToolHarness
from agent.orchestrator import Orchestrator
from agent.skills import default_skills, mailbox_skills

# LLM 규약 (app/llm과 동일): callable(prompt: str, cache_key: str = "") -> str
LlmCall = Callable[..., str]


class ManagerAgent:
    """챗 방식 관리 Agent — 오케스트레이터를 직접 다룰 필요 없이 run()만 노출."""

    def __init__(
        self,
        classifier: ClassifierAdapter | None = None,
        context: ConversationContext | None = None,
        llm_call: LlmCall | None = None,
        max_steps: int = 4,
        indexed: dict | None = None,
    ):
        self.classifier = classifier or ClassifierAdapter()
        self.context = context or ConversationContext()
        # 라이브 LLM이 기본 — 없으면(골격 단계) 규칙 폴백으로 동작
        self.llm_call = llm_call
        # 지시-009 하네스: 분류AI 어댑터에 연결된 기본 스킬 4개 등록
        self.harness = ToolHarness(mailbox_skills(indexed, llm_call) if indexed is not None else default_skills(self.classifier))
        self.orchestrator = Orchestrator(
            harness=self.harness,
            llm_call=self.llm_call,
            context=self.context,
            max_steps=max_steps,
        )

    def run(self, message: str) -> str:
        """에이전트 루프 실행 → 최종 응답 문자열 (하위 호환 인터페이스 유지)."""
        return self.orchestrator.run(message)

    def run_result(self, message: str) -> dict:
        """Structured answer metadata for the web app; context is request-local."""
        answer = self.run(message)
        return {"attachment": None, "evidence": [], "mail_ids": [],
                "cached": False,
                "fallback": self.orchestrator.used_fallback and not bool(self.orchestrator.response),
                **self.orchestrator.response, "answer": answer}
