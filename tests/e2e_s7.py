"""S7 브라우저 테스트 – 글자 크기·접근성·오프라인·도움말 (TC-17~19)
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_s7.py
"""
import os
import re
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT, exist_ok=True)
errors = []
MAKE = """(scores) => {
  const bank = CDME.app.getBank(); const s = CDME.app.store; const id = s.getActiveProfile().id;
  s.updateProfileData(id, d => { scores.forEach((n, k) => {
    const ip = CDME.exam.buildExam(bank, { sample: true });
    ip.items.forEach((it, i) => { const a = bank.byId[it.qid].answer; CDME.exam.setAnswer(ip, i, i < n ? a : a % 4 + 1); });
    const rec = CDME.exam.score(ip, bank, { now: new Date(Date.UTC(2026, 9, 1 + k, 3)).toISOString() });
    rec.noteReg = CDME.notes.registerWrong(d.wrongNotes, rec, bank, rec.finishedAt); d.exams.push(rec); }); });
}"""


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def root_px(page):
    return page.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")


def width(page):
    return page.evaluate("document.documentElement.scrollWidth")


js_errors = []
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR")
    ctx.add_init_script("localStorage.setItem('cdme_sample','1')")
    page = ctx.new_page()
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    print("[1] 도움말: 닉네임 없이도 열림")
    page.goto(BASE + "#/help")
    page.wait_for_selector("text=도움말 · 이용 안내")
    check("#/help" in page.url, "처음 방문자도 도움말 열람")
    check(page.locator("footer >> text=도움말").count() == 1, "하단에 도움말 링크")

    print("[2] 글자 크기 3단계 (NFR-07)")
    check(root_px(page) == 17, "기본 17px")
    page.click("#font-btn")
    check(root_px(page) == 19, "크게 19px")
    page.click("#font-btn")
    check(root_px(page) == 21, "아주 크게 21px")
    check("아주 크게" in page.get_attribute("#font-btn", "aria-label"), "버튼 이름에 현재 크기")
    page.reload()
    page.wait_for_selector("text=도움말 · 이용 안내")
    check(root_px(page) == 21, "새로고침 후 유지")
    page.click("[data-fontset='']")
    check(root_px(page) == 17, "도움말에서 '보통' 선택")
    page.click("[data-fontset='xl']")
    check(page.get_attribute("[data-fontset='xl']", "aria-pressed") == "true", "선택 상태 표시")

    print("[3] 아주 큰 글자 + 360px에서 모든 화면 가로 스크롤 없음 (TC-19)")
    page.goto(BASE + "#/start")
    page.fill("#nick", "큰글씨왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    page.evaluate(MAKE, [50, 66])
    screens = {}
    for r in ["home", "records", "notes", "review", "data", "help", "profiles"]:
        page.goto(BASE + "#/" + r)
        page.wait_for_timeout(250)
        screens[r] = width(page)
    page.goto(BASE + "#/home")
    page.click("#start-exam")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")
    page.click(".choice >> nth=0")
    page.wait_for_selector(".feedback")
    screens["exam"] = width(page)
    page.screenshot(path=f"{SHOT}/s7_01_exam_xl.png", full_page=True)
    page.click("#ex-grid")
    page.wait_for_selector(".grid-modal")
    screens["grid"] = width(page)
    page.keyboard.press("Escape")
    page.goto(BASE + "#/result")
    page.wait_for_selector(".result-hero")
    screens["result"] = width(page)
    page.goto(BASE + "#/review")
    page.click("text=복습 시작")
    page.wait_for_selector("#rp-card .choice")
    screens["review-play"] = width(page)
    bad = {k: v for k, v in screens.items() if v > 360}
    check(not bad, f"넘치는 화면 없음 {bad or ''}")
    page.goto(BASE + "#/records")
    page.wait_for_selector("#trend svg")
    page.screenshot(path=f"{SHOT}/s7_02_records_xl.png", full_page=True)

    print("[4] 화면 이동 시 제목에 포커스 (화면 읽기 프로그램)")
    page.goto(BASE + "#/notes")
    page.wait_for_selector(".page-title")
    check(page.evaluate("document.activeElement.tagName") == "H1", "새 화면 제목에 포커스")

    print("[5] 다크 모드 대비: 빨강·초록 바탕 글자 어둡게")
    ctx2 = browser.new_context(viewport={"width": 360, "height": 740}, color_scheme="dark")
    p2 = ctx2.new_page()
    p2.goto(BASE + "#/help")
    p2.wait_for_selector(".help")
    col = p2.evaluate("""() => { const b = document.createElement('button'); b.className = 'btn btn-danger'; document.body.appendChild(b);
        const c = getComputedStyle(b).color; b.remove(); return c; }""")
    check(col == "rgb(16, 21, 28)", f"다크 모드 위험 버튼 글자색 {col}")
    ctx2.close()

    print("[6] 오프라인 동작 (NFR-04, TC-18)")
    ctx3 = browser.new_context(viewport={"width": 360, "height": 740})
    ctx3.add_init_script("localStorage.setItem('cdme_sample','1')")
    p3 = ctx3.new_page()
    p3.on("pageerror", lambda e: js_errors.append(str(e)))
    p3.goto(BASE)
    p3.fill("#nick", "오프라인")
    p3.press("#nick", "Enter")
    p3.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    p3.evaluate("navigator.serviceWorker.ready.then(() => true)")
    p3.reload()
    p3.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    p3.wait_for_timeout(800)
    cached = p3.evaluate("caches.keys().then(ks => Promise.all(ks.map(k => caches.open(k).then(c => c.keys())))).then(a => a.flat().length)")
    check(cached >= 25, f"파일 미리 저장 ({cached}개)")
    ctx3.set_offline(True)
    p3.reload()
    p3.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제", timeout=15000)
    check(p3.is_visible("#offline-badge"), "오프라인 표시")
    p3.click("#start-exam")
    p3.click(".modal [data-act=ok]")
    p3.wait_for_selector(".q-card .choice")
    n = int(re.search(r"정답은 (\d)번", p3.inner_text(".q-text")).group(1))
    p3.click(f"[data-choice='{n}']")
    check(p3.locator(".feedback.is-correct").count() == 1, "인터넷 없이 시험 진행·채점")
    p3.screenshot(path=f"{SHOT}/s7_03_offline.png")
    ctx3.set_offline(False)
    p3.evaluate("window.dispatchEvent(new Event('online'))")
    p3.wait_for_timeout(300)
    check(not p3.is_visible("#offline-badge"), "다시 연결되면 표시 사라짐")
    ctx3.close()

    print("[7] 키보드만으로 조작: Tab 순서")
    page.goto(BASE + "#/home")
    page.wait_for_selector("#start-exam")
    page.evaluate("document.querySelector('.skip').focus()")
    seen = []
    for _ in range(6):
        page.keyboard.press("Tab")
        seen.append(page.evaluate("document.activeElement.id || document.activeElement.className || document.activeElement.tagName"))
    check("font-btn" in seen and "user-chip" in seen, f"상단 버튼에 키보드 접근 {seen}")

    print("[8] 문제 데이터가 늦게 와도 입력 중인 닉네임 유지")
    import time as _t
    c4 = browser.new_context(service_workers="block")
    p4 = c4.new_page()
    p4.route("**/data/config.json", lambda r: (_t.sleep(1.5), r.continue_()))
    p4.goto(BASE)
    p4.type("#nick", "느린망")
    p4.wait_for_timeout(2500)
    check(p4.input_value("#nick") == "느린망" and p4.evaluate("document.activeElement.id") == "nick", "다시 그려져도 입력값·커서 유지")
    c4.close()

    print("[9] 매니페스트·아이콘")
    r = page.request.get(BASE + "manifest.webmanifest")
    check(r.ok and r.json()["short_name"] == "화물 모의시험", "manifest 제공")
    check(page.request.get(BASE + "images/icon-512.png").ok, "아이콘 512")

    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
