---
"version": "1.0"
"name": "mail-agent-workspace"
"description": "발표 가독성을 위한 밝은 업무용 메일함. 중성 표면과 인디고 강조, 명확한 정보 위계."
"colors":
  "canvas": "#f7f8fa"
  "surface": "#ffffff"
  "soft": "#f0f2f6"
  "ink": "#202536"
  "muted": "#687085"
  "line": "#e3e6ed"
  "primary": "#5856d6"
  "hover": "#4543b8"
  "tint": "#eeedfc"
  "success": "#22775c"
  "success-bg": "#eaf5ef"
  "warning": "#94651d"
  "warning-bg": "#fff4df"
"typography":
  "display":
    "fontFamily": "Segoe UI, Malgun Gothic, sans-serif"
    "fontSize": "32px"
    "fontWeight": !!int "600"
    "lineHeight": !!float "1.6"
  "metric":
    "fontFamily": "Segoe UI, Malgun Gothic, sans-serif"
    "fontSize": "28px"
    "fontWeight": !!int "600"
    "lineHeight": !!float "1.6"
  "headline":
    "fontFamily": "Segoe UI, Malgun Gothic, sans-serif"
    "fontSize": "20px"
    "fontWeight": !!int "700"
    "lineHeight": !!float "1.6"
  "section":
    "fontFamily": "Segoe UI, Malgun Gothic, sans-serif"
    "fontSize": "18px"
    "fontWeight": !!int "600"
    "lineHeight": !!float "1.6"
  "card":
    "fontFamily": "Segoe UI, Malgun Gothic, sans-serif"
    "fontSize": "16px"
    "fontWeight": !!int "600"
    "lineHeight": !!float "1.6"
  "body":
    "fontFamily": "Segoe UI, Malgun Gothic, sans-serif"
    "fontSize": "14px"
    "fontWeight": !!int "400"
    "lineHeight": !!float "1.6"
  "caption":
    "fontFamily": "Segoe UI, Malgun Gothic, sans-serif"
    "fontSize": "12px"
    "fontWeight": !!int "400"
    "lineHeight": !!float "1.6"
"rounded":
  "sm": "6px"
  "md": "8px"
  "lg": "12px"
  "xl": "16px"
  "pill": "999px"
"spacing":
  "4": "4px"
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "20": "20px"
  "24": "24px"
  "32": "32px"
  "40": "40px"
"components":
  "button-primary":
    "background": "{colors.primary}"
    "text": "{colors.surface}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
  "button-hover":
    "background": "{colors.hover}"
    "text": "{colors.surface}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
  "card":
    "background": "{colors.surface}"
    "text": "{colors.ink}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
  "input":
    "background": "{colors.surface}"
    "text": "{colors.ink}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
  "nav-active":
    "background": "{colors.tint}"
    "text": "{colors.primary}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
  "evidence":
    "background": "{colors.canvas}"
    "text": "{colors.ink}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
  "badge-success":
    "background": "{colors.success-bg}"
    "text": "{colors.success}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
  "badge-warning":
    "background": "{colors.warning-bg}"
    "text": "{colors.warning}"
    "radius": "{rounded.md}"
    "padding": "{spacing.12}"
    "typography": "{typography.body}"
---

## Overview
발표용 업무 워크스페이스. 제목, 최신 대화, 메일 수, 타임라인 순으로 읽는다.
참고: https://raw.githubusercontent.com/voltagent/awesome-design-md/main/design-md/linear.app/DESIGN.md
참고 자료의 절제된 강조색과 정보 위계를 제품에 맞게 재해석했다. 밝은 팔레트는 발표용으로 새로 정의했으며 원본 브랜드의 복제는 아니다.

## Colors
- `canvas`: 페이지 배경
- `surface`: 카드와 버튼의 흰 표면
- `soft`: 보조 표면
- `ink`: 주요 텍스트
- `muted`: 보조 텍스트
- `line`: 구분선
- `primary`: 주요 행동 및 선택
- `hover`: 주요 버튼 hover 및 pressed
- `tint`: 선택 메뉴와 폴더 배경
- `success`: 최신 버전 상태
- `success-bg`: 성공 배지 표면
- `warning`: 캐시 폴백 상태
- `warning-bg`: 폴백 배지 표면

## Typography
로컬 시스템 글꼴을 사용하여 외부 폰트 로딩 없이 발표한다. display 32px, metric 28px, headline 20px, section 18px, card 16px, body 14px, caption 12px. 제목은 단단하게, 본문은 여유 있는 행간으로 표시한다.

## Layout
224px 탐색 메뉴, 72px 헤더, 40px 본문 여백. 업무 목록과 352px 질문 패널을 나란히 놓는다. 4개 지표는 실제 데이터를 사용한다. 카드 간격 16px, 큰 패널 간격 24px. 아이콘 20px, 아바타 32px, 폴더 36px.

## Elevation & Depth
기본 표면은 1px line 테두리. 선택 토글만 가벼운 그림자를 사용한다. 모달 배경은 ink 40% 불투명도. 카드 hover는 primary 테두리와 2px 이동. 키보드 포커스는 3px primary outline.

## Shapes
버튼과 입력 8px, 카드 12px, 모달 16px. 배지 6px, 아바타 원형. SVG 아이콘은 단색 선으로 통일한다.

## Components
button-primary와 button-hover는 주요 제출 동작. card는 제목, 기간, 최신 대화, 개수, 타임라인 버튼으로 구성한다. input은 레이블과 포커스를 제공한다. nav-active는 현재 메뉴를 표시한다. evidence는 실제 문서 인용. badge-success는 최신본, badge-warning은 캐시 폴백을 표시한다. 비활성 버튼은 중복 요청을 막고 진행 상태를 알린다.

### AI 답변 읽기
첫 문장은 canvas 표면과 primary 왼쪽 선으로 강조한다. 본문 body 14px, 섹션 card 16px, 출처 caption 12px. 굵은 글씨는 금액·날짜 등 핵심 값만 표시한다. 나의 질문은 tint, 파일 카드는 canvas + line, 상세 원문은 접힌 details로 구분한다. 긴 답변은 최대 880px 모달로 펼치며 본문 16px 및 제목 18px를 사용한다. 새로운 질문을 제출하면 안내 카드를 숨겨 답변에 집중한다.

## Do's and Don'ts
- 주요 행동과 선택 상태에만 인디고를 사용한다.
- 표시 수치와 파일명은 서버 데이터에서 가져온다.
- 내부 첨부 ID 대신 읽을 수 있는 파일명을 사용한다.
- 장식용 그라디언트, 임의의 강조색, 큰 그림자를 추가하지 않는다.
- 캐시 답변을 라이브 답변처럼 표시하지 않는다.
- 원본 데이터를 보존하고 라이브 LLM 기본·실패 시 폴백 원칙을 유지한다.

## Responsive Behavior
1600px 이상 카드는 3열. 1200px 이하 카드 1열 및 질문 패널 320px. 950px 이하 질문 패널은 목록 아래, 카드 2열. 650px 이하 탐색 메뉴는 상단 가로형, 지표 2열, 카드 1열, 제목 28px. 모달은 최대 85vh. reduced-motion에서는 이동 전환을 제거한다.

## Agent Prompt Guide
canvas 배경 위에 surface 카드, ink 제목, muted 메타데이터를 배치한다. primary는 선택과 제출에만 사용한다. body와 caption의 구분을 유지한다. 건 단위 카드, 도착순 검색, 문서 버전, 알림, 신규 분류, AI 질문의 단일 페이지 구조를 유지한다.
