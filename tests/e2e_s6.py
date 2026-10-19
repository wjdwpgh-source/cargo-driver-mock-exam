"""S6 브라우저 테스트 – 기록 개별 삭제·백업·불러오기·초기화
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_s6.py
"""
import json
import os
import sys
import tempfile
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8000/")
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
TMP = tempfile.mkdtemp()
os.makedirs(SHOT, exist_ok=True)
errors = []

MAKE = """(scores) => {
  const bank = CDME.app.getBank(); const s = CDME.app.store; const id = s.getActiveProfile().id;
  s.updateProfileData(id, d => {
    scores.forEach((n, k) => {
      const ip = CDME.exam.buildExam(bank, { sample: true });
      ip.items.forEach((it, i) => { const a = bank.byId[it.qid].answer; CDME.exam.setAnswer(ip, i, i < n ? a : a % 4 + 1); });
      const rec = CDME.exam.score(ip, bank, { now: new Date(Date.UTC(2026, 9, 1 + k + (window.__off || 0), 3)).toISOString() });
      rec.noteReg = CDME.notes.registerWrong(d.wrongNotes, rec, bank, rec.finishedAt);
      d.exams.push(rec);
    });
  });
}"""
DATA = "() => { const d = CDME.app.store.getProfileData(); return { exams: d.exams.length, notes: Object.keys(d.wrongNotes).length, reviews: (d.reviewSessions||[]).length }; }"


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def new_device(browser, nick, w=360):
    c = browser.new_context(viewport={"width": w, "height": 800}, locale="ko-KR", accept_downloads=True)
    c.add_init_script("localStorage.setItem('cdme_sample','1')")
    pg = c.new_page()
    pg.on("pageerror", lambda e: js_errors.append(str(e)))
    pg.goto(BASE)
    pg.fill("#nick", nick)
    pg.press("#nick", "Enter")
    pg.wait_for_selector("text=80문항 · 80분 · 과목별 랜덤 출제")
    return c, pg


def export_me(page, name):
    with page.expect_download() as dl:
        page.click("#exp-me")
    path = os.path.join(TMP, name)
    dl.value.save_as(path)
    return path, dl.value.suggested_filename


js_errors = []
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()

    print("[1] 기기 A: 시험 3회 → 개별 기록 삭제 (FR-801)")
    ca, pa = new_device(browser, "화물왕")
    pa.evaluate(MAKE, [50, 60, 70])
    pa.goto(BASE + "#/records")
    pa.wait_for_selector(".hist-del")
    check(pa.locator(".hist-row").count() == 3, "이력 3건")
    pa.locator(".hist-del").first.click()
    check("오답노트에 등록된 문제는 그대로" in pa.inner_text(".modal"), "삭제 확인 창 안내")
    pa.click(".modal [data-act=cancel]")
    check(pa.locator(".hist-row").count() == 3, "취소 → 유지")
    notes_before = pa.evaluate(DATA)["notes"]
    pa.locator(".hist-del").first.click()
    pa.click(".modal [data-act=ok]")
    pa.wait_for_function("document.querySelectorAll('.hist-row').length === 2")
    d = pa.evaluate(DATA)
    check(d["exams"] == 2 and d["notes"] == notes_before, "최신 기록 1건 삭제, 오답노트 유지")
    st = pa.inner_text(".stats-4")
    check("2회" in st and "68.8점" in st and "75점" in st, f"통계 다시 계산 (정답 50·60 → 평균 68.8, 최고 75) {st.split()}")

    print("[2] 백업 내보내기 (FR-901)")
    pa.click("text=기록 관리 (백업 · 불러오기 · 초기화)")
    pa.wait_for_selector("#exp-me")
    pa.screenshot(path=f"{SHOT}/s6_01_data.png", full_page=True)
    path_a, fname = export_me(pa, "a.json")
    check(fname.startswith("화물모의시험_백업_화물왕_") and fname.endswith(".json"), f"파일 이름 ({fname})")
    j = json.load(open(path_a, encoding="utf-8"))
    check(j["app"] == "cdme" and len(j["profiles"]) == 1 and len(j["profiles"][0]["data"]["exams"]) == 2, "백업 내용: 닉네임 1, 시험 2")
    check(pa.locator("#exp-all").count() == 0, "닉네임 1개면 전체 백업 버튼 없음")

    print("[3] 기기 B: 같은 닉네임(시험 1회)에 불러오기 → 합치기 (FR-902, 903)")
    cb, pb = new_device(browser, "화물왕", 1100)
    pb.evaluate("window.__off = 10")
    pb.evaluate(MAKE, [80])
    pb.goto(BASE + "#/data")
    pb.wait_for_selector("#imp-file")
    pb.set_input_files("#imp-file", path_a)
    pb.wait_for_selector(".imp-box")
    check("같은 닉네임 있음" in pb.inner_text(".imp-box") and "실전 2회" in pb.inner_text(".imp-box"), "미리보기: 같은 닉네임·기록 수")
    check(pb.locator("[data-step='0']").input_value() == "merge", "기본값 합치기")
    pb.screenshot(path=f"{SHOT}/s6_02_import_pc.png", full_page=True)
    pb.click("#imp-apply")
    pb.wait_for_selector(".toast")
    check(pb.evaluate(DATA)["exams"] == 3, "합치기 → 시험 3회")

    print("[4] 같은 파일 다시 합치기 → 중복 없음")
    pb.set_input_files("#imp-file", path_a)
    pb.wait_for_selector(".imp-box")
    pb.click("#imp-apply")
    pb.wait_for_selector(".toast")
    check(pb.evaluate(DATA)["exams"] == 3, "중복 기록 생기지 않음")

    print("[5] 이름 바꿔 가져오기 → 새 닉네임")
    pb.set_input_files("#imp-file", path_a)
    pb.wait_for_selector(".imp-box")
    pb.select_option("[data-step='0']", "rename")
    pb.click("#imp-apply")
    pb.wait_for_selector(".toast")
    names = pb.evaluate("() => CDME.app.store.listProfiles().map(p => p.name)")
    check(names == ["화물왕", "화물왕 (2)"], f"닉네임 목록 {names}")

    print("[6] 덮어쓰기 (확인 창)")
    pb.set_input_files("#imp-file", path_a)
    pb.wait_for_selector(".imp-box")
    pb.select_option("[data-step='0']", "overwrite")
    pb.click("#imp-apply")
    pb.wait_for_selector("text=기존 기록 덮어쓰기")
    pb.click(".modal [data-act=ok]")
    pb.wait_for_selector(".toast")
    check(pb.evaluate(DATA)["exams"] == 2, "덮어쓰기 → 백업의 2회만")

    print("[7] 잘못된 파일")
    bad = os.path.join(TMP, "bad.json")
    open(bad, "w", encoding="utf-8").write('{"hello": 1}')
    pb.set_input_files("#imp-file", bad)
    pb.wait_for_function("document.getElementById('imp-err').textContent.length > 0")
    check("이 프로그램의 백업 파일이 아닙니다" in pb.inner_text("#imp-err"), "다른 형식 파일 거부")
    check(pb.evaluate(DATA)["exams"] == 2, "기존 기록 변화 없음")

    print("[8] 전체 백업 (닉네임 2개)")
    pb.goto(BASE + "#/data")
    pb.wait_for_selector("#exp-all")
    with pb.expect_download() as dl:
        pb.click("#exp-all")
    pall = os.path.join(TMP, "all.json")
    dl.value.save_as(pall)
    check(len(json.load(open(pall, encoding="utf-8"))["profiles"]) == 2, "전체 백업에 닉네임 2개")

    print("[9] 기기 A로 전체 백업 불러오기 → 새 닉네임 추가 + 합치기")
    pa.set_input_files("#imp-file", pall)
    pa.wait_for_selector(".imp-box")
    vals = [pa.locator(f"[data-step='{i}']").input_value() for i in range(2)]
    check(vals == ["merge", "new"], f"처리 기본값 {vals}")
    pa.click("#imp-apply")
    pa.wait_for_selector(".toast")
    check(len(pa.evaluate("() => CDME.app.store.listProfiles()")) == 2, "기기 A 닉네임 2개")

    print("[10] 초기화: 오답노트만 (FR-802)")
    pa.goto(BASE + "#/data")
    pa.wait_for_selector("[name=rs]")
    pa.check("[name=rs][value=notes]")
    pa.click("#rs-only")
    check("백업 없이" in pa.inner_text(".modal"), "백업 없이 경고")
    pa.click(".modal [data-act=ok]")
    pa.wait_for_selector(".toast")
    d = pa.evaluate(DATA)
    check(d["notes"] == 0 and d["exams"] == 2, f"오답노트만 비움 ({d})")

    print("[11] 백업 후 초기화: 실전 기록 (FR-803)")
    pa.check("[name=rs][value=exams]")
    with pa.expect_download() as dl:
        pa.click("#rs-backup")
        pa.click(".modal [data-act=ok]")
    check("초기화전" in dl.value.suggested_filename, f"초기화 전 백업 파일 ({dl.value.suggested_filename})")
    pa.wait_for_selector(".toast")
    check(pa.evaluate(DATA)["exams"] == 0, "실전 기록 0")

    print("[12] 전체 초기화: 닉네임 다시 입력")
    pa.evaluate(MAKE, [55])
    pa.goto(BASE + "#/data")
    pa.wait_for_selector("[name=rs]")
    pa.check("[name=rs][value=all]")
    pa.click("#rs-only")
    pa.fill("#modal-input", "틀린이름")
    pa.click(".modal [data-act=ok]")
    check("일치하지 않습니다" in pa.inner_text("#modal-error"), "닉네임 불일치 → 막음")
    pa.fill("#modal-input", "화물왕")
    pa.click(".modal [data-act=ok]")
    pa.wait_for_selector(".toast")
    d = pa.evaluate(DATA)
    check(d == {"exams": 0, "notes": 0, "reviews": 0}, f"전체 0 ({d})")
    check(len(pa.evaluate("() => CDME.app.store.listProfiles()")) == 2, "닉네임은 남음")
    pa.reload()
    pa.wait_for_selector("#exp-me")
    check(pa.evaluate(DATA)["exams"] == 0, "새로고침 후에도 초기화 유지")

    w = pa.evaluate("document.documentElement.scrollWidth")
    check(w <= 360, f"360px 가로 스크롤 없음 ({w})")
    check(not js_errors, "자바스크립트 오류 없음 " + "; ".join(js_errors))
    browser.close()

print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
