"""대형운전면허 검수표 만들기 (PRD 13.8.3 ⑦ 운영자 검수)
사용: python tools/make_review_sheet_license.py [출력 경로] [--all]
  - data/license/raw/문제_DL.xlsx에서 폐기·검수 완료되지 않은 문제를 모아 검수표로 만든다(--all이면 폐기 빼고 전부).
  - '1차 40' 표시: 실제 시험을 처음 열기 위한 유형별 17/4/5/13/1문항 (근거 ○ → △ → ×, 쉬운 문제·번호 순)
  - LAW·SIGN 문제는 국가법령정보센터 조문 바로가기, 그림 문제는 그림 파일 이름·설명을 함께 보여 준다.
  - 결과는 화물과 같은 tools/apply_review.py(검수반영.bat)로 반영한다(열 이름이 같음).
"""
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lcommon as L  # noqa: E402
from make_review_sheet import BORDER, FONT, FIRSTFILL, HEAD, INPUT, VERDICTS, evidence, law_link  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.comments import Comment  # noqa: E402
from openpyxl.formatting.rule import FormulaRule  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

COLS = [
    ("순번", 6, False), ("1차 40", 7, False), ("유형", 12, False), ("문제 ID", 10, False), ("상태", 9, False),
    ("근거", 6, False), ("내용분류", 10, False), ("지문", 44, False), ("보기", 44, False), ("정답", 26, False),
    ("해설", 48, False), ("힌트", 30, False), ("그림", 30, False), ("관련 법령", 24, False), ("법령 바로가기", 12, False),
    ("확인 포인트", 30, False), ("검수 판정", 13, True), ("수정 의견", 34, True), ("검수자", 10, True), ("검수일", 12, True),
]
COL = {c[0]: i + 1 for i, c in enumerate(COLS)}


def check_point(rec, ev):
    pts = []
    ch = [rec["c%d" % k] for k in range(1, L.TYPE[rec["type"]]["choices"] + 1)] if rec["type"] in L.TYPE else []
    if rec["category"] in L.LAW_CATS:
        if any(re.search(r"\d", c) for c in ch) or re.search(r"\d", rec["question"]):
            pts.append("숫자(속도·거리·기간·벌점 등)를 최신 조문과 대조")
        else:
            pts.append("조문 내용과 정답·보기 대조")
        if ev != "○":
            pts.append("근거 %s – 원문 확인 필수" % ev)
    else:
        pts.append("운전면허 학과 교본·안전운전 원리와 맞는지")
    if L.TYPE.get(rec["type"], {}).get("answers") == 2:
        pts.append("정답이 정확히 2개이고 나머지가 분명히 틀린지")
    else:
        pts.append("정답이 하나뿐인지")
    if rec["image"]:
        pts.append("그림과 지문·보기의 기호·방향 일치")
    pts.append("공단 문제은행 문장과 겹치지 않는지")
    return " / ".join(pts)


def collect(path=None, all_=False):
    _, _, _, rows = L.read_rows(path or L.RAW_PATH)
    items = []
    order = {"○": 0, "△": 1, "×": 2}
    for code in L.TYPE_CODES:
        recs = [r for _, r in rows if r["type"] == code and r["status"] != "deprecated" and (all_ or r["status"] != "verified")]
        ranked = sorted(recs, key=lambda r: (order[evidence(r["note"])], int(r["difficulty"] or 2), r["id"]))
        first = {r["id"] for r in ranked[:L.TYPE[code]["per_exam"]]}
        for r in recs:
            items.append((code, r, r["id"] in first, evidence(r["note"])))
    items.sort(key=lambda t: (not t[2], L.TYPE_CODES.index(t[0]), t[1]["id"]))
    return items


def build(out, path=None, all_=False):
    items = collect(path, all_)
    wb = Workbook()
    g = wb.active
    g.title = "사용법"
    for text, size, bold in [
        ("대형운전면허 문제 검수표 – 사용법", 14, True),
        ("만든 날: %s · 대상 %d문항" % (date.today().isoformat(), len(items)), 10, False),
        ("", 10, False),
        ("1. '검수표' 시트의 노란 칸(검수 판정·수정 의견·검수자·검수일)만 입력합니다.", 10, False),
        ("2. 파란 줄('1차 40' = ○)부터 보세요. 유형별 17/4/5/13/1문항이 '법령대조완료'가 되면 대형 실제 시험이 열립니다.", 10, False),
        ("3. 정답 2개 유형(TEXT2·ILLUST2)은 정답이 정확히 2개인지, 그림 문제는 그림 파일을 열어 지문·보기와 맞는지 확인하세요.", 10, False),
        ("4. LAW·SIGN 문제는 '법령 바로가기'로 최신 조문과 대조합니다.", 10, False),
        ("5. 판정: 1차확인(→reviewed) / 법령대조완료(→verified, 검수자·검수일 필수) / 수정필요(의견만 기록) / 폐기(→deprecated)", 10, False),
        ("6. 다 했으면 '검수반영.bat'을 실행하거나 이 파일을 Claude에게 보내 주세요.", 10, False),
    ]:
        g.append([text])
        g.cell(row=g.max_row, column=1).font = Font(name=FONT, size=size, bold=bold)
    g.column_dimensions["A"].width = 120

    ws = wb.create_sheet("검수표")
    ws.append([c[0] for c in COLS])
    for i, (h, w, inp) in enumerate(COLS, start=1):
        c = ws.cell(row=1, column=i)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", start_color="B7791F") if inp else HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        ws.column_dimensions[c.column_letter].width = w
    ws.cell(row=1, column=COL["1차 40"]).comment = Comment("○ = 대형 실제 시험을 처음 열기 위해 먼저 검수할 문제 (17/4/5/13/1)", "검수표")
    ws.row_dimensions[1].height = 30
    for n, (code, r, first, ev) in enumerate(items, start=1):
        nc = L.TYPE[code]["choices"]
        ch = [r["c%d" % k] for k in range(1, nc + 1)]
        ans = L.parse_answer(r["answer"]) or []
        link = law_link(r["law_ref"]) if r["category"] in L.LAW_CATS else None
        row = [n, "○" if first else "", "%s %s" % (code, L.TYPE[code]["name"]), r["id"], r["status"], ev,
               L.CATEGORIES.get(r["category"], r["category"]), r["question"],
               "\n".join("%s %s" % (L.CIRCLED[k], ch[k]) for k in range(nc)),
               "\n".join("%s %s" % (L.CIRCLED[a - 1], ch[a - 1]) for a in ans if 1 <= a <= nc),
               r["explanation"], r.get("hint", ""),
               ("%s\n%s" % (r["image"], r["image_alt"])).strip(),
               r["law_ref"] + (" (" + r["law_date"] + " 기준)" if r["law_date"] else ""),
               "열기" if link else "", check_point(r, ev), "", "", "", ""]
        ws.append(row)
        rr = ws.max_row
        for c in range(1, len(COLS) + 1):
            cell = ws.cell(row=rr, column=c)
            cell.font = Font(name=FONT, size=10, bold=(c == COL["정답"]))
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = BORDER
            if COLS[c - 1][2]:
                cell.fill = INPUT
            elif first:
                cell.fill = FIRSTFILL
        if link:
            c = ws.cell(row=rr, column=COL["법령 바로가기"])
            c.hyperlink = link
            c.font = Font(name=FONT, size=10, color="0563C1", underline="single")
    last = max(ws.max_row, 2)
    letter = {h: ws.cell(row=1, column=i).column_letter for h, i in COL.items()}
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(VERDICTS), allow_blank=True, showErrorMessage=True,
                        errorTitle="검수 판정", error="목록에서 고르세요: " + " / ".join(VERDICTS))
    dv.add("%s2:%s%d" % (letter["검수 판정"], letter["검수 판정"], last))
    ws.add_data_validation(dv)
    for r in range(2, last + 1):
        ws.cell(row=r, column=COL["검수일"]).number_format = "yyyy-mm-dd"
    rng = "A2:%s%d" % (letter["검수일"], last)
    j = letter["검수 판정"]
    for val, color in (("법령대조완료", "D8F3DC"), ("1차확인", "E3F2FD"), ("수정필요", "FFE0E0"), ("폐기", "E0E0E0")):
        ws.conditional_formatting.add(rng, FormulaRule(formula=['$%s2="%s"' % (j, val)], fill=PatternFill("solid", start_color=color, end_color=color)))
    ws.freeze_panes = ws.cell(row=2, column=COL["지문"])
    ws.auto_filter.ref = "A1:%s%d" % (letter["검수일"], last)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    wb.save(out)
    print("저장: %s (%d문항, 1차 40 = %d)" % (out, len(items), sum(1 for t in items if t[2])))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    all_ = "--all" in sys.argv
    if not os.path.exists(L.RAW_PATH):
        print("대형 엑셀 원본이 없습니다: %s" % L.RAW_PATH)
        sys.exit(1)
    if not collect(all_=all_):
        print("검수할 대형 문제가 없습니다. 전체가 필요하면 --all 을 붙이세요.")
        sys.exit(0)
    build(args[0] if args else os.path.join(L.ROOT, "검수", "검수표_DL_%s.xlsx" % date.today().isoformat()), all_=all_)
