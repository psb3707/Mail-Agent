# 연결 지점 추가 분석 — 지시-008 관리 Agent 골격 (로컬 신규 작업)

> 작성: 2026-09-10 · 감시 주기 결과
> 원격 신규 커밋: **없음** (최신 `f9348c0` 유지, last_seen 갱신 완료)

## 발견된 로컬 작업 (다른 개발자 세션 진행 중)

워크스페이스 작업 트리에 지시-008(관리 Agent 골격) 산출물이 등장했다.

| 파일 | 역할 |
|---|---|
| `agent/__init__.py` | 패키지 |
| `agent/manager.py` | `ManagerAgent` — 에이전트 루프 (맥락→도구선택→어댑터→응답) |
| `agent/classifier_adapter.py` | `ClassifierAdapter` + `Classifier` Protocol(계약) + `MockClassifier` |
| `agent/context.py` | 대화 맥락 |
| `agent/responder.py` | 도구 결과 렌더링 |
| `docs/specs/2026-09-10-manager-agent-skeleton.md` | 설계·계약서 |
| `tests/test_agent.py` | 스모크 테스트 |

## 연결 지점 (충돌 아님 — 맞물릴 부분)

### 1. `ClassifierAdapter` ↔ `data/indexed.json` (핵심)
- 설계서 §3: `get_tree`/`get_case_emails`/`get_attachment_text` — 분류AI(동료 PC)가
  **같은 레포의 모듈**로 구현되면 어댑터로 교체.
- 골격 단계의 `MockClassifier`는 하드코딩(2건)이라, **실제 통합 시 `indexed.json` 형식에 맞춰**
  목을 실제 데이터 읽기로 바꿔야 함.
- 리베이스 중 확정되는 `indexed.json`(동료 `36a59d8` + 로컬 `9ecf6a3` 병합본)의
  `cases[].id`·`attachment_ids`·`attachment_texts` 키가 그대로 입력 계약이 된다.

### 2. `agent/manager.py` ↔ `app/llm.py` (규약 재사용)
- `manager.py:15` — "LLM 규약 (app/llm과 동일): callable(prompt, cache_key='') -> str"
- `app/llm.llm_call`가 이 규약을 제공하므로, `agent/`가 `app/llm`을 import하지 않더라도
  규약 호환. 라이브 기본·캐시 폴백 원칙도 동일 적용.

### 3. 패키지 분리 (충돌 회피 설계)
- `agent/` 신규 패키지는 `app/`과 분리 — 동료·개발자3 작업이 파일 경로상 **겹치지 않음**.
- 단, `tests/test_agent.py`가 `tests/`에 추가되므로 `pytest tests/` 전체 실행에 포함.
  리베이스 완료 후 `tests/` 전체 실행으로 회귀 확인 필요.

## PM 전달 요약

1. 원격 신규 커밋 없음 — 감시 기준 `f9348c0` 유지 (last_seen 갱신 완료).
2. 지시-008 산출물이 로컬에 진행 중 — **분류AI 계약(`Classifier` Protocol)이 동료 PC 분류AI의
   인터페이스 사양**이라는 점이 중요. 동료가 이 계약에 맞춰 구현해야 어댑터 교체만으로 통합된다.
3. 리베이스(`f9348c0` 위 로컬 3커밋)는 여전히 `--continue` 대기 — 빠른 확정 필요.
4. **권고**: `indexed.json` 읽기 전용 유지 + `agent/` 테스트 포함 전체 `pytest tests/ -v` 1회 실행.