"""data/mails.json의 첨부 메타데이터대로 진짜 PDF/XLSX 파일을 만든다.

장면 3에서 "왜 이것인가"를 말할 때 인용할 실제 값(금액·일자·인원·호차)을
문서 안에 심는 것이 이 스크립트의 목적이다.
"""
import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
KO = "HYSMyeongJo-Medium"
H1 = ParagraphStyle("h1", fontName=KO, fontSize=16, leading=22, spaceAfter=10)
BODY = ParagraphStyle("body", fontName=KO, fontSize=10, leading=16)


def pdf(path, title, lines, table=None, col_widths=None):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=20 * mm, bottomMargin=20 * mm)
    flow = [Paragraph(title, H1), Spacer(1, 4 * mm)]
    for ln in lines:
        flow.append(Paragraph(ln, BODY))
    if table:
        flow.append(Spacer(1, 6 * mm))
        t = Table(table, colWidths=col_widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), KO),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(t)
    doc.build(flow)


def xlsx(path, title, header, rows, notes=()):
    wb = Workbook()
    ws = wb.active
    ws.title = re.sub(r"[\\/*?:\[\]]", " ", title)[:28].strip()
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    ws.append(header)
    for c in ws[3]:
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append(r)
    if notes:
        ws.append([])
        for n in notes:
            ws.append([n])
    for i, w in enumerate([26, 18, 18, 18, 20][:len(header)], start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    wb.save(path)


# ------------------------------------------------------------------ 정답 문서
def a_quote_v3(p):   # 시연 질문 1의 정답
    xlsx(p, "Project N_CX UI/UX 외주 견적 취합 (3차 / 최종)",
         ["업체명", "설계", "디자인", "퍼블리싱", "합계(VAT 별도)"],
         [["(주)디자인랩스", 18000000, 21500000, 9000000, 48500000],
          ["크리에이티브웍스", 21000000, 24000000, 11000000, 56000000],
          ["유엑스파트너스", 16500000, 19000000, 8500000, 44000000]],
         ["※ 작성일: 2026-05-12 (3차 취합본)",
          "※ 1차 대비 단가 산정 기준 통일 (M/M 기준 → 화면 수 기준)",
          "※ 최종 선정: (주)디자인랩스 — 48,500,000원 (VAT 별도)",
          "※ 유엑스파트너스는 최저가이나 유지보수 범위 미포함으로 제외"])


def a_quote_v1(p):   # 헷갈리게 만드는 후보 — 금액이 다르다
    xlsx(p, "Project N_CX UI/UX 외주 견적 취합 (1차)",
         ["업체명", "견적금액", "산정기준", "비고"],
         [["(주)디자인랩스", 52000000, "M/M 기준", "유지보수 포함"],
          ["크리에이티브웍스", 47000000, "화면 수 기준", "유지보수 별도"],
          ["유엑스파트너스", 61000000, "M/M 기준", "-"]],
         ["※ 작성일: 2026-05-09 (1차 취합본)",
          "※ 업체별 산정 기준이 달라 직접 비교 불가 → 재요청 예정"])


def a_bus(p):        # 시연 질문 2의 정답
    pdf(p, "Next W Workshop 버스 배차 및 최종 명단",
        ["일시: 2026-09-12(금) / 장소: 양평 리버뷰 컨벤션",
         "집결 후 정시 출발하오니 시간 엄수 부탁드립니다."],
        [["호차", "집결 장소", "출발 시각", "탑승자"],
         ["1호차", "본사 정문", "08:00", "경영지원부 12명"],
         ["2호차", "본사 정문", "08:15", "IT기획팀 14명"],
         ["3호차", "본사 정문", "08:30", "디지털전략팀 11명 (박지훈, 김도현, 이수민, 최민석 외)"],
         ["4호차", "제2사옥 후문", "08:30", "고객채널부 9명"]],
        col_widths=[22 * mm, 34 * mm, 24 * mm, 78 * mm])


DOCS = {
    "N_CX_UIUX_견적취합_v3.xlsx": a_quote_v3,
    "N_CX_UIUX_견적취합_v1.xlsx": a_quote_v1,
    "NextW_버스배차_최종명단.pdf": a_bus,
    "D-MIG_이관비용_견적서.xlsx": lambda p: xlsx(
        p, "D-MIG 데이터 이관 비용 견적서",
        ["항목", "수량", "단가", "금액"],
        [["이관 설계", 1, 12000000, 12000000],
         ["ETL 개발", 1, 15000000, 15000000],
         ["검증/리허설", 1, 5000000, 5000000]],
        ["※ 합계: 32,000,000원 (VAT 별도)", "※ 작성일: 2026-03-18",
         "※ Project N_CX와 무관한 별도 건입니다"]),
    "UIUX_요구사항정의서_v2.pdf": lambda p: pdf(
        p, "차세대 고객채널 UI/UX 요구사항 정의서 (v2)",
        ["대상: 개인뱅킹 웹/모바일 통합 채널", "총 화면 수: 148개 (신규 96 / 개선 52)",
         "작성일: 2026-05-04 / 작성: 디지털전략팀"]),
    "NextW_Workshop_초대장.pdf": lambda p: pdf(
        p, "Next W Workshop 초대장",
        ["일시: 2026-09-12(금) 09:30 ~ 18:00", "장소: 양평 리버뷰 컨벤션 3층 그랜드홀",
         "대상: Project N_CX 참여 부서 전원", "회신 마감: 2026-08-30"]),
    "D-MIG_이관대상_테이블목록.xlsx": lambda p: xlsx(
        p, "D-MIG 이관 대상 테이블 목록", ["스키마", "테이블", "건수", "우선순위"],
        [["CORE", "TB_CUST_MST", 1240000, "1"], ["CORE", "TB_ACCT_MST", 3180000, "1"],
         ["MKT", "TB_CMPGN_HIST", 890000, "2"]], ["※ 총 3개 스키마 / 47개 테이블"]),
    "D-MIG_리허설결과보고.pdf": lambda p: pdf(
        p, "D-MIG 이관 리허설 결과 보고", ["리허설 일자: 2026-04-11",
        "총 소요: 6시간 42분 (목표 8시간 이내 충족)", "검증 결과: 정합성 오류 3건 → 조치 완료"]),
    "ESG공시_1차초안.pdf": lambda p: pdf(
        p, "2026 ESG 공시 1차 초안", ["작성일: 2026-02-20", "총 47개 항목 중 31개 작성 완료"]),
    "ESG공시_최종안_v2.pdf": lambda p: pdf(
        p, "2026 ESG 공시 최종안 (v2)", ["작성일: 2026-04-30", "외부 검증 완료 (검증기관: 한국품질재단)"]),
    "고객채널TF_회의록_0312.pdf": lambda p: pdf(
        p, "고객채널 개선 TF 회의록", ["일시: 2026-03-12 14:00~15:30", "장소: 본사 7층 회의실",
        "결정사항: 개선 과제 12건 중 우선순위 상위 5건 선정, 2분기 착수"]),
    "고객채널TF_중간보고.pdf": lambda p: pdf(
        p, "고객채널 개선 TF 중간 보고", ["보고일: 2026-05-28", "진척률: 62%"]),
    "2026_상반기_실적취합.xlsx": lambda p: xlsx(
        p, "2026 상반기 부서별 실적 취합", ["부서", "목표", "실적", "달성률"],
        [["디지털전략팀", 100, 112, "112%"], ["IT기획팀", 100, 96, "96%"],
         ["고객채널부", 100, 104, "104%"]], ["※ 기준일: 2026-06-30"]),
    "보안점검_취약점조치요청.pdf": lambda p: pdf(
        p, "분기 보안점검 취약점 조치 요청", ["점검일: 2026-06-15",
        "조치 기한: 2026-06-30", "대상: 미조치 8건 (고위험 2 / 중위험 6)"]),
    "멘토멘티_육성계획서_양식.xlsx": lambda p: xlsx(
        p, "멘토-멘티 육성계획서", ["구분", "내용", "기한"],
        [["목표", "", ""], ["실행계획", "", ""], ["점검주기", "월 1회", ""]],
        ["※ 제출 기한: 2026-10-15"]),
    "멘토멘티_결과보고서.pdf": lambda p: pdf(
        p, "멘토-멘티 육성 결과 보고서", ["대상 기간: 2026-03 ~ 2026-08", "면담 횟수: 6회"]),
}

data = json.loads((ROOT / "data" / "mails.json").read_text(encoding="utf-8"))
made = 0
for a in data["attachments"]:
    target = ROOT / a["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    fn = DOCS.get(a["filename"])
    if fn is None:
        print(f"  [건너뜀] 정의 없음: {a['filename']}")
        continue
    fn(target)
    made += 1
print(f"첨부 {made}개 생성 → data/attachments/")
