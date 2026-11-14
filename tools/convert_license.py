"""대형운전면허 문제 엑셀 → JSON 변환 (PRD 13.7)
사용법:  python tools/convert_license.py        (문제변환.bat → tools/convert.py 가 화물 변환 뒤 함께 실행)
 1) data/license/raw/문제_DL.xlsx 검사 (오류가 있으면 중단, 아무것도 바꾸지 않음)
 2) id가 빈 행에 새 번호 부여 (DL-0001 …) → 엑셀에도 기록
 3) 이전 JSON과 비교해 지문·보기·정답·해설·그림이 바뀐 문제는 version +1
 4) 유형별로 나눠 data/license/questions/<유형>.json 저장. 엑셀에서 지운 문제는 폐기(deprecated)로 남김
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lcommon as L  # noqa: E402
import validate_license  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def today():
    return datetime.date.today().isoformat()


def load_old(qdir):
    old = {}
    for code in L.TYPE_CODES:
        p = os.path.join(qdir, code + ".json")
        if os.path.exists(p):
            for q in json.load(open(p, encoding="utf-8")).get("questions", []):
                old[q["id"]] = q
    return old


def main(raw_path=None, qdir=None, quiet=False):
    raw_path = raw_path or L.RAW_PATH
    qdir = qdir or L.QDIR
    if not os.path.exists(raw_path):
        if not quiet:
            print("[대형운전면허] 엑셀 원본이 없어 건너뜀 (%s)" % raw_path)
        return 0
    errors, warnings, _ = validate_license.run("excel", quiet=True, path=raw_path)
    if errors:
        validate_license.run("excel", path=raw_path)
        print("\n[대형운전면허] 변환을 중단했습니다. 오류를 고친 뒤 다시 실행하세요.")
        return 1
    wb, ws, idx, rows = L.read_rows(raw_path)
    old = load_old(qdir)

    used = [int(L.ID_RE.match(rec["id"]).group(1)) for _, rec in rows if rec["id"]] + \
           [int(L.ID_RE.match(i).group(1)) for i in old if L.ID_RE.match(i)]
    nxt = max([n for n in used if n < L.SAMPLE_ID_MIN] + [0]) + 1
    new_ids = 0
    for r, rec in rows:
        if not rec["id"]:
            rec["id"] = "DL-%04d" % nxt
            ws.cell(row=r, column=idx["id"] + 1, value=rec["id"])
            nxt += 1
            new_ids += 1
    if new_ids:
        wb.save(raw_path)

    by_type = {c: [] for c in L.TYPE_CODES}
    added = bumped = removed = 0
    seen = set()
    for _, rec in rows:
        q = L.to_question(rec)
        seen.add(q["id"])
        prev = old.get(q["id"])
        if prev is None:
            q["version"], q["updated_at"] = 1, today()
            added += 1
        elif L.content_key(prev) != L.content_key(q):
            q["version"], q["updated_at"] = prev.get("version", 1) + 1, today()
            bumped += 1
        else:
            q["version"], q["updated_at"] = prev.get("version", 1), prev.get("updated_at", today())
        by_type[q["subject"]].append(q)
    for qid, prev in old.items():
        if qid in seen:
            continue
        prev = dict(prev)
        if prev.get("status") != "deprecated":
            prev["status"], prev["updated_at"] = "deprecated", today()
            removed += 1
        by_type.setdefault(prev.get("subject"), []).append(prev)
    os.makedirs(qdir, exist_ok=True)
    for code in L.TYPE_CODES:
        qs = sorted(by_type.get(code, []), key=lambda x: x["id"])
        doc = {"subject": code, "exam": "license", "updated_at": today(), "questions": qs}
        with open(os.path.join(qdir, code + ".json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
    if not quiet:
        print("[대형운전면허] %d문항 저장 (새 문제 %d · 수정 %d(version+1) · 엑셀에서 빠져 폐기 %d · 새 번호 부여 %d)"
              % (sum(len(v) for v in by_type.values()), added, bumped, removed, new_ids))
        for code in L.TYPE_CODES:
            print("   %-8s %d문항" % (code, len(by_type.get(code, []))))
        if warnings:
            print("   (엑셀 검사 경고 %d건 – python tools/validate_license.py 로 확인)" % len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
