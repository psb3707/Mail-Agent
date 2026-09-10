# 분류AI(건 트리 구축) OpenRouter 기반 설계서

> - 지시: 022 (설계서 작성 — 코드 구현 범위 아님)
> - 우선순위: **낮음** — 지시-021(UI 전면 개편)보다 후순위. 구현 지시는 본 설계 확정 후 별도 발행.
> - 상태: 설계 초안 (2026-09-10)
> - 참조: `data/SCHEMA.md`, `data/DESIGN.md`, `app/llm.py`, `agent/classifier_adapter.py`,
>   `docs/specs/2026-09-09-mail-agent-design.md`, `docs/plans/2026-09-10-mail-agent-poc.md`,
>   지시-017(LLM OpenRouter 전환), 지시-020(AI-Ready DB 연결)

---

## 1. 목적·범위

### 1-1. 목적

가상 사내 메일 400통(`data/mails.json`)을 **건(件) 단위**로 재조립하는
**분류 파이프라인의 헤드(head)** 로서, LLM(OpenRouter)을 이용해 메일을
건 라벨(`A`·`B`·`C`·`BG01`~`BG06`, 총 9종)로 분류하고,
결과를 `data/indexed.json`(AI-Ready DB) 스키마와 호환되는 JSON으로 산출한다.

기존 목표 아키텍처(지시-020)에서 분류AI는 사전 파이프라인의 중간 단계다:

```
신메일 → [규칙 전처리] → [분류AI: LLM 건 그룹핑·버전 판별] → data/indexed.json (AI-Ready DB)
        → 관리 Agent(agent/indexed_reader.py)가 소비
```

분류AI 완료 시 `agent/classifier_adapter.py`는 `IndexedReader`(지시-020) 대신
실분류AI의 산출물(`indexed.json`)만 소비하므로, **분류AI는 파이프라인 헤드**로
독립 모듈로 설계한다. 기존 규칙 기반 `scripts/build_index.py`는 LLM이 없는
오프라인 폴백 경로로 남겨두되, LLM이 있을 때 분류 품질을 높이는 **업그레이드
경로**로 취급한다(기존 색인 결과를 폐기하지 않음).

### 1-2. 범위 (이 설계서가 다루는 것)

- 메일 → 건(件) 재조립 판단 (같은 건인가)
- 건 안정 키 부여·비건(非件) 처리
- 같은 문서 버전 계열 판별 (시연 장면 4)
- 증분 편입(기존 건 참가 / 새 건 / 비건) + 순서 무관·멱등 보장

### 1-3. 비범위 (이 설계서가 다루지 않는 것)

- `data/indexed.json` **읽기**(관리 Agent 소비는 지시-020 `agent/indexed_reader.py` 담당)
- 원본 데이터(`data/mails.json`·`data/attachments/`) 수정 — 전역 제약
- DB(SQLite 등) 영속화 — 저장은 인메모리, 영속화는 비범위(PoC 한정)
- 발표용 UI 개편(지시-021) — 별도 지시

---

## 2. 입출력 계약

### 2-1. 입력

**전체 배치 (1회 색인)**

- `data/mails.json` — 기존 데이터 (400통, 불변)
  - 필드 사용: `id`, `subject`, `sender_name`, `sender_email`, `sender_dept`,
    `recipients`, `sent_at`, `body`, `attachments[]`, `reply_to`
  - `_case` 라벨은 **평가(테스트)에서만** 사용하며 분류 입력으로 쓰지 않는다.
- `data/attachments/` — 첨부 파일 (16개, 불변). LLM 분류에선 첨부 **메타데이터**(id·filename)만
  사용하고, 본문 텍스트 추출은 규칙 파이프라인(`build_index.py`의 `_extract_text`)이 담당한다.

**증분 편입 (신메일 1통)**

- 신메일 1통의 `mails.json`과 동일한 필드 구성 (새 `id`, `sent_at` 등).
- 기존 `cases[]`(인메모리 상태)와 함께 입력으로 받는다.

### 2-2. 출력

`data/indexed.json` 스키마(지시-020 계약)와 **정합**되는 JSON:

```jsonc
{
  "cases": [                       // 건(件) — 재조립 결과
    {
      "id": "c-m0001",             // 안정 키 (콘텐츠·발신자 기반, 시퀀스 아님)
      "title": "n cx",
      "mail_ids": ["m0001", ...],  // 정렬: sent_at, id
      "attachment_ids": ["a002", "a003", "a001"],
      "period": ["2026-05-04", "2026-05-20"],
      "mail_type": "프로젝트",
      "summary": "..."
    }
  ],
  "attachment_texts": { "a003": "추출된 전문..." },   // 규칙 파이프라인이 채움
  "version_groups": [               // 같은 문서 버전 계열 (장면 4)
    { "doc": "n cx uiux 견적취합", "ids": ["a003", "a001"], "latest": "a001" }
  ],
  "non_cases": [                    // 비건 357통 — 무시하지 않고 분류
    { "id": "m0123", "subject": "...", "type": "alert" | "misc" }
  ],
  "attachments": [ ... ]            // 첨부 메타데이터 (그대로 전달)
}
```

### 2-3. 의존·순서·재현 규칙

- **의존**: 분류AI는 `mails.json`(읽기)과 LLM 게이트(`app/llm.py`)에만 의존한다.
  `agent/classifier_adapter.py`·`agent/indexed_reader.py`(지시-020)와는 **산출물
  (`indexed.json`)로만** 연결된다 — 직접 호출·순환 의존 금지.
- **순서 무관**: 메일이 어떤 순서로 도착해도 같은 건으로 묶인다. 도착 시각·정렬은
  결정 근거가 아니라 **보조 단서**다. (기존 `build_index.py`의 재현 테스트 원칙 계승)
- **멱등 재색인**: 신메일이 들어와 전체를 다시 색인해도 기존 건 ID·결론이 흔들리지 않는다.
  건 ID는 시퀀스가 아니라 **콘텐츠·발신자 기반 안정 키**를 쓴다.
- **증분 편입 3종**: 신메일은 ① 기존 건에 편입 ② 새 건으로 시작 ③ 비건 처리 중 하나로
  귀결된다. 어느 건에도 안 붙는 메일의 처리 규칙이 분류의 일부다.

---

## 3. OpenRouter 호출 설계

### 3-1. 게이트 재사용: `app/llm.py`

분류AI는 지시-017로 OpenRouter에 통일된 **기존 게이트 `app/llm.py`를 그대로 재사용**한다.
새 LLM 클라이언트를 만들지 않는다.

- `app/llm.py::call_openrouter(prompt, model=None)` — raw 호출. `max_tokens` 1024 고정이므로,
  분류 배치 결과가 클 경우 **호출부에서 `max_tokens`를 인자로 받도록 확장**하거나
  배치 크기를 조절한다(§3-4).
- `app/llm.py::llm_call(prompt, cache_key="")` — 캐시 폴백 기본 경로. 분류에서도
  `cache_key`를 지정해 **동일 건 결정은 재호출 없이 캐시 재사용**할 수 있다.
  단, 캐시는 폴백·재현용이며 기본 경로 승격 금지(전역 제약).
- 확장 원칙: `app/llm.py`에 `call_openrouter(..., response_format=..., max_tokens=...)`
  옵션을 추가하는 방식으로 **확장**하고, 기존 시그니처(`llm_call`)는 그대로 둔다.
  분류 전용 프롬프트·JSON 스키마는 분류AI 모듈 내부에 둔다.

### 3-2. 모델 선택

| 후보 | 특성 | 판단 |
|---|---|---|
| `openai/o3-mini` | 저비용·고속, JSON/구조화 우수 | **권장(기본)** — 배치 분류에 적합 |
| `anthropic/claude-sonnet-4-5` | 현재 `OPENROUTER_MODEL` 기본값 | fallback/정밀 판단용 |
| `openai/gpt-4o-mini` | 저비용 대안 | 예비 후보 |

- 모델은 **환경변수 `OPENROUTER_MODEL`(또는 분류 전용 `CLASSIFIER_MODEL`)로 주입**,
  하드코딩 금지(§6).
- temperature: `0` (결정 재현성 — 분류는 생성이 아닌 판단이므로 낮은 온도).
- max_tokens: 배치 크기와 프롬프트에 따라 조절(§3-4).

### 3-3. JSON 모드 + 응답 파싱·검증·폴백

- OpenRouter `response_format: {"type": "json_object"}` 사용 — 구조화된 결정 반환.
- 응답 파싱은 `app/llm.py::parse_openrouter_response`를 재사용하고, 그 위에
  **분류 전용 검증**을 얹는다:
  - 반환 JSON이 `{ "assignments": [ { "mail_id", "case_key", "reason" } ] }` 형태인지 검증
  - 누락 필드·미지정 `mail_id`·JSON 파싱 실패 → 해당 배치만 재시도(§3-4 폴백)
- 폴백 3단계 (우선순위):
  1. **부분 재시도**: 실패한 배치만 재호출(재시도 1회, 온도 0 유지).
  2. **규칙 폴백**: LLM 불가 시 기존 `build_index.py` 규칙 결과(회신 그래프·표기 정규화)로 대체.
  3. **비건 배치 처리**: 그래도 분류 못 한 메일은 `non_cases`(alert/misc)로 안전하게 귀결 —
     어느 건에도 강제로 붙이지 않는다.

### 3-4. 배치 청킹 전략 (문맥 창 초과 방지)

400통을 한 번에 넣지 않고, **문맥 창을 넘지 않도록 청킹**한다. 원칙:

1. **1차 규칙 전처리로 후보 압축** (§4-1): 회신 그래프 연결요소·제목 표기 정규화로
   "분명히 같은 건" 후보를 묶어 LLM이 볼 양을 줄인다.
2. **청크 단위**: 하나의 요청은 대략 **30~50통** 정도의 메일 메타(제목·발신·시각·reply_to·첨부명)로
   구성한다. 전부 보내지 않고 **요약/핵심 필드만** 직렬화해 토큰을 절약한다.
3. **청크 경계**: 건 단위 or 시간대 단위로 나눈다. 같은 `reply_to` 체인은 같은 청크에 유지해
   컨텍스트를 보존한다(스레드가 청크 경계에서 끊기지 않게).
4. **병합**: 청크별 결정(같은 건 판단)을 **안정 키 기준으로 합치고**, 충돌 시
   발신자·기간·공유 첨부로 우선순위를 정한다(§4-3).
5. 증분 신메일 1통은 청킹 불필요 — 기존 건 요약 + 신메일만으로 단일 호출.

---

## 4. 알고리즘 흐름

```
[입력: mails.json or 신메일+기존 cases]
   │
   ▼
4-1. 1차 규칙 전처리 (LLM 전)
   - 제목 말머리·RE:/Re:/FW: 정규화 (build_index.py의 _norm_subject 재사용)
   - 회신 그래프(reply_to) 연결요소로 "분명한 스레드" 후보 추출
   - 시스템 발신자(sender_dept=="시스템")는 비건 후보로 우선 표시
   │
   ▼
4-2. 2차 LLM 그룹핑 (같은 건 판단) — §3
   - 청크별로 "이 메일들이 같은 건인가? 다른 건인가?" 결정 (JSON mode)
   - 결정 근거 reason(제목 일치·발신자·기간·첨부 공유)을 함께 반환 → 검증 가능
   │
   ▼
4-3. 3차 건 안정 키 부여
   - 건 키: min(mail_ids) + 발신자 + 공유 첨부 기반 (시퀀스 금지, 멱등 보장)
   - 충돌/중복 건 병합, 어느 건에도 안 붙는 메일은 비건 분류
   │
   ▼
4-4. 버전 계열 판별 (시연 장면 4)
   - 첨부 파일명 정규화(공백·구분자·_vN·_최종)로 같은 문서 계열 탐지
   - LLM이 "같은 문서의 어느 버전이 최신인가"를 판단 (규칙 폴백: 파일명 버전·일자)
   - version_groups[]: { doc, ids, latest }
   │
   ▼
4-5. 증분 편입 + 순서 무관·멱등 보장 (§2-3)
   - 신메일 1통 → 기존 건 참가 / 새 건 / 비건 3갈래로 귀결
   - 재색인해도 기존 건 ID·결론 불변 (안정 키, 순서 무관)
   │
   ▼
[출력: indexed.json 호환 JSON]
```

### 4-1. 1차 규칙 전처리

- `build_index.py::_norm_subject`·`_topic_marker`·`_reply_components`를 **그대로 재사용**한다
  (규칙으로 되는 판단은 규칙 — AI 경계 원칙).
- 목적은 LLM이 볼 양 줄이기 + "확실한 스레드" 사전 묶음. 이 단계 결과가
  최종 건을 **강제하지 않는다** — LLM이 뒤집을 수 있다(규칙이 아니라 후보 생성).

### 4-2. LLM 그룹핑

- 각 청크에 대해: "같은 건" 판단 + 근거. 비건(공지·알림·개인)은 별도 태그.
- 시연 건 A(`Project N_CX` 5통)처럼 **표기 흔들림·끊긴 스레드·축약**을 LLM이
  같은 건으로 묶는 것이 핵심 판단 대상.

### 4-3. 건 안정 키

- 규칙: `c-{min(mail_ids)}` (현재 `build_index.py` 관례 유지) + 필요 시 발신자·첨부로 보강.
- **시퀀스 금지**: 도착 순서가 바뀌어도 같은 건이 같은 키를 가져야 한다(멱등).
- QA 검증 규칙(§5): 건 라벨은 `mails.json`의 `_case`(A·B·C·BG01…)와 **1:1 id 집합 대조** —
  문자열 비교 금지.

### 4-4. 버전 계열 판별

- 파일명 정규화로 같은 문서 계열 후보 생성 → LLM이 최신본 판별.
- 예: `N_CX_UIUX_견적취합_v3.xlsx`·`_v1` → `latest` 판별 (시연 정답 1).

---

## 5. 테스트·검증 계획

- 실제 데이터 400통을 입력으로 분류AI 1회 실행(전체 배치) → **9건 라벨 재현율** 확인.
- 대조 방식 (QA 검증 규칙 반영, 지시-020·QA검증-2026-09-10-013-014 참고):
  - `mails.json`의 `_case` 라벨 집합과 분류 결과 case `mail_ids` 집합을 **1:1 대조(set comparison)**.
  - **문자열 직접 비교 금지** — `c-m0001` ↔ `A`처럼 형태가 달라 전부 오탐하는 실수 방지.
- 검증 지표:
  1. 9개 건의 `mail_ids`가 `_case` 라벨별 메일 id 집합과 **완전 일치**(재현율 1.0) — 시연 정답 3종 포함
  2. 비건 357통이 `non_cases`에 alert/misc로 올바르게 분류
  3. `version_groups`가 실제 버전 계열(예: 견적취합 v1·v3)과 일치, `latest` 정확
  4. 순서 무관·멱등 재현 테스트: 입력 순서를 뒤섞어도 같은 `cases[]`, 재색인해도 건 ID 불변
  5. 증분 편입: 신메일 1통이 기존 건/새 건/비건 중 올바른 갈래로 귀결
- 테스트는 기존 `tests/` 구조를 따르되, **LLM 실호출은 외부 의존이므로**:
  - CI/오프라인: 캐시 폴백(mock)으로 동일 시나리오 검증
  - 온라인 실측: OpenRouter 키 있을 때 1회 실호출로 재현율 측정 (결과는 별도 리포트)

---

## 6. 비용·I/O 추정

### 6-1. 호출 수·토큰 추정 (400통 전체 배치 기준)

- 청크당 ~40통 메타(제목·발신·시각·reply_to·첨부명, 평균 ~600자) → 청크당
  입력 토큰 ≈ 1.5k, 출력(JSON 결정) ≈ 0.5k.
- 청크 수 ≈ 400/40 ≈ **10회 호출** (규칙 전처리로 후보가 압축되면 그 이하).
- 증분(신메일 1통)은 건당 1회 호출.
- **추정 총 토큰**: 입력 ≈ 15k, 출력 ≈ 5k (합 ~20k/전체 색인 1회).

### 6-2. 실리미트 (hard-limit, 하드코딩 금지)

- 모든 상한(청크 크기·max_tokens·재시도 횟수·온도·모델명)은 **상수로 명시하되
  설정값(env/config)으로 주입** — 분류 모듈 코드에 임의 숫자를 박지 않는다.
- 예: `CLASSIFIER_CHUNK_SIZE=40`, `CLASSIFIER_MAX_TOKENS=4096`,
  `CLASSIFIER_MODEL=openai/o3-mini`, `CLASSIFIER_TEMPERATURE=0.0`,
  `CLASSIFIER_MAX_RETRIES=1`.

### 6-3. I/O 특성

- 읽기: `mails.json` 1회, 첨부는 LLM에 안 보냄(메타데이터만) → I/O 최소.
- 쓰기: `indexed.json` 1회(전체 색인) 또는 증분 상태 인메모리 갱신.
- 무상태 재현: 동일 입력 → 동일 결과(온도 0·캐시)로 비용 예측 가능.

---

## 7. 구현 계획서 체크리스트 (후속 지시 배정 기준)

> 이 설계서는 원래 **코드 구현이 아니었다.** 지시-022 후속으로 사용자가 구현을 요청해
> **2026-09-10 구현 완료** (개발자8). 아래 체크리스트는 구현 후 갱신된 상태다.
> **우선순위 낮음** — 지시-021(UI 개편) 완료 후 발행.

- [x] 분류 모듈 신규 생성: `scripts/classify.py`
  - 입력: `data/mails.json` / 신메일 1통 + 기존 cases (`incremental()` 함수)
  - 출력: `data/indexed.json` 스키마 호환 JSON
- [x] `app/llm.py` 확장: `call_openrouter`에 `response_format`·`max_tokens`·`model` 옵션 추가
  (기존 `llm_call` 시그니처 유지)
- [x] §4 알고리즘 5단계 구현: 규칙 전처리 → LLM 그룹핑 → 안정 키 → 버전 판별 → 증분 편입
- [x] 배치 청킹(§3-4)·JSON 검증·폴백 3단계(§3-3) 구현
- [x] 실리미트 설정화(§6-2): `CLASSIFIER_*` env 주입 (기본값은 `.env.example` 참고)
- [x] `agent/classifier_adapter.py` 교체: `IndexedReader`(지시-020) → 실분류AI 산출물 소비
  (지시-020에서 이미 IndexedReader 기반, classify.py는 `indexed.json` 호환 산출로 연결)
- [x] 테스트(§5): `tests/test_classify.py` 8건 — 1:1 대조·비건 357·버전·순서 무관·멱등·증분 편입 PASS
- [ ] 온라인 실측: OpenRouter 키로 1회 전체 색인 재현율 측정 리포트 — **`.env` 키 필요**
- [x] `data/SCHEMA.md` 갱신: 분류AI 산출 계약 명시
- [x] 기존 `pytest tests\ -v` 전체 PASS (기존 75 + 신규 8 = **83건**)

### 모델 선택 (사용자 지정 2026-09-10)

- 모델: **`deepseek/deepseek-v4-flash-0731`** (DeepSeek V4 Flash 0731, OpenRouter) — `CLASSIFIER_MODEL` 기본값
- `OPENROUTER_MODEL` env가 있으면 우선 (기존 `app/llm.py` 관례 유지)

---

## 완료 조건 대조 (지시-022)

| # | 완료 조건 | 충족 |
|---|---|---|
| 1 | 위 7개 섹션 모두 포함 | ✅ §1~§7 |
| 2 | 입출력 계약이 `data/SCHEMA.md`의 `indexed.json` 계약과 정합 | ✅ §2 — cases/attachment_texts/version_groups/non_cases/attachments 5키 일치 |
| 3 | OpenRouter 호출부가 지시-017 `app/llm.py` 재사용/확장 방식 명시 | ✅ §3-1 — 재사용 + 옵션 확장, 기존 시그니처 유지 |
| 4 | 우선순위 낮음 명시 (지시-021보다 후순위) | ✅ 본문 헤더·§7 — 구현 지시는 설계 확정 후 별도 발행 |
