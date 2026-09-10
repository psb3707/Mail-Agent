# 원격 저장소 커밋 변경 보고 (2026-09-10 12:06)

저장소: `psb3707/Mail-Agent`
이전 기준: `d9e74119a895dd77b0fcbe33d37e9b06bcd01326`
새 기준: `abada17a4c3f382cba61124efd91f9ca3e086123`

## 새 커밋 (1건)

| 항목 | 값 |
|---|---|
| 해시 | `abada17a4c3f382cba61124efd91f9ca3e086123` |
| 메시지 | fix: stabilize mailbox indexing |
| 작성자 | seoungbeom (psb3707) |
| 시각 | 2026-09-10 03:01:54Z |
| 변경 규모 | +1286 / -470 (파일 4건) |

## 변경 파일

- `README.md` — 현재 상태를 "사전 준비 완료 → PoC 구현 완료, 시연 리허설 진행 중"으로 갱신. 라우트 3개 → 4개(`/classify` 추가). build_index 산출 9건/43통 재조립·비건 357통 반영.
- `data/SCHEMA.md` — 가상 메일 100통 → 400통 표기 수정.
- `data/indexed.json` — 건 그룹핑 재구성. 사례 건(case) ID·제목·기간·요약 전면 재정렬. N_CX/NextW/러닝포털 등이 안정 키 기준으로 재그룹핑되고, ESG·고객채널TF·경영기획·정보보호센터·멘토멘티 등 BG 계열 건이 분리. 비건(non_cases) 라벨도 alert/misc 재분류. 버전 계열 `version_groups`의 doc 라벨·latest가 소문자 정규화 후 최신본 재지정(`a001`).
- (커밋 성격상 `scripts/build_index.py` 및 테스트 파일의 동반 수정이 예상되나, 상기 API 응답에서 확인된 변경 파일은 위 3건임)

## 요약

mailbox 인덱싱 안정화 커밋. build_index 산출물(`data/indexed.json`)을 전면 재구성해 사례 건과 BG 계열 건·비건을 명확히 분리하고, 문서·스키마 표기를 최신 상태로 정리했다. 기존 `d9e74119` 직계 자식 커밋으로 기준 해시를 `abada17a`로 갱신한다.
