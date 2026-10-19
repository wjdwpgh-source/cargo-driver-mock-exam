"""S5 브라우저 테스트 – 오답노트·복습 재시험
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_s5.py
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
  s.updateProfileData(id, d => {
    scores.forEach((n, k) => {
      const ip = CDME.exam.buildExam(bank, { sample: true, recent: CDME.exam.recentQids(d.exams, true) });
      ip.items.forEach((it, i) => { const a = bank.byId[it.qid].answer; CDME.exam.setAnswer(ip, i, i < n ? a : a % 4 + 1); });
      const rec = CDME.exam.score(ip, bank, { now: new Date().toISOString() });
      rec.noteReg = CDME.notes.registerWrong(d.wrongNotes, rec, bank, rec.finishedAt);
      d.exams.push(rec);
    });
  });
}"""
NOTES = "() => CDME.app.store.getProfileData().wrongNotes"


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def ans_no(page):
    return int(re.search(r"정답은 (\d)번", page.inner_text(".q-text")).group(1))


def pick(page, correct=True):
    """화면에서 원래 보기 번호(정답/오답)의 버튼을 찾아 누름 – 보기 순서가 섞여 있어도 동작"""
    a = ans_no(page)
    target = a if correct else a % 4 + 1
    page.locator(f".choice:has-text('샘플 보기 {target}')").click()
    page.wait_for_selector("#rp-fb")


def active_count(page):
    return page.evaluate("() => Object.values(CDME.app.store.getProfileData().wrongNotes).filter(n => n.state === 'active').length")


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR")
    ctx.add_init_script("localStorage.setItem('cdme_sample','1')")
    page = ctx.new_page()
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.fill("#nick", "복습왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")

    print("[1] 빈 오답노트")
    page.click("#go-review")
    page.wait_for_selector("text=복습할 오답이 없습니다")
    check("#/notes" in page.url, "대시보드 → 오답노트 (FR-709)")

    print("[2] 시험 2회(정답 60, 64) → 오답노트 화면 (FR-604, 605)")
    page.evaluate(MAKE, [60, 64])
    n0 = len(page.evaluate(NOTES))
    page.goto(BASE + "#/home")
    page.wait_for_selector("#go-review")
    check(str(n0) in page.inner_text("#go-review"), f"대시보드 복습할 오답 {n0}")
    page.click("#go-review")
    page.wait_for_selector(".note-item")
    check(page.locator(".note-item").count() == n0, f"목록 {n0}개")
    check(page.evaluate("document.documentElement.scrollWidth") <= 360, "오답노트 360px 가로 스크롤 없음")
    check(str(n0) in page.inner_text(".stats"), "요약 수치")
    check(page.locator(".chip").count() == 5, "과목 필터 칩 (전체+4)")
    page.screenshot(path=f"{SHOT}/s5_01_notes.png", full_page=False)

    print("[3] 과목 필터·정렬")
    page.click("[data-subj='SERVICE']")
    svc = page.locator(".note-item").count()
    check(svc > 0 and all("운송서비스" in t for t in page.locator(".note-meta").all_inner_texts()), f"운송서비스만 {svc}개")
    page.click("[data-subj='']")
    page.select_option("#nt-sort", "count")
    first_meta = page.locator(".note-meta").first.inner_text()
    has2 = page.evaluate("() => Object.values(CDME.app.store.getProfileData().wrongNotes).some(n => n.wrong_count >= 2)")
    check(("2회 틀림" in first_meta) == has2, f"많이 틀린 순 정렬 ({first_meta})")

    print("[4] 펼쳐서 해설 보기 → 복습 완료 처리 → 다시 복습 → 제거")
    item = page.locator(".note-item").first
    qid = item.get_attribute("data-id")
    item.locator(".note-head").click()
    check(item.locator(".note-body .choice.correct").count() == 1 and "해설" in item.inner_text(), "정답·최근 내 답·해설 표시")
    item.locator("[data-act='master']").click()
    page.wait_for_selector(f".note-item[data-id='{qid}']", state="detached")
    check(page.evaluate(NOTES)[qid]["state"] == "mastered", "복습 완료 처리")
    page.click("[data-tab='mastered']")
    page.wait_for_selector(f".note-item[data-id='{qid}']")
    page.locator(f".note-item[data-id='{qid}'] .note-head").click()
    page.locator(f".note-item[data-id='{qid}'] [data-act='activate']").click()
    page.wait_for_selector("text=아직 복습 완료한 문제가 없습니다")
    check(page.evaluate(NOTES)[qid]["state"] == "active", "다시 복습으로")
    page.click("[data-tab='active']")
    page.locator(f".note-item[data-id='{qid}'] .note-head").click()
    page.locator(f".note-item[data-id='{qid}'] [data-act='remove']").click()
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(f".note-item[data-id='{qid}']", state="detached")
    check(qid not in page.evaluate(NOTES), "제거 (확인 창 후)")

    print("[5] 복습 설정 (FR-701~704)")
    page.click("text=복습 재시험 시작")
    page.wait_for_selector("#rv-form")
    check(page.locator("[name=scope]").count() == 8, "범위 8개 (전체·많이 틀림·최근·과목4·완료)")
    check(page.is_disabled("[name=scope][value=mastered]"), "복습 완료 0개 → 비활성")
    page.screenshot(path=f"{SHOT}/s5_02_setup.png", full_page=True)
    sw = page.evaluate("document.documentElement.scrollWidth")
    check(sw <= 360, f"설정 화면 360px 가로 스크롤 없음 ({sw})")
    page.click("text=10문항")
    page.click("text=복습 시작")
    page.wait_for_selector("#rp-card .choice")
    check("1</b> / 10" in page.inner_html("#rp-progress"), "10문항 출제")
    check(page.evaluate("document.documentElement.scrollWidth") <= 360, "복습 풀이 360px 가로 스크롤 없음")

    print("[6] 보기 순서 섞기 + 원래 번호로 채점 (FR-705)")
    shuffled = 0
    for i in range(10):
        if i:
            page.click("#rp-next")
        order = [t.split()[-1] for t in page.locator(".choice-text").all_inner_texts()]
        if order != ["1", "2", "3", "4"]:
            shuffled += 1
        pick(page, correct=(i != 9))
        if i == 0:
            check("연속 정답 1/2" in page.inner_text("#rp-fb"), "정답 → 연속 정답 1/2 안내")
    check(shuffled >= 5, f"보기 순서 섞임 ({shuffled}/10)")
    check("오답입니다" in page.inner_text("#rp-fb") and "정답은" in page.inner_text("#rp-fb"), "오답 → 섞인 화면 기준 정답 위치 안내")
    page.screenshot(path=f"{SHOT}/s5_03_play.png", full_page=True)
    check(page.inner_text("#rp-next") == "복습 결과 보기", "다 풀면 결과 보기")
    page.click("#rp-next")
    page.wait_for_selector("text=복습 결과")
    check("9" in page.inner_text(".result-score") and "10" in page.inner_text(".result-score"), "결과 9 / 10")
    check("다시 틀린 문제 1" in page.inner_text("#view"), "다시 틀린 문제 1")

    print("[7] 같은 문제 연속 2회 정답 → 복습 완료 (FR-706, 707)")
    streak1 = page.evaluate("() => Object.entries(CDME.app.store.getProfileData().wrongNotes).filter(([k, n]) => n.streak === 1).map(([k]) => k)")
    check(len(streak1) == 9, "연속 정답 1인 문제 9개")
    page.evaluate("""(ids) => { const s = CDME.app.store; const id = s.getActiveProfile().id;
      s.updateProfileData(id, d => { const keep = new Set(ids); Object.keys(d.wrongNotes).forEach(k => { if (!keep.has(k)) d.wrongNotes[k].state = 'mastered'; }); }); }""", streak1)
    page.goto(BASE + "#/review")
    page.wait_for_selector("#rv-form")
    page.click("text=전체")
    page.click("text=복습 시작")
    page.wait_for_selector("#rp-card .choice")
    pick(page, True)
    check("복습 완료" in page.inner_text("#rp-fb"), "🎓 복습 완료 안내")
    for i in range(1, 9):
        page.click("#rp-next")
        pick(page, True)
    page.click("#rp-next")
    page.wait_for_selector("text=복습 결과")
    check("이번에 복습 완료한 문제 9" in page.inner_text("#view"), "결과에 복습 완료 9문제")
    check(active_count(page) == 0, "남은 오답 0")

    print("[8] 복습 완료 문제 다시 풀기 → 틀리면 재등록 (FR-708)")
    page.goto(BASE + "#/review")
    page.wait_for_selector("#rv-form")
    check(page.is_disabled("[name=scope][value=all]"), "복습 중 0개 → 전체 비활성")
    page.check("[name=scope][value=mastered]")
    page.click("text=10문항")
    page.click("text=복습 시작")
    page.wait_for_selector("#rp-card .choice")
    pick(page, False)
    check("다시 복습 목록" in page.inner_text("#rp-fb"), "완료 문제 오답 → 재등록 안내")
    check(active_count(page) == 1, "복습 중 1개로")

    print("[9] 나중에 이어 풀기 / 그만하기 (부분 기록)")
    page.click("#rp-later")
    page.wait_for_selector("text=진행 중인 복습이 있습니다")
    page.click(".resume >> text=이어 풀기")
    page.wait_for_selector("#rp-card .choice")
    check(page.locator("#rp-fb").count() == 1, "이어 풀기: 답한 문항 상태 유지")
    page.click("#rp-next")
    pick(page, True)
    page.click("#rp-quit")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector("text=복습 결과")
    check("2문항 풀이" in page.inner_text(".result-hero"), "그만하기 → 푼 2문항만 기록")

    print("[10] 시간 제한 (FR-704)")
    page.goto(BASE + "#/review")
    page.wait_for_selector("#rv-form")
    page.check("[name=scope][value=mastered]")
    page.check("#rv-timed")
    page.click("text=10문항")
    page.click("text=복습 시작")
    page.wait_for_selector("#rp-timer")
    check(page.inner_text("#rp-timer") in ("10:00", "09:59"), f"10문항 → 10분 ({page.inner_text('#rp-timer')})")
    pick(page, True)
    page.click("#rp-later")
    page.wait_for_selector(".resume")
    page.evaluate("""() => { const s = CDME.app.store; const id = s.getActiveProfile().id; s.updateProfileData(id, d => { d.reviewInProgress.remainingMs = 1200; }); }""")
    page.click(".resume >> text=이어 풀기")
    page.wait_for_selector("text=복습 결과", timeout=6000)
    check(True, "시간 종료 → 결과")

    print("[11] 실전 성적과 분리 (FR-505)")
    page.goto(BASE + "#/records")
    page.wait_for_selector(".stats-4")
    check("2회" in page.inner_text(".stats-4"), "실전 응시 2회 그대로")
    page.goto(BASE + "#/notes")
    page.wait_for_selector(".session-list")
    check(page.locator(".session-list li").count() == 4, "최근 복습 기록 4건 표시")

    w = page.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px 가로 스크롤 없음 ({w})")
    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))

    print("[12] PC 다크 스크린샷")
    c3 = browser.new_context(viewport={"width": 1100, "height": 1000}, color_scheme="dark")
    c3.add_init_script("localStorage.setItem('cdme_sample','1')")
    p3 = c3.new_page()
    p3.goto(BASE)
    p3.fill("#nick", "다크")
    p3.press("#nick", "Enter")
    p3.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    p3.evaluate(MAKE, [55])
    p3.goto(BASE + "#/notes")
    p3.wait_for_selector(".note-item")
    p3.locator(".note-head").first.click()
    p3.screenshot(path=f"{SHOT}/s5_04_notes_dark_pc.png")
    p3.goto(BASE + "#/review")
    p3.click("text=복습 시작")
    p3.wait_for_selector("#rp-card .choice")
    pick(p3, False)
    p3.screenshot(path=f"{SHOT}/s5_05_play_dark_pc.png")
    c3.close()
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
