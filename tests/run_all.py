"""전체 자동 테스트 한 번에 실행 (6단계)
사용법: 프로젝트 폴더에서  python tests/run_all.py
필요: Node.js(단위 테스트), Python + openpyxl(도구 테스트), Playwright + Chromium(브라우저 테스트)
  - 8000번 포트에 로컬 서버가 없으면 자동으로 띄웠다가 끝나면 닫는다.
  - 접근성 검사(axe-core)는 AXE_JS 환경변수로 axe.min.js 경로를 주면 실행된다(없으면 그 항목만 실패로 표시).
"""
import os
import shutil
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
E2E = ["e2e_s1", "e2e_s2", "e2e_s3", "e2e_s4", "e2e_s5", "e2e_s6", "e2e_s7", "e2e_preview", "e2e_hint", "e2e_tc", "e2e_study"]


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def run(name, cmd):
    t = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
    out = (p.stdout or "") + (p.stderr or "")
    logdir = os.path.join(ROOT, "tests", "screenshots")
    os.makedirs(logdir, exist_ok=True)
    with open(os.path.join(logdir, "log_" + name.replace(" ", "_") + ".txt"), "w", encoding="utf-8") as f:
        f.write(out)
    fails = [l.strip() for l in out.splitlines() if "FAIL" in l or l.startswith("not ok")]
    ok = p.returncode == 0
    print("%-14s %s  (%.0f초)" % (name, "통과" if ok else "실패", time.time() - t))
    for f in fails[:10]:
        print("      " + f)
    if not ok and not fails:
        print("      " + "\n      ".join(out.strip().splitlines()[-5:]))
    return ok


def main():
    server = None
    if not port_open(8000):
        server = subprocess.Popen([sys.executable, "-m", "http.server", "8000"], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    results = []
    try:
        if shutil.which("node"):
            results.append(run("단위 테스트", ["node", "--test", "tests/unit.test.js"]))
        else:
            print("단위 테스트     건너뜀 (Node.js 없음)")
        results.append(run("문제 도구", [sys.executable, "tests/test_tools.py"]))
        results.append(run("문제 검사", [sys.executable, "tools/validate.py", "--json"]))
        for t in E2E:
            results.append(run(t, [sys.executable, os.path.join("tests", t + ".py")]))
    finally:
        if server:
            server.terminate()
    print("\n결과: %d개 중 %d개 통과" % (len(results), sum(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
