"""도구 실행 하네스 — 스킬(도구)의 등록·목록·실행을 담당.

오케스트레이터(지시-010)가 이 하네스를 통해 도구를 실행한다.
스킬은 `agent/skills.py`에서 데이터로 정의되고, 여기서는 **이름 → 스킬** 매핑만 관리한다.

원칙:
- 순수 실행 (부작용 없음, 인메모리) — DB 없음
- 분류AI 어댑터 교체는 `set_classifier`로 지원 (실제 분류AI 도착 시 즉시 교체)
"""
from __future__ import annotations

from typing import Any

from agent.skills import Skill


class ToolHarness:
    """스킬(도구) 레지스트리 + 실행기.

    - register(skill): 스킬을 등록 (같은 이름은 덮어씀)
    - list_skills(): LLM이 읽을 name·description 목록 반환
    - execute(name, arguments): 이름으로 스킬을 찾아 실행. 없으면 KeyError.
    - set_classifier(impl): 분류AI 어댑터 교체. 이미 등록된 스킬의 handler가
      새 어댑터를 쓰도록 default_skills()로 다시 등록한다.
    """

    def __init__(self, skills: list[Skill] | None = None):
        self._skills: dict[str, Skill] = {}
        if skills:
            for s in skills:
                self.register(s)

    def register(self, skill: Skill) -> None:
        """스킬 하나를 등록한다. 같은 이름이면 교체(멱등)."""
        self._skills[skill.name] = skill

    def list_skills(self) -> list[dict[str, Any]]:
        """LLM이 도구 선택 시 읽는 name·description·parameters 요약 목록."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            }
            for s in self._skills.values()
        ]

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """이름으로 스킬을 찾아 실행한다. 없는 스킬이면 KeyError를 일으킨다."""
        if name not in self._skills:
            raise KeyError(f"등록되지 않은 스킬: {name!r}. 사용 가능: {sorted(self._skills)}")
        args = {} if arguments is None else arguments
        if not isinstance(args, dict):
            raise ValueError("도구 인자는 JSON 객체여야 합니다.")
        skill = self._skills[name]
        schema = skill.parameters
        properties = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in args:
                raise ValueError(f"필수 인자가 없습니다: {required}")
        for key, value in args.items():
            if key not in properties:
                if schema.get("additionalProperties") is False:
                    raise ValueError(f"허용하지 않는 인자: {key}")
                continue
            if properties[key].get("type") == "string" and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{key}에는 비어 있지 않은 문자열이 필요합니다.")
        return skill.execute(args)

    def has(self, name: str) -> bool:
        """스킬 등록 여부 확인."""
        return name in self._skills

    def set_classifier(self, impl) -> None:
        """분류AI 어댑터를 교체하고, 기본 스킬을 새 어댑터에 맞춰 다시 만든다.

        default_skills는 classifier를 클로저로 캡처하므로, 스킬 전체를 교체해야
        새 어댑터가 실제로 동작한다. (skills.py의 default_skills 참조)
        """
        from agent.skills import default_skills

        new_skills = default_skills(impl)
        self._skills = {s.name: s for s in new_skills}