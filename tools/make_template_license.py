"""대형운전면허 문제 입력용 엑셀 양식 v2 만들기 (PRD 13.7)
사용법:  python tools/make_template_license.py          → data/license/raw/문제_DL.xlsx (없을 때만 새로 만듦)
         python tools/make_template_license.py --force  → 덮어쓰기
         python tools/make_template_license.py 경로.xlsx → 그 경로에 빈 양식
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lcommon as L  # noqa: E402

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

FONT = "Arial"
WIDTH = {"id": 10, "유형": 10, "내용분류": 9, "지문": 46, "보기1": 22, "보기2": 22, "보기3": 22, "보기4": 22, "보기5": 22,
         "정답": 7, "해설": 46, "힌트": 32, "그림": 14, "그림설명": 32, "보기섞기": 8, "관련 법령": 26, "기준일": 12,
         "출처": 10, "난이도": 7, "상태": 10, "검수자·검수일": 18, "비고": 32}
HELP = {
    "id": "비워 두면 변환할 때 자동으로 번호를 붙입니다 (DL-0001). 한 번 붙은 번호는 바꾸지 마세요.",
    "유형": "TEXT1 문장형(4지1답) / TEXT2 문장형(4지2답) / SIGN 안전표지(4지1답) / ILLUST2 일러스트(5지2답) / ILLUST1 일러스트 상황(4지1답)",
    "내용분류": " / ".join("%s %s" % kv for kv in L.CATEGORIES.items()),
    "지문": "500자 이내",
    "보기1": "각 150자 이내, 같은 보기 금지. 4지 유형은 보기5를 비워 두세요.",
    "보기5": "ILLUST2(5지 2답)만 입력",
    "정답": "1답: 2 / 2답: 1,4 (쉼표로 2개)",
    "해설": "정답 근거 + 틀린 보기의 핵심 이유",
    "힌트": "선택, 200자 이내. 정답을 직접 말하지 말고 생각의 방향만. 비우면 앱이 틀린 보기 하나를 지워 줍니다.",
    "그림": "SIGN·ILLUST 필수. data/license/images 의 파일 이름 (예: DL-0174.svg)",
    "그림설명": "그림이 있으면 필수(화면 읽기용 대체 텍스트, 300자 이내). 정답을 직접 말하지 마세요.",
    "보기섞기": "Y/N. 비우면 문장·표지는 Y(복습 때 섞음), 일러스트는 N(그림 속 기호와 보기 번호 연결)",
    "관련 법령": "내용분류 LAW·SIGN 필수. 예) 도로교통법 제25조",
    "기준일": "LAW·SIGN 필수. 법령을 확인한 날짜 YYYY-MM-DD",
    "출처": "자체 작성 (도로교통공단 문제은행 원문은 쓰지 않음)",
    "난이도": "1 쉬움 · 2 보통 · 3 어려움",
    "상태": "draft 초안 → reviewed 1차 검수 → verified 법령 대조 완료(출제됨) / deprecated 폐기",
    "검수자·검수일": "verified로 바꿀 때 필수. 예) 홍길동 / 2026-11-20",
    "비고": "근거 확인 수준(근거 확인 ○/△/×), 유사도 점검, 수정 이력 메모",
}
HEAD_FILL = PatternFill("solid", start_color="1E7D43")
INPUT_FILL = PatternFill("solid", start_color="FFFDE7")
THIN = Side(style="thin", color="C9D2DC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
EXAMPLES = [
    ["", "TEXT1", "LAW", "도로교통법령상 1종 대형면허 시험에 응시할 수 있는 사람은?", "만 18세이고 운전경험이 2년인 사람",
     "만 19세이고 자동차 운전경험이 1년 이상인 사람", "만 19세이고 이륜자동차 운전경험만 2년인 사람", "만 20세이고 운전경험이 6개월인 사람", "",
     "2", "도로교통법 제82조: 대형면허는 19세 미만이거나 이륜자동차를 제외한 자동차 운전경험이 1년 미만이면 받을 수 없다.",
     "나이와 '어떤 차'로 쌓은 경험인지 두 가지를 함께 보세요.", "", "", "", "도로교통법 제82조", "2026-11-14", "자체 작성", 2, "draft", "", "[예시]"],
    ["", "ILLUST2", "SAFE", "그림과 같이 교차로에서 우회전하려는 대형 화물차(A)의 가장 안전한 운전 방법 2가지는?", "속도를 줄이며 오른쪽 뒤 사각지대를 살핀다",
     "앞차를 바짝 따라 빨리 지나간다", "보행자가 횡단보도에 있으면 기다린다", "경음기를 계속 울리며 진입한다", "왼쪽으로 크게 벌려 회전한다",
     "1,3", "대형차는 내륜차가 커서 오른쪽 뒤 사각지대 확인과 보행자 보호가 가장 중요하다.", "", "DL-0216.svg",
     "사거리 교차로, 오른쪽 아래 횡단보도에 보행자, 내 차 A는 우회전 대기", "", "", "", "자체 작성", 2, "draft", "", "[예시]"],
]


def build(path, overwrite=False):
    if os.path.exists(path) and not overwrite:
        print("이미 있습니다: %s (덮어쓰지 않음)" % path)
        return False
    wb = Workbook()
    ws = wb.active
    ws.title = L.SHEET
    ws.append(L.HEADERS)
    for i, h in enumerate(L.HEADERS, start=1):
        c = ws.cell(row=1, column=i)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        key = h if h in HELP else ("보기1" if h.startswith("보기") and h != "보기섞기" else None)
        if key:
            c.comment = Comment(HELP[key], "양식")
        ws.column_dimensions[c.column_letter].width = WIDTH.get(h, 14)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "E2"
    last = 400
    for r in range(2, last + 1):
        for i in range(1, len(L.HEADERS) + 1):
            c = ws.cell(row=r, column=i)
            c.font = Font(name=FONT, size=10)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = BORDER
            if i > 1:
                c.fill = INPUT_FILL
    col = {h: ws.cell(row=1, column=i).column_letter for i, h in enumerate(L.HEADERS, start=1)}
    lists = [
        ("유형", L.TYPE_CODES, True), ("내용분류", list(L.CATEGORIES), True), ("난이도", ["1", "2", "3"], True),
        ("상태", L.STATUSES, True), ("보기섞기", ["Y", "N"], True), ("출처", ["자체 작성"], False),
    ]
    for h, vals, strict in lists:
        dv = DataValidation(type="list", formula1='"%s"' % ",".join(vals), allow_blank=True,
                            showErrorMessage=strict, errorTitle=h, error="목록에서 고르세요: " + ", ".join(vals))
        dv.add("%s2:%s%d" % (col[h], col[h], last))
        ws.add_data_validation(dv)

    g = wb.create_sheet("작성 안내")
    lines = [
        ("대형운전면허(1종) 학과 문제 입력 양식 v2 – 작성 안내", True),
        ("", False),
        ("1. '문제' 시트에 1행 = 1문항. 유형이 섞여도 됩니다. 제목 줄(1행)은 바꾸지 마세요. 열 제목에 마우스를 올리면 규칙이 보입니다.", False),
        ("2. 유형별 형식: TEXT1 4지1답 · TEXT2 4지2답 · SIGN 4지1답(표지 그림) · ILLUST2 5지2답(상황 그림) · ILLUST1 4지1답(상황 그림, 실제 시험 동영상 자리).", False),
        ("3. 정답 2개 유형은 '1,4'처럼 쉼표로 두 개를 적습니다. 앱에서는 두 개를 모두 맞혀야 정답(부분 점수 없음).", False),
        ("4. 그림은 data/license/images 폴더에 넣고 파일 이름만 적습니다(SVG 권장, 30KB 이하). '그림설명'은 화면 읽기 프로그램이 읽는 글입니다.", False),
        ("5. 내용분류 LAW·SIGN은 관련 법령·기준일 필수. 숫자(속도·거리·기간·벌점·금액)는 국가법령정보센터 최신 조문과 대조하세요.", False),
        ("6. 도로교통공단 학과시험 문제은행은 참고만 하고 문장·보기를 옮기지 않습니다. 같은 조문도 다른 상황·다른 문장으로 묻습니다(유사도 검사: tools/similarity.py).", False),
        ("7. 상태: draft → reviewed → verified(법령 대조 완료, 출제) / deprecated(폐기 – 행을 지우지 말 것).", False),
        ("8. 입력이 끝나면 '문제변환.bat'을 실행하세요. 화물 문제와 함께 검사·변환되고, 오류는 행 번호와 함께 알려 줍니다.", False),
        ("", False),
        ("[예시] (아래 행은 예시일 뿐 변환되지 않습니다)", True),
    ]
    for text, bold in lines:
        g.append([text])
        g.cell(row=g.max_row, column=1).font = Font(name=FONT, bold=bold, size=12 if bold else 10)
    g.append(L.HEADERS)
    for i in range(1, len(L.HEADERS) + 1):
        c = g.cell(row=g.max_row, column=i)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
    for ex in EXAMPLES:
        g.append(ex)
        for i in range(1, len(L.HEADERS) + 1):
            g.cell(row=g.max_row, column=i).font = Font(name=FONT, size=10, color="555555")
    g.column_dimensions["A"].width = 14
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    print("저장: %s" % path)
    return True


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(args[0] if args else L.RAW_PATH, overwrite="--force" in sys.argv or bool(args))
