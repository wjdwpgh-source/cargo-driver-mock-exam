"""대형운전면허 문제 엑셀 양식 v2 공통 정의 (PRD 13.7)
- 엑셀: data/license/raw/문제_DL.xlsx, 시트 '문제', 1행 제목, 2행부터 1행 = 1문항 (유형이 섞여도 됨)
- 변환 결과: data/license/questions/<유형>.json (TEXT1·TEXT2·SIGN·ILLUST2·ILLUST1)
- 그림: data/license/images/<파일명> (SVG 권장)
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LDIR = os.path.join(ROOT, "data", "license")
RAW = os.path.join(LDIR, "raw")
QDIR = os.path.join(LDIR, "questions")
IMGDIR = os.path.join(LDIR, "images")
SCENEDIR = os.path.join(LDIR, "scenes")
RAW_PATH = os.path.join(RAW, "문제_DL.xlsx")
SHEET = "문제"
PREFIX = "DL"

# 유형 코드, 이름, 보기 수, 정답 수, 그림 필수, 1차 목표(330), 시험당 문항
TYPES = [
    ("TEXT1", "문장형", 4, 1, False, 140, 17),
    ("TEXT2", "문장형(2답)", 4, 2, False, 33, 4),
    ("SIGN", "안전표지형", 4, 1, True, 42, 5),
    ("ILLUST2", "일러스트형(2답)", 5, 2, True, 107, 13),
    ("ILLUST1", "일러스트형(상황)", 4, 1, True, 8, 1),
]
TYPE = {t[0]: {"name": t[1], "choices": t[2], "answers": t[3], "image": t[4], "target": t[5], "per_exam": t[6]} for t in TYPES}
TYPE_CODES = [t[0] for t in TYPES]
# 내용 분류 (PRD 13.6.2)
CATEGORIES = {
    "LAW": "법규", "SAFE": "안전운전", "SIGN": "안전표지", "CAR": "자동차 관리·점검",
    "AID": "응급처치", "ECO": "친환경차·PM·신기술", "HEAVY": "대형·특수 차량",
}
LAW_CATS = {"LAW", "SIGN"}   # 관련 법령·기준일 필수

COLUMNS = [
    ("id", "id"),
    ("유형", "type"),
    ("내용분류", "category"),
    ("지문", "question"),
    ("보기1", "c1"), ("보기2", "c2"), ("보기3", "c3"), ("보기4", "c4"), ("보기5", "c5"),
    ("정답", "answer"),
    ("해설", "explanation"),
    ("힌트", "hint"),
    ("그림", "image"),
    ("그림설명", "image_alt"),
    ("보기섞기", "shuffle"),
    ("관련 법령", "law_ref"),
    ("기준일", "law_date"),
    ("출처", "source"),
    ("난이도", "difficulty"),
    ("상태", "status"),
    ("검수자·검수일", "reviewer"),
    ("비고", "note"),
]
HEADERS = [c[0] for c in COLUMNS]
OPTIONAL = {"힌트", "보기섞기"}
STATUSES = ["draft", "reviewed", "verified", "deprecated"]
ID_RE = re.compile(r"^DL-(\d{4})$")
SAMPLE_ID_MIN = 9001   # 9001~9999는 개발·테스트 전용
LIMITS = {"question": 500, "choice": 150, "hint": 200, "image_alt": 300}
IMG_WARN = 30 * 1024     # 그림 1개 30KB 넘으면 경고 (NFR-03)
IMG_MAX = 100 * 1024     # 100KB 넘으면 오류
CIRCLED = "①②③④⑤"


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


def read_rows(path=RAW_PATH):
    """엑셀 문항 행 → (wb, ws, 열 위치, [(엑셀 행 번호, {키: 문자열})])"""
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
            continue
        if rec.get("note", "").startswith("[예시]"):
            continue
        rows.append((r, rec))
    return wb, ws, idx, rows


def parse_answer(text):
    """'2' → [2], '1,4' / '1, 4' / '①④' → [1, 4]. 형식이 틀리면 None"""
    t = (text or "").strip()
    for k, c in enumerate(CIRCLED):
        t = t.replace(c, ",%d," % (k + 1))
    parts = [p for p in re.split(r"[,\s/·]+", t) if p]
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return sorted(int(p) for p in parts)


def default_shuffle(type_code):
    return not type_code.startswith("ILLUST")


def to_question(rec):
    t = rec["type"]
    nc = TYPE.get(t, {}).get("choices", 4)
    ans = parse_answer(rec["answer"])
    sh = rec.get("shuffle", "").upper()
    q = {
        "id": rec["id"],
        "exam": "license",
        "subject": t,
        "category": rec["category"],
        "question": rec["question"],
        "choices": [rec["c%d" % k] for k in range(1, nc + 1)],
        "answer": ans if ans is not None else rec["answer"],
        "explanation": rec["explanation"],
        "hint": rec.get("hint", ""),
        "source": rec["source"],
        "law_ref": (rec["law_ref"] + (" (" + rec["law_date"] + " 기준)" if rec["law_date"] else "")).strip(),
        "difficulty": int(rec["difficulty"]) if rec["difficulty"].isdigit() else rec["difficulty"],
        "status": rec["status"],
    }
    if rec["image"]:
        q["image"] = rec["image"] if "/" in rec["image"] else "license/images/" + rec["image"]
        q["image_alt"] = rec["image_alt"]
    if sh in ("Y", "N") and (sh == "Y") != default_shuffle(t):
        q["shuffle"] = sh == "Y"
    return q


def image_file(q):
    """JSON의 그림 경로(data/ 기준) → 실제 파일 경로"""
    img = q.get("image")
    return os.path.join(ROOT, "data", img) if img else None


def content_key(q):
    """지문·보기·정답·해설·그림이 바뀌면 version +1 (힌트·그림설명·비고는 그대로)"""
    return "␞".join([q["question"]] + list(q["choices"]) + [str(q["answer"]), q["explanation"], q.get("image") or ""])
