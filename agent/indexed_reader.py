"""indexed.json(AI-Ready DB) 읽기 전용 리더 — 관리 Agent의 분류 데이터 소비 계층.

파이프라인: 신메일 → build_index.py → 분류AI(건 트리·건별 메일·첨부 텍스트 축적)
  → data/indexed.json → IndexedReader → 관리 Agent 도구(get_tree 등)

- 원칙: **읽기 전용** — indexed.json을 절대 수정하지 않는다.
- 인메모리 1회 로드: 모듈 캐시로 파일을 한 번만 읽고 재사용한다 (매 호출 재로드 금지).
- 폴백: 파일 없음/키 없음 → 빈 구조, 파일 손상(JSON 파싱 실패) → 기본 구조.
  예외를 던지지 않고 빈 결과를 반환한다. (Agent 폴백 체인과 호환)
- case 메일의 메타(제목·발신·시각·첨부)는 indexed.json에 없어 원본
  data/mails.json(읽기 전용)에서 보완한다. indexed.json이 그대로 계약이므로
  mails.json은 메타 조회용 보조 소스 역할만 한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "data" / "indexed.json"
MAILS_PATH = ROOT / "data" / "mails.json"

# 파일 손상 시 돌려줄 기본 구조 (빈 결과)
_EMPTY = {
    "cases": [],
    "attachment_texts": {},
    "version_groups": [],
    "non_cases": [],
    "attachments": [],
}


class IndexedReader:
    """data/indexed.json을 로드해 조회 API를 제공하는 읽기 전용 리더.

    - get_tree() -> dict — cases[]에서 {id, title, mail_ids, attachment_ids, period} 트리
    - get_case_emails(case_id) -> list[dict] — case의 mail_ids → 메일 정보(제목·발신·시각) + 첨부 목록
    - get_attachment_text(attachment_id) -> str — attachment_texts[attachment_id]
    """

    def __init__(self, root: Path | None = None):
        self._root = Path(root) if root else ROOT
        self._store: dict[str, Any] | None = None
        self._mails_by_id: dict[str, Any] = {}

    # --- 로드 (인메모리 1회, 실패 시 빈 구조) --------------------------------

    def _load(self) -> dict[str, Any]:
        """indexed.json + mails.json을 1회 로드해 인메모리 캐시를 만든다.

        파일 없음/키 없음/JSON 손상 어느 경우에도 빈 구조를 반환하며 예외를 던지지 않는다.
        """
        if self._store is not None:
            return self._store

        store = dict(_EMPTY)
        try:
            raw = json.loads(
                (self._root / "data" / "indexed.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            raw = {}
        if isinstance(raw, dict):
            for key in _EMPTY:
                if key in raw:
                    store[key] = raw[key]
        self._store = store

        try:
            mails_raw = json.loads(
                (self._root / "data" / "mails.json").read_text(encoding="utf-8")
            )
            self._mails_by_id = {
                mail["id"]: mail
                for mail in mails_raw.get("mails", [])
                if isinstance(mail, dict) and mail.get("id")
            }
        except (OSError, json.JSONDecodeError, AttributeError):
            self._mails_by_id = {}
        return store

    # --- 공개 API -----------------------------------------------------------

    def get_tree(self) -> dict[str, Any]:
        """건 트리 전체 구조 — cases[]의 재조립 요약만 담는다."""
        store = self._load()
        cases = store.get("cases", [])
        return {
            "root": "메일함",
            "cases": [
                {
                    "id": case.get("id", ""),
                    "title": case.get("title", ""),
                    "mail_ids": list(case.get("mail_ids", [])),
                    "attachment_ids": list(case.get("attachment_ids", [])),
                    "period": list(case.get("period", [])),
                }
                for case in cases
                if isinstance(case, dict)
            ],
        }

    def get_case_emails(self, case_id: str) -> list[dict[str, Any]]:
        """지정한 건의 메일 목록(제목·발신·시각) + 첨부 목록.

        메일 메타는 원본 mails.json(읽기 전용)에서, 첨부 메타는 indexed.json에서 조합한다.
        case를 찾지 못하면 빈 리스트를 반환한다 (예외 아님).
        """
        store = self._load()
        cases = store.get("cases", [])
        case = next(
            (c for c in cases if isinstance(c, dict) and c.get("id") == case_id),
            None,
        )
        if case is None:
            return []

        attachments_by_id = {
            att["id"]: att
            for att in store.get("attachments", [])
            if isinstance(att, dict) and att.get("id")
        }
        emails = []
        for mail_id in case.get("mail_ids", []):
            mail = self._mails_by_id.get(mail_id)
            if mail is None:
                continue
            emails.append(
                {
                    "id": mail_id,
                    "subject": mail.get("subject", ""),
                    "sender_name": mail.get("sender_name", ""),
                    "sender_email": mail.get("sender_email", ""),
                    "sent_at": mail.get("sent_at", ""),
                    "attachments": [
                        attachments_by_id[aid]
                        for aid in mail.get("attachments", [])
                        if aid in attachments_by_id
                    ],
                }
            )
        return emails

    def get_attachment_text(self, attachment_id: str) -> str:
        """첨부 추출 전문. 없는 첨부면 빈 문자열 (예외 아님)."""
        store = self._load()
        texts = store.get("attachment_texts", {})
        if not isinstance(texts, dict):
            return ""
        return texts.get(attachment_id, "")