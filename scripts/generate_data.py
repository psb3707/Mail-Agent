"""가상 사내 메일 400통 생성 → data/mails.json

말투는 실제 사내 메일함에서 계승, 내용은 전부 가상.
seed 고정으로 재현 가능하다.
"""
import json, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(20260910)
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
END = datetime(2026, 9, 9, tzinfo=KST)
START = END - timedelta(days=360)

ME = {"name": "박지훈", "email": "jhpark@hangyeol.co.kr", "dept": "디지털전략팀"}

PEOPLE = [
    ("김도현 / DohyunKim", "dhkim@hangyeol.co.kr", "디지털전략팀"),
    ("이수민 / SuminLee", "smlee@hangyeol.co.kr", "디지털전략팀"),
    ("박서준 / SeojunPark", "sjpark@hangyeol.co.kr", "IT기획팀"),
    ("정하늘 / HaneulJeong", "hnjeong@hangyeol.co.kr", "고객채널부"),
    ("최민석 / MinseokChoi", "mschoi@hangyeol.co.kr", "디지털전략팀"),
    ("한지우 / JiwooHan", "jwhan@hangyeol.co.kr", "경영지원부"),
    ("오세영 / SeyoungOh", "syoh@hangyeol.co.kr", "리스크관리부"),
]
SYSTEMS = [
    ("러닝포털", "no-reply@learningportal.co.kr"),
    ("그룹웨어", "system@hangyeol.co.kr"),
    ("정보보호센터", "security@hangyeol.co.kr"),
    ("인사시스템", "hr-system@hangyeol.co.kr"),
]
RE = ["RE: ", "Re: ", "FW: ", "Fw: ", ""]

mails, attachments = [], []
_mid, _aid = [0], [0]

def mid():
    _mid[0] += 1
    return f"m{_mid[0]:04d}"

def att(filename, path_ext, mime):
    _aid[0] += 1
    aid = f"a{_aid[0]:03d}"
    attachments.append({
        "id": aid, "filename": filename,
        "path": f"data/attachments/{aid}{path_ext}", "mime": mime,
    })
    return aid

XLSX = (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
PDF = (".pdf", "application/pdf")

def add(subject, sender, sent_at, body="", atts=None, reply_to=None, case=None):
    name, email, dept = sender
    m = {
        "id": mid(), "subject": subject,
        "sender_name": name, "sender_email": email, "sender_dept": dept,
        "recipients": [ME["email"]],
        "sent_at": sent_at.isoformat(),
        "body": body, "attachments": atts or [], "reply_to": reply_to,
        "_case": case,          # 정답지. 색인 파이프라인은 이 필드를 보지 않는다
    }
    mails.append(m)
    return m["id"]

def d(month, day, hour=10, minute=0, year=2026):
    return datetime(year, month, day, hour, minute, tzinfo=KST)

# ---------------------------------------------------------------- 건 A
# Project N_CX UI/UX 외주 업체 선정 — 시연 장면 1·2·3의 무대
a_quote = att("N_CX_UIUX_견적취합_v3.xlsx", *XLSX)
a_req = att("UIUX_요구사항정의서_v2.pdf", *PDF)

a_quote1 = att("N_CX_UIUX_견적취합_v1.xlsx", *XLSX)

m1 = add("〔Project N_CX〕UI/UX 외주 업체 선정 관련 협조 요청",
         PEOPLE[0], d(5, 4, 9, 20),
         "차세대 고객채널 UI/UX 외주 업체 선정 건으로 협조 요청드립니다.",
         [a_req], case="A")
add("RE: 〔Project N_CX〕UI/UX 외주 업체 선정 관련 협조 요청",
    PEOPLE[3], d(5, 7, 14, 5),
    "요구사항 검토 완료했습니다. 업체 3곳 접촉하겠습니다.",
    reply_to=m1, case="A")
add("〔Project N_CX〕 1차 견적 취합본 공유",
    PEOPLE[0], d(5, 9, 11, 30),
    "1차 취합본입니다. 업체별 단가 기준이 달라 재요청 예정입니다.",
    [a_quote1], case="A")
# 표기 흔들림: N_CX -> N CX  (검색 누락의 결정적 증거)
add("〔Project N CX〕 업체 견적 취합본 공유드립니다",
    PEOPLE[0], d(5, 12, 17, 42),
    "3개 업체 견적 취합하여 공유드립니다. 검토 부탁드립니다.",
    [a_quote], case="A")
# 말머리 없음 + 스레드 끊김 + 제목에 프로젝트명 없음
add("FW: 견적 관련 문의드립니다",
    PEOPLE[2], d(5, 14, 11, 8),
    "취합본 관련해서 단가 산정 기준 문의드립니다.", case="A")
add("〔N_CX〕 최종 업체 확정 안내",
    PEOPLE[0], d(5, 20, 16, 30),
    "최종 업체 확정되었습니다. 계약 진행하겠습니다.", case="A")

# ---------------------------------------------------------------- 건 B
a_bus = att("NextW_버스배차_최종명단.pdf", *PDF)
a_inv = att("NextW_Workshop_초대장.pdf", *PDF)

m2 = add("〔Next W〕Workshop 초대장 공유",
         PEOPLE[1], d(8, 24, 17, 10),
         "워크숍 초대장 공유드립니다.", [a_inv], case="B")
add("Re: 〔Next W〕Workshop 초대장 공유",
    PEOPLE[4], d(8, 24, 17, 56), "확인했습니다.", reply_to=m2, case="B")
add("〔Next W〕 워크샵 버스 배차 및 최종 명단",
    PEOPLE[1], d(8, 26, 16, 53),
    "버스 배차 확정되었습니다. 첨부 명단 확인 부탁드립니다.", [a_bus], case="B")
add("Fw: 워크숍 관련 안내드립니다",
    PEOPLE[5], d(9, 3, 18, 20), "집결 시간 관련 재공지드립니다.", case="B")

# ---------------------------------------------------------------- 건 C
COURSES = [
    ("〔2026 필수〕ESG경영", d(9, 1, 14, 20), d(9, 8, 10, 41)),
    ("〔2026 법정필수〕금융권 정보보호 (내근·위촉직)", d(9, 1, 13, 37), d(9, 8, 17, 44)),
    ("〔2026 필수〕윤리경영", d(9, 1, 13, 36), d(9, 8, 17, 38)),
    ("기획자를 위한 챗GPT 활용법", d(9, 1, 12, 16), d(9, 8, 17, 47)),
]
lp = ("러닝포털", "no-reply@learningportal.co.kr", "시스템")
for course, t_start, t_stat in COURSES:
    add(f"〔러닝포털〕{ME['name']}님,{course} 학습시작 안내입니다.", lp, t_start,
        f"{course} 과정 학습이 시작되었습니다.", case="C")
    add(f"〔러닝포털〕{course} 학습현황 안내입니다.", lp, t_stat,
        f"{course} 과정 학습현황을 안내드립니다.", case="C")

# ---------------------------------------------------------------- 배경 메일
# (제목, 첨부 파일명 또는 None) — 첨부는 장면 3의 "후보군"을 이룬다
BG_CASES = [
    ("D-MIG 데이터 이관", "〔D-MIG〕", [
        ("이관 대상 테이블 목록 검토 요청", ("D-MIG_이관대상_테이블목록.xlsx", XLSX)),
        ("이관 일정 협의 관련", None),
        ("이관 비용 견적서 회신드립니다", ("D-MIG_이관비용_견적서.xlsx", XLSX)),
        ("검증 결과 공유", None),
        ("이관 리허설 결과 보고", ("D-MIG_리허설결과보고.pdf", PDF)),
        ("본이관 일정 확정 안내", None)]),
    ("ESG 공시 대응", "〔ESG공시〕", [
        ("공시 항목 담당자 지정 안내", None),
        ("1차 초안 검토 요청", ("ESG공시_1차초안.pdf", PDF)),
        ("외부 검증 일정 안내", None),
        ("최종 공시안 확정", ("ESG공시_최종안_v2.pdf", PDF))]),
    ("고객채널 개선 TF", "〔고객채널TF〕", [
        ("TF 킥오프 안내", None),
        ("주간 회의록 공유", ("고객채널TF_회의록_0312.pdf", PDF)),
        ("개선 과제 우선순위 논의", None),
        ("중간 보고 자료 공유", ("고객채널TF_중간보고.pdf", PDF)),
        ("TF 종료 보고", None)]),
    ("2026 상반기 실적", "〔경영기획〕", [
        ("상반기 실적 취합 요청", ("2026_상반기_실적취합.xlsx", XLSX)),
        ("부서별 실적 자료 제출 안내", None),
        ("실적 보고회 일정 안내", None)]),
    ("정보보호 점검", "〔정보보호센터〕", [
        ("분기 보안점검 실시 안내", None),
        ("취약점 조치 요청", ("보안점검_취약점조치요청.pdf", PDF)),
        ("조치 결과 회신 요망", None)]),
    ("멘토-멘티 육성", "〔멘토-멘티〕", [
        ("육성계획서 제출 안내", ("멘토멘티_육성계획서_양식.xlsx", XLSX)),
        ("진행상황 공유 관련 공지", None),
        ("중간 점검 면담 일정", None),
        ("육성 결과 보고서 제출", ("멘토멘티_결과보고서.pdf", PDF))]),
]
SYS_TEMPLATES = [
    ("〔그룹웨어〕전자결재 미처리 건 안내", "그룹웨어"),
    ("〔인사시스템〕근태 미입력 안내드립니다", "인사시스템"),
    ("〔정보보호센터〕〔필수〕PC 보안점검 미실시 안내", "정보보호센터"),
    ("〔그룹웨어〕메일함 용량 초과 안내", "그룹웨어"),
    ("〔인사시스템〕연차 사용 촉진 안내", "인사시스템"),
    ("〔러닝포털〕미이수 과정 안내입니다", "러닝포털"),
]
# 공지는 말머리와 발신 부서를 일치시킨다 (심사자가 같은 회사 사람이라 어긋나면 티가 난다)
NOTICE_TEMPLATES = [
    ("〔전사공지〕{y}년 하계휴가 시행 안내", "경영지원부"),
    ("〔총무팀〕{n}차 사옥 정기 소방점검 실시 안내", "경영지원부"),
    ("〔인사팀〕{y}년 {half} 인사발령 공지", "경영지원부"),
    ("〔경영지원부〕법인카드 사용 지침 개정 안내 ({m}월)", "경영지원부"),
    ("〔전사공지〕정보보호의 날 캠페인 참여 안내", "리스크관리부"),
    ("〔총무팀〕주차장 공사에 따른 통제 안내 ({m}/{dd} ~ )", "경영지원부"),
    ("〔리스크관리부〕{n}분기 내부통제 점검 협조 요청", "리스크관리부"),
    ("〔IT기획팀〕{m}월 정기 시스템 점검 안내", "IT기획팀"),
]
DEPT_SENDERS = {}
for _p in PEOPLE:
    DEPT_SENDERS.setdefault(_p[2], []).append(_p)

def rand_dt():
    delta = (END - START).days
    day = START + timedelta(days=random.randint(0, delta - 1))
    return day.replace(hour=random.randint(8, 18), minute=random.choice([0, 8, 12, 20, 30, 41, 53]))

case_no = 0
for title, tag, subjects in BG_CASES:
    case_no += 1
    cid = f"BG{case_no:02d}"
    base = rand_dt()
    prev = None
    for i, (sub, spec) in enumerate(subjects):
        # 표기 흔들림을 배경 건에도 일부 섞는다
        t = tag.replace("-", " ") if (i % 4 == 3) else tag
        prefix = random.choice(RE) if prev and random.random() < 0.5 else ""
        atts = [att(spec[0], *spec[1])] if spec else []
        prev = add(f"{prefix}{t}{sub}", random.choice(PEOPLE),
                   base + timedelta(days=i * random.randint(2, 9)),
                   f"{title} 관련 내용입니다.", atts=atts, reply_to=prev, case=cid)

used_notice = set()
while len(mails) < 400:
    r = random.random()
    when = rand_dt()
    if r < 0.42:
        subject, sysname = random.choice(SYS_TEMPLATES)
        sysmap = dict((n, e) for n, e in SYSTEMS)
        add(subject, (sysname, sysmap.get(sysname, "system@hangyeol.co.kr"), "시스템"),
            when, "시스템 자동발송 메일입니다.", case=None)
    elif r < 0.68:
        tmpl, dept = random.choice(NOTICE_TEMPLATES)
        subject = tmpl.format(y=when.year, m=when.month, dd=when.day,
                              n=random.randint(1, 4),
                              half="상반기" if when.month <= 6 else "하반기")
        if subject in used_notice:      # 완전히 동일한 제목의 반복을 막는다
            continue
        used_notice.add(subject)
        add(subject, random.choice(DEPT_SENDERS.get(dept, PEOPLE)), when,
            "전사 공지사항입니다.", case=None)
    else:
        sub = random.choice([
            "〔협조〕자료 회신 요망", "〔요청〕검토 부탁드립니다",
            "회의 일정 관련 문의드립니다", "〔보고〕주간 업무 현황 공유",
            "관련 件 확인 부탁드립니다", "〔공유〕참고 자료 전달드립니다",
        ])
        add(f"{random.choice(RE)}{sub}", random.choice(PEOPLE), when,
            "업무 관련 메일입니다.", case=None)

mails.sort(key=lambda m: m["sent_at"])
out = ROOT / "data" / "mails.json"
out.write_text(json.dumps({"mails": mails, "attachments": attachments},
                          ensure_ascii=False, indent=2), encoding="utf-8")

cases = {}
for m in mails:
    if m["_case"]:
        cases.setdefault(m["_case"], []).append(m["id"])
print(f"메일 {len(mails)}통 / 첨부 {len(attachments)}개 / 건 {len(cases)}개 → {out}")
for k in ("A", "B", "C"):
    print(f"  건 {k}: {len(cases.get(k, []))}통")
