# GitHub 원격 변경 감시 보고 (2026-09-10 13:08 KST)

- 저장소: `psb3707/Mail-Agent`
- 직전 기준 커밋: `a79e60eb2d0551a8b42bdead029b451b9342d24e` (docs: add role-based behavior norms to AGENTS.md)
- 새 커밋: **4건** (아래, 최신순)

---

## 1. `dac18543870e06aedda142f2cb7c2f02570f0657` — chore: add QA smoke check script (fallback/indexed alignment) (최신)

- 작성자: KEEKE132 · 2026-09-10 04:07 UTC
- 변경 파일:
  - `qa_smoke_check.py` (신규, +52)
- 요약: QA 실측 스모크 스크립트 추가. ① `_fallback()`이 `demo_cache.json`을 우선 읽어 `cached=True`·정답 첨부(N_CX_UIUX_견적취합_v3.xlsx), ② `data/indexed.json` 정합성(9건·357비건·버전그룹·latest a001), ③ 정답지(`_case`) 1:1 대조, ④ 원본 무수정 확인.

## 2. `128470e4d4ce7c6b07cee1c89cf1903aaae307c7` — docs: add remote monitoring reports (last_seen tracking)

- 작성자: KEEKE132 · 2026-09-10 04:06 UTC
- 변경 파일: `docs/monitor/` 아래 원격 감시 보고서 다수 추가
  - `2026-09-10-1056-remote-updates.md` (개발자 온보딩 추가 보고)
  - `2026-09-10-1100-conflict-analysis.md` (리베이스 충돌 분석)
  - `2026-09-10-1101-remote-updates.md` (QA 온보딩 + 저장 3계층 설계 보고)
  - `2026-09-10-1109-remote-updates.md` (build_index 최초 커밋 보고)
  - `2026-09-10-1112-agent-connection.md` (관리 Agent 골격 연결점)
  - `2026-09-10-1116-demo-assets.md` (시연 자산 연결점)
  - `2026-09-10-1117-rebase-verified.md` (리베이스 완료·테스트 검증)
- 요약: 지난 주기 원격 감시 보고서 커밋 묶음 + last_seen 기반 감시 체계 확립.

## 3. `618f2fa2a30b15e43e8bd652d6a170a974dbee7b` — feat: OpenRouter LLM gateway, search fallback/evidence fix, deploy scripts (#014, 016-018)

- 작성자: KEEKE132 · 2026-09-10 04:06 UTC
- 변경 파일:
  - `app/llm.py` (수정, +90/−23) — anthropic SDK → **OpenRouter**(OpenAI-호환 `/chat/completions` + urllib) 전환, 루트 `.env` 로드, `OPENROUTER_API_KEY`·`OPENROUTER_MODEL` 환경변수, 키 미설정 시 캐시 폴백
  - `app/search.py` (수정, +38/−9) — `_fallback()`이 `data/demo_cache.json` 우선 읽기, `_find_attachment_in_answer()`로 LLM 답변에서 언급된 첨부 기준으로 attachment·evidence 갱신
  - `.env.example` (신규, +11), `run.ps1` (신규, +22, PORT 기본 8765), `README.md` (수정, +10)
  - `pyproject.toml` (수정, −1, anthropic 의존성 제거)
  - `tests/test_llm.py`·`tests/test_build_index.py` (수정), `docs/BACKLOG.md` (수정)
- 요약: 지시-014·016·018 반영 — OpenRouter LLM 게이트웨이, 검색 폴백·근거 인용 보강, Windows 로컬 배포(`run.ps1`).

## 4. `4feef90f347fb686f8621f20a7ed4e2b51da52b6` — feat: add manager agent core (skills, harness, orchestrator, prompts) + integration tests (#009-011, 013)

- 작성자: KEEKE132 · 2026-09-10 04:06 UTC
- 변경 파일(12개):
  - `agent/__init__.py` (수정 — export 정리), `agent/context.py` (수정 — 도구 실행 이력 `steps` 추가), `agent/manager.py` (수정 — 오케스트레이터 기반 개편), `agent/harness.py` (신규), `agent/orchestrator.py` (신규 — LLM JSON 도구 선택 멀티스텝 루프), `agent/prompts.py`, `agent/skills.py`
  - `tests/test_agent.py`, `tests/test_agent_integration.py`, `tests/test_harness.py`, `tests/test_orchestrator.py`, `tests/test_prompts.py` (통합 테스트)
- 요약: 관리 Agent 코어 구현 — 스킬(도구) 정의·하네스(등록/실행, `set_classifier` 어댑터 교체)·오케스트레이터(LLM JSON 도구 선택 + 규칙 폴백)·프롬프트 + 통합 테스트. 지시-009~011·013 완료분.

---

## 종합

- 감시 기간(기준 `a79e60` → 최신 `dac18543`) 동안 4건의 새 커밋이 도착. 전부 단일 작성자(KEEKE132)가 원격에 일괄 push.
- 핵심 변화: ① LLM 백엔드 anthropic SDK → **OpenRouter 게이트웨이** 전환(키 없으면 캐시 폴백), ② 검색 질문 답변의 담당 첨부 인용 보강, ③ 관리 Agent 오케스트레이터·하네스·스킬 코어 완성 + 통합 테스트, ④ QA 스모크·로컬 실행 스크립트(`run.ps1`) 추가.
- 우리 워크스페이스 4대 축(색인·시연 웹앱·관리 Agent·발표 자산)과 내용 일치. 특히 `app/llm.py` OpenRouter 전환·`app/search.py` 폴백 개편은 확정된 방향과 동일.
- 원본 데이터(`data/mails.json`·`data/attachments/`) 변경 없음.

---

## 기준 커밋 갱신

- 신규 기준: `dac18543870e06aedda142f2cb7c2f02570f0657` (chore: add QA smoke check script)