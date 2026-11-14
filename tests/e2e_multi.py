"""v2.0 L2 브라우저 테스트 – 대형면허 정답 2개·보기 5개 채점
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_multi.py
대형 문제는 아직 없으므로 테스트 전용 가짜 문제(tests/fixtures/license, DL-9001~)를 가로채 넣어 확인한다.
확인: 40문항·40분 출제, 2답 '선택됨'(취소·새로고침 유지)·두 번째 선택에서 채점, 정답 2개 표시, 5지·숫자키 5,
      힌트(지운 보기는 정답 아님), 28문항 70점 합격·유형별 결과, 다시보기, 복습(5지·2답), 360px
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
HERE = os.path.dirname(os.path.abspath(__file__))
SHOT = os.path.join(HERE, "screenshots")
FIX = os.path.join(HERE, "fixtures", "license")
os.makedirs(SHOT, exist_ok=True)
errors = []
CIRCLED = "①②③④⑤"


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def serve_fixture(route):
    name = route.request.url.split("/")[-1].split("?")[0]
    path = os.path.join(FIX, name)
    if os.path.exists(path):
        route.fulfill(status=200, content_type="application/json", body=open(path, encoding="utf-8").read())
    else:
        route.continue_()


def serve_image(route):
    name = route.request.url.split("/")[-1].split("?")[0]
    path = os.path.join(FIX, "images", name)
    if os.path.exists(path):
        route.fulfill(status=200, content_type="image/svg+xml", body=open(path, encoding="utf-8").read())
    else:
        route.continue_()


IP = "CDME.app.store.getProfileData().inProgress"
CUR_Q = "(() => { const ip = " + IP + "; return CDME.app.getBank().byId[ip.items[ip.current].qid]; })()"


def goto_index(page, idx):
    page.evaluate("(i) => { const s = CDME.app.store; s.updateProfileData(s.getActiveProfile().id, d => { d.inProgress.current = i; }); CDME.app.render(); }", idx)
    page.wait_for_selector(f"#ex-progress >> text={idx + 1}")


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    js_errors = []
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    ctx.route("**/data/license/questions/*.json", serve_fixture)
    ctx.route("**/data/license/images/*", serve_image)
    page = ctx.new_page()
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    print("[1] 대형으로 닉네임 만들기 → 실전 시작 40문항·40분")
    page.goto(BASE)
    page.wait_for_selector("#nick")
    page.check("[name=start-exam][value=license]")
    page.wait_for_selector("text=4지·5지선다")
    page.fill("#nick", "두개왕")
    page.press("#nick", "Enter")
    page.wait_for_selector(".exam-bar")
    page.wait_for_selector("text=40문항 · 40분")
    page.click("#start-exam")
    page.wait_for_selector(".modal")
    check("정답 2개" in page.inner_text(".modal"), "시작 안내에 '정답 2개' 문항 설명")
    page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")
    ip = page.evaluate(IP)
    check(len(ip["items"]) == 40 and ip["totalMs"] == 40 * 60000, "40문항 · 40분")
    check(page.inner_text("#ex-timer").startswith("40:") or page.inner_text("#ex-timer").startswith("39:"), "타이머 40분")
    check(page.inner_text("#ex-subject") == "문장형", "첫 문항 유형 '문장형'")

    print("[2] 1답 문항: 숫자키로 바로 채점")
    q = page.evaluate(CUR_Q)
    page.keyboard.press(str(q["answer"][0]))
    page.wait_for_selector("#ex-feedback")
    check("정답입니다" in page.inner_text("#ex-feedback"), "1답 정답 처리")

    print("[3] 2답 문항: 첫 선택은 '선택됨', 다시 누르면 취소, 새로고침 유지, 두 번째에 채점")
    t2 = [i for i, it in enumerate(ip["items"]) if it["subject"] == "TEXT2"]
    goto_index(page, t2[0])
    q = page.evaluate(CUR_Q)
    a, b = q["answer"]
    check("정답 2개 선택" in page.inner_text(".q-card") and "0 / 2 선택" in page.inner_text("#multi-count"), "'정답 2개 선택' 안내·0/2")
    page.click(f"[data-choice='{a}']")
    page.wait_for_selector(".choice.picked")
    check(page.locator("#ex-feedback").count() == 0, "하나만 고르면 채점하지 않음")
    check("1 / 2 선택" in page.inner_text("#multi-count"), "1/2 선택 표시")
    check(page.get_attribute(f"[data-choice='{a}']", "aria-pressed") == "true", "선택됨 aria-pressed")
    page.click(f"[data-choice='{a}']")
    page.wait_for_function("!document.querySelector('.choice.picked')")
    check("0 / 2 선택" in page.inner_text("#multi-count"), "다시 누르면 취소")
    page.click(f"[data-choice='{b}']")
    page.wait_for_selector(".choice.picked")
    page.screenshot(path=f"{SHOT}/multi_01_picked.png", full_page=True)
    page.reload()
    page.wait_for_selector(".q-card .choice")
    check(page.locator(".choice.picked").count() == 1 and page.locator(f"[data-choice='{b}'].picked").count() == 1, "새로고침 후에도 선택됨 유지")
    check(page.evaluate(IP)["answers"][t2[0]] is None, "새로고침 후에도 채점 전")
    page.click(f"[data-choice='{a}']")
    page.wait_for_selector("#ex-feedback")
    fb = page.inner_text("#ex-feedback")
    check("정답입니다" in fb, "정답 2개 모두 → 정답")
    check(page.locator(".choice.correct").count() == 2, "정답 2개 모두 ✓ 표시")
    check(page.locator(".choices.locked").count() == 1 and page.is_disabled(f"[data-choice='{a}']"), "답 고정")
    check(page.evaluate(IP)["answers"][t2[0]] == sorted([a, b]), "답안 배열 저장")

    goto_index(page, t2[1])
    q = page.evaluate(CUR_Q)
    wrong = [n for n in range(1, 5) if n not in q["answer"]][0]
    page.keyboard.press(str(q["answer"][0]))
    page.wait_for_selector(".choice.picked")
    page.keyboard.press(str(wrong))
    page.wait_for_selector("#ex-feedback")
    fb = page.inner_text("#ex-feedback")
    lab = ", ".join(CIRCLED[n - 1] for n in q["answer"])
    check("오답입니다" in fb and f"정답은 {lab}번" in fb, f"정답 1개 + 오답 1개 → 오답, '정답은 {lab}번'")
    check(page.locator(".choice.wrong").count() == 1 and page.locator(".choice.correct").count() == 2, "내 오답 ✗ 1, 정답 ✓ 2")

    print("[4] 5지 2답 일러스트: 보기 ⑤, 숫자키 5, 힌트")
    i2 = [i for i, it in enumerate(ip["items"]) if it["subject"] == "ILLUST2"]
    target = None
    for idx in i2:
        qq = page.evaluate("(i) => CDME.app.getBank().byId[" + IP + ".items[i].qid]", idx)
        if not qq["hint"] and 5 in qq["answer"]:
            target = idx
            break
    if target is None:
        target = i2[0]
    goto_index(page, target)
    q = page.evaluate(CUR_Q)
    check(page.locator(".q-card .choice").count() == 5 and "⑤" in page.inner_text(".q-card .choices"), "보기 5개(⑤)")
    if not q["hint"]:
        page.click("#ex-hint")
        page.wait_for_selector("#ex-hintbox")
        el = page.locator(".choice.eliminated")
        check(el.count() == 1, "힌트: 보기 하나 지움")
        removed = int(el.get_attribute("data-choice"))
        check(removed not in q["answer"], "지운 보기는 정답이 아님")
        page.keyboard.press(str(removed))
        check(page.locator(".choice.picked").count() == 0, "지운 보기는 선택 불가")
    page.keyboard.press("5")
    if 5 in q["answer"]:
        page.wait_for_selector(".choice.picked")
        check(page.locator("[data-choice='5'].picked").count() == 1, "숫자키 5로 ⑤ 선택")
    other = [n for n in q["answer"] if n != 5][0] if 5 in q["answer"] else q["answer"][0]
    if 5 not in q["answer"]:
        page.keyboard.press("5")   # 취소
    page.keyboard.press(str(other))
    if 5 not in q["answer"]:
        page.keyboard.press(str(q["answer"][1]))
    page.wait_for_selector("#ex-feedback")
    check("정답입니다" in page.inner_text("#ex-feedback"), "5지 2답 정답")
    page.screenshot(path=f"{SHOT}/multi_02_illust_answered.png", full_page=True)
    check(page.evaluate("document.documentElement.scrollWidth") <= 360, "시험 화면 360px 가로 스크롤 없음")

    print("[5] 28문항 정답 → 70점 합격, 유형별 결과")
    # 지금까지 정답 3(1답 1, 2답 1, 일러스트 1), 오답 1. 남은 문항을 정답 25 + 오답으로 채움
    page.evaluate("""() => { const s = CDME.app.store, bank = CDME.app.getBank(), E = CDME.exam;
      s.updateProfileData(s.getActiveProfile().id, d => { const ip = d.inProgress; let need = 25;
        ip.items.forEach((it, i) => { if (ip.answers[i] != null) return; const q = bank.byId[it.qid];
          const right = q.answer.length > 1 ? q.answer.slice() : q.answer[0];
          if (need > 0) { ip.answers[i] = right; need--; }
          else { const w = [1,2,3,4].find(n => q.answer.indexOf(n) < 0); ip.answers[i] = q.answer.length > 1 ? [q.answer[0], w].sort() : w; } });
        ip.current = 0; }); CDME.app.render(); }""")
    page.wait_for_selector("#ex-finish")
    page.click("#ex-finish")
    page.wait_for_selector(".result-hero")
    hero = page.inner_text(".result-hero")
    check("70" in hero and "합격" in hero and "불합격" not in hero, "28문항 정답 → 70점 합격")
    check("정답 28 / 40" in hero and "합격 기준 70점" in hero, "정답 28/40 · 합격 기준 70점")
    check("전 문항 2.5점" in hero, "학습용 배점 안내")
    check("유형별 점수" in page.inner_text("main") and "문장형(2답)" in page.inner_text("main"), "유형별 점수 표")
    page.click("[data-filter=all]")
    card = page.locator(".rv-card").nth(t2[0])
    check(card.locator(".choice.correct").count() == 2 and "정답 2개 선택" in card.inner_text(), "다시보기: 2답 정답 2개 표시")
    wcard = page.locator(".rv-card").nth(t2[1])
    check("✗ 내 답" in wcard.inner_text() and "✓ 정답 · 내 답" in wcard.inner_text(), "다시보기: 내 답(정답·오답) 표시")
    page.screenshot(path=f"{SHOT}/multi_03_result.png", full_page=True)
    notes = page.evaluate("CDME.app.store.getProfileData().wrongNotes")
    arr_notes = [n for n in notes.values() if isinstance(n.get("last_choice"), list)]
    check(len(notes) == 12 and arr_notes, f"오답노트 12문제 등록, 2답 최근 내 답은 배열 ({len(notes)})")

    print("[6] 복습: 2답 문항 위치 섞여도 원래 번호로 채점")
    page.goto(BASE + "#/review")
    page.wait_for_selector("#rv-form")
    page.click("text=복습 시작")
    page.wait_for_selector("#rp-card .choice")
    rv = page.evaluate("CDME.app.store.getProfileData().reviewInProgress")
    idx = next((i for i, it in enumerate(rv["items"]) if it["subject"] in ("TEXT2", "ILLUST2")), None)
    check(idx is not None, "복습에 2답 문항 포함")
    if idx is not None:
        page.evaluate("(i) => { const s = CDME.app.store; s.updateProfileData(s.getActiveProfile().id, d => { d.reviewInProgress.current = i; }); CDME.app.render(); }", idx)
        page.wait_for_selector(f"#rp-card .choice >> nth=0")
        it = rv["items"][idx]
        qq = page.evaluate("(id) => CDME.app.getBank().byId[id]", it["qid"])
        check(page.locator("#rp-card .choice").count() == len(qq["choices"]), "복습 보기 수 = 문제 보기 수")
        if it["subject"] == "ILLUST2":
            check(it["perm"] == list(range(1, 6)), "일러스트는 보기 순서 그대로")
        pos = [it["perm"].index(n) for n in qq["answer"]]
        page.click(f"#rp-card [data-pos='{pos[0]}']")
        page.wait_for_selector("#rp-card .choice.picked")
        check(page.locator("#rp-fb").count() == 0, "복습: 하나만 고르면 채점 전")
        page.click(f"#rp-card [data-pos='{pos[1]}']")
        page.wait_for_selector("#rp-fb")
        check("정답입니다" in page.inner_text("#rp-fb"), "복습 2답 정답")
        n = page.evaluate("(id) => CDME.app.store.getProfileData().wrongNotes[id]", it["qid"])
        check(n["streak"] == 1, "연속 정답 1")
        page.screenshot(path=f"{SHOT}/multi_04_review.png", full_page=True)

    print("[7] 집중 학습: 일러스트(2답)만")
    page.click("#rp-later")
    page.goto(BASE + "#/study")
    page.wait_for_selector("#st-avail")
    page.click("[data-subj=ILLUST2]")
    page.wait_for_function("document.querySelector('[data-subj=ILLUST2]').getAttribute('aria-pressed') === 'true'")
    check("16</b>개" in page.inner_html("#st-avail"), "일러스트(2답) 16문제")
    page.click("#st-start")
    page.wait_for_selector("#rp-card .choice")
    check(page.locator("#rp-card .choice").count() == 5, "학습 화면 보기 5개")
    st = page.evaluate("CDME.app.store.getProfileData().studyInProgress")
    qq = page.evaluate("(id) => CDME.app.getBank().byId[id]", st["items"][0]["qid"])
    page.keyboard.press(str(st["items"][0]["perm"].index(qq["answer"][0]) + 1))
    page.keyboard.press(str(st["items"][0]["perm"].index(qq["answer"][1]) + 1))
    page.wait_for_selector("#rp-fb")
    check("정답입니다" in page.inner_text("#rp-fb"), "학습 2답 숫자키 정답")
    check(page.evaluate("document.documentElement.scrollWidth") <= 360, "학습 화면 360px 가로 스크롤 없음")

    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
