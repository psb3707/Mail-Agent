import json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_index import build_index

def _load():
    d = json.loads(Path("data/mails.json").read_text(encoding="utf-8"))
    return d["mails"], d["attachments"]

def test_build_index_creates_cases():
    mails, atts = _load()
    result = build_index(mails, atts)
    assert result["cases"], "cases가 비어 있으면 안 됨"
    # 건 A: 6통이 같은 건으로 묶여야 함
    case_a = next(c for c in result["cases"] if "m0001" in c["mail_ids"])
    assert {"m0001","m0002","m0003","m0004","m0005","m0006"} <= set(case_a["mail_ids"])

def test_build_index_order_invariant():
    random.seed(1)
    mails, atts = _load()
    shuffled = mails[:]
    random.shuffle(shuffled)
    base = build_index(mails, atts)
    other = build_index(shuffled, atts)
    # 순서 무관: 건 ID → mail_ids 집합과 비건 판정이 동일해야 함
    b = {c["id"]: frozenset(c["mail_ids"]) for c in base["cases"]}
    o = {c["id"]: frozenset(c["mail_ids"]) for c in other["cases"]}
    assert b == o
    assert base["non_cases"] == other["non_cases"]

def test_build_index_idempotent():
    mails, atts = _load()
    r1 = build_index(mails, atts)
    r2 = build_index(mails, atts)
    assert r1 == r2  # 재실행해도 건 ID뿐 아니라 결론 전체가 흔들리지 않음

def test_attachment_texts_extracted():
    _, atts = _load()
    result = build_index(*_load())
    for a in atts:
        assert result["attachment_texts"][a["id"]], f"첨부 텍스트가 비어 있음: {a['id']}"  # 모든 첨부 텍스트 존재
    # 시연 정답 1 근거: N_CX 견적 취합 최신본(a001, v3)에는 업체명·금액이 실제로 추출되어야 함
    txt = result["attachment_texts"]["a001"]
    for kw in ("디자인랩스", "48,500,000"):
        assert kw in txt, f"a001 추출 텍스트에 {kw!r} 없음"


def test_build_index_versions_latest_is_v3():
    # P1-1: a001 = _v3.xlsx(최신), a003 = _v1.xlsx → latest는 파일명 버전 기준 최고(최신)여야 함
    mails, atts = _load()
    result = build_index(mails, atts)
    vg = next(v for v in result["version_groups"] if "a001" in v["ids"])
    assert vg["latest"] == "a001", f"latest should be a001 (v3), got {vg['latest']}"


def test_build_index_reassembles_all_nine_cases_without_leakage():
    # 정답 라벨은 평가에만 사용한다. 9개 건은 각각 독립적이고 일반 메일을 흡수하지 않는다.
    mails, atts = _load()
    result = build_index(mails, atts)
    expected = {
        label: frozenset(m["id"] for m in mails if m.get("_case") == label)
        for label in {m.get("_case") for m in mails} - {None}
    }
    actual = {frozenset(case["mail_ids"]) for case in result["cases"]}
    assert len(result["cases"]) == 9
    assert actual == set(expected.values())
    assert {item["id"] for item in result["non_cases"]} == {
        m["id"] for m in mails if m.get("_case") is None
    }


def test_build_index_does_not_read_answer_labels():
    mails, atts = _load()
    without_labels = [{key: value for key, value in mail.items() if key != "_case"} for mail in mails]
    labeled = build_index(mails, atts)
    unlabeled = build_index(without_labels, atts)
    assert labeled["cases"] == unlabeled["cases"]
    assert labeled["non_cases"] == unlabeled["non_cases"]


def test_version_detection_is_attachment_order_invariant():
    mails, atts = _load()
    shuffled = atts[:]
    random.Random(7).shuffle(shuffled)
    assert build_index(mails, atts)["version_groups"] == build_index(mails, shuffled)["version_groups"]
