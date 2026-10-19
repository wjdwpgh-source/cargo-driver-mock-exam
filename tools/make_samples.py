"""개발 확인용 샘플 문제 생성기
- data/samples/ 에 과목별 샘플 문제(JSON)를 만든다.
- 실제 문제가 아니며, 지문에 정답 번호가 적혀 있어 합격/불합격을 일부러 만들어 볼 수 있다.
- 샘플 문제 id는 9001번부터 사용한다(실제 문제와 겹치지 않도록 9000번대는 샘플용으로 예약).
사용법: python tools/make_samples.py
"""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "samples")
SUBJECTS = [
    ("LAW", "법규", 40),
    ("CARGO", "화물취급요령", 25),
    ("SAFE", "안전운행", 40),
    ("SERVICE", "운송서비스", 25),
]

rng = random.Random(20261019)
os.makedirs(OUT, exist_ok=True)
for code, name, n in SUBJECTS:
    qs = []
    for i in range(1, n + 1):
        ans = rng.randint(1, 4)
        qs.append({
            "id": f"{code}-{9000 + i}",
            "subject": code,
            "question": f"[샘플 {name} {i}] 개발 확인용 문제입니다. 이 문제의 정답은 {ans}번입니다.",
            "choices": [f"샘플 보기 {k}" for k in range(1, 5)],
            "answer": ans,
            "explanation": f"샘플 문제의 해설입니다. 정답은 {ans}번입니다.",
            "source": "개발용 샘플",
            "law_ref": "",
            "difficulty": 1,
            "image": None,
            "status": "verified",
            "version": 1,
            "updated_at": "2026-10-19",
        })
    with open(os.path.join(OUT, f"{code}.json"), "w", encoding="utf-8") as f:
        json.dump({"subject": code, "sample": True, "updated_at": "2026-10-19", "questions": qs}, f, ensure_ascii=False, indent=1)
    print(code, n)
