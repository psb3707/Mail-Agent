import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.grouping import reassemble, classify_new_mail


def _load_indexed():
    return json.loads(Path("data/indexed.json").read_text(encoding="utf-8"))


def _load_mails():
    d = json.loads(Path("data/mails.json").read_text(encoding="utf-8"))
    return d["mails"]


def _indexed_with_case_a():
    """실제 indexed.json + mails.json 기반 테스트용 indexed.

    건 A(_case=="A") 6통(m0001~m0006)이 하나의 case로 묶이도록 구성한다.
    참고: 아직 data/indexed.json이 D1-1 그룹핑 보완 전이라 파일의 c-m0001은
    4통만 담고 있다. 여기서는 indexed.json을 수정하지 않고, mails.json의
    _case 메타데이터로 case를 재구성해 reassemble 로직 자체를 검증한다.
    """
    idx = _load_indexed()
    mails = _load_mails()
    case_a = next(c for c in idx["cases"] if c["id"] == "c-m0001")
    case_a["mail_ids"] = [m["id"] for m in mails if m.get("_case") == "A"]
    idx["mails"] = mails  # 원문 포함 → reassemble이 mails.json 보조 로드 없이 사용
    return idx


def test_reassemble_returns_cards_with_latest_reply():
    cards = reassemble(_indexed_with_case_a())
    card_a = next(c for c in cards if "m0001" in [m["id"] for m in c["mails"]])
    # 건 A: 6통이 하나의 카드로 재조립
    assert len(card_a["mails"]) == 6
    # "마지막 답변 확인" — latest_*가 채워져 있어야 한다
    assert card_a["latest_body"]  # 마지막 답변 본문
    assert card_a["latest_sender"]  # 마지막 발신자
    assert card_a["latest_at"]  # 마지막 시각
    # 마지막 메일이 가장 최신 sent_at이어야 한다 (정렬 검증)
    assert card_a["mails"][-1]["sent_at"] == card_a["latest_at"]


def test_classify_new_mail_assigns_existing_case():
    new = {"id": "m9999", "subject": "〔Project N_CX〕2차 견적 요청", "body": "추가 견적 요청드립니다", "sender_dept": "디지털전략팀"}
    idx = _load_indexed()
    assigned = classify_new_mail(new, idx, lambda p: "c-m0001")
    assert assigned == "c-m0001"


def test_classify_new_mail_without_llm_uses_token_fallback():
    new = {"id": "m9999", "subject": "〔Project N_CX〕2차 견적 요청", "body": "추가 견적 요청드립니다", "sender_dept": "디지털전략팀"}
    idx = _load_indexed()

    def offline_llm(prompt, **kw):
        raise RuntimeError("offline")

    cid = classify_new_mail(new, idx, offline_llm)
    assert cid  # 빈 문자열/미배정 금지 — 폴백으로 배정이 결정된다
    assert cid != "NEW_CASE"  # 토큰 교집합으로 기존 건(N_CX)에 배정돼야 한다