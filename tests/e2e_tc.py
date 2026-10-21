"""6단계 테스트 – 기존 테스트에서 빠진 TC와 비기능 요구사항 점검 (PRD v1.19 10장)
사용법: 프로젝트 폴더에서  python -m http.server 8000  실행 후  python tests/e2e_tc.py
  TC-01 닉네임별 기록 분리 · TC-02 실제 문제 400문항으로 출제 100회 · TC-15 폐기 문제 숨김 · TC-16 수정된 문제 표시
  NFR-03 성능 · NFR-05 저장 공간 부족 안내 · NFR-06 외부 요청 없음 · NFR-01/02 기기별 화면 · NFR-07 자동 접근성 검사(axe)
"""
import json
import os
import re
import sys
import time
from playwright.sync_api import sync_playwright
from draft_data import as_drafts, dev_on

BASE = os.environ.get("BASE", "http://localhost:8000/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(os.path.dirname(__file__), "screenshots")
AXE = os.environ.get("AXE_JS", "/tmp/claude-0/axe/node_modules/axe-core/axe.min.js")
os.makedirs(SHOT, exist_ok=True)
errors = []
report = {}


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)
    return cond


def launch(p):
    exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


def new_page(browser, mode=None, drafts=True, dev=True, **kw):
    opts = dict(viewport={"width": 360, "height": 740}, locale="ko-KR", service_workers="block")
    opts.update(kw)
    ctx = browser.new_context(**opts)
    if drafts:
        as_drafts(ctx, dev=dev)
    elif dev:
        dev_on(ctx)
    page = ctx.new_page()
    page.js_errors = []
    page.on("pageerror", lambda e: page.js_errors.append(str(e)))
    page.goto(BASE)
    if mode:
        page.evaluate("(m) => localStorage.setItem('cdme_sample', m)", mode)
        page.reload()
    return ctx, page


def make_nick(page, name):
    page.wait_for_selector("#nick")
    page.fill("#nick", name)
    page.press("#nick", "Enter")
    page.wait_for_selector("#start-exam")


def start_exam(page):
    page.goto(BASE + "#/home")
    page.wait_for_selector("#start-exam")
    page.click("#start-exam")
    if page.locator(".modal [data-act=ok]").count():
        page.click(".modal [data-act=ok]")
    page.wait_for_selector(".q-card .choice")


def end_by_timeout(page):
    page.click("#ex-later")
    page.wait_for_selector(".resume")
    page.evaluate("""() => { const s = CDME.app.store; s.updateProfileData(s.getActiveProfile().id, d => { d.inProgress.remainingMs = 1200; }); }""")
    page.click("#resume-exam")
    page.wait_for_selector(".result-hero", timeout=8000)


def answer_current(page, correct=True):
    page.wait_for_selector(".q-card .choices:not(.locked) [data-choice]:not([disabled])")
    a = page.evaluate("""() => { const ip = CDME.app.store.getProfileData().inProgress; return CDME.app.getBank().byId[ip.items[ip.current].qid].answer; }""")
    if correct:
        n = a
    else:   # 힌트로 지워진(누를 수 없는) 보기는 피해서 오답 선택
        n = [int(x) for x in page.eval_on_selector_all(".q-card [data-choice]:not([disabled])", "els => els.map(e => e.dataset.choice)") if int(x) != a][0]
    page.click(f".q-card [data-choice='{n}']")
    page.wait_for_selector(".feedback")


with sync_playwright() as p:
    browser = launch(p)

    # ------------------------------------------------------------------
    print("[TC-01] 닉네임 2개가 각각 응시 → 기록이 섞이지 않음")
    ctx, page = new_page(browser, "1")
    make_nick(page, "가나다")
    start_exam(page)
    for i in range(3):
        if i:
            page.click("#ex-next")
        answer_current(page, True)
    end_by_timeout(page)
    a_id = page.evaluate("() => CDME.app.store.getActiveProfile().id")
    page.evaluate("() => { CDME.app.store.createProfile('라마바'); }")
    page.goto(BASE + "#/home")
    page.reload()
    page.wait_for_selector("#start-exam")
    check("라마바" in page.inner_text("body"), "두 번째 닉네임으로 전환")
    check("0회" in page.inner_text(".stats"), "두 번째 닉네임 응시 0회 (첫 닉네임 기록 안 보임)")
    start_exam(page)
    for i in range(2):
        if i:
            page.click("#ex-next")
        answer_current(page, False)
    end_by_timeout(page)
    da = page.evaluate("(id) => CDME.app.store.getProfileData(id)", a_id)
    db = page.evaluate("() => CDME.app.store.getProfileData()")
    check(len(da["exams"]) == 1 and len(db["exams"]) == 1, "각 닉네임 시험 기록 1회씩")
    check(da["exams"][0]["correct"] == 3 and db["exams"][0]["correct"] == 0, "각자의 정답 수 유지 (3 / 0)")
    check(da["exams"][0]["id"] != db["exams"][0]["id"], "서로 다른 시험 기록")
    na, nb = len(da["wrongNotes"]), len(db["wrongNotes"])
    check(na == 77 and nb == 80, f"오답노트도 각자 (77 / 80) – {na} / {nb}")
    page.evaluate("(id) => CDME.app.store.selectProfile(id)", a_id)
    page.goto(BASE + "#/records")
    page.reload()
    page.wait_for_selector(".page-title")
    check(re.search(r"응시\s*1\s*회|1회", page.inner_text("#view")) is not None, "첫 닉네임으로 돌아가면 내 기록 1회")
    check(not page.js_errors, "자바스크립트 오류 없음 " + "; ".join(page.js_errors))
    ctx.close()

    # ------------------------------------------------------------------
    print("[TC-02] 실제 문제(전체 초안, 미리보기)로 출제 100회")
    ctx, page = new_page(browser, "draft")
    make_nick(page, "출제검사")
    r = page.evaluate("""() => {
        const bank = CDME.app.getBank(), E = CDME.exam, out = { bad: 0, dup: 0, dep: 0, counts: null, n: 0 };
        let rng = 12345; const rnd = () => { rng = (rng * 1103515245 + 12345) % 2147483648; return rng / 2147483648; };
        const seen = {};
        for (let k = 0; k < 100; k++) {
          const ip = E.buildExam(bank, { rng: rnd });
          const ids = ip.items.map(i => i.qid);
          if (new Set(ids).size !== ids.length) out.dup++;
          const c = {}; ip.items.forEach(i => { c[i.subject] = (c[i.subject] || 0) + 1; });
          const order = ip.items.map(i => i.subject).join(',');
          const expect = ['LAW','CARGO','SAFE','SERVICE'].map((s, j) => Array([25,15,25,15][j]).fill(s).join(',')).join(',');
          if (order !== expect) out.bad++;
          if (ids.some(id => bank.byId[id].status === 'deprecated')) out.dep++;
          ids.forEach(id => { seen[id] = 1; });
          out.counts = c; out.n++;
        }
        out.covered = Object.keys(seen).length;
        return out; }""")
    check(r["n"] == 100 and r["bad"] == 0, "100회 모두 과목 순서·문항 수 25/15/25/15")
    check(r["dup"] == 0, "한 시험 안에 중복 문항 없음")
    check(r["dep"] == 0, "폐기 문제 출제 없음")
    total_q = page.evaluate("Object.keys(CDME.app.getBank().byId).length")
    check(r["covered"] >= 0.9 * total_q, f"100회 동안 {total_q}문항 중 {r['covered']}문항이 한 번 이상 출제 (고르게 출제)")
    real = page.evaluate("""() => { localStorage.setItem('cdme_sample', ''); return true; }""")
    page.reload()
    page.wait_for_selector("#start-exam")
    page.wait_for_function("() => CDME.app.getBank() !== null")   # 문제 데이터를 다 읽은 뒤 누르기 (읽기 전 클릭은 무시됨)
    page.click("#start-exam")
    page.wait_for_selector(".modal")
    check("부족" in page.inner_text(".modal") or "미리보기" in page.inner_text(".modal"), "실제 모드: verified 0 → 시험 시작 차단 (verified만 출제)")
    ctx.close()

    # ------------------------------------------------------------------
    print("[TC-15·16] 문제 폐기(deprecated)·수정(version+1) 후 접속")
    ctx, page = new_page(browser, "draft")
    make_nick(page, "폐기검사")
    page.evaluate("""() => { const s = CDME.app.store, b = CDME.app.getBank();
        s.updateProfileData(s.getActiveProfile().id, d => {
          CDME.notes.addManual(d.wrongNotes, b.byId['LAW-0001'], { sample: true, choice: 1 });
          CDME.notes.addManual(d.wrongNotes, b.byId['LAW-0002'], { sample: true, choice: 1 });
          CDME.notes.addManual(d.wrongNotes, b.byId['LAW-0003'], { sample: true, choice: 1 });
        }); }""")
    kind = page.evaluate("() => Object.values(CDME.app.store.getProfileData().wrongNotes).map(n => n.sample)")
    page.goto(BASE + "#/notes")
    page.wait_for_selector(".page-title")
    before = page.inner_text("#view")
    law = json.load(open(os.path.join(ROOT, "data", "questions", "LAW.json"), encoding="utf-8"))
    for q in law["questions"]:
        if q["id"] == "LAW-0001":
            q["status"] = "deprecated"
        if q["id"] == "LAW-0002":
            q["version"] = q.get("version", 1) + 1
            q["explanation"] += " (보완)"
    body = json.dumps(law, ensure_ascii=False)
    ctx.route(re.compile(r".*/data/questions/LAW\.json.*"), lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page.reload()
    page.wait_for_selector(".page-title")
    page.wait_for_timeout(500)
    txt = page.inner_text("#view")
    q1 = [q for q in law["questions"] if q["id"] == "LAW-0001"][0]["question"]
    q2 = [q for q in law["questions"] if q["id"] == "LAW-0002"][0]["question"]
    check(q1[:15] in before, "폐기 전: 오답노트에 LAW-0001 표시")
    check(q1[:15] not in txt, "폐기 후: 오답노트에서 LAW-0001 숨김 (TC-15)")
    check(q2[:15] in txt and "수정된 문제" in txt, "수정 후: LAW-0002에 '수정된 문제' 표시 (TC-16)")
    dep = page.evaluate("""() => { const b = CDME.app.getBank(); let n = 0;
        for (let k = 0; k < 50; k++) { const ip = CDME.exam.buildExam(b, {}); if (ip.items.some(i => i.qid === 'LAW-0001')) n++; } return n; }""")
    check(dep == 0, "폐기 문제는 출제 50회 중 0회 (TC-15)")
    check(page.evaluate("() => CDME.app.store.getProfileData().wrongNotes['LAW-0001'] != null"), "폐기 문제의 오답 기록은 지우지 않고 보관")
    ctx.close()

    # ------------------------------------------------------------------
    print("[실제 모드] 검수 완료(verified) 문제로 미리보기 없이 실전 시험")
    ctx, page = new_page(browser, None, drafts=False, dev=False)
    make_nick(page, "실전검사")
    bank = page.evaluate("() => { const b = CDME.app.getBank(); const c = {}; Object.values(b.byId).forEach(q => { if (q.status === 'verified') c[q.subject] = (c[q.subject] || 0) + 1; }); return c; }")
    need = {"LAW": 25, "CARGO": 15, "SAFE": 25, "SERVICE": 15}
    if all(bank.get(k, 0) >= v for k, v in need.items()):
        check("부족" not in page.inner_text("#view"), "문제 부족 안내 없음 (verified %s)" % bank)
        start_exam(page)
        ids = page.evaluate("() => CDME.app.store.getProfileData().inProgress.items.map(i => i.qid)")
        st = page.evaluate("(ids) => ids.map(id => CDME.app.getBank().byId[id].status)", ids)
        check(len(ids) == 80 and set(st) == {"verified"}, "80문항 모두 verified에서 출제")
        check("검수 전" not in page.inner_text(".q-card") and page.locator(".notice-warn").count() == 0, "'검수 전'·미리보기 안내 없음")
        answer_current(page, True)
        end_by_timeout(page)
        rec = page.evaluate("() => { const e = CDME.app.store.getProfileData().exams; return e[e.length-1]; }")
        check(not rec.get("sample"), "실제 성적으로 기록 (미리보기 기록과 분리)")
    else:
        print("  SKIP verified가 과목별 기준에 못 미침 %s" % bank)
    ctx.close()

    # ------------------------------------------------------------------
    print("[공개 모드] 개발·검수용 모드 숨김 (config dev_modes: false)")
    ctx, page = new_page(browser, "draft", drafts=True, dev=False)   # 문제는 초안으로 보이게 + 예전에 켜 둔 미리보기 상태
    make_nick(page, "공개검사")
    page.wait_for_timeout(500)
    check(page.evaluate("localStorage.getItem('cdme_sample')") is None, "예전에 켜 둔 미리보기 모드는 자동으로 꺼짐")
    check(page.locator("[data-draft-on], [data-sample-on], [data-sample-off]").count() == 0, "미리보기·샘플 버튼 없음 (검수 문제 부족해도)")
    page.click("#start-exam")
    page.wait_for_selector(".modal")
    mt = page.inner_text(".modal")
    check("샘플" not in mt and "미리보기" not in mt and "검수하고 있습니다" in mt, "시작 불가 안내에도 샘플·미리보기 권유 없음")
    page.click(".modal [data-act=ok]")
    check(page.evaluate("localStorage.getItem('cdme_sample')") is None, "확인을 눌러도 샘플 모드로 바뀌지 않음")
    ctx.close()
    ctx, page = new_page(browser, None, drafts=True, dev=False)
    page.goto(BASE + "?dev=1#/home")
    make_nick(page, "운영자")
    check(page.locator("[data-draft-on]").count() == 1, "운영자: 주소에 ?dev=1 을 붙이면 미리보기 버튼 표시")
    page.click("[data-draft-on]")
    page.wait_for_selector("text=검수 미리보기 모드")
    page.goto(BASE + "#/home")
    page.reload()
    page.wait_for_selector("text=검수 미리보기 모드")
    check(True, "같은 창에서는 ?dev=1 없이도 유지")
    ctx.close()

    # ------------------------------------------------------------------
    print("[NFR-03] 성능: 첫 화면 3초 이내, 문제 이동 0.1초 이내, 문제 데이터 3MB 이하")
    size = sum(os.path.getsize(os.path.join(ROOT, "data", "questions", c + ".json")) for c in ("LAW", "CARGO", "SAFE", "SERVICE"))
    report["data_bytes"] = size
    check(size <= 3 * 1024 * 1024, "문제 데이터 합계 %.0fKB (≤ 3MB)" % (size / 1024))
    ctx, page = new_page(browser, "draft")
    make_nick(page, "성능검사")
    t0 = time.time()
    page.reload()
    page.wait_for_selector("text=80문항 · 80분")
    load_ms = (time.time() - t0) * 1000
    report["load_ms"] = round(load_ms)
    check(load_ms < 3000, "새로고침 후 대시보드(문제 400개 불러오기 포함)까지 %dms (< 3000ms)" % load_ms)
    start_exam(page)
    moves = page.evaluate("""async () => { const r = []; const next = document.getElementById('ex-next');
        for (let k = 0; k < 20; k++) { const t = performance.now(); next.click(); r.push(performance.now() - t); }
        return r; }""")
    mx = max(moves)
    report["move_ms_max"] = round(mx, 1)
    check(mx < 100, "문제 이동 20회 최대 %.1fms (< 100ms)" % mx)
    ctx.close()

    # ------------------------------------------------------------------
    print("[NFR-05] 저장 공간 부족 시 안내")
    ctx, page = new_page(browser, "1")
    make_nick(page, "용량검사")
    start_exam(page)
    page.evaluate("""() => { const orig = Storage.prototype.setItem;
        Storage.prototype.setItem = function (k, v) { if (k === 'cdme') { const e = new Error('QuotaExceededError'); e.name = 'QuotaExceededError'; throw e; } return orig.call(this, k, v); }; }""")
    answer_current(page, True)
    page.wait_for_selector(".toast")
    check("저장하지 못했습니다" in page.inner_text(".toast"), "풀이 중에도 저장 실패 알림(토스트) 표시")
    page.click("#ex-later")
    page.wait_for_selector("#view .notice-error, .resume, #start-exam")
    txt = page.inner_text("#view")
    check("저장하지 못했습니다" in txt, "저장 실패 시 '기록을 저장하지 못했습니다' 안내 표시")
    check(not page.js_errors, "저장 실패해도 자바스크립트 오류 없음 " + "; ".join(page.js_errors))
    ctx.close()

    # ------------------------------------------------------------------
    print("[NFR-06] 개인정보: 외부 서버로 나가는 요청 없음 (전체 흐름)")
    ctx, page = new_page(browser, "1")
    outside = []
    host = re.match(r"https?://[^/]+", BASE).group(0)
    page.on("request", lambda req: outside.append(req.url) if not req.url.startswith(host) and not req.url.startswith("data:") and not req.url.startswith("blob:") else None)
    make_nick(page, "외부요청")
    start_exam(page)
    answer_current(page, True)
    page.click("#ex-hint") if page.locator("#ex-hint").count() else None
    end_by_timeout(page)
    for route in ("records", "notes", "review", "data", "help"):
        page.goto(BASE + "#/" + route)
        page.wait_for_selector(".page-title")
    check(not outside, "외부 요청 0건 " + "; ".join(outside[:3]))
    check(page.evaluate("() => document.cookie") == "", "쿠키 사용 없음")
    ctx.close()

    # ------------------------------------------------------------------
    print("[NFR-01·02] 기기별 화면 (Chromium 기기 흉내 – 크롬·엣지·삼성 인터넷과 같은 엔진)")
    devices = ["iPhone SE", "Galaxy S9+", "Pixel 7", "iPad Mini", "iPad Pro 11 landscape"]
    sizes = []
    for dn in devices:
        d = dict(p.devices[dn])
        d.pop("default_browser_type", None)
        ctx, page = new_page(browser, "draft", **d)
        make_nick(page, "기기")
        bad = []
        for route in ("home", "exam", "result", "records", "notes", "data", "help"):
            if route == "exam":
                start_exam(page)
                answer_current(page, False)
            elif route == "result":
                end_by_timeout(page)
            else:
                page.goto(BASE + "#/" + route)
                page.wait_for_selector(".page-title, #start-exam")
            w = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if w > 0:
                bad.append("%s(+%dpx)" % (route, w))
        page.goto(BASE + "#/home")
        page.wait_for_selector("#start-exam")
        page.screenshot(path=f"{SHOT}/tc_device_{dn.replace(' ', '_')}.png")
        sizes.append("%s %dx%d" % (dn, d["viewport"]["width"], d["viewport"]["height"]))
        check(not bad, f"{dn}: 7개 화면 가로 스크롤 없음 " + ", ".join(bad))
        ctx.close()
    for w, h in ((1280, 800), (1920, 1080)):
        ctx, page = new_page(browser, "draft", viewport={"width": w, "height": h})
        make_nick(page, "PC")
        start_exam(page)
        sw = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(sw <= 0, f"PC {w}x{h}: 시험 화면 가로 스크롤 없음")
        page.screenshot(path=f"{SHOT}/tc_pc_{w}.png")
        ctx.close()
    report["devices"] = sizes

    # ------------------------------------------------------------------
    print("[NFR-07] 자동 접근성 검사 (axe-core, WCAG 2.1 AA) – 라이트·다크")
    axe_src = open(AXE, encoding="utf-8").read() if os.path.exists(AXE) else None
    if axe_src is None:
        print("  SKIP axe-core 파일이 없어 건너뜀 (npm install axe-core 후 AXE_JS 환경변수에 axe.min.js 경로 지정)")
    else:
        found = {}
        for scheme in ("light", "dark"):
            ctx, page = new_page(browser, "1", color_scheme=scheme)
            page.goto(BASE + "#/start")
            page.wait_for_selector("#nick")
            screens = [("start", None)]
            make_nick(page, "접근성")
            screens = ["start", "home", "exam", "exam-hint", "exam-answered", "result", "records", "notes", "review", "data", "help"]
            for sname in screens:
                if sname == "start":
                    continue
                if sname == "exam":
                    start_exam(page)
                elif sname == "exam-hint":
                    page.click("#ex-hint")
                    page.wait_for_selector("#ex-hintbox")
                elif sname == "exam-answered":
                    answer_current(page, False)
                elif sname == "result":
                    end_by_timeout(page)
                else:
                    page.goto(BASE + "#/" + sname)
                    page.wait_for_selector(".page-title, #start-exam")
                page.add_script_tag(content=axe_src)
                res = page.evaluate("""async () => { const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] } });
                    return r.violations.map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, t: v.nodes.slice(0,2).map(x => x.target.join(' ')) })); }""")
                for v in res:
                    key = (scheme, sname, v["id"])
                    found[key] = v
            ctx.close()
        report["axe"] = [{"scheme": k[0], "screen": k[1], **v} for k, v in found.items()]
        serious = [v for v in report["axe"] if v["impact"] in ("serious", "critical")]
        for v in report["axe"]:
            print("     -", v["scheme"], v["screen"], v["impact"], v["id"], v["n"], v["t"])
        check(not serious, "심각(serious·critical) 접근성 위반 0건 (%d건)" % len(serious))

    browser.close()

json.dump(report, open(os.path.join(SHOT, "tc_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n결과:", "모두 통과" if not errors else f"실패 {len(errors)}건")
sys.exit(1 if errors else 0)
