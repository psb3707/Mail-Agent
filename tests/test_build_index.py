import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_index import build_index

def _load():
    d = json.loads(Path("data/mails.json").read_text())
    return d["mails"], d["attachments"]

def test_build_index_creates_cases():
    mails, atts = _load()
    result = build_index(mails, atts)
    assert result["cases"], "cases가 비어 있으면 안 됨"
    # 건 A: 6통이 같은 건으로 묶여야 함
    case_a = next(c for c in result["cases"] if "m0001" in c["mail_ids"])
    assert {"m0001","m0002","m0003","m0004","m0005","m0006"} <= set(case_a["mail_ids"])

def test_build_index_order_invariant():
    import random
    random.seed(1)
    mails, atts = _load()
    shuffled = mails[:]
    random.shuffle(shuffled)
    base = build_index(mails, atts)
    other = build_index(shuffled, atts)
    # 순서 무관: 건 ID → mail_ids 집합이 동일해야 함
    b = {c["id"]: frozenset(c["mail_ids"]) for c in base["cases"]}
    o = {c["id"]: frozenset(c["mail_ids"]) for c in other["cases"]}
    assert b == o

def test_build_index_idempotent():
    mails, atts = _load()
    r1 = build_index(mails, atts)
    r2 = build_index(mails, atts)
    ids1 = {c["id"] for c in r1["cases"]}
    ids2 = {c["id"] for c in r2["cases"]}
    assert ids1 == ids2  # 재실행해도 건 ID가 흔들리지 않음

def test_attachment_texts_extracted():
    _, atts = _load()
    result = build_index(*_load())
    for a in atts:
        assert result["attachment_texts"][a["id"]]  # 모든 첨부 텍스트 존재
