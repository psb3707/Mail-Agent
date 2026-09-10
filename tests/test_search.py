import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.search import answer_question


def _indexed():
    return json.loads(Path("data/indexed.json").read_text(encoding="utf-8"))


# 라이브 경로 스텁 — LLM이 문서 근거를 인용하는 답변을 반환
def _dummy_llm(prompt, **kw):
    return "N_CX 외주 견적 최종은 (주)디자인랩스 48,500,000원(VAT 별도)입니다."


def test_answer_finds_correct_attachment():
    """시연 정답 1: N_CX 견적 최종 → v3.xlsx, evidence에 실제 값, cached=False"""
    idx = _indexed()
    res = answer_question("N_CX 외주 견적 최종 얼마였지?", idx, _dummy_llm)
    assert res["attachment"] == "N_CX_UIUX_견적취합_v3.xlsx"
    assert any("디자인랩스" in t for t in res["evidence"]), "근거에 실제 값(업체) 필요"
    assert any("48,500,000" in t for t in res["evidence"]), "근거에 실제 값(금액) 필요"
    assert res["cached"] is False


def test_answer_returns_evidence_from_corpus():
    """시연 정답 2: 워크숍 버스 → NextW_버스배차_최종명단.pdf 또는 evidence에 3호차·08:30"""
    idx = _indexed()
    res = answer_question("워크숍 버스 몇 시에 어디서 타?", idx, _dummy_llm)
    assert res["attachment"] == "NextW_버스배차_최종명단.pdf" or any(
        "3호차" in t or "08:30" in t for t in res["evidence"]
    )


def test_answer_fallback_when_llm_fails():
    """오프라인(LLM 스텁 예외) → cached=True + 최소한의 답변"""
    idx = _indexed()

    def boom(prompt, **kw):
        raise RuntimeError("offline")

    res = answer_question("N_CX 외주 견적 최종 얼마였지?", idx, boom)
    assert res["cached"] is True
    assert res["answer"], "폴백에도 답변이 있어야 함"
    assert res["attachment"]  # 폴백은 정답 첨부를 알고 있음