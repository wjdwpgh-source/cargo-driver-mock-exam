"""문제 변환·검사 도구 테스트
사용법: python tests/test_tools.py   (임시 폴더에 복사해서 실행하므로 실제 파일은 바뀌지 않음)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
errors = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def run(tmp, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable] + list(args), cwd=tmp, capture_output=True, text=True, encoding="utf-8", env=env)
    return p.returncode, p.stdout + p.stderr


tmp = tempfile.mkdtemp()
for d in ("tools", "data"):
    shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d))
os.makedirs(os.path.join(tmp, "images"), exist_ok=True)
sys.path.insert(0, os.path.join(tmp, "tools"))
from openpyxl import load_workbook  # noqa: E402

xlsx = os.path.join(tmp, "data", "raw", "문제_LAW.xlsx")
js = os.path.join(tmp, "data", "questions", "LAW.json")


def load():
    return {q["id"]: q for q in json.load(open(js, encoding="utf-8"))["questions"]}


print("[1] 현재 엑셀 검사·변환")
code, out = run(tmp, "tools/validate.py")
check(code == 0, "엑셀 검사 통과")
code, out = run(tmp, "tools/convert.py")
check(code == 0 and "LAW" in out, "변환 성공")
before = load()
check(len(before) >= 40 and all(q["status"] == "draft" for q in before.values()), "법규 문항 저장 (draft)")
orig = {q["id"]: q["version"] for q in json.load(open(os.path.join(ROOT, "data", "questions", "LAW.json"), encoding="utf-8"))["questions"]}
check(all(q["version"] == orig[k] for k, q in before.items()), "변경 없으면 version 유지")

print("[2] 해설 수정 → version +1, 다른 문제는 그대로")
wb = load_workbook(xlsx)
ws = wb["문제"]
head = [c.value for c in ws[1]]
ws.cell(row=2, column=head.index("해설") + 1, value=ws.cell(row=2, column=head.index("해설") + 1).value + " (보완)")
qid2 = ws.cell(row=2, column=1).value
wb.save(xlsx)
run(tmp, "tools/convert.py")
after = load()
check(after[qid2]["version"] == orig[qid2] + 1, "수정한 %s version +1" % qid2)
check(sum(1 for k, q in after.items() if q["version"] == orig[k]) == len(after) - 1, "나머지는 version 그대로")

print("[3] 비고·검수자만 바꾸면 version 그대로")
wb = load_workbook(xlsx)
ws = wb["문제"]
ws.cell(row=3, column=head.index("비고") + 1, value="메모만 수정")
qid3 = ws.cell(row=3, column=1).value
wb.save(xlsx)
run(tmp, "tools/convert.py")
check(load()[qid3]["version"] == orig[qid3], "내용 외 수정은 version 유지")

print("[3-1] 힌트만 바꾸면 version 그대로, JSON에 힌트 반영 (v1.17)")
check(all(q.get("hint") for q in before.values()), "모든 법규 문항에 힌트 있음")
wb = load_workbook(xlsx)
ws = wb["문제"]
ws.cell(row=3, column=head.index("힌트") + 1, value="새 힌트 문구")
wb.save(xlsx)
run(tmp, "tools/convert.py")
check(load()[qid3]["version"] == orig[qid3] and load()[qid3]["hint"] == "새 힌트 문구", "힌트 수정은 version 유지·내용 반영")

print("[3-2] 힌트에 정답 보기 문구 → 경고(변환은 진행)")
wb = load_workbook(xlsx)
ws = wb["문제"]
ans = ws.cell(row=3, column=head.index("정답") + 1).value
ws.cell(row=3, column=head.index("힌트") + 1, value="정답은 " + ws.cell(row=3, column=head.index("보기%d" % ans) + 1).value)
wb.save(xlsx)
code, out = run(tmp, "tools/validate.py")
check(code == 0 and "힌트에 정답 보기 문구" in out, "정답 노출 경고")
ws.cell(row=3, column=head.index("힌트") + 1, value="새 힌트 문구")
wb.save(xlsx)

print("[4] 새 행(id 비움) 추가 → 다음 번호 자동 부여, 엑셀에도 기록")
wb = load_workbook(xlsx)
ws = wb["문제"]
r = len(before) + 2
vals = {"지문": "테스트 문제 지문", "보기1": "가", "보기2": "나", "보기3": "다", "보기4": "라", "정답": 3, "해설": "테스트 해설",
        "관련 법령": "도로교통법 제1조", "기준일": "2026-10-19", "출처": "자체 작성", "난이도": 1, "상태": "draft"}
for k, v in vals.items():
    ws.cell(row=r, column=head.index(k) + 1, value=v)
wb.save(xlsx)
code, out = run(tmp, "tools/convert.py")
new_id = "LAW-%04d" % (len(before) + 1)
check(new_id in load(), "새 번호 %s 부여" % new_id)
check(load_workbook(xlsx)["문제"].cell(row=r, column=1).value == new_id, "엑셀에 번호 기록")

print("[5] 행 삭제 → JSON에서는 deprecated로 남음 (번호 재사용 방지)")
wb = load_workbook(xlsx)
ws = wb["문제"]
ws.delete_rows(r)
wb.save(xlsx)
run(tmp, "tools/convert.py")
check(load()[new_id]["status"] == "deprecated", "지운 문제는 폐기 처리")

print("[6] 오류 검출 → 변환 중단, JSON 그대로")
snapshot = open(js, encoding="utf-8").read()
wb = load_workbook(xlsx)
ws = wb["문제"]
ws.cell(row=4, column=head.index("정답") + 1, value=5)                 # 정답 범위 오류
ws.cell(row=5, column=head.index("보기2") + 1, value=ws.cell(row=5, column=head.index("보기1") + 1).value)  # 보기 중복
ws.cell(row=6, column=head.index("기준일") + 1).value = None          # 법규 기준일 누락 (cell(value=None)은 값을 지우지 않음)
ws.cell(row=7, column=head.index("상태") + 1, value="verified")        # 검수자 없이 verified
ws.cell(row=8, column=1, value=ws.cell(row=9, column=1).value)          # id 중복
wb.save(xlsx)
code, out = run(tmp, "tools/convert.py")
check(code == 1 and "중단" in out, "변환 중단")
for word in ("정답은 1~4", "같은 보기", "기준일이 필요", "검수자·검수일이 없음", "id 중복"):
    check(word in out, "오류 메시지: " + word)
check(open(js, encoding="utf-8").read() == snapshot, "JSON 변경 없음")
check("행" in out, "행 번호 안내")

print("[7] 배포 전 JSON 검사 (--json)")
code, out = run(tmp, "tools/validate.py", "--json")
check(code == 0, "JSON 검사 통과")

shutil.rmtree(tmp, ignore_errors=True)

print("[8] 힌트 열이 없는 예전 양식도 변환 / 200자 넘는 힌트는 오류")
tmp = tempfile.mkdtemp()
for d in ("tools", "data"):
    shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d))
xlsx = os.path.join(tmp, "data", "raw", "문제_LAW.xlsx")
js = os.path.join(tmp, "data", "questions", "LAW.json")
wb = load_workbook(xlsx)
ws = wb["문제"]
head = [c.value for c in ws[1]]
ws.delete_cols(head.index("힌트") + 1)
wb.save(xlsx)
code, out = run(tmp, "tools/convert.py")
check(code == 0, "힌트 열 없어도 변환 성공")
check(all(not q.get("hint") and q["version"] == orig[k] for k, q in load().items()), "힌트 비움, version 유지")
wb = load_workbook(os.path.join(ROOT, "data", "raw", "문제_LAW.xlsx"))
wb.save(xlsx)
wb = load_workbook(xlsx)
ws = wb["문제"]
head = [c.value for c in ws[1]]
ws.cell(row=2, column=head.index("힌트") + 1, value="가" * 201)
wb.save(xlsx)
code, out = run(tmp, "tools/convert.py")
check(code == 1 and "힌트가 200자를 넘음" in out, "긴 힌트 오류")
wt = load_workbook(os.path.join(ROOT, "data", "raw", "문제_양식.xlsx"))
check("힌트" in [c.value for c in wt["문제"][1]] and wt["문제"].cell(row=1, column=[c.value for c in wt["문제"][1]].index("힌트") + 1).comment is not None,
      "양식에 힌트 열·안내")
shutil.rmtree(tmp, ignore_errors=True)
print("\n결과:", "모두 통과" if not errors else "실패 %d건" % len(errors))
sys.exit(1 if errors else 0)
