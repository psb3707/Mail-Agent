# 데이터 스키마

## mails.json — 가상 사내 메일 400통

```jsonc
{
  "mails": [
    {
      "id": "m0001",
      "subject": "[협조] 차세대 ISP 관련 件 회신 요망",   // 사내 말투 그대로
      "sender_name": "김○○ 책임",
      "sender_dept": "정보전략팀",
      "sender_email": "kim@example-corp.co.kr",
      "recipients": ["me@example-corp.co.kr"],
      "sent_at": "2026-06-14T09:12:00+09:00",
      "body": "...",                    // 로컬 전용. 외부 전송 안 함
      "attachments": ["a003"],          // attachments[].id 참조
      "reply_to": "m0009"               // 스레드 관계. null 가능
    }
  ],
  "attachments": [
    {
      "id": "a003",
      "filename": "차세대ISP_견적서_v3_최종.xlsx",
      "path": "data/attachments/a003.xlsx",
      "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
  ]
}
```

**설계 제약**
- `subject`에 검색 키워드가 없는 메일을 의도적으로 포함 (시연 장면 1 성립 조건)
- 하나의 `건`이 여러 메일에 걸쳐 진행되도록 구성. `reply_to`가 끊긴 경우도 포함
  (스레드가 끊겨도 같은 건으로 묶는 게 AI의 일)
- 같은 문서의 버전 계열 3~4개 포함 (시연 장면 4 성립 조건)

## indexed.json — AI-Ready DB (분류AI → 관리 Agent 사이의 계약, classify.py 생성)

> 지시-020 확정: 분류AI가 먼저 동작해 분류된 정보와 기존 메일 정보를 수집한 뒤
> `data/indexed.json`(AI-Ready 구조 DB)로 저장하고, 관리 Agent는 이 DB를 **읽어**
> 사용자 대화에 활용한다. `agent/indexed_reader.py`가 소비 계층이며, 이 파일은
> **읽기 전용** 계약이다.
> 지시-022 구현: `scripts/classify.py`가 분류 헤드(규칙 전처리→OpenRouter LLM 그룹핑→
> 안정 키→버전 판별)로 이 파일을 생성. LLM 불가 시 `scripts/build_index.py` 규칙 결과로
> 폴백(재현율 1.0 보장).

```jsonc
{
  "cases": [                            // 건(件) — 재조립의 결과물
    {
      "id": "c01",
      "title": "차세대 ISP 구축 - 협력사 견적 검토",
      "mail_ids": ["m0009", "m0014", "m0021"],
      "attachment_ids": ["a003", "a007"],
      "period": ["2026-05-02", "2026-06-14"],
      "mail_type": "요청·협조"
    }
  ],
  "attachment_texts": { "a003": "추출된 전문..." },
  "version_groups": [                   // 같은 문서의 버전 계열 (장면 4)
    { "doc": "차세대ISP 견적서", "ids": ["a001", "a003", "a007"], "latest": "a007" }
  ],
  "non_cases": [                        // 건에 안 붙은 메일 (비건 처리)
    { "id": "m0054", "subject": "...", "type": "alert|misc" }
  ],
  "attachments": [                      // 첨부 메타 (IndexedReader가 메일과 조합)
    { "id": "a001", "filename": "...", "path": "...", "mime": "..." }
  ]
}
```

**관리 Agent 소비 계약**: `IndexedReader.get_tree() / get_case_emails() /
get_attachment_text()`가 이 파일을 조회한다. case 메일의 제목·발신·시각 메타는
indexed.json에 없으므로 원본 `mails.json`(읽기 전용)에서 보완한다 — indexed.json이
분류 결과(건 트리·첨부 전문)의 계약이고 mails.json은 메타 보조 소스다.
