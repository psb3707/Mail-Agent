import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.search import answer_question, _fallback, DATA, _FALLBACK_ANSWERS


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


def test_fallback_reads_demo_cache_first():
    """지시 014(1): demo_cache.json이 있으면 파일의 answer·attachment·evidence 우선"""
    assert (DATA / "demo_cache.json").exists(), "테스트 전제: demo_cache.json 존재"
    res = _fallback("N_CX 외주 견적 최종 얼마")
    assert res["cached"] is True
    assert res["attachment"] == "N_CX_UIUX_견적취합_v3.xlsx"
    assert any("48,500,000" in t for t in res["evidence"]), "파일의 evidence가 반영되어야 함"


def test_fallback_defaults_when_cache_missing(monkeypatch, tmp_path):
    """지시 014(2): 파일 없음 → 예외 없이 기존 하드코딩 폴백으로 하강"""
    monkeypatch.setattr("app.search.DATA", tmp_path)
    res = _fallback("N_CX 외주 견적 최종 얼마")
    assert res["cached"] is True
    assert res["attachment"] == "N_CX_UIUX_견적취합_v3.xlsx"


def test_fallback_no_match_generic_answer(monkeypatch, tmp_path):
    """지시 014(2): 질문 미매칭 → 예외 없이 기본 메시지 폴백"""
    monkeypatch.setattr("app.search.DATA", tmp_path)
    res = _fallback("이런 질문은 없음")
    assert res["cached"] is True
    assert res["attachment"] is None
    assert "네트워크 오류" in res["answer"]


def test_answer_fallback_when_llm_fails():
    """오프라인(LLM 스텁 예외) → cached=True + 최소한의 답변"""
    idx = _indexed()

    def boom(prompt, **kw):
        raise RuntimeError("offline")

    res = answer_question("N_CX 외주 견적 최종 얼마였지?", idx, boom)
    assert res["cached"] is True
    assert res["answer"], "폴백에도 답변이 있어야 함"
    assert res["attachment"]  # 폴백은 정답 첨부를 알고 있음


# ── 지시-016: 대본 밖 예비 질문 3개 검증 (새 색인 기준, 라이브 스텁) ──────────

def _llm_quoting_answer(prompt, **kw):
    """LLM이 실제 값과 정답 첨부 파일명을 인용한다고 가정한 스텁.

    프롬프트의 후보 목록에 다른 질문 키워드(예: 리허설)가 섞여 있어도
    본 질문 기준으로 분기한다 — 실제 LLM 동작을 흉내 낸다.
    """
    if "리허설 얼마나" in prompt:
        return "D-MIG 이관 리허설은 6시간 42분이 걸렸습니다. 첨부: D-MIG_리허설결과보고.pdf"
    if "고객채널 TF" in prompt:
        return "고객채널 TF에서 우선순위 상위 5건이 결정됐습니다. 첨부: 고객채널TF_회의록_0312.pdf"
    return "ESG 공시 외부 검증은 한국품질재단이 했습니다. 첨부: ESG공시_최종안_v2.pdf"


def test_backlog_q_dmig_rehearsal_time():
    """BACKLOG #4-1: D-MIG 이관 리허설 소요 → 리허설결과보고.pdf·6시간 42분"""
    res = answer_question("D-MIG 이관 리허설 얼마나 걸렸어?", _indexed(), _llm_quoting_answer)
    assert res["attachment"] == "D-MIG_리허설결과보고.pdf"
    assert any("6시간" in t and "42분" in t for t in res["evidence"]), "근거에 실제 소요 시간"
    assert res["cached"] is False


def test_backlog_q_customer_channel_decision():
    """BACKLOG #4-2: 고객채널 TF 결정 → 회의록_0312.pdf·우선순위 상위 5건"""
    res = answer_question("고객채널 TF에서 뭐 결정됐지?", _indexed(), _llm_quoting_answer)
    assert res["attachment"] == "고객채널TF_회의록_0312.pdf"
    assert any("우선순위" in t and "5건" in t for t in res["evidence"])


def test_backlog_q_esg_external_auditor():
    """BACKLOG #4-3: ESG 공시 외부 검증 → 최종안_v2.pdf·한국품질재단"""
    res = answer_question("ESG 공시 외부 검증 누가 했어?", _indexed(), _llm_quoting_answer)
    assert res["attachment"] == "ESG공시_최종안_v2.pdf"
    assert any("한국품질재단" in t for t in res["evidence"])
    assert any("외부 검증" in t for t in res["evidence"])