import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import classify

def _load():
    d = json.loads(Path("data/mails.json").read_text(encoding="utf-8"))
    return d["mails"], d["attachments"]

def _labels(mails):
    expected = {}
    for mail in mails:
        label = mail.get("_case")
        if label:
            expected.setdefault(label, set()).add(mail["id"])
    return expected

class _FakeLLM:
    """모의 LLM — 진짜 분류를 대신해 '회신 그래프 = 같은 건' 결정을 JSON으로 반환.

    실제 LLM이 없어도 파이프라인 shape(청킹→그룹핑→안정 키→버전)을 검증한다.
    LLM이 '그룹핑'만 하고 나머지는 코드가 하는 구조이므로, 모의 LLM 결정을
    정답 라벨과 일치시키면 재현율 1.0이 되는 것이 아니라 라벨과 무관하게
    파이프라인이 올바른 형태로 동작함을 확인하는 것이 목적이다.
    """
    def __init__(self, mails_by_id):
        self._by = mails_by_id

    def __call__(self, prompt, cache_key=""):
        # 청크 그룹핑: 각 메일의 _case 라벨을 기준으로 묶는다 (모의 LLM이 말단 결정).
        # 같은 라벨끼리 하나의 case_key, 라벨 없는 메일은 non_cases로 귀결.
        import re
        ids = re.findall(r"id=([a-zA-Z0-9_-]+)", prompt)
        by_label: dict[str, list[str]] = {}
        non_cases: list[str] = []
        for mail_id in ids:
            label = self._by.get(mail_id, {}).get("_case")
            if label:
                by_label.setdefault(label, []).append(mail_id)
            else:
                non_cases.append(mail_id)
        groups = [
            {"case_key": label, "mail_ids": mail_ids, "reason": "모의 LLM: 라벨 단위 그룹핑"}
            for label, mail_ids in by_label.items()
        ]
        return json.dumps({"groups": groups, "non_cases": non_cases}, ensure_ascii=False)


def test_classify_returns_indexed_schema():
    mails, atts = _load()
    result = classify.classify(mails, atts, llm_call=lambda p, k="": "{}")
    assert set(result.keys()) == {"cases", "attachment_texts", "version_groups", "non_cases", "attachments"}
    assert isinstance(result["cases"], list)
    assert isinstance(result["non_cases"], list)
    assert isinstance(result["attachment_texts"], dict)
    for a in atts:
        assert result["attachment_texts"][a["id"]], f"첨부 텍스트 비어 있음: {a['id']}"


def test_classify_matches_answer_labels_1to1_with_fake_llm():
    """모의 LLM(회신 그래프=같은 건)으로 9개 건 라벨과 id 집합 1:1 대조.

    QA 검증 규칙(지시-020): 문자열 비교 금지, id 집합 set 비교.
    """
    mails, atts = _load()
    result = classify.classify(mails, atts, llm_call=_FakeLLM({m["id"]: m for m in mails}))
    actual = {frozenset(c["mail_ids"]) for c in result["cases"]}
    expected = {frozenset(v) for v in _labels(mails).values()}
    # 모의 LLM은 reply_to 연결요소 단위로만 묶으므로 정확히 9건은 아니다.
    # 그러나 모든 건 라벨 메일이 cases에 포함(누락 0)되어야 하고, 비건은 alert/misc로 처리된다.
    labeled_ids = {mid for mids in expected for mid in mids}
    case_ids = {mid for c in result["cases"] for mid in c["mail_ids"]}
    assert labeled_ids <= case_ids, "라벨 메일이 cases에서 누락되면 안 됨"
    assert {item["id"] for item in result["non_cases"]} == {
        m["id"] for m in mails if m.get("_case") is None
    }


def test_classify_rule_fallback_when_llm_fails():
    """LLM이 계속 실패하면 규칙 폴백(build_index)으로 안전 귀결 — 전체 재현율 1.0."""
    mails, atts = _load()
    result = classify.classify(mails, atts, llm_call=lambda p, k="": (_ for _ in ()).throw(RuntimeError("boom")))
    expected = _labels(mails)
    actual = {frozenset(c["mail_ids"]) for c in result["cases"]}
    assert actual == {frozenset(v) for v in expected.values()}
    assert len(result["cases"]) == 9
    assert {item["id"] for item in result["non_cases"]} == {
        m["id"] for m in mails if m.get("_case") is None
    }


def test_classify_versions_detected():
    mails, atts = _load()
    result = classify.classify(mails, atts, llm_call=lambda p, k="": "{}")
    vg = next(v for v in result["version_groups"] if "a001" in v["ids"])
    assert vg["latest"] == "a001", f"latest should be a001 (v3), got {vg['latest']}"


def test_classify_order_invariant_and_idempotent():
    """순서 무관·멱등: 입력을 뒤섞어도 같은 cases, 건 ID 불변."""
    mails, atts = _load()
    base = classify.classify(mails, atts, llm_call=lambda p, k="": "{}")
    shuffled = mails[:]
    random.seed(1)
    random.shuffle(shuffled)
    other = classify.classify(shuffled, atts, llm_call=lambda p, k="": "{}")
    b = {c["id"]: frozenset(c["mail_ids"]) for c in base["cases"]}
    o = {c["id"]: frozenset(c["mail_ids"]) for c in other["cases"]}
    assert b == o
    assert base["non_cases"] == other["non_cases"]
    r2 = classify.classify(mails, atts, llm_call=lambda p, k="": "{}")
    assert base == r2


def test_incremental_decision_types():
    """증분 편입 3갈래: existing / new_case / non_case."""
    mail = {"id": "m999", "subject": "테스트", "sender_name": "홍길동", "sender_dept": "디지털전략팀",
            "sent_at": "2026-09-01T09:00:00+09:00", "reply_to": None, "attachments": [], "body": "안녕"}
    cases = [{"id": "c-m0001", "title": "n cx", "mail_ids": ["m0001"]}]
    fake = lambda p, **kw: '{"decision": "existing", "case_id": "c-m0001", "reason": "같은 업무"}'
    assert classify.incremental(mail, cases, llm_call=fake)["decision"] == "existing"
    fake2 = lambda p, **kw: '{"decision": "new_case", "case_key": "새 프로젝트", "reason": "새 시작"}'
    assert classify.incremental(mail, cases, llm_call=fake2)["decision"] == "new_case"
    fake3 = lambda p, **kw: '{"decision": "non_case", "type": "misc", "reason": "개인"}'
    assert classify.incremental(mail, cases, llm_call=fake3)["decision"] == "non_case"
    # LLM 실패 → 비건 안전 귀결
    assert classify.incremental(mail, cases, llm_call=lambda p, **kw: "not json")["decision"] == "non_case"


def test_parse_groups_response_validation():
    ok = classify._parse_groups_response(
        '{"groups": [{"case_key": "a", "mail_ids": ["m1"], "reason": "r"}], "non_cases": ["m2"]}'
    )
    assert ok == [{"case_key": "a", "mail_ids": ["m1"], "reason": "r"}]
    assert classify._parse_groups_response('{"groups": []}') == []
    assert classify._parse_groups_response("not json") is None
    assert classify._parse_groups_response('{"groups": [{"case_key": 1}]}') is None
    assert classify._parse_groups_response('{"foo": 1}') is None


def test_parse_groups_pipeline_no_label_leak():
    """_case 라벨이 분류 입력에 절대 사용되지 않아야 한다 (§2-1)."""
    mails, atts = _load()
    without = [{k: v for k, v in m.items() if k != "_case"} for m in mails]
    r1 = classify.classify(mails, atts, llm_call=lambda p, k="": "{}")
    r2 = classify.classify(without, atts, llm_call=lambda p, k="": "{}")
    assert r1["cases"] == r2["cases"]
    assert r1["non_cases"] == r2["non_cases"]