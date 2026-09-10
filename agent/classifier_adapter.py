"""분류AI 연동 어댑터 — 계약 정의 + 목(mock) 구현.

설계서의 인터페이스 계약:
- get_tree() -> dict                     건 트리 전체 구조
- get_case_emails(case_id) -> list[dict] 건에 속한 메일 메타
- get_attachment_text(attachment_id) -> str  첨부 추출 전문

분류AI 본체는 동료 PC가 같은 레포에 구현한다. 이 모듈은 그 **경계**다.
실제 구현이 도착하면 아래 함수들을 실제 분류AI 모듈 호출로 바꾼다 (시그니처 유지).
"""
from __future__ import annotations

from typing import Any, Callable, Protocol


class Classifier(Protocol):
    """분류AI가 반드시 제공해야 하는 인터페이스 (계약)."""

    def get_tree(self) -> dict[str, Any]: ...

    def get_case_emails(self, case_id: str) -> list[dict[str, Any]]: ...

    def get_attachment_text(self, attachment_id: str) -> str: ...


class ClassifierAdapter:
    """분류AI 호출 경계.

    - 구현체가 없어도 동작하도록 `impl`에 기본값(목)을 둔다.
    - 실제 분류AI가 붙으면 `ClassifierAdapter(impl=실제분류AI)`로 교체한다.
    """

    def __init__(self, impl: Classifier | None = None):
        self._impl: Classifier = impl or MockClassifier()

    def get_tree(self) -> dict[str, Any]:
        return self._impl.get_tree()

    def get_case_emails(self, case_id: str) -> list[dict[str, Any]]:
        return self._impl.get_case_emails(case_id)

    def get_attachment_text(self, attachment_id: str) -> str:
        return self._impl.get_attachment_text(attachment_id)


class MockClassifier:
    """분류AI가 아직 없을 때 쓰는 목 — 스모크 테스트용.

    데이터는 index.json과 조회 가능한 최소 구조만 담는다.
    (실제 분류 결과가 아니므로 시연·테스트용으로만 사용)
    """

    _TREE = {
        "root": "메일함",
        "cases": [
            {"id": "c-m0001", "title": "Project N_CX UI/UX 외주"},
            {"id": "c-m0019", "title": "D-MIG 데이터 이관"},
        ],
    }

    _CASE_MAILS = {
        "c-m0001": [
            {"id": "m0001", "subject": "〔Project N_CX〕UI/UX 외주 업체 선정", "sent_at": "2026-05-04"},
            {"id": "m0006", "subject": "〔N_CX〕최종 업체 확정 안내", "sent_at": "2026-05-20"},
        ],
        "c-m0019": [
            {"id": "m0019", "subject": "D-MIG 이관 관련", "sent_at": "2025-11-13"},
        ],
    }

    _ATTACH_TEXT = {
        "a001": "Project N_CX UI/UX 외주 견적 취합 (3차/최종)",
        "a003": "Project N_CX UI/UX 외주 견적 취합 (1차)",
    }

    def get_tree(self) -> dict[str, Any]:
        return self._TREE

    def get_case_emails(self, case_id: str) -> list[dict[str, Any]]:
        return self._CASE_MAILS.get(case_id, [])

    def get_attachment_text(self, attachment_id: str) -> str:
        return self._ATTACH_TEXT.get(attachment_id, "")