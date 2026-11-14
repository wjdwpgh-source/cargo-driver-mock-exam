"""대형면허 화면·채점 확인용 가짜 문제(테스트 전용) 만들기 – v2.0 L2
사용법: python tests/make_license_fixture.py  → tests/fixtures/license/<그룹>.json
- id는 개발 확인용 예약 번호 DL-9001~ (PRD 7.2), 상태는 verified(테스트에서 실제 시험처럼 출제되도록)
- 지문에 정답 번호를 적어 둔다(화면 확인용). 공개 사이트 데이터(data/license)에는 넣지 않는다.
"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "license")
# 그룹, 문항 수, 보기 수, 정답 수
GROUPS = [("TEXT1", 20, 4, 1), ("TEXT2", 6, 4, 2), ("SIGN", 6, 4, 1), ("ILLUST2", 16, 5, 2), ("ILLUST1", 3, 4, 1)]
CIRCLED = "①②③④⑤"
IMG = os.path.join(OUT, "images")

SIGN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 180" width="200" height="180">
<polygon points="100,10 190,170 10,170" fill="#fff" stroke="#d6262d" stroke-width="14" stroke-linejoin="round"/>
<text x="100" y="150" font-size="90" font-weight="700" text-anchor="middle" font-family="sans-serif">{n}</text></svg>"""

ILLUST_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 260" width="400" height="260">
<rect width="400" height="260" fill="#cfe8c4"/><rect x="150" y="0" width="100" height="260" fill="#6b7280"/>
<rect x="0" y="90" width="400" height="80" fill="#6b7280"/>
<line x1="200" y1="0" x2="200" y2="90" stroke="#facc15" stroke-width="4"/><line x1="200" y1="170" x2="200" y2="260" stroke="#facc15" stroke-width="4"/>
<rect x="210" y="190" width="30" height="50" rx="6" fill="#1f5fbf"/><text x="225" y="222" font-size="20" fill="#fff" text-anchor="middle" font-family="sans-serif">A</text>
<rect x="40" y="135" width="50" height="28" rx="6" fill="#d6262d"/><text x="65" y="155" font-size="18" fill="#fff" text-anchor="middle" font-family="sans-serif">B</text>
<text x="390" y="20" font-size="14" text-anchor="end" font-family="sans-serif">확인용 {n}</text></svg>"""


def main():
    os.makedirs(OUT, exist_ok=True)
    no = 9001
    for code, count, nc, na in GROUPS:
        qs = []
        for k in range(count):
            if na == 1:
                ans = [(k % nc) + 1]
            else:
                a = (k % nc) + 1
                b = ((k + 2) % nc) + 1
                ans = sorted({a, b}) if a != b else [a, (a % nc) + 1]
            marks = ", ".join(CIRCLED[a - 1] for a in ans)
            q = {
                "id": "DL-%04d" % no, "exam": "license", "subject": code, "category": "SAFE",
                "question": "[확인용 %s %d] 정답은 %s입니다.%s" % (code, k + 1, marks, " 2개를 고르세요." if na > 1 else ""),
                "choices": ["보기 %d (%s %d)" % (c, code, k + 1) for c in range(1, nc + 1)],
                "answer": ans,
                "explanation": "확인용 해설 – 정답은 %s번입니다." % marks,
                "hint": "확인용 힌트 글입니다." if k % 3 == 0 else "",
                "source": "자체 작성", "difficulty": (k % 3) + 1,
                **({"image": "license/images/DL-%04d.svg" % no,
                    "image_alt": ("확인용 안전표지 %d – 빨간 테두리 삼각형" % (k + 1)) if code == "SIGN" else
                                 ("확인용 교차로 %d – 내 차 A가 교차로 앞, 왼쪽에서 차 B가 다가옴" % (k + 1))}
                   if code in ("SIGN", "ILLUST2", "ILLUST1") else {}),
                "status": "verified", "version": 1, "updated_at": "2026-11-14",
            }
            if "image" in q:
                os.makedirs(IMG, exist_ok=True)
                svg = (SIGN_SVG if code == "SIGN" else ILLUST_SVG).format(n=k + 1)
                with open(os.path.join(IMG, "DL-%04d.svg" % no), "w", encoding="utf-8") as f:
                    f.write(svg)
            qs.append(q)
            no += 1
        with open(os.path.join(OUT, code + ".json"), "w", encoding="utf-8") as f:
            json.dump({"subject": code, "exam": "license", "updated_at": "2026-11-14", "questions": qs}, f, ensure_ascii=False, indent=1)
    print("완료:", no - 9001, "문항 →", OUT)


if __name__ == "__main__":
    main()
