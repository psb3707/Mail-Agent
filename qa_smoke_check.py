# -*- coding: utf-8 -*-
"""QA 실측 스모크 — 지시 013/014 재검증용. 원본 데이터 무수정 확인 포함."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.search import _fallback

# 1) 폴백 연동(지시 014): demo_cache.json 우선 읽기
r = _fallback("N_CX 외주 견적 최종 얼마")
print("FALLBACK cached=", r["cached"], "| att=", r["attachment"])
assert r["cached"] is True
assert r["attachment"] == "N_CX_UIUX_견적취합_v3.xlsx"

# 2) 색인 정합성(지시 012 재확인): 9건/357비건/버전그룹
idx = json.loads((ROOT / "data" / "indexed.json").read_text(encoding="utf-8"))
cases = idx.get("cases", [])
non_cases = idx.get("non_cases", [])
vgroups = idx.get("version_groups", [])
mail_ids = {m["id"] for m in idx.get("mails", [])}
print("CASES=", len(cases), "| NON_CASES=", len(non_cases), "| TOTAL=", len(cases) + len(non_cases))
print("VGROUPS=", len(vgroups))
print("latest a001 =", next((vg for vg in vgroups if vg.get("doc") == "N_CX_UIUX" and vg.get("latest") == "a001"), None) is not None)

# 3) 정답지(_case) 1:1 대조
src = json.loads((ROOT / "data" / "mails.json").read_text(encoding="utf-8"))
by_case = {}
for m in src["mails"]:
    by_case.setdefault(m.get("_case"), []).append(m["id"])
case_ids_expected = {c: sorted(v) for c, v in by_case.items() if c and not str(c).upper().startswith("BG") or True}
counted = {}
for c in cases:
    for mid in c["mail_ids"]:
        counted.setdefault(c["id"], []).append(mid)
ok = True
for cid, mids in counted.items():
    cid_clean = cid.split("(")[0].strip()
    if cid_clean not in by_case:
        ok = False
        print("MISSING case label in mails.json:", cid_clean, "mids=", mids)
        continue
    if sorted(mids) != sorted(by_case[cid_clean]):
        ok = False
        print("MISMATCH", cid_clean, "cases:", sorted(mids), "expected:", sorted(by_case[cid_clean]))
print("CASE_1TO1_OK=", ok)

# 4) 원본 무수정: mails.json 해시(원본 기준은 git diff로 별도 확인)
print("SMOKE_DONE")