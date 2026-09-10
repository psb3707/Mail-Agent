"""분류AI 연동 어댑터 — 계약 정의 + AI-Ready DB(indexed.json) 기반 기본 구현.

설계서의 인터페이스 계약:
- get_tree() -> dict                     건 트리 전체 구조
- get_case_emails(case_id) -> list[dict] 건에 속한 메일 메타
- get_attachment_text(attachment_id) -> str  첨부 추출 전문

지시-020: 분류AI 산출물(AI-Ready DB = data/indexed.json)을 관리 Agent가 소비하도록
선·후 관계를 바로잡았다. 기본 impl은 IndexedReader로, data/indexed.json을 읽어 조회한다.
실분류AI가 도착하면 ClassifierAdapter(impl=실제분류AI)로 교체한다 (시그니처 유지).
"""
from __future__ import annotations

from typing import Any, Protocol

from agent.indexed_reader import IndexedReader


class Classifier(Protocol):
    """분류AI가 반드시 제공해야 하는 인터페이스 (계약)."""

    def get_tree(self) -> dict[str, Any]: ...

    def get_case_emails(self, case_id: str) -> list[dict[str, Any]]: ...

    def get_attachment_text(self, attachment_id: str) -> str: ...


class ClassifierAdapter:
    """분류AI 호출 경계.

    - 기본 impl은 IndexedReader(indexed.json 기반)다. 파일 없음/손상 시 빈 구조 폴백.
    - 실제 분류AI가 붙으면 ClassifierAdapter(impl=실제분류AI)로 교체한다.
    """

    def __init__(self, impl: Classifier | None = None):
        self._impl: Classifier = impl or IndexedReader()

    def get_tree(self) -> dict[str, Any]:
        return self._impl.get_tree()

    def get_case_emails(self, case_id: str) -> list[dict[str, Any]]:
        return self._impl.get_case_emails(case_id)

    def get_attachment_text(self, attachment_id: str) -> str:
        return self._impl.get_attachment_text(attachment_id)