"""S2 브라우저 테스트 (v1.9 즉시 채점 방식) – 샘플 문제로 실전 시험 완주
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_s2.py
"""
import os
import re
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT, exist_ok=True)
errors = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def correct_no(page):
    return int(re.search(r"정답은 (\d)번", page.inner_text(".q-text")).group(1))


def wrong_no(page):
    return correct_no(page) % 4 + 1


def timer_sec(page):
    m, s = page.inner_text("#ex-timer").split(":")
    return int(m) * 60 + int(s)


def progress(page):
    return page.inner_text("#ex-progress").strip()


def tally(page):
    return page.inner_text("#ex-tally")


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR")
    page = ctx.new_page()
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    print("[1] 문제 부족 → 시작 차단 → 샘플 모드 (FR-211)")
    page.goto(BASE)
    page.fill("#nick", "시험왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("text=출제 가능한 문제가 아직 부족합니다")
    page.click("#start-exam")
    page.wait_for_selector("text=아직 시험을 볼 수 없습니다")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    check(True, "샘플 모드에서 출제 가능")

    print("[2] 시험 시작, 제출 버튼 없음")
    page.click("#start-exam")
    check("정답·오답과 해설" in page.inner_text(".modal"), "시작 안내에 즉시 채점 설명")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")
    check(progress(page) == "1 / 80", "1 / 80 표시")
    check(page.locator("#ex-submit").count() == 0 and page.locator("text=제출하기").count() == 0, "제출하기 버튼 없음")
    check(page.locator(".feedback").count() == 0, "답하기 전에는 정답·해설 없음")
    page.wait_for_timeout(2100)
    check(4795 <= timer_sec(page) <= 4799, f"타이머 감소 ({page.inner_text('#ex-timer')})")

    print("[3] 정답 선택 → 즉시 정답 표시·해설, 답 고정")
    c = correct_no(page)
    page.click(f"[data-choice='{c}']")
    page.wait_for_selector(".feedback.is-correct")
    check("정답입니다" in page.inner_text(".feedback"), "정답 안내")
    check("샘플 문제의 해설" in page.inner_text(".feedback"), "해설 표시")
    check(page.locator(".choice.correct").count() == 1 and page.locator(".choice.wrong").count() == 0, "정답 보기 초록 표시")
    check(page.is_disabled(f"[data-choice='{wrong_no(page)}']"), "답한 뒤 보기 잠김")
    page.keyboard.press(str(wrong_no(page)))
    check(page.locator(".feedback.is-correct").count() == 1, "키보드로도 답 변경 불가")
    check("정답 1" in tally(page) and "오답 0" in tally(page), "정답 1 · 오답 0 집계")
    page.screenshot(path=f"{SHOT}/v19_01_correct.png", full_page=True)

    print("[4] 오답 선택 → 오답 표시, 정답 번호 안내")
    page.click("#ex-next")
    w = wrong_no(page)
    c = correct_no(page)
    page.click(f"[data-choice='{w}']")
    page.wait_for_selector(".feedback.is-wrong")
    fb = page.inner_text(".feedback")
    check("오답입니다" in fb and "정답은" in fb, "오답 안내 + 정답 번호")
    check("wrong" in page.get_attribute(f"[data-choice='{w}']", "class"), "고른 오답 빨강")
    check("correct" in page.get_attribute(f"[data-choice='{c}']", "class"), "정답 보기 초록")
    check("오답 1" in tally(page), "오답 집계")
    page.screenshot(path=f"{SHOT}/v19_02_wrong.png", full_page=True)

    print("[5] 3~30번 정답 (누적 정답 29, 오답 1), 키보드 사용")
    for i in range(2, 30):
        page.keyboard.press("ArrowRight")
        page.keyboard.press(str(correct_no(page)))
    page.wait_for_selector(".feedback")
    check(progress(page) == "30 / 80", "30번 도달")
    check("정답 29" in tally(page) and "오답 1" in tally(page) and "남은 문항 50" in tally(page), f"집계 ({tally(page)})")

    print("[6] 새로고침 → 이어 풀기 (FR-208), 답한 문항은 해설 상태 유지")
    before = timer_sec(page)
    page.reload()
    page.wait_for_selector(".q-card .choice")
    check(progress(page) == "30 / 80", "현재 문항 유지")
    check(page.locator(".feedback").count() == 1, "답한 문항은 해설 그대로")
    check("정답 29" in tally(page), "정답 수 유지")
    check(0 <= before - timer_sec(page) <= 6, "남은 시간 유지")

    print("[7] 대시보드 → 이어 풀기")
    page.click("#ex-later")
    page.wait_for_selector("text=진행 중인 시험이 있습니다")
    page.click("#resume-exam")
    page.wait_for_selector(".q-card .choice")

    print("[8] 31~49번 정답 (누적 정답 48), 50번 비움")
    for i in range(30, 49):
        page.click("#ex-next")
        page.click(f"[data-choice='{correct_no(page)}']")
    check("정답 48" in tally(page), f"정답 48 ({tally(page)})")

    print("[9] 번호판: 정답/오답/안 푼 문항 색, 다 풀기 전 결과 보기 없음")
    page.click("#ex-grid")
    page.wait_for_selector(".grid-modal")
    check(page.locator(".grid .cell.correct").count() == 48, "정답 칸 48")
    check(page.locator(".grid .cell.wrong").count() == 1, "오답 칸 1")
    check(page.locator("[data-finish]").count() == 0 and page.locator(".grid-modal >> text=제출").count() == 0, "결과 보기·제출 없음")
    page.screenshot(path=f"{SHOT}/v19_03_grid.png")
    page.click("[data-go='79']")
    check(page.inner_text("#ex-next") == "안 푼 문항으로", "마지막 문항에서 '안 푼 문항으로'")
    page.click("#ex-next")
    check(progress(page) == "50 / 80", "첫 안 푼 문항(50번)으로 이동")

    print("[10] 남은 31문항 모두 오답 → 결과 보기 (정답 48 = 60점 합격)")
    for i in range(49, 80):
        check_pos = progress(page) == f"{i + 1} / 80"
        if not check_pos:
            check(False, f"{i + 1}번 위치 ({progress(page)})")
            break
        page.click(f"[data-choice='{wrong_no(page)}']")
        if i < 79:
            page.click("#ex-next")
    page.wait_for_selector("#ex-finish")
    check("모든 문항을 풀었습니다" in page.inner_text(".done-box"), "다 풀면 안내 + 결과 보기 버튼")
    check(page.inner_text("#ex-next") == "결과 보기", "하단 버튼도 결과 보기")
    page.screenshot(path=f"{SHOT}/v19_04_done.png", full_page=True)
    page.click("#ex-finish")
    page.wait_for_selector(".result-hero")
    check(page.inner_text(".result-score") == "60점", f"60점 ({page.inner_text('.result-score')})")
    check(page.inner_text(".result-badge") == "합격", "합격")
    check("정답 48 / 80" in page.inner_text(".result-hero"), "정답 48 / 80")

    print("[11] 시간 알림·자동 종료 (FR-203, 204)")
    page.goto(BASE + "#/home")
    page.click("#start-exam")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")
    page.click(f"[data-choice='{correct_no(page)}']")
    page.click("#ex-later")
    page.wait_for_selector(".resume")
    page.evaluate("""() => { const s = CDME.app.store; const id = s.getActiveProfile().id;
        s.updateProfileData(id, d => { d.inProgress.remainingMs = 61500; }); }""")
    page.click("#resume-exam")
    page.wait_for_selector(".toast", timeout=5000)
    page.wait_for_timeout(300)
    check("1분" in page.inner_text(".toast"), "1분 전 알림")
    page.click("#ex-later")
    page.wait_for_selector(".resume")
    page.evaluate("""() => { const s = CDME.app.store; const id = s.getActiveProfile().id;
        s.updateProfileData(id, d => { d.inProgress.remainingMs = 1500; }); }""")
    page.click("#resume-exam")
    page.wait_for_selector(".result-hero", timeout=6000)
    check("자동으로" in page.inner_text("#view"), "시간 종료 → 자동 종료 안내")
    check(page.inner_text(".result-badge") == "불합격", "1문항 정답 → 불합격")

    w = page.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px 가로 스크롤 없음 ({w})")
    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))

    print("[12] PC 다크 모드 스크린샷")
    ctx3 = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark")
    pg = ctx3.new_page()
    pg.goto(BASE)
    pg.evaluate("localStorage.setItem('cdme_sample','1')")
    pg.reload()
    pg.fill("#nick", "다크")
    pg.press("#nick", "Enter")
    pg.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    pg.click("#start-exam")
    pg.click(".modal [data-act=ok]")
    pg.wait_for_selector(".q-card .choice")
    pg.click(f"[data-choice='{wrong_no(pg)}']")
    pg.wait_for_selector(".feedback")
    pg.screenshot(path=f"{SHOT}/v19_05_dark_pc.png")
    ctx3.close()
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
