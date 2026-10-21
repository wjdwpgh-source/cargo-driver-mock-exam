"""북마크·집중 학습·취약 과목 분석 브라우저 테스트 (PRD 12.1, v1.1.0)
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_study.py
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
AXE = os.environ.get("AXE_JS", "/tmp/claude-0/axe/node_modules/axe-core/axe.min.js")
os.makedirs(SHOT, exist_ok=True)
errors = []
QS = {}
for code in ("LAW", "CARGO", "SAFE", "SERVICE"):
    for q in json.load(open(os.path.join(ROOT, "data", "questions", code + ".json"), encoding="utf-8"))["questions"]:
        QS[q["id"]] = q
VER = {c: [q for q in QS.values() if q["subject"] == c and q["status"] == "verified"] for c in ("LAW", "CARGO", "SAFE", "SERVICE")}

PD = "() => CDME.app.store.getProfileData()"


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def no_hscroll(page, w):
    return page.evaluate("document.documentElement.scrollWidth") <= w


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    page = ctx.new_page()
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.fill("#nick", "학습왕")
    page.press("#nick", "Enter")
    page.wait_for_selector("#start-exam")

    print("[1] 대시보드: 집중 학습 카드 (기록 없을 때)")
    card = page.inner_text("#study-h >> xpath=..")
    check("실전 모의시험을 보면" in card, "기록이 없으면 취약 과목 안내 문구")
    check(page.locator("a[href='#/study']").count() >= 1 and "북마크 0" in card.replace("\n", " "), "학습 버튼·북마크 0")
    page.screenshot(path=f"{SHOT}/study_01_home.png", full_page=True)

    print("[2] 실전 시험에서 북마크 → 결과·오답노트에서도 표시")
    page.click("#start-exam")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .bm-btn")
    qid0 = page.evaluate("() => { const ip = CDME.app.store.getProfileData().inProgress; return ip.items[0].qid; }")
    page.click(".q-card .bm-btn")
    check(page.get_attribute(".q-card .bm-btn", "aria-pressed") == "true", "북마크 버튼 눌림 표시(aria-pressed)")
    check(page.evaluate("(id) => !!CDME.app.store.getProfileData().bookmarks[id]", qid0), "북마크 저장")
    # 답하고 다음 문항 갔다 와도 유지
    q0 = QS[qid0]
    wrong = 1 if q0["answer"] != 1 else 2
    page.click(f"[data-choice='{wrong}']")
    page.wait_for_selector(".feedback")
    page.click("#ex-next")
    page.click("#ex-prev")
    check(page.get_attribute(".q-card .bm-btn", "aria-pressed") == "true", "다시 와도 북마크 표시 유지")
    page.screenshot(path=f"{SHOT}/study_02_exam_bm.png", full_page=True)
    # 나머지는 정답으로 채우고 끝내기
    page.evaluate("""() => { const s = CDME.app.store, b = CDME.app.getBank(); s.updateProfileData(s.getActiveProfile().id, d => {
        const ip = d.inProgress; ip.items.forEach((it, i) => { if (ip.answers[i] == null) ip.answers[i] = b.byId[it.qid].answer; }); }); }""")
    page.click("#ex-later")
    page.wait_for_selector("#resume-exam")
    page.click("#resume-exam")
    page.wait_for_selector("#ex-finish")
    page.click("#ex-finish")
    page.wait_for_selector(".result-hero")
    page.click("[data-filter=all]")
    first = page.locator(".rv-card").first
    check(first.locator(".bm-btn").get_attribute("aria-pressed") == "true", "결과 다시보기에 북마크 표시")
    # 결과에서 두 번째 문제 북마크
    qid1 = page.locator(".rv-card").nth(1).get_attribute("data-qid")
    page.locator(".rv-card").nth(1).locator(".bm-btn").click()
    check(page.evaluate("(id) => !!CDME.app.store.getProfileData().bookmarks[id]", qid1), "결과 화면에서도 북마크 추가")
    page.goto(BASE + "#/notes")
    page.wait_for_selector(".note-head")
    page.click(f".note-item[data-id='{qid0}'] .note-head")
    check(page.locator(f".note-item[data-id='{qid0}'] .bm-btn.on").count() == 1, "오답노트 펼치면 북마크됨 표시")

    print("[3] 북마크 목록")
    page.goto(BASE + "#/bookmarks")
    page.wait_for_selector("#bm-list")
    check(page.locator("#bm-list .note-item").count() == 2, "북마크 2문제")
    page.click(f".note-item[data-id='{qid1}'] .note-head")
    check("정답" in page.inner_text(f".note-item[data-id='{qid1}'] .note-body"), "펼치면 정답·해설")
    page.screenshot(path=f"{SHOT}/study_03_bookmarks.png", full_page=True)
    page.click(f".note-item[data-id='{qid1}'] .bm-btn")
    page.wait_for_function("document.querySelectorAll('#bm-list .note-item').length === 1")
    check(True, "목록에서 해제하면 바로 빠짐")
    check(not page.evaluate("(id) => !!CDME.app.store.getProfileData().bookmarks[id]", qid1), "해제 저장")

    print("[4] 집중 학습 설정: 과목 여러 개·난이도·범위, 문제 수 표시")
    page.click("text=북마크 문제 풀기")
    page.wait_for_selector("#st-avail")
    check(page.is_checked("input[name=src][value=bookmark]"), "북마크 문제 풀기 → 범위 '북마크'로 선택됨")
    check("1</b>개" in page.inner_html("#st-avail"), "북마크 1문제")
    page.check("input[name=src][value=all]")
    total_ver = sum(len(v) for v in VER.values())
    check(f"{total_ver}</b>개" in page.inner_html("#st-avail"), f"전체 {total_ver}문제")
    page.click("[data-subj=LAW]")
    page.click("[data-subj=CARGO]")
    n_lc = len(VER["LAW"]) + len(VER["CARGO"])
    check(f"{n_lc}</b>개" in page.inner_html("#st-avail"), f"법규+화물 {n_lc}문제")
    check(page.get_attribute("[data-subj=LAW]", "aria-pressed") == "true", "과목 칩 눌림 표시")
    page.check("input[name=diff][value='3']", force=True)
    n_hard = len([q for q in VER["LAW"] + VER["CARGO"] if q["difficulty"] == 3])
    check(f"{n_hard}</b>개" in page.inner_html("#st-avail"), f"어려움만 {n_hard}문제")
    page.check("input[name=count][value='10']", force=True)
    check(no_hscroll(page, 360), "360px 가로 스크롤 없음")
    page.screenshot(path=f"{SHOT}/study_04_setup.png", full_page=True)
    page.click("#st-start")
    page.wait_for_selector("#rp-card .choice")

    print("[5] 학습 풀이: 즉시 해설, 오답노트 담기, 북마크, 결과")
    st = page.evaluate(PD + ".studyInProgress")
    check(len(st["items"]) == min(10, n_hard), "문항 수 %d" % len(st["items"]))
    check(all(QS[it["qid"]]["subject"] in ("LAW", "CARGO") and QS[it["qid"]]["difficulty"] == 3 for it in st["items"]), "조건에 맞는 문제만 출제")
    check("어려움" in page.inner_text("#rp-card .q-num"), "난이도 표시")
    check(page.inner_text(".exam-bar .tag") == "학습", "상단에 '학습' 표시")
    first_q = QS[st["items"][0]["qid"]]
    bad = 1 if first_q["answer"] != 1 else 2
    page.click(f"#rp-card [data-pos='{bad - 1}']")
    page.wait_for_selector("#rp-fb")
    check("오답노트에 담았습니다" in page.inner_text("#rp-fb"), "틀리면 오답노트에 담았다는 안내")
    check(page.evaluate("(id) => CDME.app.store.getProfileData().wrongNotes[id].added_by", first_q["id"]) in ("study", "auto"), "오답노트에 저장")
    page.click("#rp-card .bm-btn")
    check(page.evaluate("(id) => !!CDME.app.store.getProfileData().bookmarks[id]", first_q["id"]), "풀이 중 북마크")
    page.screenshot(path=f"{SHOT}/study_05_play.png", full_page=True)
    page.click("#rp-next")
    sq = QS[page.evaluate(PD + ".studyInProgress.items[1].qid")]
    page.keyboard.press(str(sq["answer"]))
    page.wait_for_selector("#rp-fb.feedback")
    check("정답입니다" in page.inner_text("#rp-fb"), "숫자 키로 답하기")
    # 새로고침해도 이어 풀기
    page.reload()
    page.wait_for_selector("#rp-card")
    check(page.evaluate(PD + ".studyInProgress.current") == 1, "새로고침 후 이어서")
    page.click("#rp-quit")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector("text=학습 결과")
    hero = page.inner_text(".result-hero")
    check("1" in hero and "2" in hero and "어려움" in hero, "학습 결과: 1/2, 조건 표시")
    rec = page.evaluate("() => { const s = CDME.app.store.getProfileData().studySessions; return s[s.length-1]; }")
    check(rec["answered"] == 2 and rec["correct"] == 1 and rec["quit"], "학습 기록 저장 (실전과 분리)")
    check(len(page.evaluate(PD + ".exams")) == 1, "실전 기록 수는 그대로 1회")
    page.screenshot(path=f"{SHOT}/study_06_result.png", full_page=True)

    print("[6] 취약 과목 분석 (최근 5회)")
    page.evaluate("""() => { const s = CDME.app.store; s.updateProfileData(s.getActiveProfile().id, d => {
        const mk = (law, cargo, safe, svc, i) => ({ id: 'w' + i, score: 70, passed: true, total: 80, correct: 56, finishedAt: '2026-10-2' + i + 'T00:00:00Z', durationSec: 600, answers: [],
          bySubject: { LAW: { correct: law, total: 25 }, CARGO: { correct: cargo, total: 15 }, SAFE: { correct: safe, total: 25 }, SERVICE: { correct: svc, total: 15 } } });
        for (let i = 0; i < 5; i++) d.exams.push(mk(12, 12, 20, 13, i)); }); }""")
    page.goto(BASE + "#/home")
    page.reload()
    page.wait_for_selector("#study-h")
    card = page.inner_text("#study-h >> xpath=..")
    check("법규" in card and "48%" in card, "대시보드에 합격선 아래 과목(법규 48%)")
    page.screenshot(path=f"{SHOT}/study_07_home_weak.png", full_page=True)
    page.click("text=취약 과목 분석")
    page.wait_for_selector("#weak")
    w = page.inner_text("#weak")
    check("최근 5회" in w and "합격선 미달" in w and "3문항 더" in w, "내 기록: 최근 5회 분석·부족 문항 수")
    check(page.locator(".weak-row.is-weak").count() == 1, "미달 과목 1개 강조")
    page.screenshot(path=f"{SHOT}/study_08_weak.png", full_page=True)
    page.click(".weak-row.is-weak .btn")
    page.wait_for_selector("#st-avail")
    check(page.get_attribute("[data-subj=LAW]", "aria-pressed") == "true" and page.get_attribute("[data-subj=CARGO]", "aria-pressed") == "false", "집중 학습 → 법규만 선택된 설정")
    check("법규 48%" in page.inner_text("#st-form"), "설정 화면에 추천 과목")

    print("[7] 백업에 북마크·학습 기록 포함, 큰 글씨·다크 모드")
    bk = page.evaluate("() => CDME.backup.buildBackup([{ name: 'x', data: CDME.app.store.getProfileData() }])")
    check(len(bk["profiles"][0]["data"]["bookmarks"]) == 2 and len(bk["profiles"][0]["data"]["studySessions"]) == 1, "백업 파일에 북마크 2·학습 1")
    page.emulate_media(color_scheme="dark")
    page.evaluate("localStorage.setItem('cdme_font','xl')")
    for r in ("study", "bookmarks", "records"):
        page.goto(BASE + "#/" + r)
        page.reload()
        page.wait_for_selector(".page-title")
        check(no_hscroll(page, 360), f"360px·아주 큰 글씨·다크: #{r} 가로 스크롤 없음")
    page.screenshot(path=f"{SHOT}/study_09_dark_xl.png", full_page=True)

    if os.path.exists(AXE):
        print("[8] 접근성 자동 검사 (axe, 라이트·다크)")
        page.evaluate("localStorage.removeItem('cdme_font')")
        bad = []
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            for r in ("home", "study", "bookmarks", "records", "study-result"):
                page.goto(BASE + "#/" + r)
                page.reload()
                page.wait_for_selector(".page-title")
                page.add_script_tag(path=AXE)
                res = page.evaluate("""async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] } }))
                    .violations.filter(v => v.impact === 'serious' || v.impact === 'critical').map(v => v.id + ' ' + v.nodes.slice(0,2).map(n => n.target.join(' ')).join(','))""")
                bad += [scheme + " " + r + ": " + x for x in res]
        for b in bad:
            print("     -", b)
        check(not bad, "심각 접근성 위반 0건")

    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
