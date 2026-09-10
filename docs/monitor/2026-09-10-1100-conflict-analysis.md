# 충돌·연결 지점 분석 보고 — 동료 PC 커밋 대비 (검증자 보고)

- 작성자: QA/검증자 세션 · 일시: 2026-09-10 11:0x KST
- 기준: 로컬 `main`(rebase 중) vs 원격 `origin/main` (`f9348c0`)

## 1. 최신 커밋 상황

| 구분 | 커밋 | 내용 |
|---|---|---|
| 동료(원격) | `f9348c0` | merge origin/main — PM review Actions 요약 게시 |
| 동료(원격) | `cecd7c8` / `0f752d3` | fix: publish PM review in Actions summary |
| 동료(원격) | `36a59d8` | **feat: add build_index (case grouping + attachment text + version detection)** ← D1-1 공식 |
| 내(로컬, 미푸시) | `92cac6b` | feat: app modules (grouping/llm/search/versions) + tests — D1-2/3/4/5 |
| 내(로컬, 미푸시) | `9ecf6a3` | feat: fix D1-1 project token grouping (N_CX variants + token-less mail merge) |

## 2. 🔴 실제 병합 충돌 (2개 파일 — rebase 중 중단 상태)

현재 워크트리는 **interactive rebase 진행 중**(`onto f9348c0`)이며, 아래 2개 파일이 충돌 상태로 멈춰 있다.

| 파일 | 충돌 종류 | 원인 |
|---|---|---|
| `data/indexed.json` | **add/add** (both added) | 동료가 `36a59d8`에서 생성, 나(`9ecf6a3`)도 생성 → 같은 경로에 서로 다른 산출물 |
| `scripts/build_index.py` | **content** (both modified) | 동료는 D1-1 그룹핑 공식 구현, 나는 토큰 그룹핑 결함 수정 → 같은 함수(`_project_token`, `build_index`)를 서로 다르게 수정 |

**필수 확인**: `data/indexed.json`과 `scripts/build_index.py`는 `PM/COMMON.md` 규약상 **읽기 전용**인데, 두 쪽 모두 이 파일을 수정했다는 점이 재설계가 필요한 신호다.

## 3. 내용 수준 충돌 분석

### 3-1. `scripts/build_index.py` — 기능 충돌 (해결 안 하면 D1-1이 이중 구현)

| 쪽 | 변경 방향 |
|---|---|
| 동료 `36a59d8` | `_project_token` 정규화(N_CX 변종 통일), `_STOPWORDS`, 토큰 없는 메일을 키워드 교집합으로 case 편입, `_sent_at` 기반 정렬, `non_cases`에서 `joined` 제외 |
| 나 `9ecf6a3` | 같은 목적(토큰 변종·무토큰 편입)을 다른 방식으로 구현 |

→ **같은 목표의 중복 구현**. 리베이스에서 "동료 버전을 기준으로 삼고 내 수정을 병합"할지, "내 버전을 유지"할지 결정 필요. 별도 분기에서 같은 일을 한 것.

### 3-2. `data/indexed.json` — 산출물 정합성

- 동료 버전 `95fc135`: `cases: 4` (c-m0019 d mig · c-m0025 esg · c-m0001 n cx · c-m0007 next w), `non_cases` 많음 (66+)
- 내 버전 `321ab87`: 동료 버전 생성 전에 만든 것으로 추정

→ `build_index.py`를 어느 쪽으로 확정하든 **산출물을 재생성**(`python scripts/build_index.py`)해서 기준에 맞춰야 한다.

## 4. ⚠️ PM 검토 필요 — "읽기 전용" 규약 위반 소지

`PM/COMMON.md`·`ISSUES.md`는 `data/indexed.json`·`scripts/build_index.py`를 **읽기 전용**으로 규정.
그런데 이번에 동료(원격)와 나(로컬) 양쪽이 모두 이 파일을 수정·생성했다.
- **단일 산출물(`indexed.json`)을 두 작업자가 동시에 만든 것이 병합 충돌의 근본 원인.**
- PM 판단 필요: (a) `indexed.json`은 "재생성 가능한 파생물"로 격하해 커밋에서 제외(.gitignore)하거나,
  (b) 파일 소유권을 개발자1에게 명시하고 타인 수정 금지 재확인.

## 5. 🔶 연결 지점 (충돌은 아니지만 기능이 맞물리는 곳)

| 연결 대상 | 내용 |
|---|---|
| `app/main.py`(내 D1-6) ↔ `scripts/build_index.py`(동료) | main.py가 `indexed.json`을 로드 → build_index가 만든 `cases[]` 스키마에 의존. 리베이스 결과에 따라 스키마가 달라지면 main.py 수정 필요 |
| `app/search.py` ↔ `scripts/build_index.py` | `attachment_texts`·`cases[].title` 형식 의존. 동료 버전의 토큰 제목('n cx', 'd mig')이 검색 코퍼스에 그대로 들어감 → 질의 정확도에 영향 |
| `data/indexed.json` ↔ `app/` 전체 | app 모듈 테스트(D1-2~5)가 이 파일에서 로드 → 충돌 해결 후 **반드시 pytest 전원 패스 재확인** |

## 6. 권고 조치 (다음 단계)

1. **리베이스 충돌 해결**: `scripts/build_index.py`는 동료 공식 버전(원격)을 베이스로 두고, 내 `9ecf6a3`의 추가 개선만 취한다. `data/indexed.json`은 새 build_index로 재생성.
2. **테스트 검증**: `.venv\Scripts\python.exe -m pytest tests -v` → 12+건 전원 통과 확인.
3. **PM 보고**: `PM/DONE/` 또는 검증자 보고 채널로 본 문서 전달. 특히 **"동시 산출물 충돌" 재발 방지 규정**(§4)을 제안.
4. 칸반 발견 카드 등록: `kanban_discovery_card` — category `standard_violation` (indexed.json 동시 수정) / `doc_mismatch` (필요 시).