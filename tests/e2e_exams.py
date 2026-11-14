"""v2.0 L1 브라우저 테스트 – 시험 종류(화물·대형면허) 선택·전환, 기록 변환
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_exams.py
확인: 사이트 이름, 시작 화면 시험 선택, 상단 시험 배지, 시험 선택 화면(#/exams), 시험별 기록 분리(TC-L02),
      v1 기록이 있는 기기에서 접속 시 자동 변환(TC-L01), 대형 문제 부족 시 시작 차단, 360px 가로 스크롤
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright
from draft_data import as_drafts

BASE = os.environ.get("BASE", "http://localhost:8000/")
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT, exist_ok=True)
errors = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def width(pg):
    return pg.evaluate("document.documentElement.scrollWidth")


V1_STATE = {
    "schemaVersion": 1, "activeProfileId": "p1",
    "profiles": [{"id": "p1", "name": "옛기록", "createdAt": "2026-10-01T00:00:00Z", "lastUsedAt": "2026-10-20T00:00:00Z"}],
    "data": {"p1": {
        "exams": [{"id": "e%d" % i, "startedAt": "2026-10-0%dT00:00:00Z" % i, "finishedAt": "2026-10-0%dT01:00:00Z" % i,
                   "durationSec": 3600, "score": s, "correct": int(s / 1.25), "passed": s >= 60, "total": 80,
                   "bySubject": {}, "answers": []} for i, s in [(1, 55), (2, 65), (3, 72.5)]],
        "wrongNotes": {"LAW-%04d" % n: {"subject": "LAW", "question_version": 1, "wrong_count": 1, "streak": 0,
                                         "state": "active", "added_by": "auto", "sample": False,
                                         "first_wrong_at": "2026-10-03T00:00:00Z", "last_wrong_at": "2026-10-03T00:00:00Z"} for n in range(1, 11)},
        "reviewSessions": [], "inProgress": None, "reviewInProgress": None}}
}

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    js_errors = []

    print("[1] 사이트 이름·시작 화면 시험 선택")
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    page = ctx.new_page()
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_selector("#nick")
    page.wait_for_selector("text=4지선다")
    check(page.title() == "면허문제의 모든것", "브라우저 제목 '면허문제의 모든것'")
    check(page.text_content(".brand-full") == "면허문제의 모든것" and page.inner_text(".brand") == "면허문제", "상단 사이트 이름(좁은 화면은 '면허문제')")
    check("면허문제의 모든것" in page.inner_text(".hero h1"), "시작 화면 제목")
    check(page.locator("[name=start-exam]").count() == 2, "시험 선택 2개(화물·대형)")
    check(page.is_checked("[name=start-exam][value=cargo]"), "기본 선택: 화물")
    check("40문항 · 40분 · 70점 이상 합격" in page.inner_text(".exam-pick"), "대형 규격 표시(40문항·40분·70점)")
    page.screenshot(path=f"{SHOT}/exams_01_start.png", full_page=True)
    check(width(page) <= 360, f"시작 화면 360px 가로 스크롤 없음 ({width(page)})")

    print("[2] 대형을 골라 닉네임 만들기 → 대형 대시보드")
    page.check("[name=start-exam][value=license]")
    page.wait_for_selector("text=대형운전면허(1종) 학과")
    page.wait_for_selector("text=4지·5지선다")
    check("문장형" in page.inner_text("main") and "안전표지형" in page.inner_text("main"), "시험 안내가 대형 유형표로 바뀜")
    page.fill("#nick", "면허왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("text=면허왕님, 반갑습니다")
    page.wait_for_selector(".exam-bar")
    check("대형운전면허(1종) 학과" in page.inner_text(".exam-bar"), "대시보드에 현재 시험 이름")
    check(page.is_visible("#exam-chip") and page.inner_text("#exam-chip") == "대형", "상단 시험 배지 '대형'")
    check(page.evaluate("localStorage.getItem('cdme_exam')") == "license", "현재 시험을 기기에 기억(cdme_exam)")
    page.wait_for_selector("text=유형별 출제 가능 문제 수", state="attached")
    check("유형" in page.inner_text("main"), "문제 준비 현황이 유형 기준")
    check(page.locator("[data-sample-on]").count() == 0, "대형은 샘플 모드 버튼 없음(FR-L16)")
    page.screenshot(path=f"{SHOT}/exams_02_home_license.png", full_page=True)
    check(width(page) <= 360, f"대시보드 360px 가로 스크롤 없음 ({width(page)})")

    print("[3] 대형 문제가 부족하면 시작 차단")
    verified = page.evaluate("() => CDME.questions.summarize(CDME.app.getBank()).examReady")
    page.click("#start-exam")
    page.wait_for_selector(".modal")
    if not verified:
        check("아직 시험을 볼 수 없습니다" in page.inner_text(".modal"), "검수 전에는 '아직 시험을 볼 수 없습니다'")
        check("유형" in page.inner_text(".modal"), "부족한 유형 안내")
    else:
        check("실전 모의시험을 시작합니다" in page.inner_text(".modal") and "40문항 · 40분" in page.inner_text(".modal"), "시작 안내 40문항·40분")
    page.keyboard.press("Escape")

    print("[4] 시험 선택 화면(#/exams) → 화물로 전환")
    page.click("#exam-chip")
    page.wait_for_selector("text=시험 선택")
    page.wait_for_selector(".exam-card >> nth=1")
    page.wait_for_function("() => !document.querySelector('main').innerText.includes('확인 중')")
    cards = page.inner_text("main")
    check(page.locator(".exam-card").count() == 2, "시험 카드 2개")
    check("사용 중" in page.inner_text(".exam-card.is-current") and "대형" in page.inner_text(".exam-card.is-current"), "대형이 사용 중")
    check("시험 가능" in page.inner_text(".exam-card:not(.is-current)"), "화물 카드: 시험 가능(검수 완료)")
    page.screenshot(path=f"{SHOT}/exams_03_select.png", full_page=True)
    check(width(page) <= 360, f"시험 선택 화면 360px 가로 스크롤 없음 ({width(page)})")
    page.click("[data-exam=cargo]")
    page.wait_for_selector("text=면허왕님, 반갑습니다")
    page.wait_for_function("() => document.getElementById('exam-chip').innerText === '화물'")
    check("화물운송종사자격" in page.inner_text(".exam-bar"), "화물로 전환")
    page.wait_for_selector("text=80문항 · 80분")
    check(page.evaluate("CDME.app.getBank().config.kind") == "cargo", "화물 문제 데이터로 다시 불러옴")

    print("[5] 시험별 기록 분리 (TC-L02)")
    page.evaluate("""() => { const s = CDME.app.store; s.updateProfileData(s.getActiveProfile().id, d => {
        d.exams.push({ id: 'c-1', startedAt: '2026-10-25T00:00:00Z', finishedAt: '2026-10-25T01:00:00Z', durationSec: 3600,
          score: 61.25, correct: 49, passed: true, total: 80, bySubject: {}, answers: [] });
        d.bookmarks['LAW-0001'] = { subject: 'LAW', added_at: '2026-10-25T00:00:00Z', sample: false }; }); CDME.app.render(); }""")
    page.wait_for_selector("text=61.25점")
    page.goto(BASE + "#/exams")
    page.wait_for_selector(".exam-card >> nth=1")
    check("응시 1회" in page.inner_text(".exam-card.is-current"), "화물 카드: 응시 1회")
    check("응시 0회" in page.inner_text(".exam-card:not(.is-current)"), "대형 카드: 응시 0회")
    page.click("[data-exam=license]")
    page.wait_for_function("() => document.getElementById('exam-chip').innerText === '대형'")
    page.wait_for_selector("text=면허왕님, 반갑습니다")
    stats = page.inner_text(".stats")
    check("0회" in stats and "61.25" not in stats, "대형 대시보드에는 화물 기록이 보이지 않음")
    bm = page.evaluate("() => Object.keys(CDME.app.store.getProfileData().bookmarks).length")
    check(bm == 0, "북마크도 시험별")
    page.reload()
    page.wait_for_selector("text=면허왕님, 반갑습니다")
    page.wait_for_function("() => document.getElementById('exam-chip').innerText === '대형'")
    check(True, "새로고침해도 대형 유지")

    print("[6] 기록 관리: 백업에 두 시험, 초기화는 현재 시험만")
    page.goto(BASE + "#/data")
    page.wait_for_selector("text=기록 관리")
    check("화물: 실전 1회" in page.inner_text("main"), "백업 요약에 화물 기록 표시")
    check("대형운전면허(1종) 학과</b> 기록만" in page.inner_html("main") or "대형운전면허(1종) 학과 기록만" in page.inner_text("main"), "초기화 안내: 현재 시험 기록만")
    bk = page.evaluate("() => CDME.backup.buildBackup([{ name: 'x', data: CDME.app.store.getProfileAll() }])")
    check(bk["schemaVersion"] == 2 and len(bk["profiles"][0]["data"]["cargo"]["exams"]) == 1 and "license" in bk["profiles"][0]["data"], "백업 v2: 두 시험 기록")

    print("[7] 닉네임 관리: 시험별 응시 수")
    page.goto(BASE + "#/profiles")
    page.wait_for_selector(".manage-item")
    check("화물 응시 1회" in page.inner_text(".manage-item"), "닉네임 목록에 '화물 응시 1회'")
    ctx.close()

    print("[8] v1 기록이 있는 기기에서 v2 접속 → 자동 변환 (TC-L01)")
    ctx2 = browser.new_context(viewport={"width": 390, "height": 800}, locale="ko-KR", service_workers="block")
    ctx2.add_init_script("if (!localStorage.getItem('cdme')) localStorage.setItem('cdme', %s);" % json.dumps(json.dumps(V1_STATE, ensure_ascii=False)))
    pg = ctx2.new_page()
    pg.on("pageerror", lambda e: js_errors.append(str(e)))
    pg.goto(BASE)
    pg.wait_for_selector("text=옛기록님, 반갑습니다")
    pg.wait_for_selector("text=72.5점")
    check("3회" in pg.inner_text(".stats"), "화물 응시 3회 그대로")
    check("10" in pg.inner_text("#go-review"), "복습할 오답 10문제 그대로")
    check(pg.inner_text("#exam-chip") == "화물", "변환 후 화물 시험으로 시작")
    saved = pg.evaluate("JSON.parse(localStorage.getItem('cdme'))")
    check(saved["schemaVersion"] == 2 and len(saved["data"]["p1"]["cargo"]["exams"]) == 3 and saved["data"]["p1"]["license"]["exams"] == [], "저장 구조 v2(화물 3회, 대형 빈 기록)")
    orig = pg.evaluate("localStorage.getItem('cdme_backup_v1')")
    check(orig is not None and json.loads(orig)["schemaVersion"] == 1, "변환 전 원본 보관(cdme_backup_v1)")
    pg.goto(BASE + "#/records")
    pg.wait_for_selector("text=내 기록")
    check("72.5" in pg.inner_text("main"), "내 기록 화면에 기존 점수")
    pg.screenshot(path=f"{SHOT}/exams_04_migrated.png", full_page=True)
    ctx2.close()

    print("[9] 다크 모드·PC 화면")
    ctx3 = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark", service_workers="block")
    as_drafts(ctx3)
    pg3 = ctx3.new_page()
    pg3.on("pageerror", lambda e: js_errors.append(str(e)))
    pg3.goto(BASE)
    pg3.wait_for_selector("#nick")
    pg3.fill("#nick", "다크")
    pg3.press("#nick", "Enter")
    pg3.wait_for_selector(".exam-bar")
    pg3.goto(BASE + "#/exams")
    pg3.wait_for_selector(".exam-card >> nth=1")
    pg3.screenshot(path=f"{SHOT}/exams_05_select_dark_pc.png", full_page=True)
    ctx3.close()

    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
