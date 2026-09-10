"""대화 맥락 관리 — 사용자 메시지·에이전트 결과·도구 실행 이력을 세션 동안 유지.

인메모리 전용 (DB 금지). 최근 N턴·N스텝을 보관해 "지금 무슨 일을 하는가"를 안다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationContext:
    """짧은 대화 히스토리 + 도구 실행 이력을 기록한다.

    - turns: 사용자/에이전트 대화 (max_turns 초과 시 앞에서부터 버림)
    - steps: 도구 실행 이력 (max_steps 초과 시 앞에서부터 버림) — 오케스트레이터가 기록
    """

    max_turns: int = 10
    max_steps: int = 20
    turns: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)

    def add_user(self, message: str) -> None:
        self.turns.append({"role": "user", "content": message})
        self._trim_turns()

    def add_agent(self, message: str) -> None:
        self.turns.append({"role": "agent", "content": message})
        self._trim_turns()

    def history(self) -> list[dict]:
        return list(self.turns)

    def add_step(self, tool: str, result: Any) -> None:
        """도구 실행 이력 한 건을 기록한다 (오케스트레이터가 호출)."""
        self.steps.append({"tool": tool, "result": result})
        self._trim_steps()

    def steps_history(self) -> list[dict]:
        """최근 도구 실행 이력 목록."""
        return list(self.steps)

    def summary(self, max_entries: int = 3) -> str:
        """대화+도구 이력을 간략 요약한다 (오케스트레이터 프롬프트용).

        최근 대화 턴과 최근 도구 실행 결과를 짧은 텍스트로 합친다.
        """
        parts: list[str] = []
        for t in self.turns[-max_entries:]:
            role = t.get("role", "?")
            content = (t.get("content", "") or "")[:120]
            parts.append(f"[{role}] {content}")
        for s in self.steps[-max_entries:]:
            tool = s.get("tool", "?")
            result = str(s.get("result", ""))[:120]
            parts.append(f"[도구:{tool}] {result}")
        return "\n".join(parts) if parts else "(대화 기록 없음)"

    def last_user_message(self) -> str:
        for t in reversed(self.turns):
            if t["role"] == "user":
                return t["content"]
        return ""

    def _trim_turns(self) -> None:
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def _trim_steps(self) -> None:
        if len(self.steps) > self.max_steps:
            self.steps = self.steps[-self.max_steps:]