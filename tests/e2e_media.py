"""v2.0 L3 브라우저 테스트 – 대형면허 그림·크게 보기·화면 표기·도움말·오프라인 그림
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_media.py
대형 문제는 테스트 전용 가짜 문제(tests/fixtures/license, 그림 포함)를 사용한다.
  - [1]~[6]: 요청 가로채기로 가짜 문제·그림을 넣어 확인
  - [7] 오프라인: 임시 폴더에 사이트를 복사하고 가짜 문제를 넣어 별도 서버(8010)로 띄운 뒤 Service Worker 확인
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHOT = os.path.join(HERE, "screenshots")
FIX = os.path.join(HERE, "fixtures", "license")
os.makedirs(SHOT, exist_ok=True)
errors = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def serve(route):
    url = route.request.url.split("?")[0]
    name = url.split("/")[-1]
    if "/data/license/images/" in url:
        path, ctype = os.path.join(FIX, "images", name), "image/svg+xml"
    else:
        path, ctype = os.path.join(FIX, name), "application/json"
    if os.path.exists(path):
        route.fulfill(status=200, content_type=ctype, body=open(path, encoding="utf-8").read())
    else:
        route.continue_()


IP = "CDME.app.store.getProfileData().inProgress"


def goto_index(page, idx):
    page.evaluate("(i) => { const s = CDME.app.store; s.updateProfileData(s.getActiveProfile().id, d => { d.inProgress.current = i; }); CDME.app.render(); }", idx)
    page.wait_for_selector(f"#ex-progress >> text={idx + 1}")


def new_license_user(page, base, nick):
    page.goto(base)
    page.wait_for_selector("#nick")
    page.check("[name=start-exam][value=license]")
    page.wait_for_selector("text=4지·5지선다")
    page.fill("#nick", nick)
    page.press("#nick", "Enter")
    page.wait_for_selector("text=40문항 · 40분")


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    js_errors = []
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    ctx.route("**/data/license/**", serve)
    page = ctx.new_page()
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    print("[1] 표지·일러스트 문항 그림 표시, 대체 텍스트")
    new_license_user(page, BASE, "그림왕")
    page.click("#start-exam")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")
    ip = page.evaluate(IP)
    check(page.locator(".q-card .q-fig").count() == 0, "문장형은 그림 없음")
    sign = next(i for i, it in enumerate(ip["items"]) if it["subject"] == "SIGN")
    goto_index(page, sign)
    page.wait_for_selector(".q-card .q-img-btn")
    page.wait_for_function("() => { const i = document.querySelector('.q-card .q-img'); return i && i.complete && i.naturalWidth > 0; }")
    q = page.evaluate("(i) => CDME.app.getBank().byId[" + IP + ".items[i].qid]", sign)
    label = page.get_attribute(".q-card .q-img-btn", "aria-label")
    check(q["image_alt"] in label and "크게 보기" in label, "그림 버튼 이름 = 대체 텍스트 + 크게 보기")
    check(page.get_attribute(".q-card .q-img", "src") == "data/" + q["image"], "그림 경로 data/license/images/…")
    page.screenshot(path=f"{SHOT}/media_01_sign.png", full_page=True)
    check(page.evaluate("document.documentElement.scrollWidth") <= 360, "그림 문항 360px 가로 스크롤 없음")

    print("[2] 크게 보기: 열기·숫자키 무시·Esc·초점 복귀·닫기 버튼 (TC-L09)")
    page.click(".q-card .q-img-btn")
    page.wait_for_selector(".zoom-backdrop .zoom-img")
    check(page.get_attribute(".zoom-img", "alt") == q["image_alt"], "크게 보기 그림 대체 텍스트")
    check(q["image_alt"] in page.inner_text(".zoom-cap"), "그림 설명 글자로 표시")
    check(page.evaluate("document.activeElement.hasAttribute('data-zoom-close')"), "초점은 닫기 버튼")
    page.screenshot(path=f"{SHOT}/media_02_zoom.png")
    page.keyboard.press(str(q["answer"][0]))
    check(page.evaluate(IP)["answers"][sign] is None, "크게 보기 중 숫자키로 답이 골라지지 않음")
    page.keyboard.press("Tab")
    check(page.evaluate("document.activeElement.hasAttribute('data-zoom-close')"), "Tab 해도 창 안에 머묾")
    page.keyboard.press("Escape")
    page.wait_for_selector(".zoom-backdrop", state="detached")
    check(page.evaluate("document.activeElement.classList.contains('q-img-btn')"), "Esc로 닫으면 그림 버튼으로 초점 복귀")
    page.focus(".q-card .q-img-btn")
    page.keyboard.press("Enter")
    page.wait_for_selector(".zoom-backdrop")
    page.click("[data-zoom-close]")
    page.wait_for_selector(".zoom-backdrop", state="detached")
    check(True, "키보드(Enter)로 열고 닫기 버튼으로 닫기")
    page.keyboard.press(str(q["answer"][0]))
    page.wait_for_selector("#ex-feedback")
    check("정답입니다" in page.inner_text("#ex-feedback"), "닫은 뒤에는 숫자키로 답하기")

    print("[3] 오류 신고 주소에 시험 표시 (FR-L15)")
    href = page.get_attribute("#ex-feedback a:has-text('오류 신고')", "href")
    from urllib.parse import unquote
    check("[대형] DL-" in unquote(href) and "시험: 대형운전면허(1종) 학과" in unquote(href), "이슈 제목 [대형] DL-…, 본문에 시험 이름")

    print("[4] 일러스트 5지 그림, 결과 다시보기 그림")
    ill = next(i for i, it in enumerate(ip["items"]) if it["subject"] == "ILLUST2")
    goto_index(page, ill)
    page.wait_for_selector(".q-card .q-img-btn")
    page.wait_for_function("() => { const i = document.querySelector('.q-card .q-img'); return i && i.complete && i.naturalWidth > 0; }")
    check(page.locator(".q-card .choice").count() == 5, "일러스트 2답: 그림 + 보기 5개")
    page.screenshot(path=f"{SHOT}/media_03_illust.png", full_page=True)
    page.evaluate("""() => { const s = CDME.app.store, bank = CDME.app.getBank();
      s.updateProfileData(s.getActiveProfile().id, d => { const ip = d.inProgress; let k = 0;
        ip.items.forEach((it, i) => { if (ip.answers[i] != null) return; const q = bank.byId[it.qid];
          const w = [1,2,3,4].find(n => q.answer.indexOf(n) < 0);
          ip.answers[i] = (k++ % 3 === 0) ? (q.answer.length > 1 ? q.answer.slice() : q.answer[0]) : (q.answer.length > 1 ? [q.answer[0], w].sort() : w); });
        ip.current = 0; }); CDME.app.render(); }""")
    page.click("#ex-finish")
    page.wait_for_selector(".result-hero")
    page.click("[data-filter=all]")
    check(page.locator(".rv-card .q-img-btn").count() == 19, "다시보기: 그림 문항 19개(표지 5·일러스트 14) 그림 표시")

    print("[5] 내 기록·오답노트·집중 학습: '유형' 표기, 합격선 70%")
    page.goto(BASE + "#/records")
    page.wait_for_selector("text=유형별 평균 정답률")
    main = page.inner_text("main")
    check("취약 유형 분석" in main and "과목" not in main, "내 기록: 유형 표기('과목' 없음)")
    check("합격선(70%)" in main, "합격선 70%")
    page.goto(BASE + "#/notes")
    page.wait_for_selector(".note-head")
    check(page.get_attribute(".filter-row .chips", "aria-label") == "유형", "오답노트 필터 '유형'")
    page.click(".note-item:has(.tag:has-text('안전표지')) .note-head") if page.locator(".note-item:has(.tag:has-text('안전표지'))").count() else None
    page.goto(BASE + "#/review")
    page.wait_for_selector("#rv-form")
    check("유형별" in page.inner_text("#rv-form"), "복습 설정 '유형별'")
    page.goto(BASE + "#/study")
    page.wait_for_selector("#st-avail")
    st = page.inner_text("#st-form")
    check("유형" in st and "과목" not in st, "집중 학습 '유형'")
    check(page.evaluate("document.documentElement.scrollWidth") <= 360, "집중 학습 360px 가로 스크롤 없음")

    print("[6] 도움말: 시험별 안내 탭")
    page.goto(BASE + "#/help")
    page.wait_for_selector("#help-exam")
    hx = page.inner_text("#help-exam")
    check("도로교통법 제82조" in hx and "학습용 점수" in hx and "일러스트형" in hx, "대형 안내: 응시 자격·학습용 배점·사진/동영상 대체")
    check(page.locator("#help-exam a[href*='safedriving.or.kr']").count() == 1, "공단 문제은행 링크")
    check(page.get_attribute("[data-help-exam=license]", "aria-pressed") == "true", "지금 시험 탭이 기본")
    page.click("[data-help-exam=cargo]")
    page.wait_for_function("document.getElementById('help-exam').innerText.includes('한국교통안전공단')")
    check("법규" in page.inner_text("#help-exam") or "교통 및 화물자동차" in page.inner_text("#help-exam"), "화물 탭: 과목표")
    page.screenshot(path=f"{SHOT}/media_04_help.png", full_page=True)
    ctx.close()

    print("[7] 오프라인: 지금 시험 그림까지 저장 (NFR-04, TC-L13)")
    tmp = tempfile.mkdtemp(prefix="cdme_site_")
    for name in ["index.html", "manifest.webmanifest", "sw.js"]:
        shutil.copy(os.path.join(ROOT, name), tmp)
    for d in ["src", "images", "data"]:
        shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d), ignore=shutil.ignore_patterns("raw"))
    for f in os.listdir(FIX):
        if f.endswith(".json"):
            shutil.copy(os.path.join(FIX, f), os.path.join(tmp, "data", "license", "questions", f))
    shutil.copytree(os.path.join(FIX, "images"), os.path.join(tmp, "data", "license", "images"), dirs_exist_ok=True)
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8010"], cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            if port_open(8010):
                break
            time.sleep(0.2)
        B2 = "http://localhost:8010/"
        c2 = browser.new_context(viewport={"width": 390, "height": 800})
        p2 = c2.new_page()
        p2.on("pageerror", lambda e: js_errors.append(str(e)))
        new_license_user(p2, B2, "오프라인")
        p2.evaluate("navigator.serviceWorker.ready.then(() => true)")
        p2.reload()
        p2.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
        p2.wait_for_selector("text=40문항 · 40분")
        # (wait_for_function은 Promise를 참으로 보므로 직접 기다림)
        COUNT = "caches.keys().then(ks => Promise.all(ks.map(k => caches.open(k).then(c => c.keys())))).then(a => a.flat().filter(r => r.url.includes('/data/license/images/')).length)"
        n = 0
        for _ in range(60):
            n = p2.evaluate(COUNT)
            if n >= 25:
                break
            p2.wait_for_timeout(250)
        check(n >= 25, f"대형 그림 미리 저장 ({n}개)")
        c2.set_offline(True)
        p2.reload()
        p2.wait_for_selector("text=40문항 · 40분", timeout=15000)
        p2.click("#start-exam")
        p2.click(".modal [data-act=ok]")
        p2.wait_for_selector(".q-card .choice")
        ip2 = p2.evaluate(IP)
        s2 = next(i for i, it in enumerate(ip2["items"]) if it["subject"] == "SIGN")
        goto_index(p2, s2)
        p2.wait_for_selector(".q-card .q-img")
        ok = p2.wait_for_function("() => { const i = document.querySelector('.q-card .q-img'); return i && i.complete && i.naturalWidth > 0; }", timeout=8000)
        check(bool(ok), "비행기 모드에서 표지 그림 표시")
        c2.set_offline(False)
        c2.close()
    finally:
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)

    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
