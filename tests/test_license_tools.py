"""대형운전면허 도구 테스트 (v2.0 L4)
사용법: python tests/test_license_tools.py
- 엑셀 양식 v2·검사·변환(번호 부여·version·폐기)·검수표·검수 반영·안전표지·장면 그림·유사도 검사
- 모두 임시 폴더에서 실행해 실제 data/license 파일은 건드리지 않는다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import lcommon as L  # noqa: E402
import make_template_license as T  # noqa: E402
import validate_license as V  # noqa: E402
import convert_license as CV  # noqa: E402
import signs  # noqa: E402
import scene  # noqa: E402
import similarity as SIM  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

errors = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


SVG_OK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'


def row(**kw):
    base = {"id": "", "type": "TEXT1", "category": "SAFE", "question": "질문", "c1": "가", "c2": "나", "c3": "다", "c4": "라", "c5": "",
            "answer": "2", "explanation": "해설", "hint": "", "image": "", "image_alt": "", "shuffle": "", "law_ref": "", "law_date": "",
            "source": "자체 작성", "difficulty": 2, "status": "draft", "reviewer": "", "note": ""}
    base.update(kw)
    return base


def write_rows(path, rows):
    wb = load_workbook(path)
    ws = wb[L.SHEET]
    for r, rec in enumerate(rows, start=2):
        for i, (h, key) in enumerate(L.COLUMNS, start=1):
            v = rec.get(key, "")
            ws.cell(row=r, column=i).value = v if v != "" else None   # (cell(value=None)은 값을 지우지 않음)
    for r in range(len(rows) + 2, ws.max_row + 1):
        for i in range(1, len(L.COLUMNS) + 1):
            ws.cell(row=r, column=i).value = None
    wb.save(path)


def valid_rows():
    return [
        row(question="대형 문장형 질문 하나", answer="2"),
        row(type="TEXT2", question="두 개 고르는 문장형 질문", answer="1,4"),
        row(type="SIGN", category="SIGN", question="이 표지의 뜻은?", image="DL-T001.svg", image_alt="빨간 원 표지",
            law_ref="도로교통법 시행규칙 별표 6", law_date="2026-11-14", answer="3"),
        row(type="ILLUST2", question="그림 상황에서 옳은 것 2가지는?", c5="마", answer="2, 5", image="DL-T002.svg", image_alt="사거리 그림"),
        row(type="ILLUST1", question="그림 상황에서 가장 안전한 것은?", answer="①", image="DL-T003.svg", image_alt="고속도로 그림"),
        row(type="TEXT1", category="LAW", question="법규 질문", law_ref="도로교통법 제82조", law_date="2026-11-14", answer="4"),
    ]


with tempfile.TemporaryDirectory() as tmp:
    # 임시 프로젝트 구조
    L.ROOT = tmp
    raw = os.path.join(tmp, "data", "license", "raw", "문제_DL.xlsx")
    qdir = os.path.join(tmp, "data", "license", "questions")
    imgdir = os.path.join(tmp, "data", "license", "images")
    os.makedirs(imgdir)
    for n in ("DL-T001.svg", "DL-T002.svg", "DL-T003.svg"):
        open(os.path.join(imgdir, n), "w").write(SVG_OK)

    print("[1] 엑셀 양식 v2")
    T.build(raw)
    wb = load_workbook(raw)
    check(wb.sheetnames == ["문제", "작성 안내"], "시트: 문제·작성 안내")
    check([c.value for c in wb["문제"][1]] == L.HEADERS, "제목 줄 = 양식 v2 열 22개")
    check(len(L.HEADERS) == 22, "열 수 22")
    _, _, _, rows = L.read_rows(raw)
    check(rows == [], "빈 양식은 문항 0 (예시 행은 '작성 안내' 시트)")
    check(T.build(raw) is False, "이미 있으면 덮어쓰지 않음")

    print("[2] 정답 읽기")
    check(L.parse_answer("2") == [2] and L.parse_answer("1,4") == [1, 4] and L.parse_answer("4, 1") == [1, 4], "'2'·'1,4'·'4, 1'")
    check(L.parse_answer("①④") == [1, 4] and L.parse_answer("가") is None, "'①④' 허용, 글자는 오류")

    print("[3] 올바른 6문항 검사·변환")
    write_rows(raw, valid_rows())
    e, w, rep = V.run("excel", quiet=True, path=raw)
    check(e == [], "오류 없음 " + "; ".join(e))
    check(CV.main(raw, qdir, quiet=True) == 0, "변환 성공")
    files = sorted(os.listdir(qdir))
    check(files == sorted(c + ".json" for c in L.TYPE_CODES), "유형별 JSON 5개")
    allq = {}
    for code in L.TYPE_CODES:
        for q in json.load(open(os.path.join(qdir, code + ".json"), encoding="utf-8"))["questions"]:
            allq[q["id"]] = q
    check(sorted(allq) == ["DL-%04d" % n for n in range(1, 7)], "번호 DL-0001~0006 자동 부여")
    _, _, _, rows = L.read_rows(raw)
    check([r["id"] for _, r in rows] == ["DL-%04d" % n for n in range(1, 7)], "엑셀에도 번호 기록")
    q2 = allq["DL-0002"]
    check(q2["answer"] == [1, 4] and q2["subject"] == "TEXT2" and len(q2["choices"]) == 4, "TEXT2: 정답 배열 [1,4], 보기 4")
    q4 = allq["DL-0004"]
    check(q4["answer"] == [2, 5] and len(q4["choices"]) == 5 and q4["image"] == "license/images/DL-T002.svg" and q4["image_alt"] == "사거리 그림", "ILLUST2: 5지·[2,5]·그림 경로·설명")
    check("shuffle" not in q4 and "shuffle" not in allq["DL-0001"], "보기섞기 기본값은 저장하지 않음")
    check(allq["DL-0005"]["answer"] == [1], "ILLUST1 정답 ① → [1]")
    check(allq["DL-0006"]["law_ref"] == "도로교통법 제82조 (2026-11-14 기준)", "법규 기준일 붙임")
    check(all(q["version"] == 1 and q["exam"] == "license" for q in allq.values()), "version 1, exam license")
    e, w, _ = V.run("json", quiet=True, path=qdir)
    check(e == [], "변환 결과 JSON 검사 통과 " + "; ".join(e))

    print("[4] 앱 형식 검사(questions.js)와 맞는지")
    js = ("require('./src/util.js');const Q=require('./src/questions.js');const fs=require('fs');"
          "const c=Q.normalizeConfig(JSON.parse(fs.readFileSync('data/config.json')),'license');const f={};"
          "for(const g of c.exam.subjects) f[g.code]=JSON.parse(fs.readFileSync(process.argv[1]+'/'+g.code+'.json'));"
          "const b=Q.buildBank(c,f);console.log(JSON.stringify({w:b.warnings,n:Object.keys(b.byId).length}))")
    if shutil.which("node"):
        out = subprocess.run(["node", "-e", js, qdir], cwd=ROOT, capture_output=True, text=True)
        res = json.loads(out.stdout.strip() or "{}")
        check(res.get("w") == [] and res.get("n") == 6, "앱이 6문항 모두 읽음 %s" % res.get("w"))
    else:
        print("  (Node.js 없음 – 건너뜀)")

    print("[5] 수정 → version+1, 힌트·그림설명만 수정 → 그대로, 행 삭제 → 폐기, 보기섞기 지정")
    rs = valid_rows()
    for k, r in enumerate(rs):
        r["id"] = "DL-%04d" % (k + 1)
    rs[0]["question"] = "대형 문장형 질문 하나 (고침)"
    rs[1]["hint"] = "새 힌트"
    rs[3]["image_alt"] = "사거리 그림 – 설명 고침"
    rs[2]["shuffle"] = "N"
    del rs[5]
    rs.append(row(question="새로 추가한 문제"))
    write_rows(raw, rs)
    CV.main(raw, qdir, quiet=True)
    allq = {}
    for code in L.TYPE_CODES:
        for q in json.load(open(os.path.join(qdir, code + ".json"), encoding="utf-8"))["questions"]:
            allq[q["id"]] = q
    check(allq["DL-0001"]["version"] == 2, "지문 수정 → version 2")
    check(allq["DL-0002"]["version"] == 1 and allq["DL-0002"]["hint"] == "새 힌트", "힌트 수정 → version 그대로")
    check(allq["DL-0004"]["version"] == 1, "그림설명 수정 → version 그대로")
    check(allq["DL-0003"].get("shuffle") is False, "표지 보기섞기 N → shuffle:false")
    check(allq["DL-0006"]["status"] == "deprecated", "엑셀에서 지운 문제 → 폐기로 남김")
    check("DL-0007" in allq, "새 문제 DL-0007 (번호 재사용 안 함)")

    print("[6] 검사 오류")

    def errs_of(rec):
        write_rows(raw, [rec])
        e, w, _ = V.run("excel", quiet=True, path=raw)
        return " / ".join(e), " / ".join(w)
    big = os.path.join(imgdir, "BIG.svg")
    open(big, "w").write("<svg>" + "x" * (L.IMG_MAX + 10) + "</svg>")
    cases = [
        (row(type="TEXT2", answer="2"), "서로 다른 2개", "2답 유형에 정답 1개"),
        (row(type="ILLUST2", c5="", answer="1,2", image="DL-T002.svg", image_alt="그림"), "보기 5개", "5지 유형에 보기 4개"),
        (row(c5="마"), "보기5 칸이 채워져", "4지 유형에 보기5"),
        (row(type="SIGN", category="SIGN", law_ref="별표 6", law_date="2026-11-14"), "그림이 필요", "표지에 그림 없음"),
        (row(type="SIGN", category="SIGN", law_ref="별표 6", law_date="2026-11-14", image="DL-T001.svg"), "그림설명", "그림설명 없음"),
        (row(type="SIGN", category="SIGN", law_ref="별표 6", law_date="2026-11-14", image="NONE.svg", image_alt="x"), "그림 파일 없음", "그림 파일 없음"),
        (row(type="SIGN", category="SIGN", law_ref="별표 6", law_date="2026-11-14", image="BIG.svg", image_alt="x"), "KB를 넘음", "그림 100KB 초과"),
        (row(category="LAW"), "관련 법령이 필요", "법규 분류에 법령 없음"),
        (row(answer="가"), "정답 형식", "정답 형식 오류"),
        (row(answer="1,1"), "서로 다른", "같은 번호 두 번"),
        (row(type="TEXT9"), "유형은", "모르는 유형"),
        (row(category="XX"), "내용분류", "모르는 내용분류"),
        (row(id="DL-9001"), "개발·테스트 전용", "9001번 이상"),
        (row(status="verified"), "검수자", "verified인데 검수자 없음"),
        (row(shuffle="네"), "Y 또는 N", "보기섞기 값 오류"),
        (row(c2="가"), "같은 보기", "보기 중복"),
    ]
    for rec, needle, label in cases:
        e, _ = errs_of(rec)
        check(needle in e, "오류: %s" % label)
    _, w = errs_of(row(source="교재"))
    check("자체 작성" in w, "경고: 출처가 자체 작성이 아님")
    _, w = errs_of(row(hint="정답은 나다라마 라는 뜻이에요", c2="나다라마"))
    check("힌트에 정답" in w, "경고: 힌트에 정답 문구")

    print("[7] 오류가 있으면 변환 중단(파일 그대로)")
    before = open(os.path.join(qdir, "TEXT1.json"), encoding="utf-8").read()
    write_rows(raw, [row(type="TEXT2", answer="2")])
    check(CV.main(raw, qdir, quiet=True) == 1, "변환 실패 코드 1")
    check(open(os.path.join(qdir, "TEXT1.json"), encoding="utf-8").read() == before, "JSON 그대로")

    print("[8] 검수표·검수 반영")
    import make_review_sheet_license as RS
    import apply_review as AR
    import qcommon as QC
    rs = valid_rows()
    for k, r in enumerate(rs):
        r["id"] = "DL-%04d" % (k + 1)
    write_rows(raw, rs)
    sheet = os.path.join(tmp, "검수", "검수표_DL_test.xlsx")
    RS.build(sheet, path=raw)
    ws = load_workbook(sheet)["검수표"]
    head = [c.value for c in ws[1]]
    check(ws.max_row == 7 and "문제 ID" in head and "검수 판정" in head, "검수표 6문항, 반영 도구와 같은 열 이름")
    first = [ws.cell(row=r, column=head.index("1차 40") + 1).value for r in range(2, 8)]
    check(first.count("○") == 6, "유형별 1차 40 표시(문항이 적으면 전부)")
    ans_col = head.index("정답") + 1
    vals = {ws.cell(row=r, column=head.index("문제 ID") + 1).value: ws.cell(row=r, column=ans_col).value for r in range(2, 8)}
    check(vals["DL-0002"].count("\n") == 1 and vals["DL-0004"].startswith("②"), "2답 정답 두 줄 표시")
    link = [ws.cell(row=r, column=head.index("법령 바로가기") + 1).hyperlink for r in range(2, 8)]
    check(sum(1 for x in link if x) >= 1, "LAW·SIGN 법령 바로가기")
    jx = head.index("검수 판정") + 1
    for r in range(2, 8):
        qid = ws.cell(row=r, column=head.index("문제 ID") + 1).value
        v = {"DL-0003": "법령대조완료", "DL-0001": "1차확인", "DL-0005": "폐기", "DL-0002": "수정필요"}.get(qid)
        if v:
            ws.cell(row=r, column=jx, value=v)
            ws.cell(row=r, column=jx + 1, value="의견" if v == "수정필요" else None)
            ws.cell(row=r, column=jx + 2, value="검수자")
            ws.cell(row=r, column=jx + 3, value="2026-11-20")
    ws.parent.save(sheet)
    old_raw, old_codes = L.RAW_PATH, QC.CODES
    L.RAW_PATH = raw
    QC.CODES = []
    try:
        sys.argv = ["apply_review.py", sheet]
        AR.main()
    finally:
        L.RAW_PATH, QC.CODES = old_raw, old_codes
    _, _, _, rows = L.read_rows(raw)
    st = {r["id"]: r for _, r in rows}
    check(st["DL-0003"]["status"] == "verified" and st["DL-0003"]["reviewer"] == "검수자 / 2026-11-20", "법령대조완료 → verified·검수자")
    check(st["DL-0003"]["law_date"] == "2026-11-20", "SIGN 분류는 기준일을 검수일로")
    check(st["DL-0001"]["status"] == "reviewed" and st["DL-0005"]["status"] == "deprecated", "1차확인 → reviewed, 폐기 → deprecated")
    check("수정필요" in st["DL-0002"]["note"], "수정필요 → 비고에 의견")

print("[9] 안전표지 도안")
check(len(signs.SIGNS) >= 60, "표지 %d종 (60종 이상)" % len(signs.SIGNS))
kinds = {v[0] for v in signs.SIGNS.values()}
check(kinds == set(signs.KINDS), "주의·규제·지시·보조·노면 모두")
bad = []
for sid in signs.SIGNS:
    s = signs.svg(sid)
    try:
        ET.fromstring(s)
    except ET.ParseError as e:
        bad.append("%s %s" % (sid, e))
    if len(s.encode("utf-8")) > L.IMG_WARN:
        bad.append("%s 크기 %d" % (sid, len(s)))
check(not bad, "모든 표지 SVG 형식 정상·30KB 이하 " + "; ".join(bad))
check("주의" in signs.SIGNS["c-crossroad"][0] and "<title>+자형 교차로</title>" in signs.svg("c-crossroad"), "표지 이름이 SVG 제목에")
with tempfile.TemporaryDirectory() as t2:
    out = os.path.join(t2, "p.html")
    signs.preview(out)
    check(os.path.getsize(out) > 10000, "미리보기 HTML")

print("[10] 장면 그림")
bad = []
for d in scene.DEMO:
    s = scene.render(d)
    try:
        ET.fromstring(s)
    except ET.ParseError as e:
        bad.append(str(e))
    if len(s.encode("utf-8")) > L.IMG_WARN:
        bad.append("크기 %d" % len(s))
check(not bad, "예시 장면 %d개 SVG 정상·30KB 이하 %s" % (len(scene.DEMO), bad))
s = scene.render({"road": {"type": "cross", "lanes": 2}, "items": [{"kind": "sign", "id": "r-stop", "x": 10, "y": 10}], "alt": "그림 설명"})
check("<title>그림 설명</title>" in s and "정지" in s, "장면에 표지 넣기·제목")
try:
    scene.render({"items": [{"kind": "ufo", "x": 1, "y": 1}]})
    check(False, "모르는 부품은 오류")
except ValueError:
    check(True, "모르는 부품은 오류")
with tempfile.TemporaryDirectory() as t2:
    src = os.path.join(t2, "DL-0216.json")
    json.dump(scene.DEMO[0], open(src, "w", encoding="utf-8"), ensure_ascii=False)
    out = scene.render_file(src, os.path.join(t2, "DL-0216.svg"))
    check(os.path.exists(out) and ET.parse(out) is not None, "장면 파일 → SVG 파일")

print("[11] 유사도 검사")
bank = [SIM.entry("공단", "공단 1", "교차로에서 우회전할 때 가장 안전한 운전 방법은?", ["서행하며 보행자를 살핀다", "빠르게 지나간다", "경음기를 울린다", "중앙선을 넘는다"]),
        SIM.entry("공단", "공단 2", "터널 안에서 차로를 바꾸는 것에 대한 설명으로 맞는 것은?", ["금지된다", "자유롭다", "야간만 된다", "버스만 된다"])]
mine = [SIM.entry("대형", "DL-0001", "교차로에서 우회전할 때 가장 안전한 운전 방법은 무엇인가?", ["서행하며 보행자를 살핀다", "빠르게 지나간다", "경음기를 울린다", "중앙선을 넘는다"]),
        SIM.entry("대형", "DL-0002", "대형 화물차의 내륜차가 커지는 경우로 알맞은 것은?", ["축간거리가 길 때", "차가 가벼울 때", "속도가 빠를 때", "타이어가 클 때"])]
res = {q["id"]: (m, f) for q, m, f in SIM.check(mine, bank)}
check(res["DL-0001"][1] and res["DL-0001"][0][0][2]["id"] == "공단 1", "거의 같은 문장 → 재작성 검토(공단 1)")
check(not res["DL-0002"][1], "다른 문장 → 표시 안 함")
txt = SIM.report(SIM.check(mine, bank), 0.6, 0.5, {"공단": 2})
check("재작성 검토 1 / 2문항" in txt, "보고서 요약")

print("\n결과:", "모두 통과" if not errors else "실패 %d건" % len(errors))
sys.exit(1 if errors else 0)
