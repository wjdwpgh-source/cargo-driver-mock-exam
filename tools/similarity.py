"""문장 유사도 검사 – 대형면허 자체 작성 문제가 공단 문제은행·화물 문제와 너무 비슷하지 않은지 (PRD 13.5·13.8.4)
사용법:
  python tools/similarity.py                               → 엑셀(data/license/raw/문제_DL.xlsx) 문제를 검사
  python tools/similarity.py --json                        → data/license/questions/*.json 검사
  python tools/similarity.py --bank 참고자료/문제은행.json   → 공단 문제은행 사본과도 비교 (기본: 참고자료/문제은행.json 이 있으면 사용)
  옵션: --stem 0.6 (지문 기준값) --full 0.5 (지문+보기 기준값) --out 보고서.txt
- 공단 문제은행 사본은 '참고자료/' 폴더에만 두고 저장소·사이트에 올리지 않는다(.gitignore, 업로드 묶음 제외).
- 비교 방법: 띄어쓰기·문장부호를 뺀 글자 3개 묶음(3-gram)의 자카드 유사도. 지문만 / 지문+보기 두 가지로 보고,
  어느 하나라도 기준값 이상이면 '재작성 검토'로 표시한다. 기준값 아래라도 같은 상황·같은 보기 구성이면 사람이 판단한다.
- 결과: 검수/유사도_DL_날짜.txt (문항별 가장 비슷한 문제와 점수)
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lcommon as L  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SHORT_STEM = 25   # 이보다 짧은 지문은 지문 점수로 판단하지 않음
NORM_RE = re.compile(r"[\s\.,·…!?\"'“”‘’()\[\]{}<>:;~\-–—/①②③④⑤]+")


def norm(text):
    return NORM_RE.sub("", text or "")


def grams(text, n=3):
    t = norm(text)
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def entry(src, qid, stem, choices):
    return {"src": src, "id": qid, "stem": stem, "choices": list(choices or []),
            "g_stem": grams(stem), "g_full": grams(stem + " " + " ".join(sorted(choices or [])))}


def load_bank(path):
    """공단 문제은행 사본(JSON). [{number, stem, options}] 또는 [{id, question, choices}] 형식 지원"""
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("questions", [])
    out = []
    for q in data:
        stem = q.get("stem") or q.get("question") or ""
        ch = q.get("options") or q.get("choices") or []
        qid = "공단 %s" % (q.get("number") or q.get("id") or len(out) + 1)
        out.append(entry("공단", qid, stem, ch))
    return out


def load_cargo():
    out = []
    qdir = os.path.join(L.ROOT, "data", "questions")
    for f in sorted(os.listdir(qdir)) if os.path.isdir(qdir) else []:
        if f.endswith(".json"):
            for q in json.load(open(os.path.join(qdir, f), encoding="utf-8")).get("questions", []):
                if q.get("status") != "deprecated":
                    out.append(entry("화물", q["id"], q.get("question", ""), q.get("choices", [])))
    return out


def load_license(mode="excel", path=None):
    out = []
    if mode == "excel":
        p = path or L.RAW_PATH
        if not os.path.exists(p):
            return out
        _, _, _, rows = L.read_rows(p)
        for r, rec in rows:
            q = L.to_question(rec)
            if q.get("status") != "deprecated":
                out.append(entry("대형", q["id"] or "%d행" % r, q["question"], q["choices"]))
    else:
        qdir = path or L.QDIR
        for code in L.TYPE_CODES:
            p = os.path.join(qdir, code + ".json")
            if os.path.exists(p):
                for q in json.load(open(p, encoding="utf-8")).get("questions", []):
                    if q.get("status") != "deprecated":
                        out.append(entry("대형", q["id"], q.get("question", ""), q.get("choices", [])))
    return out


def build_index(refs):
    idx = {}
    for i, r in enumerate(refs):
        for g in r["g_full"]:
            idx.setdefault(g, []).append(i)
    return idx


def best_matches(q, refs, idx, top=3, skip_id=None):
    cnt = {}
    for g in q["g_full"]:
        for i in idx.get(g, ()):
            cnt[i] = cnt.get(i, 0) + 1
    cands = sorted(cnt, key=lambda i: -cnt[i])[:40]
    res = []
    for i in cands:
        r = refs[i]
        if skip_id and r["id"] == skip_id:
            continue
        res.append((jaccard(q["g_stem"], r["g_stem"]), jaccard(q["g_full"], r["g_full"]), r))
    res.sort(key=lambda t: -max(t[0], t[1]))
    return res[:top]


def check(questions, refs, stem_th=0.6, full_th=0.5, against_self=True):
    """반환: [(문항, [(지문 점수, 전체 점수, 비교 대상)…], 표시 여부)]"""
    pool = list(refs) + (list(questions) if against_self else [])
    idx = build_index(pool)
    out = []
    for q in questions:
        m = best_matches(q, pool, idx, skip_id=q["id"])
        # 그림 문제처럼 지문이 짧고 틀이 같은 경우("다음 안전표지가 뜻하는 것은?")는 지문 점수 대신 지문+보기 점수로만 판단
        short = bool(m) and min(len(norm(q["stem"])), len(norm(m[0][2]["stem"]))) < SHORT_STEM
        flag = bool(m) and ((m[0][0] >= stem_th and not short) or m[0][1] >= full_th)
        out.append((q, m, flag))
    return out


def report(results, stem_th, full_th, sources):
    lines = ["대형면허 문제 유사도 검사 (%s)" % datetime.date.today().isoformat(),
             "비교 대상: %s" % ", ".join("%s %d" % kv for kv in sources.items()),
             "기준값: 지문 %.2f 이상 또는 지문+보기 %.2f 이상 → 재작성 검토" % (stem_th, full_th), ""]
    flagged = [r for r in results if r[2]]
    lines.append("재작성 검토 %d / %d문항" % (len(flagged), len(results)))
    lines.append("")
    for q, m, flag in sorted(results, key=lambda r: (not r[2], -(max(r[1][0][0], r[1][0][1]) if r[1] else 0))):
        if not m:
            continue
        s, f, r = m[0]
        mark = "★ 재작성 검토" if flag else "  "
        lines.append("%s %s  지문 %.2f · 전체 %.2f  ↔ [%s] %s" % (mark, q["id"], s, f, r["src"], r["id"]))
        if flag:
            lines.append("      내 문제: %s" % q["stem"][:90])
            lines.append("      비슷한 것: %s" % r["stem"][:90])
    return "\n".join(lines) + "\n"


def main(argv):
    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default
    mode = "json" if "--json" in argv else "excel"
    stem_th, full_th = float(opt("--stem", 0.6)), float(opt("--full", 0.5))
    bank = opt("--bank", os.path.join(L.ROOT, "참고자료", "문제은행.json"))
    qs = load_license(mode)
    if not qs:
        print("검사할 대형 문제가 없습니다.")
        return 0
    refs, sources = [], {}
    if bank and os.path.exists(bank):
        b = load_bank(bank)
        refs += b
        sources["공단 문제은행"] = len(b)
    else:
        print("※ 공단 문제은행 사본이 없어 화물 문제·대형 문제끼리만 비교합니다 (%s)" % bank)
    c = load_cargo()
    refs += c
    sources["화물"] = len(c)
    sources["대형(서로)"] = len(qs)
    results = check(qs, refs, stem_th, full_th)
    text = report(results, stem_th, full_th, sources)
    out = opt("--out", os.path.join(L.ROOT, "검수", "유사도_DL_%s.txt" % datetime.date.today().isoformat()))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print("\n".join(text.splitlines()[:30]))
    print("...\n저장: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
