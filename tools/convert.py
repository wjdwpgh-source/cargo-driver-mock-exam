"""문제 엑셀 → JSON 변환 (PRD 8.2)
사용법:  python tools/convert.py
 1) data/raw/문제_<과목>.xlsx 를 검사 (오류가 있으면 중단, 아무것도 바꾸지 않음)
 2) id가 빈 행에 새 번호 부여 (예: LAW-0041) → 엑셀에도 기록
 3) 이전 JSON과 비교해 지문·보기·정답·해설이 바뀐 문제는 version +1, updated_at 갱신
 4) data/questions/<과목>.json 저장, 과목별 현황 출력
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qcommon as C  # noqa: E402
import validate  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def today():
    return datetime.date.today().isoformat()


def main():
    errors, warnings, _ = validate.run("excel", quiet=True)
    if errors:
        validate.run("excel")
        print("\n변환을 중단했습니다. 오류를 고친 뒤 다시 실행하세요.")
        return 1

    changed_total = 0
    for code, name, target, per_exam in C.SUBJECTS:
        path = C.raw_path(code)
        if not os.path.exists(path):
            continue
        wb, ws, idx, rows = C.read_rows(path)
        old = {}
        if os.path.exists(C.json_path(code)):
            for q in json.load(open(C.json_path(code), encoding="utf-8")).get("questions", []):
                old[q["id"]] = q

        # 새 번호 부여
        used = [int(C.ID_RE.match(rec["id"]).group(2)) for _, rec in rows if rec["id"]] + \
               [int(C.ID_RE.match(i).group(2)) for i in old]
        nxt = max([n for n in used if n < C.SAMPLE_ID_MIN] + [0]) + 1
        new_ids = 0
        for r, rec in rows:
            if not rec["id"]:
                rec["id"] = "%s-%04d" % (code, nxt)
                ws.cell(row=r, column=idx["id"] + 1, value=rec["id"])
                nxt += 1
                new_ids += 1
        if new_ids:
            wb.save(path)

        out, bumped, added = [], 0, 0
        for _, rec in rows:
            q = C.to_question(code, rec)
            prev = old.get(q["id"])
            if prev is None:
                q["version"], q["updated_at"] = 1, today()
                added += 1
            elif C.content_key(prev) != C.content_key(q):
                q["version"], q["updated_at"] = prev.get("version", 1) + 1, today()
                bumped += 1
            else:
                q["version"], q["updated_at"] = prev.get("version", 1), prev.get("updated_at", today())
            out.append(q)
        # 엑셀에서 지워진 문제는 JSON에서도 없애지 않고 폐기 처리 (번호 재사용 방지·오답노트 보호)
        removed = 0
        for qid, prev in old.items():
            if qid not in {q["id"] for q in out} and prev.get("status") != "deprecated":
                prev = dict(prev)
                prev["status"], prev["updated_at"] = "deprecated", today()
                out.append(prev)
                removed += 1
            elif qid not in {q["id"] for q in out}:
                out.append(prev)
        out.sort(key=lambda q: q["id"])
        doc = {"subject": code, "updated_at": today(), "questions": out}
        with open(C.json_path(code), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
        changed_total += added + bumped + removed
        print("%-8s %d문항 저장 (새 문제 %d · 수정 %d(version+1) · 엑셀에서 빠져 폐기 %d · 새 번호 부여 %d)"
              % (code, len(out), added, bumped, removed, new_ids))

    print()
    validate.run("json")
    if warnings:
        print("\n(엑셀 검사 경고 %d건은 위 목록 참고)" % len(warnings))
    print("\n완료. 바뀐 문제 %d개. 배포 전에 sw.js의 VERSION 값을 올리세요." % changed_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
