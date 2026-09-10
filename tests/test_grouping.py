import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.grouping import reassemble, classify_new_mail, DECISION_EXISTING, DECISION_NEW_CASE, DECISION_NON_CASE


def _load_indexed():
    return json.loads(Path("data/indexed.json").read_text(encoding="utf-8"))


def _load_mails():
    d = json.loads(Path("data/mails.json").read_text(encoding="utf-8"))
    return d["mails"]


def offline_llm(prompt, **kw):
    raise RuntimeError("offline")


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
    assert assigned["decision"] == DECISION_EXISTING
    assert assigned["case_id"] == "c-m0001"


def test_classify_new_mail_without_llm_uses_token_fallback():
    new = {"id": "m9999", "subject": "〔Project N_CX〕2차 견적 요청", "body": "추가 견적 요청드립니다", "sender_dept": "디지털전략팀"}
    idx = _load_indexed()

    def offline_llm(prompt, **kw):
        raise RuntimeError("offline")

    result = classify_new_mail(new, idx, offline_llm)
    assert result["decision"] == DECISION_EXISTING  # 토큰 교집합으로 기존 건(N_CX)에 배정
    assert result["case_id"] == "c-m0001"


def test_classify_unrelated_misc_mail_does_not_contaminate_case():
    # 상투어(견적) 1개만 겹치는 단발 메일은 어느 건에도 배정되지 않아야 한다
    # (비건 오염 방지 — AGENTS.md 비건 처리 원칙)
    new = {"id": "m9999", "subject": "견적서 확인 부탁드립니다",
           "body": "개인 업무로 견적서 하나 확인 부탁드립니다.", "sender_dept": "총무팀"}
    idx = _load_indexed()
    result = classify_new_mail(new, idx, offline_llm)
    assert result["decision"] == DECISION_NEW_CASE  # 상투어만으로 어느 건에도 배정 안 됨


def test_classify_general_notice_mail_returns_new_case():
    # 단발성 전사 공지(업무 마커 없음)는 건으로 오르지 않아야 한다
    new = {"id": "m9998", "subject": "〔전사공지〕점심시간 변경 안내",
           "body": "익일부터 점심시간이 변경됩니다.", "sender_dept": "경영지원부"}
    result = classify_new_mail(new, _load_indexed(), offline_llm)
    assert result["decision"] == DECISION_NEW_CASE  # 단발 공지 — 새 업무 후보로도 오르지 않음


def test_classify_ncx_marker_variants_assign_ncx_case():
    # 표기 흔들림(N_CX / N CX / [N_CX])은 모두 같은 건(c-m0001)에 배정돼야 한다
    idx = _load_indexed()
    for subj in ["〔Project N CX〕3차 견적 요청", "[N_CX] 인터페이스 명세 공유",
                 "〔Project N_CX〕2차 견적 요청"]:
        new = {"id": "m9997", "subject": subj,
               "body": "추가 자료 공유드립니다.", "sender_dept": "디지털전략팀"}
        result = classify_new_mail(new, idx, offline_llm)
        assert result["decision"] == DECISION_EXISTING, f"{subj} → {result}"
        assert result["case_id"] == "c-m0001", f"{subj} → {result}"


def _real_mail(mid: str) -> dict:
    """data/mails.json 원본 메일을 반환한다 (읽기 전용)."""
    d = json.loads(Path("data/mails.json").read_text(encoding="utf-8"))
    return next(m for m in d["mails"] if m["id"] == mid)


def test_classify_broken_thread_workshop_mail_joins_next_w_case():
    # m0010: reply_to가 끊긴 뒤 따로 도착한 워크숍 후속(Fw:) — 시각·표기 보정으로
    # 워크숍 건(c-m0007)에 배정돼야 한다 (실제 데이터 정답: _case == "B")
    m = _real_mail("m0010")
    result = classify_new_mail(m, _load_indexed(), offline_llm)
    assert result["decision"] == DECISION_EXISTING, f"m0010 → {result}"
    assert result["case_id"] == "c-m0007", f"m0010 → {result}"


def test_classify_system_learning_campaign_mails_assign_learning_case():
    # 시스템 발신 학습 시작/현황(러닝포털)은 학습 건(c-m0011)에 유지돼야 한다
    # (build_index의 학습 캠페인 승격과 동일한 경계)
    idx = _load_indexed()
    for mid in ["m0011", "m0013", "m0017"]:
        got = classify_new_mail(_real_mail(mid), idx, offline_llm)
        assert got["decision"] == DECISION_EXISTING, f"{mid} → {got}"
        assert got["case_id"] == "c-m0011", f"{mid} → {got}"


def test_classify_returns_three_way_decision():
    idx = _load_indexed()
    # ① 기존 건 편입 — N_CX 후속
    existing = {"id": "m9990", "subject": "〔Project N_CX〕견적 재협의",
                "body": "견적 재협의 요청드립니다", "sender_dept": "디지털전략팀"}
    res = classify_new_mail(existing, idx, offline_llm)
    assert res["decision"] == DECISION_EXISTING
    assert res["case_id"] == "c-m0001"

    # ② 새 건 시작 — 알려지지 않은 프로젝트(새 업무)는 NEW_CASE
    fresh = {"id": "m9989", "subject": "〔Project N_XX〕신규 프로젝트 킥오프",
             "body": "신규 프로젝트 N_XX 킥오프 일정 공유드립니다", "sender_dept": "디지털전략팀"}
    res = classify_new_mail(fresh, idx, offline_llm)
    assert res["decision"] == DECISION_NEW_CASE
    assert res["case_id"] == ""

    # ③ 비건 처리 — 시스템 발행 알림(학습이 아닌 미이수·점검 등)은 알림 폴더
    notice = {"id": "m9987", "subject": "〔시스템〕보안 점검 안내",
              "body": "정기 보안 점검이 예정되어 있습니다.", "sender_dept": "시스템"}
    res = classify_new_mail(notice, idx, offline_llm)
    assert res["decision"] == DECISION_NON_CASE
    assert res["case_id"] == ""


def test_classify_rules_module_is_used_by_batch_and_incremental():
    import app.classify_rules as rules
    from scripts.build_index import _tokens, _norm_subject, _topic_marker
    # 배치·증분이 같은 정규화 경계를 사용한다 (복제 금지 — 일원화 원칙)
    assert rules.normalize_subject("〔Project N_CX〕2차") == "project n cx 2차"
    assert _norm_subject("〔Project N_CX〕2차") == rules.normalize_subject("〔Project N_CX〕2차")
    assert _tokens("추가 견적 요청드립니다") == rules.tokens("추가 견적 요청드립니다")


def test_classify_llm_prompt_contains_case_summaries():
    # LLM 호출이 건 제목만이 아니라 대표어·기간 요약을 제공해야 한다
    seen = {}
    def capture_llm(prompt, **kw):
        seen["prompt"] = prompt
        raise RuntimeError("offline")
    classify_new_mail({"id": "m9999", "subject": "〔Project N_CX〕문의",
                        "body": "추가 요청드립니다", "sender_dept": "디지털전략팀"}, _load_indexed(), capture_llm)
    assert seen.get("prompt"), "LLM이 호출되어야 함"
    assert "c-m0001" in seen["prompt"]  # 건 id 노출
    assert "대표어" in seen["prompt"] or "signature" in seen["prompt"]  # 요약 정보


def test_system_reminder_alert_mail_does_not_contaminate_learning_case():
    # 시스템 발신 미이수 독촉 알림(비건)은 학습 건(c-m0011)을 오염시키면 안 된다
    # (알림 폴더 처리 대상 — build_index 비건 정책과 동일)
    idx = _load_indexed()
    for mid in ["m0400", "m0146", "m0062"]:
        got = classify_new_mail(_real_mail(mid), idx, offline_llm)
        assert got["decision"] == DECISION_NON_CASE, f"{mid} → {got}"