"""대화 맥락 관리 — 사용자 메시지·에이전트 결과를 세션 동안 유지.

인메모리 전용 (DB 금지). 최근 N턴을 보관해 "지금 무슨 일을 하는가"를 안다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationContext:
    """짧은 대화 히스토리를 기록한다. turn이 쌓이면 앞에서부터 버린다."""

    max_turns: int = 10
    turns: list[dict] = field(default_factory=list)

    def add_user(self, message: str) -> None:
        self.turns.append({"role": "user", "content": message})
        self._trim()

    def add_agent(self, message: str) -> None:
        self.turns.append({"role": "agent", "content": message})
        self._trim()

    def history(self) -> list[dict]:
        return list(self.turns)

    def last_user_message(self) -> str:
        for t in reversed(self.turns):
            if t["role"] == "user":
                return t["content"]
        return ""

    def _trim(self) -> None:
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]