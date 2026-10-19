"""문제 데이터 검사 (PRD 8.2)
사용법:  python tools/validate.py            → data/raw/문제_*.xlsx 검사
         python tools/validate.py --json     → data/questions/*.json 검사 (배포 전 자동 검사용)
오류가 있으면 종료 코드 1
"""
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qcommon as C  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_question(code, q, where, errors, warnings, root=C.ROOT):
    def err(msg):
        errors.append("%s %s: %s" % (where, q.get("id") or "(id 없음)", msg))

    def warn(msg):
        warnings.append("%s %s: %s" % (where, q.get("id") or "(id 없음)", msg))

    qid = q.get("id") or ""
    if qid:
        m = C.ID_RE.match(qid)
        if not m:
            err("id 형식 오류 (예: LAW-0001)")
        elif m.group(1) != code:
            err("id의 과목코드(%s)가 파일 과목(%s)과 다름" % (m.group(1), code))
        elif int(m.group(2)) >= C.SAMPLE_ID_MIN:
            err("9001번 이상은 샘플 문제 전용 번호입니다")
    text = q.get("question", "")
    if not text:
        err("지문이 비어 있음")
    elif len(text) > C.LIMITS["question"]:
        err("지문이 %d자를 넘음 (%d자)" % (C.LIMITS["question"], len(text)))
    ch = q.get("choices", [])
    if len(ch) != 4 or any(not c for c in ch):
        err("보기 4개가 모두 필요")
    else:
        for i, c in enumerate(ch):
            if len(c) > C.LIMITS["choice"]:
                err("보기%d가 %d자를 넘음" % (i + 1, C.LIMITS["choice"]))
        if len(set(ch)) < 4:
            err("같은 보기가 있음")
    if q.get("answer") not in (1, 2, 3, 4):
        err("정답은 1~4 숫자여야 함 (현재: %r)" % q.get("answer"))
    if not q.get("explanation"):
        err("해설이 비어 있음")
    hint = q.get("hint") or ""
    if hint:
        if len(hint) > C.LIMITS["hint"]:
            err("힌트가 %d자를 넘음 (%d자)" % (C.LIMITS["hint"], len(hint)))
        a = q.get("answer")
        if a in (1, 2, 3, 4) and len(ch) == 4 and ch[a - 1] and len(ch[a - 1]) >= 4 and ch[a - 1] in hint:
            warn("힌트에 정답 보기 문구가 그대로 들어 있음")
    if not q.get("source"):
        err("출처가 비어 있음 (자체 작성 / 공단 공개 자료 / 이용 허락 자료)")
    if q.get("difficulty") not in (1, 2, 3):
        err("난이도는 1~3")
    st = q.get("status")
    if st not in C.STATUSES:
        err("상태는 %s 중 하나" % "/".join(C.STATUSES))
    if code == "LAW":
        if not q.get("law_ref_raw"):
            err("법규 과목은 관련 법령이 필요")
        if not q.get("law_date_raw"):
            err("법규 과목은 기준일이 필요")
    if q.get("law_date_raw") and not DATE_RE.match(q["law_date_raw"]):
        err("기준일은 YYYY-MM-DD 형식")
    if st == "verified" and not q.get("reviewer_raw"):
        err("verified인데 검수자·검수일이 없음")
    img = q.get("image")
    if img:
        p = os.path.join(root, img)
        if not os.path.exists(p):
            err("이미지 파일 없음: %s" % img)
        elif os.path.getsize(p) > 200 * 1024:
            warn("이미지가 200KB를 넘음 (WebP로 압축 권장)")


def similar_pairs(items, threshold=0.9):
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if difflib.SequenceMatcher(None, a[1], b[1]).ratio() >= threshold:
                out.append((a[0], b[0]))
    return out


def load_from_excel():
    data = {}
    for code in C.CODES:
        p = C.raw_path(code)
        if not os.path.exists(p):
            data[code] = None
            continue
        _, _, _, rows = C.read_rows(p)
        qs = []
        for r, rec in rows:
            q = C.to_question(code, rec)
            q["law_ref_raw"], q["law_date_raw"], q["reviewer_raw"] = rec["law_ref"], rec["law_date"], rec["reviewer"]
            q["_where"] = "문제_%s.xlsx %d행" % (code, r)
            qs.append(q)
        data[code] = qs
    return data


def load_from_json():
    data = {}
    for code in C.CODES:
        p = C.json_path(code)
        if not os.path.exists(p):
            data[code] = None
            continue
        j = json.load(open(p, encoding="utf-8"))
        qs = []
        for q in j.get("questions", []):
            q = dict(q)
            q["law_ref_raw"] = q.get("law_ref", "")
            m = re.search(r"\((\d{4}-\d{2}-\d{2}) 기준\)", q.get("law_ref", ""))
            q["law_date_raw"] = m.group(1) if m else ""
            q["reviewer_raw"] = "json"   # JSON에는 검수자 정보가 없으므로 엑셀 단계에서 확인
            q["_where"] = "%s.json" % code
            qs.append(q)
        data[code] = qs
    return data


def run(mode="excel", quiet=False):
    data = load_from_excel() if mode == "excel" else load_from_json()
    errors, warnings, report = [], [], []
    seen = {}
    for code, name, target, per_exam in C.SUBJECTS:
        qs = data.get(code)
        if qs is None:
            report.append((code, name, None, target, per_exam))
            continue
        for q in qs:
            check_question(code, q, q["_where"], errors, warnings)
            if q.get("id"):
                if q["id"] in seen:
                    errors.append("%s %s: id 중복 (%s)" % (q["_where"], q["id"], seen[q["id"]]))
                seen[q["id"]] = q["_where"]
        live = [(q.get("id") or q["_where"], q.get("question", "")) for q in qs if q.get("status") != "deprecated"]
        for a, b in similar_pairs(live):
            warnings.append("%s: 지문이 매우 비슷함 – %s / %s" % (code, a, b))
        cnt = {s: 0 for s in C.STATUSES}
        diff = {1: 0, 2: 0, 3: 0}
        for q in qs:
            if q.get("status") in cnt:
                cnt[q["status"]] += 1
            if q.get("difficulty") in diff and q.get("status") != "deprecated":
                diff[q["difficulty"]] += 1
        report.append((code, name, (cnt, diff), target, per_exam))

    if not quiet:
        print("=" * 64)
        print(" 문제 데이터 검사 (%s)" % ("엑셀 data/raw" if mode == "excel" else "JSON data/questions"))
        print("=" * 64)
        tot_v = 0
        for code, name, info, target, per_exam in report:
            if info is None:
                print("%-8s 파일 없음" % code)
                continue
            cnt, diff = info
            tot_v += cnt["verified"]
            pct = cnt["verified"] * 100 // target if target else 0
            ready = "출제 가능" if cnt["verified"] >= per_exam else "출제 불가(시험당 %d 필요)" % per_exam
            print("%-8s draft %3d · reviewed %3d · verified %3d · deprecated %3d | 1차 목표 %d 중 %d%% | %s"
                  % (code, cnt["draft"], cnt["reviewed"], cnt["verified"], cnt["deprecated"], target, pct, ready))
            live = sum(diff.values())
            if live:
                print("         난이도  쉬움 %d%% · 보통 %d%% · 어려움 %d%%  (목표 30/50/20)"
                      % (diff[1] * 100 // live, diff[2] * 100 // live, diff[3] * 100 // live))
        print("-" * 64)
        print("verified 합계 %d / 1차 목표 400" % tot_v)
        if warnings:
            print("\n[경고 %d건]" % len(warnings))
            for w in warnings:
                print("  - " + w)
        if errors:
            print("\n[오류 %d건] – 고친 뒤 다시 실행하세요" % len(errors))
            for e in errors:
                print("  - " + e)
        else:
            print("\n오류 없음")
    return errors, warnings, report


if __name__ == "__main__":
    mode = "json" if "--json" in sys.argv else "excel"
    errs, _, _ = run(mode)
    sys.exit(1 if errs else 0)
