"""검수 미리보기 모드 브라우저 테스트 – 초안(draft) 실제 문제로 시험
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_preview.py
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT, exist_ok=True)
errors = []
QS = {}
for code in ("LAW", "CARGO", "SAFE", "SERVICE"):
    for q in json.load(open(os.path.join(ROOT, "data", "questions", code + ".json"), encoding="utf-8"))["questions"]:
        QS[q["id"]] = q


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def current_q(page):
    return page.evaluate("() => { const ip = CDME.app.store.getProfileData().inProgress; return ip.items[ip.current].qid; }")


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    page = ctx.new_page()
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.fill("#nick", "검수자")
    page.press("#nick", "Enter")
    page.wait_for_selector("text=출제 가능한 문제가 아직 부족합니다")

    print("[1] 실제 모드: verified 0 → 시험 불가, 미리보기 안내")
    check(page.locator("[data-draft-on]").count() == 1, "대시보드에 '검수 전 실제 문제로 미리보기' 링크")
    page.click("#start-exam")
    check("검수 전 실제 문제로 미리보기" in page.inner_text(".modal"), "시작 불가 창에 미리보기 안내")
    page.click(".modal [data-act=cancel]")

    print("[2] 미리보기 켜기")
    page.click("[data-draft-on]")
    page.wait_for_selector("text=검수 미리보기 모드")
    page.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    check(page.locator(".tag-ok").count() == 4, "과목 4개 모두 출제 가능으로 표시")
    page.reload()
    page.wait_for_selector("text=검수 미리보기 모드")
    check(True, "새로고침 후에도 유지")

    print("[3] 실제 초안 문제로 시험")
    page.click("#start-exam")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")
    qid = current_q(page)
    q = QS[qid]
    check(qid.startswith("LAW-") and int(qid[4:]) < 9000, f"첫 문제가 실제 법규 문제 ({qid})")
    check(q["question"] in page.inner_text(".q-text"), "지문 일치")
    check(("검수 전 · " + qid) in page.inner_text(".q-num"), "검수 전 표시와 문제 번호")
    check("미리보기 시험" in page.inner_text("#view"), "미리보기 안내 문구")
    page.click(f"[data-choice='{q['answer']}']")
    page.wait_for_selector(".feedback.is-correct")
    check(q["explanation"][:20] in page.inner_text(".feedback"), "실제 해설 표시")
    page.screenshot(path=f"{SHOT}/preview_01_exam.png", full_page=True)
    subj = page.evaluate("() => CDME.app.store.getProfileData().inProgress.items.map(i => i.subject)")
    check([subj.count(c) for c in ("LAW", "CARGO", "SAFE", "SERVICE")] == [25, 15, 25, 15], "과목별 25/15/25/15 출제")
    ids = page.evaluate("() => CDME.app.store.getProfileData().inProgress.items.map(i => i.qid)")
    check(all(QS[i]["status"] == "draft" for i in ids), "출제 문제는 모두 초안(draft)")

    print("[4] 미리보기를 끄고 이어 풀기 → 미리보기 모드로 자동 복귀")
    page.click("#ex-later")
    page.wait_for_selector(".resume")
    page.click("[data-sample-off]")
    page.wait_for_selector("text=출제 가능한 문제가 아직 부족합니다")
    page.click("#resume-exam")
    page.wait_for_selector(".q-card .choice")
    check(page.evaluate("localStorage.getItem('cdme_sample')") == "draft", "이어 풀기 때 미리보기 모드로 맞춤")
    check(current_q(page) == qid, "같은 시험 이어 풀기")

    print("[5] 시간 종료 → 결과, 기록은 실제 성적과 분리")
    page.click("#ex-later")
    page.wait_for_selector(".resume")
    page.evaluate("""() => { const s = CDME.app.store; s.updateProfileData(s.getActiveProfile().id, d => { d.inProgress.remainingMs = 1200; }); }""")
    page.click("#resume-exam")
    page.wait_for_selector(".result-hero", timeout=6000)
    check("미리보기 시험" in page.inner_text("#view"), "결과에 미리보기 안내")
    rec = page.evaluate("() => { const e = CDME.app.store.getProfileData().exams; return e[e.length-1]; }")
    check(rec["sample"] is True and rec.get("kind") == "draft", "기록에 미리보기 표시")
    page.goto(BASE + "#/home")
    page.click("[data-sample-off]")
    page.wait_for_selector("text=출제 가능한 문제가 아직 부족합니다")
    check("0회" in page.inner_text(".stats"), "실제 모드 응시 0회")

    print("[6] 결과 다시보기 → 미리보기 모드로 열림")
    page.goto(BASE + "#/result?id=" + rec["id"])
    page.wait_for_selector(".rv-card")
    check(page.evaluate("localStorage.getItem('cdme_sample')") == "draft", "결과 열 때 미리보기 모드로 맞춤")

    w = page.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px 가로 스크롤 없음 ({w})")
    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
