"""일러스트 장면 그리기 – 장면 정의(JSON) → SVG (PRD 13.5·13.8.3 ②)
도로·교차로·차량·보행자·신호등·표지·화살표를 조합해 일러스트형 문제 그림을 일관된 모양으로 만든다.

사용법:
  python tools/scene.py data/license/scenes/DL-0216.json            → data/license/images/DL-0216.svg
  python tools/scene.py --all                                        → scenes 폴더 전체를 다시 그림
  python tools/scene.py --demo [출력.html]                           → 부품·도로 모양 미리보기

장면 정의 예:
{ "size": [400, 300],
  "road": { "type": "cross", "lanes": 2 },             // straight · cross · t · roundabout · merge · curve
  "items": [
    { "kind": "car", "x": 230, "y": 230, "rot": 0, "label": "A", "role": "me" },     // role: me(파랑)·other(빨강)·etc(회색)
    { "kind": "truck", "x": 120, "y": 140, "rot": 90, "label": "B" },
    { "kind": "bus" | "bike" | "motorcycle" | "person" | "child" | "elder", ... },
    { "kind": "crosswalk", "x": 150, "y": 190, "w": 100, "h": 24, "dir": "h" },
    { "kind": "stopline", "x": 200, "y": 182, "w": 50 },
    { "kind": "signal", "x": 270, "y": 120, "state": "red" | "yellow" | "green" | "green-left", "right": "red" | "green"(선택) },
    { "kind": "sign", "id": "r-no-uturn", "x": 300, "y": 20, "size": 48 },          // tools/signs.py 표지 ID
    { "kind": "arrow", "points": [[230, 260], [230, 180], [280, 150]], "color": "#1f5fbf", "dash": false },
    { "kind": "text", "x": 20, "y": 20, "text": "어린이 보호구역" },
    { "kind": "cone", "x": .., "y": .. }, { "kind": "rail", "y": 150 }, { "kind": "zone", "x":.., "y":.., "w":.., "h":.., "color": "#fde68a" }
  ] }
좌표는 왼쪽 위가 (0,0). rot은 차량이 바라보는 방향(0 = 위쪽, 90 = 오른쪽, 180 = 아래, 270 = 왼쪽).
"""
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signs  # noqa: E402

GRASS, ROAD, YEL, WHT = "#cfe8c4", "#6b7280", "#facc15", "#ffffff"
ROLE = {"me": "#1f5fbf", "other": "#d6262d", "etc": "#4b5563", "yellow": "#eab308"}
FONT = 'font-family="Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, sans-serif"'
LANE = 34   # 차로 하나 폭


def esc(t):
    return html.escape(str(t))


# ---------- 도로 ----------
def road_straight(w, h, lanes, vertical=True):
    rw = lanes * 2 * LANE
    if vertical:
        x = (w - rw) / 2
        s = '<rect x="%s" y="0" width="%s" height="%s" fill="%s"/>' % (x, rw, h, ROAD)
        s += '<line x1="%s" y1="0" x2="%s" y2="%s" stroke="%s" stroke-width="4"/>' % (w / 2, w / 2, h, YEL)
        for k in range(1, lanes):
            for side in (-1, 1):
                lx = w / 2 + side * k * LANE
                s += '<line x1="%s" y1="0" x2="%s" y2="%s" stroke="%s" stroke-width="3" stroke-dasharray="18 14"/>' % (lx, lx, h, WHT)
        return s
    y = (h - rw) / 2
    s = '<rect x="0" y="%s" width="%s" height="%s" fill="%s"/>' % (y, w, rw, ROAD)
    s += '<line x1="0" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="4"/>' % (h / 2, w, h / 2, YEL)
    for k in range(1, lanes):
        for side in (-1, 1):
            ly = h / 2 + side * k * LANE
            s += '<line x1="0" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="3" stroke-dasharray="18 14"/>' % (ly, w, ly, WHT)
    return s


def road(spec, w, h):
    t = (spec or {}).get("type", "straight")
    lanes = int((spec or {}).get("lanes", 1))
    rw = lanes * 2 * LANE
    if t == "straight":
        return road_straight(w, h, lanes, (spec or {}).get("dir", "v") == "v")
    if t in ("cross", "t"):
        s = road_straight(w, h, lanes, True) if t == "cross" else ""
        if t == "t":   # 위쪽 가로 도로 + 아래로 이어지는 세로 도로
            x = (w - rw) / 2
            s += '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (x, h / 2, rw, h / 2, ROAD)
            s += '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="4"/>' % (w / 2, h / 2 + rw / 2, w / 2, h, YEL)
        s += road_straight(w, h, lanes, False)
        # 교차로 안은 차선 없이
        s += '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % ((w - rw) / 2, (h - rw) / 2, rw, rw, ROAD)
        return s
    if t == "roundabout":
        s = road_straight(w, h, lanes, True) + road_straight(w, h, lanes, False)
        r = rw * 0.95
        s += '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (w / 2, h / 2, r + LANE * 0.6, ROAD)
        s += '<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="4"/>' % (w / 2, h / 2, r * 0.45, GRASS, WHT)
        return s
    if t == "merge":   # 고속도로 본선(세로) + 오른쪽 아래에서 들어오는 가속차로
        s = road_straight(w, h, lanes, True)
        x = w / 2 + lanes * LANE
        s += '<polygon points="%s,%s %s,%s %s,%s %s,%s" fill="%s"/>' % (x, h * 0.25, x + LANE, h * 0.45, x + LANE * 2.4, h, x, h, ROAD)
        s += '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="3" stroke-dasharray="10 10"/>' % (x, h * 0.3, x, h, WHT)
        return s
    if t == "curve":   # 아래에서 올라와 오른쪽으로 굽는 도로
        cx, cy, r = w * 0.75, h * 0.95, min(w, h) * 0.55
        return ('<path d="M%s,%s A%s,%s 0 0 1 %s,%s" fill="none" stroke="%s" stroke-width="%s"/>' % (cx - r, h, r, r, w, cy - r, ROAD, rw) +
                '<path d="M%s,%s A%s,%s 0 0 1 %s,%s" fill="none" stroke="%s" stroke-width="4"/>' % (cx - r, h, r, r, w, cy - r, YEL))
    raise ValueError("모르는 도로 모양: %s" % t)


# ---------- 부품 ----------
def vehicle(it):
    kind = it["kind"]
    color = ROLE.get(it.get("role", "other"), it.get("color", ROLE["other"]))
    dims = {"car": (26, 44), "truck": (30, 76), "bus": (30, 84), "motorcycle": (12, 30), "bike": (10, 28)}[kind]
    w, h = dims
    if kind in ("bike", "motorcycle"):   # 두 바퀴 + 몸체 (위에서 본 모양)
        s = ('<rect x="-2.5" y="%s" width="5" height="%s" rx="2" fill="#111827"/>' % (-h / 2, h) +
             '<ellipse cx="0" cy="%s" rx="3.5" ry="7" fill="#111827"/><ellipse cx="0" cy="%s" rx="3.5" ry="7" fill="#111827"/>' % (-h / 2 + 6, h / 2 - 6) +
             '<rect x="%s" y="-3" width="%s" height="5" rx="2" fill="#111827"/>' % (-w, w * 2) +
             '<circle cx="0" cy="2" r="%s" fill="%s"/>' % (6 if kind == "bike" else 7, color))
    else:
        s = '<rect x="%s" y="%s" width="%s" height="%s" rx="5" fill="%s" stroke="#111827" stroke-width="1.5"/>' % (-w / 2, -h / 2, w, h, color)
    if kind in ("car", "bus", "truck"):
        s += '<rect x="%s" y="%s" width="%s" height="9" rx="2" fill="#dbeafe"/>' % (-w / 2 + 4, -h / 2 + 5, w - 8)   # 앞유리(진행 방향)
    if kind == "truck":
        s += '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="#111827" stroke-width="2"/>' % (-w / 2, -h / 2 + 22, w / 2, -h / 2 + 22)
    label = it.get("label")
    t = ""
    if label:
        t = '<text x="0" y="5" font-size="16" font-weight="700" text-anchor="middle" fill="#fff" %s transform="rotate(%s)">%s</text>' % (FONT, -float(it.get("rot", 0)), esc(label))
    return '<g transform="translate(%s,%s) rotate(%s)">%s%s</g>' % (it["x"], it["y"], it.get("rot", 0), s, t)


def walker(it):
    k = it["kind"]
    sc = {"person": 1.0, "child": 0.75, "elder": 1.0}[k]
    color = it.get("color", "#111827")
    s = '<circle cx="0" cy="-14" r="5" fill="%s"/><path d="M0,-9 L0,6 M0,6 L-6,18 M0,6 L6,18 M-7,-3 L7,-3" stroke="%s" stroke-width="3.5" stroke-linecap="round" fill="none"/>' % (color, color)
    if k == "elder":
        s += '<line x1="9" y1="-4" x2="11" y2="18" stroke="%s" stroke-width="2.5"/>' % color
    label = ('<text x="0" y="-24" font-size="13" font-weight="700" text-anchor="middle" fill="%s" %s>%s</text>' % (color, FONT, esc(it["label"]))) if it.get("label") else ""
    return '<g transform="translate(%s,%s) scale(%s)">%s</g>%s' % (it["x"], it["y"], sc, s, label.replace('x="0" y="-24"', 'x="%s" y="%s"' % (it["x"], it["y"] - 24 * sc)) if label else "")


def crosswalk(it):
    x, y, w, hh = it["x"], it["y"], it.get("w", 100), it.get("h", 24)
    out = []
    if it.get("dir", "h") == "h":   # 가로로 길게 놓인 횡단보도(세로 줄무늬)
        n = int(w // 12)
        out = ['<rect x="%s" y="%s" width="7" height="%s" fill="%s"/>' % (x + k * 12, y, hh, WHT) for k in range(n)]
    else:
        n = int(hh // 12)
        out = ['<rect x="%s" y="%s" width="%s" height="7" fill="%s"/>' % (x, y + k * 12, w, WHT) for k in range(n)]
    return "".join(out)


def signal(it):
    st = it.get("state", "red")
    on = {"red": 0, "yellow": 1, "green": 2, "green-left": 2}[st]
    cols = ["#ef4444", "#facc15", "#22c55e"]
    s = '<rect x="-30" y="-11" width="60" height="22" rx="5" fill="#111827"/>'
    for k in range(3):
        s += '<circle cx="%s" cy="0" r="7" fill="%s"/>' % (-18 + k * 18, cols[k] if k == on else "#374151")
    if st == "green-left":
        s += '<rect x="30" y="-11" width="22" height="22" rx="5" fill="#111827"/><path d="M47,0 L35,0 M40,-5 L35,0 L40,5" stroke="#22c55e" stroke-width="3" fill="none"/>'
    if it.get("right"):   # 우회전 화살표 신호등(따로 설치): "red" | "green"
        c = {"red": "#ef4444", "green": "#22c55e"}[it["right"]]
        s += '<g transform="translate(0,26)"><rect x="-11" y="-11" width="22" height="22" rx="5" fill="#111827"/><path d="M-6,0 L6,0 M1,-5 L6,0 L1,5" stroke="%s" stroke-width="3" fill="none"/></g>' % c
    return '<g transform="translate(%s,%s)">%s</g>' % (it["x"], it["y"], s)


def arrow(it):
    pts = it["points"]
    color = it.get("color", "#1f5fbf")
    d = "M" + " L".join("%s,%s" % (p[0], p[1]) for p in pts)
    dash = ' stroke-dasharray="8 6"' if it.get("dash") else ""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    import math
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) + 90
    head = '<polygon points="0,-12 9,4 -9,4" fill="%s" transform="translate(%s,%s) rotate(%s)"/>' % (color, x2, y2, ang)
    return '<path d="%s" fill="none" stroke="%s" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"%s/>%s' % (d, color, dash, head)


def item_svg(it):
    k = it["kind"]
    if k in ("car", "truck", "bus", "motorcycle", "bike"):
        return vehicle(it)
    if k in ("person", "child", "elder"):
        return walker(it)
    if k == "crosswalk":
        return crosswalk(it)
    if k == "stopline":
        return '<rect x="%s" y="%s" width="%s" height="5" fill="%s"/>' % (it["x"], it["y"], it.get("w", 60), WHT)
    if k == "signal":
        return signal(it)
    if k == "sign":
        return signs.group(it["id"], it["x"], it["y"], it.get("size", 48))
    if k == "arrow":
        return arrow(it)
    if k == "text":
        return '<text x="%s" y="%s" font-size="%s" font-weight="700" fill="%s" %s>%s</text>' % (it["x"], it["y"], it.get("size", 15), it.get("color", "#111827"), FONT, esc(it["text"]))
    if k == "cone":
        return '<polygon points="%s,%s %s,%s %s,%s" fill="#f97316" stroke="#fff" stroke-width="1.5"/>' % (it["x"], it["y"] - 10, it["x"] + 7, it["y"] + 6, it["x"] - 7, it["y"] + 6)
    if k == "rail":
        y = it["y"]
        return ('<rect x="0" y="%s" width="%s" height="26" fill="#78716c"/>' % (y - 13, it.get("w", 400)) +
                "".join('<rect x="%s" y="%s" width="6" height="26" fill="#44403c"/>' % (x, y - 13) for x in range(0, it.get("w", 400), 16)) +
                '<line x1="0" y1="%s" x2="%s" y2="%s" stroke="#d6d3d1" stroke-width="3"/><line x1="0" y1="%s" x2="%s" y2="%s" stroke="#d6d3d1" stroke-width="3"/>' % (y - 6, it.get("w", 400), y - 6, y + 6, it.get("w", 400), y + 6))
    if k == "zone":
        return '<rect x="%s" y="%s" width="%s" height="%s" fill="%s" opacity="%s"/>' % (it["x"], it["y"], it["w"], it["h"], it.get("color", "#fde68a"), it.get("opacity", 0.6))
    raise ValueError("모르는 부품: %s" % k)


ORDER = {"zone": 0, "rail": 1, "crosswalk": 2, "stopline": 2, "arrow": 3}


def render(scene):
    w, h = scene.get("size", [400, 300])
    body = '<rect width="%s" height="%s" fill="%s"/>' % (w, h, scene.get("bg", GRASS))
    if scene.get("road"):
        body += road(scene["road"], w, h)
    items = sorted(scene.get("items", []), key=lambda it: ORDER.get(it["kind"], 5))
    body += "".join(item_svg(it) for it in items)
    title = esc(scene.get("alt", "문제 그림"))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s" role="img" aria-label="%s"><title>%s</title>%s</svg>'
            % (w, h, w, h, title, title, body))


def render_file(src, out=None):
    scene = json.load(open(src, encoding="utf-8"))
    if out is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = os.path.join(root, "data", "license", "images", os.path.splitext(os.path.basename(src))[0] + ".svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(scene))
    return out


DEMO = [
    {"road": {"type": "cross", "lanes": 2}, "items": [
        {"kind": "car", "x": 218, "y": 250, "rot": 0, "label": "A", "role": "me"},
        {"kind": "truck", "x": 80, "y": 166, "rot": 90, "label": "B"},
        {"kind": "crosswalk", "x": 132, "y": 210, "w": 136, "h": 22},
        {"kind": "stopline", "x": 200, "y": 236, "w": 68},
        {"kind": "signal", "x": 300, "y": 70, "state": "green-left"},
        {"kind": "person", "x": 250, "y": 222, "label": "보행자"},
        {"kind": "arrow", "points": [[252, 236], [252, 190], [300, 166], [380, 166]]}], "alt": "사거리 – 내 차 A 우회전"},
    {"road": {"type": "t", "lanes": 1}, "items": [
        {"kind": "bus", "x": 200, "y": 255, "rot": 0, "label": "A", "role": "me"},
        {"kind": "bike", "x": 130, "y": 160, "rot": 90, "label": "B"},
        {"kind": "sign", "id": "r-stop", "x": 250, "y": 190, "size": 40},
        {"kind": "child", "x": 260, "y": 110}], "alt": "T자 교차로"},
    {"road": {"type": "roundabout", "lanes": 1}, "items": [
        {"kind": "car", "x": 218, "y": 270, "rot": 0, "label": "A", "role": "me"},
        {"kind": "car", "x": 140, "y": 132, "rot": 135, "label": "B", "role": "other"}], "alt": "회전교차로"},
    {"road": {"type": "merge", "lanes": 2}, "items": [
        {"kind": "truck", "x": 300, "y": 260, "rot": -15, "label": "A", "role": "me"},
        {"kind": "car", "x": 252, "y": 150, "rot": 0, "label": "B"}], "alt": "고속도로 합류"},
    {"road": {"type": "straight", "lanes": 1, "dir": "h"}, "items": [
        {"kind": "rail", "y": 0, "w": 400},
        {"kind": "zone", "x": 0, "y": 230, "w": 400, "h": 70, "color": "#fde68a"},
        {"kind": "text", "x": 12, "y": 290, "text": "어린이 보호구역"},
        {"kind": "car", "x": 120, "y": 168, "rot": 90, "label": "A", "role": "me"},
        {"kind": "cone", "x": 300, "y": 140}, {"kind": "cone", "x": 320, "y": 140},
        {"kind": "elder", "x": 360, "y": 210}], "alt": "부품 모음"},
]


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if len(argv) >= 2 and argv[1] == "--all":
        sdir = os.path.join(root, "data", "license", "scenes")
        n = 0
        for f in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []:
            if f.endswith(".json"):
                render_file(os.path.join(sdir, f))
                n += 1
        print("장면 %d개를 그렸습니다." % n)
        return 0
    if len(argv) >= 2 and argv[1] == "--demo":
        out = argv[2] if len(argv) > 2 else os.path.join(root, "검수", "장면_미리보기.html")
        cells = "".join("<figure>%s<figcaption>%s</figcaption></figure>" % (render(s), esc(s["alt"])) for s in DEMO)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write("<!doctype html><meta charset=utf-8><title>장면 부품 미리보기</title><style>body{font-family:sans-serif}figure{display:inline-block;margin:8px}svg{border:1px solid #ccc}</style><h1>일러스트 장면 미리보기</h1>" + cells)
        print("저장:", out)
        return 0
    if len(argv) >= 2:
        print("저장:", render_file(argv[1], argv[2] if len(argv) > 2 else None))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
