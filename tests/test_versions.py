import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.versions import version_compare, _pick_latest


def _indexed():
    return json.loads(Path("data/indexed.json").read_text(encoding="utf-8"))


def test_version_compare_latest_detected():
    """N_CX 견적서 버전 계열에서 v3(최신)가 latest로 선택된다."""
    groups = version_compare(_indexed())
    # N_CX 견적서 버전 계열 (doc에 '견적취합')
    nc = next(g for g in groups if "견적취합" in g["doc"])
    # a001 = N_CX_UIUX_견적취합_v3.xlsx (3차/최종)
    assert nc["latest"] == "a001", f"latest는 v3(a001)여야 한다. got={nc['latest']}"


def test_diff_summary_provided():
    """모든 버전 그룹에 diff_summary가 비어 있지 않다."""
    groups = version_compare(_indexed())
    assert groups, "버전 그룹이 하나 이상 있어야 함"
    assert all(g.get("diff_summary") for g in groups), "diff_summary는 비어 있으면 안 됨"


def test_single_document_excluded():
    """버전 계열이 없는 첨부(단일 문서)는 그룹에서 제외된다."""
    idx = _indexed()
    # 단일 문서(a002 등)는 version_groups에 없음 → version_compare 결과에 단독 그룹 없음
    groups = version_compare(idx)
    for g in groups:
        assert len(g["ids"]) >= 2, "단일 문서가 버전 그룹에 포함되면 안 됨"


def test_pick_latest_prefers_v3():
    """_pick_latest는 v3 > v1 순으로 최신을 고른다 (indexed.latest 오기재 보정)."""
    atts = [
        {"id": "a001", "filename": "N_CX_UIUX_견적취합_v3.xlsx"},
        {"id": "a003", "filename": "N_CX_UIUX_견적취합_v1.xlsx"},
    ]
    assert _pick_latest(["a003", "a001"], atts) == "a001"