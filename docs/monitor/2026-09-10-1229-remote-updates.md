# GitHub 원격 커밋 변경 감시 보고서

- 감시 시각: 2026-09-10 12:29
- 저장소: psb3707/Mail-Agent
- 직전 기준 커밋: `abada17a4c3f382cba61124efd91f9ca3e086123`
- 새 커밋: **`a79e60eb2d0551a8b42bdead029b451b9342d24e`**

## 새 커밋

| 항목 | 내용 |
|---|---|
| SHA | `a79e60eb2d0551a8b42bdead029b451b9342d24e` |
| 커밋 메시지 | `docs: add role-based behavior norms to AGENTS.md for auto-injection` |
| 작성자 | KEEKE132 (dksvlfdhs1@naver.com) |
| 커밋 시각 | 2026-09-10T03:28:24Z |
| 부모 커밋 | `abada17a4c3f382cba61124efd91f9ca3e086123` |
| 통계 | +38 / -1 (총 39) |

## 변경 파일

| 파일 | 상태 | 추가 | 삭제 |
|---|---|---|---|
| `AGENTS.md` | modified | 38 | 1 |

## 변경 요약 (한국어)

기준 커밋(`abada17`) 이후 **1건의 새 커밋**이 푸시되었다. `AGENTS.md`에 **세션 역할별 행동 규범 섹션(§8)**이 추가되어, 자동 주입을 위한 역할 기반 행동 규범이 정리되었다.

주요 내용:
- §8 "세션 역할과 행동 규범 (자동 적용)" 신설 — 역할이 같은 이름이어도 역할이 다른 세션들(개발자/QA)이 함께 작업함을 명시.
  - §8-A 개발자(구현) 세션 — 기본값: onboarding 읽기, 테스트 PASS 후 커밋, 기존 패턴 재사용, handoff.md 최신화, 결과 한국어 보고. 금지: 원본 수정·DB 도입·새 폴더 임의 생성·라이브를 캐시로 대체.
  - §8-B QA/검증자 세션: 구현·커밋·머지 금지, `docs/onboarding-qa.md` 기준 검증, `PM/DONE/QA검증-*.md` 기록.
  - §8-C 모두 공통: 위키 정리(wiki-organize), 한국어 보고(커밋 메시지는 영문 권장), `data/mails.json`·`data/attachments/` 원본 무수정.
- 기존 §8 "작업 시 지킬 것"은 **§9**로 번호 변경.

코드 로직 변경은 없으며 문서(AGENTS.md) 구조 개편만 포함된 커밋이다.
