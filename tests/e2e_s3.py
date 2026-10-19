"""S3 브라우저 테스트 – 결과 화면 다시보기·오답노트 자동 등록·담기·오류 신고
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_s3.py
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


def notes(page):
    return page.evaluate("() => CDME.app.store.getProfileData().wrongNotes")


def start_exam(page):
    page.goto(BASE + "#/home")
    page.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    page.click("#start-exam")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")


def end_by_timeout(page):
    page.click("#ex-later")
    page.wait_for_selector(".resume")
    page.evaluate("""() => { const s = CDME.app.store; const id = s.getActiveProfile().id;
        s.updateProfileData(id, d => { d.inProgress.remainingMs = 1200; }); }""")
    page.click("#resume-exam")
    page.wait_for_selector(".result-hero", timeout=6000)


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    # 설정 파일을 가로채는 [10]번 테스트를 위해 오프라인 기능(Service Worker)은 끔
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    # 저장소 주소가 정해지기 전 상태를 흉내 ([5]), [10]에서는 페이지 단위로 다시 바꿈
    CFG = open(os.path.join(os.path.dirname(__file__), "..", "data", "config.json"), encoding="utf-8").read()
    CFG = re.sub(r"https://github\.com/[^/]+/", "https://github.com/<계정>/", CFG)
    ctx.route("**/data/config.json", lambda r: r.fulfill(status=200, content_type="application/json", body=CFG))
    page = ctx.new_page()
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.evaluate("localStorage.setItem('cdme_sample','1')")
    page.reload()
    page.fill("#nick", "복습왕")
    page.press("#nick", "Enter")

    print("[1] 시험: 1~3번 정답, 4~5번 오답, 나머지 시간 종료")
    start_exam(page)
    first_qids = page.evaluate("() => CDME.app.store.getProfileData().inProgress.items.map(i => i.qid)")
    for i in range(5):
        if i:
            page.click("#ex-next")
        c = correct_no(page)
        page.click(f"[data-choice='{c if i < 3 else c % 4 + 1}']")
    check(page.locator(".fb-actions >> text=오류 신고").count() == 1, "풀이 중 해설에 오류 신고 버튼")
    end_by_timeout(page)

    print("[2] 오답노트 자동 등록 (FR-601)")
    n = notes(page)
    check(len(n) == 77, f"오답 2 + 안 푼 75 = 77개 등록 ({len(n)})")
    check(all(v["added_by"] == "auto" and v["state"] == "active" and v["sample"] for v in n.values()), "자동·활성·샘플 표시")
    check(first_qids[0] not in n, "맞힌 문제는 미등록")
    check(n[first_qids[3]]["wrong_count"] == 1 and n[first_qids[3]]["last_choice"] is not None, "오답 문제 횟수 1, 내 답 기록")
    check("틀린 문제 2개" in page.inner_text(".note-info") and "안 푼 문제 75개" in page.inner_text(".note-info"), "결과 화면 등록 안내")

    print("[3] 문제별 다시보기 필터 (FR-401, 402)")
    check(page.locator(".tab.on").inner_text().startswith("틀린 문제"), "기본 필터 = 틀린 문제")
    check(page.locator(".rv-card").count() == 2, "틀린 문제 2개 표시")
    card = page.locator(".rv-card").first
    check(card.locator(".choice.correct").count() == 1 and card.locator(".choice.wrong").count() == 1, "정답·내 오답 표시")
    check("내 답" in card.inner_text() and "해설" in card.inner_text(), "내 답 표시·해설")
    page.screenshot(path=f"{SHOT}/s3_01_result_wrong.png", full_page=True)
    page.click("[data-filter='skip']")
    check(page.locator(".rv-card").count() == 75, "안 푼 문제 75개")
    page.click("[data-filter='all']")
    check(page.locator(".rv-card").count() == 80, "전체 80개")
    check(page.locator(".rv-card .tag-ok").count() == 3, "정답 3개 표시")

    print("[4] 오답노트에 담기 (FR-403)")
    ok_card = page.locator(".rv-card:has(.tag-ok)").first
    qid = ok_card.get_attribute("data-qid")
    check(page.locator(".rv-card .tag-note").count() == 77, "등록된 77문제는 '오답노트에 있음'")
    ok_card.locator("[data-add-note]").click()
    page.wait_for_selector(".toast")
    n = notes(page)
    check(qid in n and n[qid]["added_by"] == "manual" and n[qid]["wrong_count"] == 0, "맞힌 문제 수동 담기")
    check(page.locator(f".rv-card[data-qid='{qid}'] .tag-note").count() == 1, "담은 뒤 '오답노트에 있음'으로 변경")
    page.screenshot(path=f"{SHOT}/s3_02_result_all.png")

    print("[5] 오류 신고 (FR-404) – 저장소 미정이면 비활성")
    btn = page.locator(".rv-card").first.locator("text=오류 신고")
    check(btn.is_disabled(), "저장소 주소 미정 → 비활성 버튼")

    print("[6] 대시보드 복습할 오답 수")
    page.goto(BASE + "#/home")
    page.wait_for_selector("#go-review")
    check("78" in page.inner_text("#go-review"), f"복습할 오답 78 ({page.inner_text('#go-review')})")

    print("[7] 두 번째 시험: 같은 문제 다시 틀리면 횟수 +1 (FR-602)")
    before_keys = set(notes(page).keys())
    start_exam(page)
    second = page.evaluate("() => CDME.app.store.getProfileData().inProgress.items.map(i => i.qid)")
    end_by_timeout(page)
    n = notes(page)
    again = [q for q in second if q in first_qids and q not in first_qids[:3]]
    check(len(again) > 0 and all(n[q]["wrong_count"] == 2 for q in again), f"다시 나온 문제 {len(again)}개 횟수 2")
    exp = len([q for q in second if q in before_keys])
    check("다시 틀림 " + str(exp) in page.inner_text(".note-info"), f"다시 틀림 수 안내 ({exp})")

    print("[8] 결과 화면 새로고침·지난 결과 재방문")
    page.reload()
    page.wait_for_selector(".rv-card")
    check(True, "새로고침 후 다시보기 표시")

    print("[9] 실제 모드에서는 샘플 오답 수 0")
    page.goto(BASE + "#/home")
    page.click("[data-sample-off]")
    page.wait_for_selector("text=출제 가능한 문제가 아직 부족합니다")
    check(" 0" in page.inner_text("#go-review") or "<b>0</b>" in page.inner_html("#go-review"), "실제 모드 복습할 오답 0")

    w = page.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px 가로 스크롤 없음 ({w})")
    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))

    print("[10] 오류 신고 주소가 있을 때 링크 (설정 변경 시)")
    pg = ctx.new_page()
    pg.route("**/data/config.json", lambda r: r.fulfill(status=200, content_type="application/json",
             body=CFG.replace("<계정>", "tester")))
    pg.goto(BASE)
    pg.evaluate("localStorage.setItem('cdme_sample','1')")
    pg.goto(BASE + "#/result")
    pg.wait_for_selector(".rv-card")
    href = pg.locator(".rv-card").first.locator("a:has-text('오류 신고')").get_attribute("href")
    check(href.startswith("https://github.com/tester/cargo-driver-mock-exam/issues/new?title="), "GitHub Issue 작성 주소")
    check("%EB%AC%B8%EC%A0%9C%20%EC%98%A4%EB%A5%98" in href, "제목에 [문제 오류] 포함")

    print("[11] PC 다크 모드 스크린샷")
    ctx3 = browser.new_context(viewport={"width": 1280, "height": 1000}, color_scheme="dark")
    ctx3.add_init_script("localStorage.setItem('cdme_sample','1')")
    p3 = ctx3.new_page()
    p3.goto(BASE)
    p3.fill("#nick", "다크")
    p3.press("#nick", "Enter")
    start_exam(p3)
    p3.click(f"[data-choice='{correct_no(p3) % 4 + 1}']")
    end_by_timeout(p3)
    p3.screenshot(path=f"{SHOT}/s3_03_result_dark_pc.png")
    ctx3.close()
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
