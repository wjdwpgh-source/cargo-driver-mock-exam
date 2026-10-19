"""힌트 기능 브라우저 테스트 (PRD v1.17 FR-312)
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_hint.py
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

IP = "() => CDME.app.store.getProfileData().inProgress"


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def cur(page):
    return page.evaluate("() => { const ip = CDME.app.store.getProfileData().inProgress; return ip.items[ip.current].qid; }")


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    page = ctx.new_page()
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.fill("#nick", "힌트왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("[data-draft-on]")
    page.click("[data-draft-on]")
    page.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    page.click("#start-exam")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")

    print("[1] 답하기 전: 힌트 버튼만, 누르면 힌트 글")
    q = QS[cur(page)]
    check(page.locator("#ex-hint").count() == 1 and page.locator("#ex-hintbox").count() == 0, "힌트 버튼 있음, 힌트 상자 없음")
    page.screenshot(path=f"{SHOT}/hint_01_button.png", full_page=True)
    page.click("#ex-hint")
    page.wait_for_selector("#ex-hintbox")
    check(q["hint"] in page.inner_text("#ex-hintbox"), "문제의 힌트 글 표시")
    check(page.locator("#ex-hint").count() == 0, "버튼은 사라짐")
    check(page.evaluate("document.activeElement.id") == "ex-hintbox", "힌트 상자로 초점 이동")
    check(page.evaluate(IP + ".hints[0]") is True, "힌트 사용 기록")
    page.screenshot(path=f"{SHOT}/hint_02_box.png", full_page=True)
    page.click(f"[data-choice='{q['answer']}']")
    page.wait_for_selector(".feedback.is-correct")
    check(page.locator("#ex-hintbox").count() == 0, "답한 뒤 힌트 상자 숨김")
    check("힌트 사용" in page.inner_text(".feedback"), "해설에 '힌트 사용' 표시")
    check(page.locator("#ex-hint").count() == 0, "답한 뒤 힌트 버튼 없음")

    print("[2] H 키로 힌트, 이동했다 돌아와도 유지, 새로고침 후에도 유지")
    page.click("#ex-next")
    page.wait_for_selector("#ex-hint")
    page.keyboard.press("h")
    page.wait_for_selector("#ex-hintbox")
    check(True, "H 키로 힌트 열기")
    page.click("#ex-next")
    page.wait_for_selector("#ex-hint")
    page.click("#ex-prev")
    check(page.locator("#ex-hintbox").count() == 1, "다른 문항 갔다 와도 힌트 상자 유지")
    page.reload()
    page.wait_for_selector(".q-card .choice")
    if page.locator("#resume-exam").count():
        page.click("#resume-exam")
        page.wait_for_selector(".q-card .choice")
    check(page.locator("#ex-hintbox").count() == 1, "새로고침 후에도 유지")

    print("[3] 힌트 글이 없는 문제 → 틀린 보기 하나 지우기")
    page.click("#ex-next")
    page.wait_for_selector("#ex-hint")
    qid = cur(page)
    q3 = QS[qid]
    page.evaluate("(id) => { CDME.app.getBank().byId[id].hint = ''; }", qid)
    page.click("#ex-prev")
    page.click("#ex-next")
    page.click("#ex-hint")
    page.wait_for_selector(".choice.eliminated")
    rm = int(page.get_attribute(".choice.eliminated", "data-choice"))
    check(rm != q3["answer"], "정답이 아닌 보기를 지움 (%d번)" % rm)
    check(page.locator(".choice.eliminated").is_disabled(), "지운 보기는 누를 수 없음")
    check("틀린 보기 하나" in page.inner_text("#ex-hintbox"), "지웠다는 안내")
    page.screenshot(path=f"{SHOT}/hint_03_elim.png", full_page=True)
    page.keyboard.press(str(rm))
    check(page.evaluate(IP + ".answers[2]") is None, "숫자 키로도 지운 보기는 선택 안 됨")
    other = [n for n in (1, 2, 3, 4) if n != rm and n != q3["answer"]][0]
    page.click(f"[data-choice='{other}']")
    page.wait_for_selector(".feedback.is-wrong")
    check(page.locator(".choice.eliminated").count() == 0, "답한 뒤에는 지움 표시 해제(정답·오답 표시)")

    print("[4] 결과: 힌트 사용 문항 수, 다시보기 표시, 점수 영향 없음")
    page.evaluate("""() => { const s = CDME.app.store, b = CDME.app.getBank(); s.updateProfileData(s.getActiveProfile().id, d => {
        const ip = d.inProgress; ip.items.forEach((it, i) => { if (ip.answers[i] == null) ip.answers[i] = b.byId[it.qid].answer; }); }); }""")
    page.click("#ex-later")
    page.wait_for_selector(".resume")
    page.click("#resume-exam")
    page.wait_for_selector("#ex-finish")
    page.click("#ex-finish")
    page.wait_for_selector(".result-hero")
    rec = page.evaluate("() => { const e = CDME.app.store.getProfileData().exams; return e[e.length-1]; }")
    check(rec["hintCount"] == 3, "기록에 힌트 사용 3문항")
    check(rec["correct"] == 79, "힌트 쓴 정답도 정답 처리 (79/80)")
    check("힌트 사용 3문항" in page.inner_text(".result-hero"), "결과 화면에 힌트 사용 수")
    page.click("[data-filter=all]")
    check(page.locator(".rv-card .tag-hint").count() == 3, "다시보기에 '힌트 사용' 표시 3개")
    page.screenshot(path=f"{SHOT}/hint_04_result.png", full_page=True)

    print("[5] 복습 재시험에서도 힌트")
    page.goto(BASE + "#/review")
    page.reload()   # [3]에서 화면 속 힌트를 지운 것을 원래대로
    page.wait_for_selector("#rv-start, [data-start], .btn-primary")
    page.click("text=복습 시작")
    page.wait_for_selector("#rp-card .choice")
    check(page.locator("#rp-hint").count() == 1, "복습 화면 힌트 버튼")
    page.click("#rp-hint")
    page.wait_for_selector("#rp-hintbox")
    rvq = page.evaluate("() => { const r = CDME.app.store.getProfileData().reviewInProgress; return r.items[r.current].qid; }")
    check(QS[rvq]["hint"] in page.inner_text("#rp-hintbox"), "복습 힌트 글")
    page.screenshot(path=f"{SHOT}/hint_05_review.png", full_page=True)
    page.click("#rp-card [data-pos='0']")
    page.wait_for_selector("#rp-fb")
    check("힌트 사용" in page.inner_text("#rp-fb"), "복습 해설에 '힌트 사용'")
    page.click("#rp-quit")
    if page.locator(".modal [data-act=ok]").count():
        page.click(".modal [data-act=ok]")
    page.wait_for_selector("text=복습 결과")
    check("힌트 사용 1문항" in page.inner_text(".result-hero"), "복습 결과에 힌트 사용 수")

    print("[6] 큰 글씨·다크 모드 표시")
    page.emulate_media(color_scheme="dark")
    page.evaluate("localStorage.setItem('cdme_font','xl')")
    page.goto(BASE + "#/home")
    page.reload()
    page.click("#start-exam")
    if page.locator(".modal [data-act=ok]").count():
        page.click(".modal [data-act=ok]")
    page.wait_for_selector("#ex-hint")
    page.click("#ex-hint")
    page.wait_for_selector("#ex-hintbox")
    w = page.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px·큰 글씨 가로 스크롤 없음 ({w})")
    page.screenshot(path=f"{SHOT}/hint_06_dark_xl.png", full_page=True)

    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
