"""S4 브라우저 테스트 – 내 기록 (응시 이력·점수 추이·과목별 평균)
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_s4.py
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT, exist_ok=True)
errors = []

# 샘플 문제로 시험 기록을 빠르게 만드는 스크립트 (정답 수 n개)
MAKE = """(scores) => {
  const bank = CDME.app.getBank(); const s = CDME.app.store; const id = s.getActiveProfile().id;
  s.updateProfileData(id, d => {
    scores.forEach((n, k) => {
      const ip = CDME.exam.buildExam(bank, { sample: true, recent: CDME.exam.recentQids(d.exams, true) });
      ip.items.forEach((it, i) => { const a = bank.byId[it.qid].answer; CDME.exam.setAnswer(ip, i, i < n ? a : a % 4 + 1); });
      ip.remainingMs = ip.totalMs - (40 + k) * 60000;
      const rec = CDME.exam.score(ip, bank, { now: new Date(Date.UTC(2026, 9, 1 + k, 3)).toISOString() });
      rec.noteReg = CDME.notes.registerWrong(d.wrongNotes, rec, bank, rec.finishedAt);
      d.exams.push(rec);
    });
  });
}"""


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR")
    ctx.add_init_script("localStorage.setItem('cdme_sample','1')")
    page = ctx.new_page()
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.fill("#nick", "기록왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")

    print("[1] 기록 없을 때")
    page.goto(BASE + "#/records")
    page.wait_for_selector("text=아직 응시한 실전 모의시험이 없습니다")
    check(True, "빈 화면 안내")

    print("[2] 시험 6회 기록 생성 (정답 40, 44, 52, 48, 56, 64개 → 50, 55, 65, 60, 70, 80점)")
    page.evaluate(MAKE, [40, 44, 52, 48, 56, 64])
    page.goto(BASE + "#/home")
    page.wait_for_selector(".stats")
    check("6회" in page.inner_text(".stats") and "80점" in page.inner_text(".stats"), "대시보드 요약 반영")
    page.click(".stats-link")
    page.wait_for_selector("#trend svg")
    check("#/records" in page.url, "요약 카드 → 내 기록")

    print("[3] 요약 (FR-501, 504)")
    st = page.inner_text(".stats-4")
    check("6회" in st and "63.3점" in st and "80점" in st and "67%" in st and "4/6회" in st, f"응시·평균·최고·합격률 ({st.split()})")

    print("[4] 점수 추이 그래프 (FR-503)")
    check(page.locator(".trend-dot").count() == 6, "점 6개")
    check(page.locator(".trend-dot.fail").count() == 2, "불합격 2회는 빈 점으로 구분")
    check(page.locator(".pass-line").count() == 1 and "합격선 60점" in page.inner_text("#trend"), "합격선 표시")
    check(page.locator(".value-label").text_content() == "80점", "마지막 점수 직접 라벨")
    box = page.locator("#trend svg").bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 100)
    page.wait_for_selector(".chart-tip:not([hidden])")
    check("50점" in page.inner_text(".chart-tip") and "1회차" in page.inner_text(".chart-tip"), f"툴팁: 가장 가까운 회차 ({page.inner_text('.chart-tip')})")
    page.screenshot(path=f"{SHOT}/s4_01_records.png", full_page=True)

    print("[5] 과목별 평균 (FR-504)")
    rows = page.locator(".subj-table tbody tr")
    check(rows.count() == 4, "과목 4개")
    check(rows.nth(0).inner_text().split()[1] == "100%", f"법규 100% (각 시험 앞 25문항 정답) ({rows.nth(0).inner_text().split()})")
    check(page.locator(".subj-table .tag-bad").count() >= 1, "합격선 미만 과목 '보완 필요'")

    print("[6] 응시 이력 최신순 → 다시보기 (FR-501, 502)")
    items = page.locator(".hist-item")
    check(items.count() == 6, "이력 6건")
    check(items.first.inner_text().startswith("6회") and "80" in items.first.inner_text(), "최신(6회) 맨 위")
    check("불합격" in items.nth(5).inner_text(), "1회 불합격")
    items.nth(5).click()
    page.wait_for_selector(".result-hero")
    check(page.inner_text(".result-score") == "50점", "지난 시험 결과·다시보기 열림")
    check(page.locator(".rv-card").count() == 40, "틀린 문제 40개 다시보기")
    page.click("text=내 기록 보기")
    page.wait_for_selector("#trend svg")

    print("[7] 그래프 점 두 번 누르면 해당 결과로")
    page.mouse.click(box["x"] + box["width"] - 14, box["y"] + 60)
    page.mouse.click(box["x"] + box["width"] - 14, box["y"] + 60)
    page.wait_for_selector(".result-hero")
    check(page.inner_text(".result-score") == "80점", "마지막 회차 결과로 이동")

    print("[8] 실제 응시 1회 후 추가 반영 + 25회 추이 제한")
    page.evaluate(MAKE, [60] * 19)
    page.goto(BASE + "#/records")
    page.wait_for_selector("#trend svg")
    check("25회" in page.inner_text(".stats-4"), "응시 25회")
    check(page.locator(".trend-dot").count() == 20, "그래프는 최근 20회")
    check("최근 20회" in page.inner_text("h2:has-text('점수 추이')"), "최근 20회 표시")

    print("[9] 실제 모드 분리")
    page.goto(BASE + "#/home")
    page.click("[data-sample-off]")
    page.wait_for_selector("text=출제 가능한 문제가 아직 부족합니다")
    page.goto(BASE + "#/records")
    page.wait_for_selector("text=아직 응시한 실전 모의시험이 없습니다")
    check(True, "실제 모드 기록 없음")

    w = page.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px 가로 스크롤 없음 ({w})")
    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))

    print("[10] PC 다크 스크린샷")
    c3 = browser.new_context(viewport={"width": 1100, "height": 1300}, color_scheme="dark")
    c3.add_init_script("localStorage.setItem('cdme_sample','1')")
    p3 = c3.new_page()
    p3.goto(BASE)
    p3.fill("#nick", "다크")
    p3.press("#nick", "Enter")
    p3.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    p3.evaluate(MAKE, [40, 44, 52, 48, 56, 64, 58, 70])
    p3.goto(BASE + "#/records")
    p3.wait_for_selector("#trend svg")
    b = p3.locator("#trend svg").bounding_box()
    p3.mouse.move(b["x"] + b["width"] * 0.55, b["y"] + 80)
    p3.screenshot(path=f"{SHOT}/s4_02_records_dark_pc.png", full_page=True)
    c3.close()
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
