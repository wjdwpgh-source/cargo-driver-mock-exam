"""S1 브라우저 테스트 (개발용)
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_s1.py
"""
import os
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


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR")
    page = ctx.new_page()
    console_errors = []
    page.on("pageerror", lambda e: console_errors.append(str(e)))

    print("[1] 첫 접속 → 시작 화면")
    page.goto(BASE)
    page.wait_for_selector("#nick")
    page.wait_for_selector("text=4지선다")
    check("#/start" in page.url, "닉네임 없으면 #/start")
    page.screenshot(path=f"{SHOT}/01_start.png", full_page=True)

    print("[2] 빈 닉네임 / 13자 → 오류")
    page.click("text=시작하기")
    check("입력해 주세요" in page.inner_text("#nick-err"), "빈 닉네임 오류")
    page.fill("#nick", "가" * 13)
    page.click("text=시작하기")
    check("12자" in page.inner_text("#nick-err"), "길이 초과 오류")

    print("[3] 닉네임 생성 → 대시보드")
    page.fill("#nick", "화물왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("text=화물왕님, 반갑습니다")
    check("#/home" in page.url, "생성 후 #/home")
    page.wait_for_selector("text=문제 준비 현황")
    page.wait_for_selector(".table tbody tr")
    check(page.locator(".table tbody tr").count() == 4, "과목 4개 현황 표시")
    page.screenshot(path=f"{SHOT}/02_home.png", full_page=True)

    print("[4] 새로고침 → 유지 (S1 완료 기준)")
    page.reload()
    page.wait_for_selector("text=화물왕님, 반갑습니다")
    check(True, "새로고침 후 닉네임 유지")

    print("[5] 두 번째 닉네임 추가, 중복 차단")
    page.goto(BASE + "#/profiles")
    page.click("#add-profile")
    page.fill("#modal-input", "화물왕")
    page.click(".modal [data-act=ok]")
    check("이미 있는" in page.inner_text("#modal-error"), "모달에서 중복 차단")
    page.fill("#modal-input", "홍길동")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector("text=홍길동님, 반갑습니다")

    print("[6] 전환 → 새로고침 유지")
    page.goto(BASE + "#/profiles")
    page.click("[data-act=select]")
    page.wait_for_selector("text=화물왕님, 반갑습니다")
    page.reload()
    page.wait_for_selector("text=화물왕님, 반갑습니다")
    check(True, "전환한 닉네임이 새로고침 후 유지")

    print("[7] 이름 변경")
    page.goto(BASE + "#/profiles")
    page.locator(".manage-item.is-active [data-act=rename]").click()
    page.fill("#modal-input", "화물대장")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".manage-item.is-active >> text=화물대장")
    check(page.inner_text("#user-chip").find("화물대장") >= 0, "상단 닉네임 표시 갱신")
    page.screenshot(path=f"{SHOT}/03_profiles.png", full_page=True)

    print("[8] 삭제 (취소 → 유지, 확인 → 삭제)")
    page.locator(".manage-item.is-active [data-act=delete]").click()
    page.click(".modal [data-act=cancel]")
    check(page.locator(".manage-item").count() == 2, "취소하면 유지")
    page.locator(".manage-item.is-active [data-act=delete]").click()
    page.screenshot(path=f"{SHOT}/04_delete_confirm.png")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector("text=내 닉네임으로 계속하기")
    check("#/start" in page.url, "사용 중 닉네임 삭제 → 시작 화면")
    check(page.locator(".profile-btn").count() == 1, "남은 닉네임 1개만 표시")
    page.reload()
    page.wait_for_selector("text=내 닉네임으로 계속하기")
    check(page.locator(".profile-btn").count() == 1, "새로고침 후에도 삭제 유지")
    page.click(".profile-btn")
    page.wait_for_selector("text=홍길동님, 반갑습니다")

    print("[9] 저장 불가 환경(메모리 모드) 안내")
    ctx2 = browser.new_context(viewport={"width": 360, "height": 740})
    ctx2.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
    pg2 = ctx2.new_page()
    pg2.goto(BASE)
    pg2.wait_for_selector("text=기록이 저장되지 않는 환경")
    check(True, "저장 차단 시 안내 표시")
    ctx2.close()

    print("[10] 다크 모드 · PC 폭 스크린샷")
    ctx3 = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
    pg3 = ctx3.new_page()
    pg3.goto(BASE)
    pg3.wait_for_selector("#nick")
    pg3.wait_for_selector("text=4지선다")
    pg3.screenshot(path=f"{SHOT}/05_start_dark_pc.png", full_page=True)
    ctx3.close()

    w = page.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px에서 가로 스크롤 없음 (scrollWidth={w})")
    check(not console_errors, "자바스크립트 오류 없음 " + "; ".join(console_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
