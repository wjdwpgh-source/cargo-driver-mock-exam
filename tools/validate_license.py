"""대형운전면허 문제 데이터 검사 (PRD 13.7)
사용법:  python tools/validate_license.py           → data/license/raw/문제_DL.xlsx 검사
         python tools/validate_license.py --json    → data/license/questions/*.json 검사
(tools/validate.py 가 화물 검사 뒤에 이 검사도 함께 실행한다)
"""
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lcommon as L  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
IMG_EXT = (".svg", ".webp", ".png", ".jpg", ".jpeg")


def check_question(q, where, errors, warnings, file_type=None, allow_sample=False):
    def err(msg):
        errors.append("%s %s: %s" % (where, q.get("id") or "(id 없음)", msg))

    def warn(msg):
        warnings.append("%s %s: %s" % (where, q.get("id") or "(id 없음)", msg))

    qid = q.get("id") or ""
    if qid:
        m = L.ID_RE.match(qid)
        if not m:
            err("id 형식 오류 (예: DL-0001)")
        elif int(m.group(1)) >= L.SAMPLE_ID_MIN and not allow_sample:
            err("9001번 이상은 개발·테스트 전용 번호입니다")
    t = q.get("subject")
    if t not in L.TYPE:
        err("유형은 %s 중 하나 (현재: %r)" % ("/".join(L.TYPE_CODES), t))
        return
    if file_type and t != file_type:
        err("유형(%s)이 파일(%s.json)과 다름" % (t, file_type))
    rule = L.TYPE[t]
    nc, na = rule["choices"], rule["answers"]
    if q.get("category") not in L.CATEGORIES:
        err("내용분류는 %s 중 하나" % "/".join(L.CATEGORIES))
    text = q.get("question", "")
    if not text:
        err("지문이 비어 있음")
    elif len(text) > L.LIMITS["question"]:
        err("지문이 %d자를 넘음 (%d자)" % (L.LIMITS["question"], len(text)))
    ch = q.get("choices", [])
    if len(ch) != nc or any(not c for c in ch):
        err("%s 유형은 보기 %d개가 모두 필요" % (t, nc))
    else:
        for i, c in enumerate(ch):
            if len(c) > L.LIMITS["choice"]:
                err("보기%d가 %d자를 넘음" % (i + 1, L.LIMITS["choice"]))
        if len(set(ch)) < nc:
            err("같은 보기가 있음")
    if q.get("_extra_choice"):
        err("%s 유형은 보기 %d개인데 보기%d 칸이 채워져 있음" % (t, nc, nc + 1))
    ans = q.get("answer")
    if not isinstance(ans, list) or not all(isinstance(a, int) for a in ans):
        err("정답 형식 오류 (예: 2 또는 1,4) – 현재: %r" % (ans,))
        ans = []
    elif len(ans) != na or len(set(ans)) != len(ans) or any(a < 1 or a > nc for a in ans):
        err("%s 유형 정답은 1~%d 중 서로 다른 %d개 (현재: %s)" % (t, nc, na, ",".join(map(str, ans))))
        ans = []
    if not q.get("explanation"):
        err("해설이 비어 있음")
    right = [ch[a - 1] for a in ans if len(ch) == nc and 1 <= a <= nc]
    hint = q.get("hint") or ""
    if hint:
        if len(hint) > L.LIMITS["hint"]:
            err("힌트가 %d자를 넘음 (%d자)" % (L.LIMITS["hint"], len(hint)))
        if any(len(r) >= 4 and r in hint for r in right):
            warn("힌트에 정답 보기 문구가 그대로 들어 있음")
    if not q.get("source"):
        err("출처가 비어 있음 (자체 작성)")
    elif q["source"] != "자체 작성":
        warn("대형면허 문제는 모두 '자체 작성'이어야 합니다 (공단 문제은행 원문 사용 금지, PRD 13.5)")
    if q.get("difficulty") not in (1, 2, 3):
        err("난이도는 1~3")
    st = q.get("status")
    if st not in L.STATUSES:
        err("상태는 %s 중 하나" % "/".join(L.STATUSES))
    if q.get("category") in L.LAW_CATS:
        if not q.get("law_ref_raw"):
            err("내용분류 %s는 관련 법령이 필요" % q.get("category"))
        if not q.get("law_date_raw"):
            err("내용분류 %s는 기준일이 필요" % q.get("category"))
    if q.get("law_date_raw") and not DATE_RE.match(q["law_date_raw"]):
        err("기준일은 YYYY-MM-DD 형식")
    if st == "verified" and not q.get("reviewer_raw"):
        err("verified인데 검수자·검수일이 없음")
    if q.get("_shuffle_raw") not in (None, "", "Y", "N"):
        err("보기섞기는 Y 또는 N (비우면 문장·표지 Y, 일러스트 N)")
    img = q.get("image")
    if rule["image"] and not img:
        err("%s 유형은 그림이 필요" % t)
    if img:
        alt = (q.get("image_alt") or "").strip()
        if not alt:
            err("그림설명(대체 텍스트)이 필요")
        elif len(alt) > L.LIMITS["image_alt"]:
            err("그림설명이 %d자를 넘음" % L.LIMITS["image_alt"])
        elif any(len(r) >= 6 and r in alt for r in right):
            warn("그림설명에 정답 보기 문구가 그대로 들어 있음")
        p = L.image_file(q)
        if not p.lower().endswith(IMG_EXT):
            err("그림 형식은 svg/webp/png/jpg")
        elif not os.path.exists(p):
            err("그림 파일 없음: data/%s" % img)
        else:
            size = os.path.getsize(p)
            if size > L.IMG_MAX:
                err("그림이 %dKB를 넘음 (%dKB)" % (L.IMG_MAX // 1024, size // 1024))
            elif size > L.IMG_WARN:
                warn("그림이 %dKB를 넘음 (%dKB) – 줄이기 권장" % (L.IMG_WARN // 1024, size // 1024))


def similar_pairs(items, threshold=0.9):
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            sm = difflib.SequenceMatcher(None, items[i][1], items[j][1])
            if sm.real_quick_ratio() >= threshold and sm.quick_ratio() >= threshold and sm.ratio() >= threshold:
                out.append((items[i][0], items[j][0]))
    return out


def load_from_excel(path=None):
    path = path or L.RAW_PATH
    if not os.path.exists(path):
        return None
    _, _, _, rows = L.read_rows(path)
    qs = []
    for r, rec in rows:
        q = L.to_question(rec)
        nc = L.TYPE.get(rec["type"], {}).get("choices", 5)
        q["_extra_choice"] = nc < 5 and any(rec["c%d" % k] for k in range(nc + 1, 6))
        q["law_ref_raw"], q["law_date_raw"], q["reviewer_raw"] = rec["law_ref"], rec["law_date"], rec["reviewer"]
        q["_shuffle_raw"] = rec.get("shuffle", "").upper()
        q["_where"] = "문제_DL.xlsx %d행" % r
        q["_file"] = None
        qs.append(q)
    return qs


def load_from_json(qdir=None):
    qdir = qdir or L.QDIR
    qs, found = [], False
    for code in L.TYPE_CODES:
        p = os.path.join(qdir, code + ".json")
        if not os.path.exists(p):
            continue
        found = True
        for q in json.load(open(p, encoding="utf-8")).get("questions", []):
            q = dict(q)
            if isinstance(q.get("answer"), int):
                q["answer"] = [q["answer"]]
            q["law_ref_raw"] = q.get("law_ref", "")
            m = re.search(r"\((\d{4}-\d{2}-\d{2}) 기준\)", q.get("law_ref", ""))
            q["law_date_raw"] = m.group(1) if m else ""
            q["reviewer_raw"] = "json"
            q["_where"] = "license/%s.json" % code
            q["_file"] = code
            qs.append(q)
    return qs if found else None


def run(mode="excel", quiet=False, path=None, allow_sample=False):
    qs = load_from_excel(path) if mode == "excel" else load_from_json(path)
    errors, warnings = [], []
    if qs is None:
        if not quiet:
            print("\n[대형운전면허] %s 없음 – 검사 건너뜀" % ("엑셀 data/license/raw/문제_DL.xlsx" if mode == "excel" else "문제 파일"))
        return errors, warnings, None
    seen = {}
    for q in qs:
        check_question(q, q["_where"], errors, warnings, file_type=q["_file"], allow_sample=allow_sample)
        if q.get("id"):
            if q["id"] in seen:
                errors.append("%s %s: id 중복 (%s)" % (q["_where"], q["id"], seen[q["id"]]))
            seen[q["id"]] = q["_where"]
    live = [(q.get("id") or q["_where"], q.get("question", "")) for q in qs if q.get("status") != "deprecated"]
    for a, b in similar_pairs(live):
        warnings.append("대형: 지문이 매우 비슷함 – %s / %s" % (a, b))
    report = {}
    for code in L.TYPE_CODES:
        cnt = {s: 0 for s in L.STATUSES}
        for q in qs:
            if q.get("subject") == code and q.get("status") in cnt:
                cnt[q["status"]] += 1
        report[code] = cnt
    cats = {}
    for q in qs:
        if q.get("status") != "deprecated":
            cats[q.get("category")] = cats.get(q.get("category"), 0) + 1
    if not quiet:
        print("=" * 64)
        print(" 대형운전면허 문제 검사 (%s)" % ("엑셀 data/license/raw" if mode == "excel" else "JSON data/license/questions"))
        print("=" * 64)
        tot_v = 0
        for code in L.TYPE_CODES:
            t, cnt = L.TYPE[code], report[code]
            tot_v += cnt["verified"]
            ready = "출제 가능" if cnt["verified"] >= t["per_exam"] else "출제 불가(시험당 %d 필요)" % t["per_exam"]
            print("%-8s draft %3d · reviewed %3d · verified %3d · deprecated %3d | 1차 목표 %d | %s"
                  % (code, cnt["draft"], cnt["reviewed"], cnt["verified"], cnt["deprecated"], t["target"], ready))
        print("내용분류: " + " · ".join("%s %d" % (L.CATEGORIES.get(k, k), v) for k, v in sorted(cats.items(), key=lambda kv: str(kv[0]))))
        print("-" * 64)
        print("verified 합계 %d / 1차 목표 330" % tot_v)
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
