"""IndexedReader·ClassifierAdapter 테스트 — AI-Ready DB(indexed.json) 조회·폴백 (지시 020).

- 실제 data/indexed.json(9건·43통·첨부16) 기반 조회 정합성
- 파일 없음/키 없음/손상 → 예외 없이 빈 구조 폴백
- 인메모리 1회 로드 (재로드 금지)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.classifier_adapter import ClassifierAdapter
from agent.indexed_reader import _EMPTY, IndexedReader

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "indexed.json"


def test_get_tree_returns_real_cases():
    """조건 1-1: 실제 indexed.json → 9건, 각 case에 mail_ids·attachment_ids 포함."""
    reader = IndexedReader()
    tree = reader.get_tree()
    cases = tree["cases"]
    assert len(cases) == 9
    assert tree["root"] == "메일함"
    assert all(c["id"].startswith("c-m") for c in cases)
    # 총 메일 43통 정합 (건별 mail_ids 합계)
    assert sum(len(c["mail_ids"]) for c in cases) == 43
    # case id 집합이 실제와 1:1 일치
    real_ids = {c["id"] for c in json.loads(INDEX.read_text(encoding="utf-8"))["cases"]}
    assert {c["id"] for c in cases} == real_ids


def test_get_case_emails_c_m0001():
    """조건 1-2: c-m0001 → 6통 메일(제목·발신·시각) + 첨부 3건(a001~a003)."""
    reader = IndexedReader()
    emails = reader.get_case_emails("c-m0001")
    assert len(emails) == 6
    first = emails[0]
    assert first["subject"] and first["sender_name"] and first["sent_at"]
    assert first["id"] == "m0001"
    # c-m0001의 첨부 a001~a003가 6통에 걸쳐 노출
    att_ids = {aid for em in emails for aid in [a["id"] for a in em["attachments"]]}
    assert att_ids == {"a001", "a002", "a003"}


def test_get_attachment_text_a001():
    """조건 1-3: a001 견적취합 v3 본문에 업체명·금액 포함."""
    reader = IndexedReader()
    text = reader.get_attachment_text("a001")
    assert "(주)디자인랩스" in text
    assert "48,500" in text


def test_get_case_emails_unknown_case_returns_empty():
    """키 없음 → 예외 없이 빈 리스트 폴백."""
    reader = IndexedReader()
    assert reader.get_case_emails("no-such-case") == []


def test_get_attachment_text_unknown_returns_empty():
    """키 없음 → 예외 없이 빈 문자열 폴백."""
    reader = IndexedReader()
    assert reader.get_attachment_text("no-such-att") == ""


def test_missing_files_fallback_to_empty(tmp_path):
    """파일 없음 → 예외 없이 빈 구조 폴백."""
    reader = IndexedReader(root=tmp_path)
    assert reader.get_tree() == {"root": "메일함", "cases": []}
    assert reader.get_case_emails("c-m0001") == []
    assert reader.get_attachment_text("a001") == ""


def test_corrupt_indexed_fallback_to_empty(tmp_path):
    """indexed.json 손상(비JSON) → 예외 없이 빈 구조 폴백."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "indexed.json").write_text("{broken json", encoding="utf-8")
    (tmp_path / "data" / "mails.json").write_text("{}", encoding="utf-8")
    reader = IndexedReader(root=tmp_path)
    assert reader.get_tree()["cases"] == []
    assert reader.get_case_emails("c-m0001") == []
    assert reader.get_attachment_text("a001") == ""


def test_loads_once_in_memory():
    """인메모리 1회 로드 — _load 반복 호출에도 파일을 재읽지 않는다 (캐시)."""
    reader = IndexedReader()
    first = reader._load()
    second = reader._load()
    assert first is second


def test_classifier_adapter_default_is_indexed_reader():
    """ClassifierAdapter 기본 impl은 IndexedReader다 (MockClassifier 제거 확인)."""
    adapter = ClassifierAdapter()
    assert isinstance(adapter._impl, IndexedReader)
    tree = adapter.get_tree()
    assert len(tree["cases"]) == 9