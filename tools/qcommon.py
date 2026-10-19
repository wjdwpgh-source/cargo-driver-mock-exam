"""문제 엑셀 양식 공통 정의 (PRD 8.1)
- 엑셀: data/raw/문제_<과목코드>.xlsx, 시트 '문제', 1행 제목, 2행부터 1행 = 1문항
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
QDIR = os.path.join(ROOT, "data", "questions")
SHEET = "문제"

SUBJECTS = [
    # 코드, 이름, 1차 목표(400문항 기준), 시험당 문항
    ("LAW", "교통 및 화물자동차 운수사업 관련 법규", 125, 25),
    ("CARGO", "화물취급요령", 75, 15),
    ("SAFE", "안전운행", 125, 25),
    ("SERVICE", "운송서비스", 75, 15),
]
CODES = [s[0] for s in SUBJECTS]

# (열 이름, json 키, 필수 여부 설명)
COLUMNS = [
    ("id", "id"),
    ("지문", "question"),
    ("보기1", "c1"), ("보기2", "c2"), ("보기3", "c3"), ("보기4", "c4"),
    ("정답", "answer"),
    ("해설", "explanation"),
    ("힌트", "hint"),
    ("관련 법령", "law_ref"),
    ("기준일", "law_date"),
    ("출처", "source"),
    ("난이도", "difficulty"),
    ("이미지", "image"),
    ("상태", "status"),
    ("검수자·검수일", "reviewer"),
    ("비고", "note"),
]
HEADERS = [c[0] for c in COLUMNS]
OPTIONAL = {"힌트"}   # 없어도 되는 열 (예전 양식 호환, PRD v1.17)
STATUSES = ["draft", "reviewed", "verified", "deprecated"]
ID_RE = re.compile(r"^([A-Z]+)-(\d{4})$")
SAMPLE_ID_MIN = 9001   # 9001~9999는 샘플 문제 전용 (PRD v1.8)

LIMITS = {"question": 500, "choice": 150, "hint": 200}


def raw_path(code):
    return os.path.join(RAW, "문제_%s.xlsx" % code)


def json_path(code):
    return os.path.join(QDIR, "%s.json" % code)


def cell_str(v):
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def read_rows(path):
    """엑셀에서 문항 행 읽기 → [(엑셀 행 번호, {json키: 문자열})]"""
    from openpyxl import load_workbook
    wb = load_workbook(path)
    if SHEET not in wb.sheetnames:
        raise ValueError("'%s' 시트가 없습니다: %s" % (SHEET, path))
    ws = wb[SHEET]
    head = [cell_str(c.value) for c in ws[1]]
    missing = [h for h in HEADERS if h not in head and h not in OPTIONAL]
    if missing:
        raise ValueError("제목 줄에 없는 열: %s (%s)" % (", ".join(missing), path))
    idx = {h: head.index(h) for h in HEADERS if h in head}
    rows = []
    for r in range(2, ws.max_row + 1):
        vals = [c.value for c in ws[r]]
        rec = {}
        for h, key in COLUMNS:
            i = idx.get(h)
            rec[key] = cell_str(vals[i] if i is not None and i < len(vals) else None)
        if not any(rec.values()):
            continue                      # 빈 행
        if rec.get("note", "").startswith("[예시]"):
            continue                      # 양식 예시 행
        rows.append((r, rec))
    return wb, ws, idx, rows


def to_question(code, rec):
    q = {
        "id": rec["id"],
        "subject": code,
        "question": rec["question"],
        "choices": [rec["c1"], rec["c2"], rec["c3"], rec["c4"]],
        "answer": int(rec["answer"]) if rec["answer"].isdigit() else rec["answer"],
        "explanation": rec["explanation"],
        "hint": rec.get("hint", ""),
        "source": rec["source"],
        "law_ref": (rec["law_ref"] + (" (" + rec["law_date"] + " 기준)" if rec["law_date"] else "")).strip(),
        "difficulty": int(rec["difficulty"]) if rec["difficulty"].isdigit() else rec["difficulty"],
        "image": ("images/" + rec["image"]) if rec["image"] and "/" not in rec["image"] else (rec["image"] or None),
        "status": rec["status"],
    }
    return q


def content_key(q):
    """내용이 바뀌었는지 판단하는 값 (지문·보기·정답·해설). 힌트는 버전에 영향 없음"""
    return "␞".join([q["question"]] + list(q["choices"]) + [str(q["answer"]), q["explanation"]])
