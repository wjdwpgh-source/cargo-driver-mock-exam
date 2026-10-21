"""검수표 만들기 (PRD 8.3 ②1차 검수 · ③법령 대조)
사용: python tools/make_review_sheet.py [출력 경로]
  - 엑셀 원본(data/raw/문제_<과목>.xlsx)에서 폐기되지 않은 문제를 모아 한 장의 검수표로 만든다.
  - '1차 80' 표시: 실제 시험을 처음 열기 위한 과목별 25/15/25/15문항 (근거 ○ → △ → × 순, 같은 등급은 쉬운 문제·번호 순)
  - 법규 문제는 국가법령정보센터 조문 바로가기 링크를 붙인다.
  - 검수 결과는 tools/apply_review.py(검수반영.bat)로 엑셀 원본에 반영한다.
"""
import os
import re
import sys
import urllib.parse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qcommon as C  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.comments import Comment  # noqa: E402
from openpyxl.formatting.rule import FormulaRule  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

FONT = "Arial"
VERDICTS = ["1차확인", "법령대조완료", "수정필요", "폐기"]
NAMES = {"LAW": "법규", "CARGO": "화물취급요령", "SAFE": "안전운행", "SERVICE": "운송서비스"}
FIRST = {"LAW": 25, "CARGO": 15, "SAFE": 25, "SERVICE": 15}
CIRCLED = "①②③④"
HEAD = PatternFill("solid", start_color="1F5FBF")
INPUT = PatternFill("solid", start_color="FFF6C7")
FIRSTFILL = PatternFill("solid", start_color="EAF2FF")
THIN = Side(style="thin", color="C9D2DC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

COLS = [  # (제목, 너비, 입력칸 여부)
    ("순번", 6, False), ("1차 80", 7, False), ("과목", 11, False), ("문제 ID", 12, False), ("상태", 9, False),
    ("근거", 6, False), ("지문", 44, False), ("보기", 44, False), ("정답", 22, False), ("해설", 50, False),
    ("힌트", 34, False), ("관련 법령", 26, False), ("법령 바로가기", 14, False), ("확인 포인트", 30, False),
    ("검수 판정", 13, True), ("수정 의견", 36, True), ("검수자", 10, True), ("검수일", 12, True),
]
COL = {c[0]: i + 1 for i, c in enumerate(COLS)}


def evidence(note):
    for k in ("○", "△", "×"):
        if "근거 확인 " + k in (note or ""):
            return k
    return "×"


LAW_RE = re.compile(r"^(.+?(?:법|령|규칙|법률))\s*(제\d+조(?:의\d+)?)?")


def law_link(ref):
    """'도로교통법 시행규칙 제19조 (…)' → 국가법령정보센터 주소"""
    if not ref:
        return None
    ref = ref.split(" (")[0].split(",")[0].split("·")[0].strip()
    m = LAW_RE.match(ref)
    if not m or "이론" in ref:
        return None
    name = m.group(1).strip()
    path = "/법령/" + name + ("/" + m.group(2) if m.group(2) else "")
    return "https://www.law.go.kr" + urllib.parse.quote(path)


def check_point(code, q, ev):
    pts = []
    ch = [q["c1"], q["c2"], q["c3"], q["c4"]]
    if code == "LAW":
        if any(re.search(r"\d", c) for c in ch) or re.search(r"\d", q["question"]):
            pts.append("숫자(기간·금액·거리·나이 등)를 최신 조문과 대조")
        else:
            pts.append("조문 내용과 정답·보기 대조")
        if ev != "○":
            pts.append("근거 %s – 원문 확인 필수" % ev)
    else:
        pts.append("공단 출제 기준·교재 내용과 일치하는지")
        if any(re.search(r"\d", c) for c in ch):
            pts.append("수치 확인")
    pts.append("정답이 하나뿐인지 · 해설·힌트가 맞는지")
    return " / ".join(pts)


ALL = "--all" in sys.argv   # 기본: 검수 완료(verified)·폐기 문제는 빼고 남은 문제만 (v1.1.0 – 800문항 확장)


def collect():
    items = []
    for code in C.CODES:
        _, _, _, rows = C.read_rows(C.raw_path(code))
        recs = [r for _, r in rows if r["status"] != "deprecated" and (ALL or r["status"] != "verified")]
        order = {"○": 0, "△": 1, "×": 2}
        ranked = sorted(recs, key=lambda r: (order[evidence(r["note"])], int(r["difficulty"] or 2), r["id"]))
        first = {r["id"] for r in ranked[:FIRST[code]]}
        for r in recs:
            items.append((code, r, r["id"] in first, evidence(r["note"])))
    items.sort(key=lambda t: (not t[2], C.CODES.index(t[0]), t[1]["id"]))
    return items


def style_row(ws, r, first):
    for c in range(1, len(COLS) + 1):
        cell = ws.cell(row=r, column=c)
        cell.font = Font(name=FONT, size=10)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        cell.border = BORDER
        if COLS[c - 1][2]:
            cell.fill = INPUT
        elif first:
            cell.fill = FIRSTFILL


def build(out):
    items = collect()
    wb = Workbook()

    # ---------------- 사용법 ----------------
    g = wb.active
    g.title = "사용법"
    lines = [
        ("문제 검수표 – 사용법", 14, True),
        ("만든 날: %s · 대상: 폐기되지 않은 문제 %d문항" % (date.today().isoformat(), len(items)), 10, False),
        ("", 10, False),
        ("1. '검수표' 시트에서 노란 칸(검수 판정 · 수정 의견 · 검수자 · 검수일)만 입력합니다. 나머지 칸은 고치지 마세요(문제 수정은 '수정 의견'에 적기).", 10, False),
        ("2. 파란 줄('1차 80' = ○)부터 검수하세요. 과목별 25/15/25/15문항이 '법령대조완료'가 되면 실제 시험이 열립니다.", 10, False),
        ("3. 법규 문제는 '법령 바로가기'를 누르면 국가법령정보센터 최신 조문이 열립니다. '확인 포인트'에 적힌 것을 대조하세요.", 10, False),
        ("4. 이론 과목(화물취급·안전운행·운송서비스)은 한국교통안전공단 출제 기준·교재와 맞는지 확인합니다.", 10, False),
        ("5. 다 했으면 폴더의 '검수반영.bat'을 실행하거나 이 파일을 Claude에게 보내 주세요. 엑셀 원본에 상태·검수자가 반영됩니다.", 10, False),
        ("", 10, False),
        ("검수 판정 고르는 법", 12, True),
    ]
    for text, size, bold in lines:
        g.append([text])
        g.cell(row=g.max_row, column=1).font = Font(name=FONT, size=size, bold=bold)
    table = [
        ("판정", "언제", "반영 결과"),
        ("1차확인", "정답이 하나뿐이고 보기·해설·힌트에 문제가 없음 (법령 원문은 아직 안 봄)", "상태 draft → reviewed"),
        ("법령대조완료", "1차 확인 + 법령 원문(이론 과목은 공단 교재)과 대조까지 끝남", "상태 → verified (실제 시험에 출제). 검수자·검수일 필수"),
        ("수정필요", "정답·보기·해설·힌트를 고쳐야 함 → '수정 의견'에 어떻게 고칠지 적기", "상태 그대로, 비고에 의견 기록 → Claude가 수정"),
        ("폐기", "문제 자체를 쓸 수 없음 (법령 폐지, 중복 등)", "상태 → deprecated (출제 안 됨, 기록은 보관)"),
    ]
    start = g.max_row + 1
    for i, row in enumerate(table):
        g.append(list(row))
        for j in range(1, 4):
            c = g.cell(row=g.max_row, column=j)
            c.font = Font(name=FONT, size=10, bold=(i == 0), color="FFFFFF" if i == 0 else "000000")
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = BORDER
            if i == 0:
                c.fill = HEAD
    g.append([])
    g.append(["입력 예시 (아래 두 줄은 예시일 뿐 반영되지 않습니다)"])
    g.cell(row=g.max_row, column=1).font = Font(name=FONT, size=12, bold=True)
    g.append(["문제 ID", "검수 판정", "수정 의견", "검수자", "검수일"])
    for j in range(1, 6):
        c = g.cell(row=g.max_row, column=j)
        c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        c.fill = HEAD
    for ex in (["LAW-0001", "법령대조완료", "", "정제호", "2026-10-21"],
               ["LAW-0010", "수정필요", "정답은 맞음. 해설에 근거 조항 번호(제○조)를 넣어 주세요", "정제호", "2026-10-21"]):
        g.append(ex)
        for j in range(1, 6):
            g.cell(row=g.max_row, column=j).font = Font(name=FONT, size=10, color="555555")
            g.cell(row=g.max_row, column=j).alignment = Alignment(wrap_text=True, vertical="top")
    g.column_dimensions["A"].width = 16
    g.column_dimensions["B"].width = 60
    g.column_dimensions["C"].width = 44
    g.column_dimensions["D"].width = 10
    g.column_dimensions["E"].width = 12
    _ = start

    # ---------------- 검수표 ----------------
    ws = wb.create_sheet("검수표")
    ws.append([c[0] for c in COLS])
    for i, (h, w, inp) in enumerate(COLS, start=1):
        c = ws.cell(row=1, column=i)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", start_color="B7791F") if inp else HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        ws.column_dimensions[c.column_letter].width = w
    ws.cell(row=1, column=COL["1차 80"]).comment = Comment("○ = 실제 시험을 처음 열기 위해 먼저 검수할 문제 (과목별 25/15/25/15)", "검수표")
    ws.cell(row=1, column=COL["근거"]).comment = Comment("초안 작성 때 근거 확인 수준: ○ 원문 확인 / △ 구판·2차 자료 / × 미확인", "검수표")
    ws.cell(row=1, column=COL["검수 판정"]).comment = Comment("1차확인 / 법령대조완료 / 수정필요 / 폐기 중 선택 (사용법 시트 참고)", "검수표")
    ws.row_dimensions[1].height = 30
    for n, (code, r, first, ev) in enumerate(items, start=1):
        ch = [r["c1"], r["c2"], r["c3"], r["c4"]]
        a = int(r["answer"])
        link = law_link(r["law_ref"]) if code == "LAW" else None
        row = [n, "○" if first else "", NAMES[code], r["id"], r["status"], ev, r["question"],
               "\n".join("%s %s" % (CIRCLED[k], ch[k]) for k in range(4)),
               "%s %s" % (CIRCLED[a - 1], ch[a - 1]), r["explanation"], r.get("hint", ""),
               r["law_ref"] + (" (" + r["law_date"] + " 기준)" if r["law_date"] else ""),
               "열기" if link else "", check_point(code, r, ev), "", "", "", ""]
        ws.append(row)
        rr = ws.max_row
        style_row(ws, rr, first)
        if link:
            c = ws.cell(row=rr, column=COL["법령 바로가기"])
            c.hyperlink = link
            c.font = Font(name=FONT, size=10, color="0563C1", underline="single")
        ws.cell(row=rr, column=COL["정답"]).font = Font(name=FONT, size=10, bold=True)
    last = ws.max_row
    L = {h: ws.cell(row=1, column=i).column_letter for h, i in COL.items()}
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(VERDICTS), allow_blank=True, showErrorMessage=True,
                        errorTitle="검수 판정", error="목록에서 고르세요: " + " / ".join(VERDICTS))
    dv.add("%s2:%s%d" % (L["검수 판정"], L["검수 판정"], last))
    ws.add_data_validation(dv)
    dvd = DataValidation(type="date", operator="greaterThan", formula1="DATE(2026,1,1)", allow_blank=True,
                         showErrorMessage=True, errorTitle="검수일", error="날짜로 입력하세요 (예: 2026-10-21)")
    dvd.add("%s2:%s%d" % (L["검수일"], L["검수일"], last))
    ws.add_data_validation(dvd)
    for r in range(2, last + 1):
        ws.cell(row=r, column=COL["검수일"]).number_format = "yyyy-mm-dd"
    # 판정에 따라 줄 색 표시
    rng = "A2:%s%d" % (L["검수일"], last)
    j = L["검수 판정"]
    for val, color in (("법령대조완료", "D8F3DC"), ("1차확인", "E3F2FD"), ("수정필요", "FFE0E0"), ("폐기", "E0E0E0")):
        ws.conditional_formatting.add(rng, FormulaRule(formula=['$%s2="%s"' % (j, val)], fill=PatternFill("solid", start_color=color, end_color=color)))
    ws.freeze_panes = ws.cell(row=2, column=COL["지문"])
    ws.auto_filter.ref = "A1:%s%d" % (L["검수일"], last)

    # ---------------- 진행 현황 ----------------
    s = wb.create_sheet("진행 현황")
    s.append(["검수 진행 현황 (검수표 시트에 입력하면 자동 계산)"])
    s.cell(row=1, column=1).font = Font(name=FONT, size=14, bold=True)
    s.append([])
    hdr = ["과목", "전체 문항", "1차 80 대상", "1차확인", "법령대조완료", "수정필요", "폐기", "미검수",
           "실제 시험 필요 수", "실제 시험 가능?"]
    s.append(hdr)
    for i in range(1, len(hdr) + 1):
        c = s.cell(row=3, column=i)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        c.border = BORDER
    G = "검수표!$%s$2:$%s$%d"
    subj = G % (L["과목"], L["과목"], last)
    firstr = G % (L["1차 80"], L["1차 80"], last)
    ver = G % (L["검수 판정"], L["검수 판정"], last)
    for k, code in enumerate(C.CODES):
        r = 4 + k
        s.cell(row=r, column=1, value=NAMES[code])
        s.cell(row=r, column=2, value='=COUNTIF(%s,A%d)' % (subj, r))
        s.cell(row=r, column=3, value='=COUNTIFS(%s,A%d,%s,"○")' % (subj, r, firstr))
        for col, v in ((4, "1차확인"), (5, "법령대조완료"), (6, "수정필요"), (7, "폐기")):
            s.cell(row=r, column=col, value='=COUNTIFS(%s,A%d,%s,"%s")' % (subj, r, ver, v))
        s.cell(row=r, column=8, value="=B%d-SUM(D%d:G%d)" % (r, r, r))
        s.cell(row=r, column=9, value=FIRST[code])
        s.cell(row=r, column=10, value='=IF(E%d>=I%d,"가능","부족 "&(I%d-E%d)&"문항")' % (r, r, r, r))
    tr = 4 + len(C.CODES)
    s.cell(row=tr, column=1, value="합계")
    for col in range(2, 10):
        L2 = s.cell(row=3, column=col).column_letter
        s.cell(row=tr, column=col, value="=SUM(%s4:%s%d)" % (L2, L2, tr - 1))
    s.cell(row=tr, column=10, value='=IF(COUNTIF(J4:J%d,"가능")=%d,"실제 시험 열림","과목별 기준 미달")' % (tr - 1, len(C.CODES)))
    for r in range(4, tr + 1):
        for col in range(1, len(hdr) + 1):
            c = s.cell(row=r, column=col)
            c.font = Font(name=FONT, size=11, bold=(r == tr))
            c.border = BORDER
            c.alignment = Alignment(horizontal="center")
    s.cell(row=tr + 2, column=1, value="※ '실제 시험 필요 수'는 시험 1회 출제 수(data/config.json: 25/15/25/15)이며, 법령대조완료(verified)가 이 수 이상이면 미리보기 없이 실제 시험이 열립니다.").font = Font(name=FONT, size=9, color="555555")
    for col, w in zip("ABCDEFGHIJ", (14, 10, 11, 9, 12, 9, 7, 9, 13, 16)):
        s.column_dimensions[col].width = w

    wb.move_sheet("진행 현황", offset=-1)
    wb.active = 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    print("저장: %s (%d문항, 1차 80 = %d)" % (out, len(items), sum(1 for t in items if t[2])))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else os.path.join(C.ROOT, "검수", "검수표_%s.xlsx" % date.today().isoformat())
    build(out)
