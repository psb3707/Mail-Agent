# 원격 저장소 협업 문서 변경 보고

- 감시 대상: `psb3707/Mail-Agent`
- 감시 시각: 2026-09-10 10:56 (KST)
- 직전 기준 커밋: `86dc69a42d7352cca10fdee0cfc78b9fd62e0630`
- 새 커밋 수: **1건**

---

## 새 커밋

### 1. `cdb2bda9f40a7fa902a74b30aed700b25e148247` — docs: add developer onboarding guide

- 작성자: KEEKE132 (dksvlfdhs1@naver.com)
- 일시: 2026-09-10 01:55 (UTC)
- 변경 파일:
  - `AGENTS.md` (modified, +1)
  - `docs/onboarding.md` (added, +127)

### 요약 (한국어)

신규 개발자 세션용 온보딩 가이드 `docs/onboarding.md`를 추가하고, `AGENTS.md` 진입 지침에 "새 세션은 먼저 온보딩을 읽는다" 항목을 연결했다.

온보딩 문서의 핵심 내용:
- 프로젝트 한 줄: 메일함을 도착순이 아닌 건(件) 단위로 보게 하는 레이어
- 지금 상태 스냅샷 (2026-09-10 기준): `build_index.py`·`grouping.py`·`search.py`·`llm.py` 구현 완료, `versions.py`·`main.py`(웹 서빙)·`slides/` 미작성
- 테스트 현황: `pytest tests -v` → **11 passed, 1 failed** (`test_build_index_creates_cases` — m0005·m0006이 토큰 없어 `n cx` 건에 미편입)
- 전역 제약: 원본 무수정, 저장 인메모리(DB 금지), 라이브 기본·캐시 폴백, 순서 무관·멱등·증분 편입, 비건 처리, 근거 인용, 구조 유지, AI 경계
- 다음 할 일 (우선순위): ① 실패 테스트 수리(D1-1 토큰리스 키워드 편입 로직) ② D1-5 버전 판별(`app/versions.py`) ③ D1-6 웹 서빙(`app/main.py`+`templates/`) ④ D1-7 시연 자산(`demo_cache.json`+`slides/`)
- 커밋 규칙: 커밋 하나당 한 덩어리, 테스트 PASS 확인 후 커밋, `handoff.md` 체크 표시 최신화
- 워크스페이스 관례: 위키 정리(wiki-organize), 한국어 기본 출력, Python>=3.11 `.venv` + pytest

---

## 기준 커밋 갱신

- 신규 기준: `cdb2bda9f40a7fa902a74b30aed700b25e148247`
