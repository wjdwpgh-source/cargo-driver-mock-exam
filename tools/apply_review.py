"""검수 결과 반영 (검수표 → data/raw 엑셀 원본)
사용: python tools/apply_review.py [검수표.xlsx]   (생략하면 검수 폴더의 가장 최근 검수표)
  1차확인       → 상태 reviewed (이미 verified면 그대로)
  법령대조완료  → 상태 verified, 검수자·검수일 기록 (둘 다 없으면 반영하지 않고 알림)
  수정필요      → 상태 그대로, 비고 끝에 [검수 날짜 이름] 의견 추가 (문제 수정은 따로)
  폐기          → 상태 deprecated
  법규는 기준일을 검수일로 갱신(법령대조완료일 때).
반영 후 '문제변환.bat'을 실행해야 사이트용 JSON에 들어간다.
(v2.0) 대형운전면허 검수표(검수표_DL_*.xlsx)도 같은 방법으로 data/license/raw/문제_DL.xlsx에 반영한다.
       내용분류 LAW·SIGN은 법령대조완료일 때 기준일을 검수일로 갱신.
"""
import glob
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lcommon as LC  # noqa: E402
import qcommon as C  # noqa: E402
from openpyxl import load_workbook  # noqa: E402


def as_date(v):
    if v is None or v == "":
        return ""
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def read_review(path):
    wb = load_workbook(path, data_only=True)
    ws = wb["검수표"]
    head = [c.value for c in ws[1]]
    ix = {h: head.index(h) for h in ("문제 ID", "검수 판정", "수정 의견", "검수자", "검수일")}
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        qid = row[ix["문제 ID"]]
        v = (row[ix["검수 판정"]] or "").strip() if row[ix["검수 판정"]] else ""
        if not qid or not v:
            continue
        out[qid] = {"v": v, "memo": (row[ix["수정 의견"]] or "").strip(), "who": (row[ix["검수자"]] or "").strip(),
                    "when": as_date(row[ix["검수일"]])}
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        files = sorted(glob.glob(os.path.join(C.ROOT, "검수", "검수표_*.xlsx")), key=os.path.getmtime)
        files = [f for f in files if not os.path.basename(f).startswith("~$")]
        if not files:
            print("검수 폴더에 검수표가 없습니다.")
            return 1
        path = files[-1]
    print("검수표:", path)
    rv = read_review(path)
    if not rv:
        print("입력된 판정이 없습니다.")
        return 0
    stats = {"1차확인": 0, "법령대조완료": 0, "수정필요": 0, "폐기": 0}
    problems, found = [], set()
    targets = [(code, C.raw_path(code), C.read_rows, code == "LAW") for code in C.CODES if os.path.exists(C.raw_path(code))]
    if os.path.exists(LC.RAW_PATH):
        targets.append(("DL", LC.RAW_PATH, LC.read_rows, None))
    for code, raw, reader, law_all in targets:
        wb, ws, idx, rows = reader(raw)
        changed = False
        for r, rec in rows:
            x = rv.get(rec["id"])
            if not x:
                continue
            found.add(rec["id"])
            v = x["v"]

            def put(key, val):
                ws.cell(row=r, column=idx[key] + 1).value = val
            if v not in stats:
                problems.append("%s: 알 수 없는 판정 '%s'" % (rec["id"], v))
                continue
            if v == "1차확인":
                if rec["status"] != "verified":
                    put("상태", "reviewed")
            elif v == "법령대조완료":
                if not x["who"] or not x["when"]:
                    problems.append("%s: 법령대조완료는 검수자·검수일이 필요해 반영하지 않음" % rec["id"])
                    continue
                put("상태", "verified")
                put("검수자·검수일", "%s / %s" % (x["who"], x["when"]))
                if law_all or (law_all is None and rec.get("category") in LC.LAW_CATS):
                    put("기준일", x["when"])
            elif v == "폐기":
                put("상태", "deprecated")
            if x["memo"] or v == "수정필요":
                tag = "[검수 %s %s] %s %s" % (x["when"] or date.today().isoformat(), x["who"], v, x["memo"])
                put("비고", ((rec["note"] + " · ") if rec["note"] else "") + tag.strip())
            stats[v] += 1
            changed = True
        if changed:
            wb.save(raw)
            print("  반영: %s" % raw)
    for qid in sorted(set(rv) - found):
        problems.append("%s: 엑셀 원본에서 찾지 못함" % qid)
    print("결과: " + " · ".join("%s %d" % kv for kv in stats.items()))
    for p in problems:
        print("  ! " + p)
    if stats["수정필요"]:
        print("※ '수정필요' 문제는 비고에 의견만 적었습니다. 내용 수정은 엑셀에서 직접 하거나 Claude에게 요청하세요.")
    print("다음: '문제변환.bat'을 실행하면 사이트용 문제 파일(JSON)에 반영됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
