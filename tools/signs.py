"""안전표지 SVG 도안 라이브러리 (PRD 13.5·13.8.3 ②)
도로교통법 시행규칙 별표 6(안전표지)의 도안 '형태'를 단순화해 직접 그린다. 공식 도안 파일을 복사하지 않는다.
※ 그린 표지는 검수 때 별표 6 도안과 모양·색·기호를 대조한다(검수표 확인 포인트).

사용법:
  python tools/signs.py list                     → 표지 목록
  python tools/signs.py preview [출력.html]       → 모든 표지 미리보기 HTML (기본: 검수/표지_미리보기.html)
  python tools/signs.py render <표지ID> <출력.svg> → 표지 하나를 SVG 파일로
코드에서: import signs; signs.svg('c-crossroad') / signs.group('c-crossroad', x, y, size)
"""
import html
import os
import sys

RED, YEL, BLU, BLK, WHT = "#d6262d", "#ffcc00", "#1f5fbf", "#111111", "#ffffff"
FONT = "font-family=\"Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, sans-serif\""


# ---------- 바탕 모양 ----------
def caution(inner):            # 주의표지: 빨간 테두리 · 노란 바탕 정삼각형
    return ('<polygon points="100,14 190,176 10,176" fill="%s" stroke="%s" stroke-width="14" stroke-linejoin="round"/>' % (YEL, RED)) + \
        '<g transform="translate(100,122)">%s</g>' % inner


def regulate(inner, slash=False):   # 규제표지: 빨간 원 테두리 · 흰 바탕 (금지는 빗금)
    s = '<circle cx="100" cy="100" r="86" fill="%s" stroke="%s" stroke-width="16"/>' % (WHT, RED)
    s += '<g transform="translate(100,100)">%s</g>' % inner
    if slash:
        s += '<line x1="40" y1="40" x2="160" y2="160" stroke="%s" stroke-width="14"/>' % RED
    return s


def inverted(text_ko, text_en, fill=WHT, color=RED):   # 역삼각형 (일시정지·서행·양보)
    tc = WHT if fill == RED else BLK
    return ('<polygon points="10,24 190,24 100,186" fill="%s" stroke="%s" stroke-width="12" stroke-linejoin="round"/>' % (fill, color)) + \
        '<text x="100" y="82" font-size="34" font-weight="700" text-anchor="middle" fill="%s" %s>%s</text>' % (tc, FONT, text_ko) + \
        '<text x="100" y="114" font-size="20" font-weight="700" text-anchor="middle" fill="%s" font-family="sans-serif">%s</text>' % (tc, text_en)


def instruct(inner, shape="circle"):   # 지시표지: 파란 원(또는 사각) · 흰 기호
    if shape == "square":
        s = '<rect x="14" y="14" width="172" height="172" rx="10" fill="%s" stroke="%s" stroke-width="4"/>' % (BLU, WHT)
    else:
        s = '<circle cx="100" cy="100" r="88" fill="%s" stroke="%s" stroke-width="4"/>' % (BLU, WHT)
    return s + '<g transform="translate(100,100)">%s</g>' % inner


def aux(text, sub=""):         # 보조표지: 흰 사각형 · 검은 글자
    s = '<rect x="6" y="56" width="188" height="88" rx="6" fill="%s" stroke="%s" stroke-width="5"/>' % (WHT, BLK)
    fs = 30 if len(text) <= 6 else 24
    s += '<text x="100" y="%d" font-size="%d" font-weight="700" text-anchor="middle" fill="%s" %s>%s</text>' % (106 if not sub else 96, fs, BLK, FONT, html.escape(text))
    if sub:
        s += '<text x="100" y="128" font-size="20" text-anchor="middle" fill="%s" %s>%s</text>' % (BLK, FONT, html.escape(sub))
    return s


def road_mark(inner):          # 노면표시: 회색 도로 위 표시
    return '<rect x="0" y="0" width="200" height="200" fill="#6b7280"/>' + inner


# ---------- 기호 조각 (원점 기준) ----------
def arrow(d, color=WHT, w=16):
    return '<path d="%s" fill="none" stroke="%s" stroke-width="%d" stroke-linecap="round" stroke-linejoin="round"/>' % (d, color, w)


def head(x, y, ang, color=WHT, s=22):
    return '<polygon points="0,%d %d,%d %d,%d" fill="%s" transform="translate(%s,%s) rotate(%s)"/>' % (-s, s * 0.8, s * 0.3, -s * 0.8, s * 0.3, color, x, y, ang)


def text(t, size=44, color=BLK, y=0, weight=700):
    return '<text x="0" y="%s" font-size="%s" font-weight="%s" text-anchor="middle" dominant-baseline="central" fill="%s" %s>%s</text>' % (y, size, weight, color, FONT, html.escape(t))


def car_icon(color=BLK, sx=1.0):
    return '<g transform="scale(%s)"><rect x="-34" y="-14" width="68" height="26" rx="6" fill="%s"/><rect x="-20" y="-30" width="40" height="18" rx="5" fill="%s"/>' \
        '<circle cx="-20" cy="14" r="8" fill="%s"/><circle cx="20" cy="14" r="8" fill="%s"/></g>' % (sx, color, color, color, color)


def truck_icon(color=BLK):
    return '<rect x="-40" y="-26" width="50" height="38" fill="%s"/><rect x="12" y="-14" width="26" height="26" rx="3" fill="%s"/>' \
        '<circle cx="-24" cy="16" r="8" fill="%s"/><circle cx="24" cy="16" r="8" fill="%s"/>' % (color, color, color, color)


def bus_icon(color=BLK):
    return '<rect x="-42" y="-26" width="84" height="40" rx="6" fill="%s"/><rect x="-34" y="-20" width="68" height="12" fill="%s"/>' \
        '<circle cx="-24" cy="16" r="8" fill="%s"/><circle cx="24" cy="16" r="8" fill="%s"/>' % (color, YEL if color == BLK else BLU, color, color)


def person(color=BLK, x=0, s=1.0):
    return '<g transform="translate(%s,0) scale(%s)"><circle cx="0" cy="-30" r="9" fill="%s"/>' \
        '<path d="M0,-20 L0,10 M0,10 L-12,34 M0,10 L12,34 M-14,-6 L14,-6" stroke="%s" stroke-width="7" stroke-linecap="round" fill="none"/></g>' % (x, s, color, color)


def bicycle(color=BLK):
    return '<circle cx="-24" cy="12" r="16" fill="none" stroke="%s" stroke-width="5"/><circle cx="24" cy="12" r="16" fill="none" stroke="%s" stroke-width="5"/>' \
        '<path d="M-24,12 L-6,-14 L18,-14 L24,12 M-6,-14 L4,12 L-24,12 M18,-14 L22,-24" stroke="%s" stroke-width="5" fill="none" stroke-linejoin="round"/>' % (color, color, color)


# ---------- 표지 목록: ID → (분류, 이름, SVG 본문) ----------
SIGNS = {}


def add(sid, kind, name, body):
    SIGNS[sid] = (kind, name, body)


# 주의표지 (caution)
add("c-crossroad", "주의", "+자형 교차로", caution(arrow("M0,-52 L0,40 M-44,-6 L44,-6", BLK, 18)))
add("c-t-junction", "주의", "T자형 교차로", caution(arrow("M-44,-30 L44,-30 M0,-30 L0,40", BLK, 18)))
add("c-y-junction", "주의", "Y자형 교차로", caution(arrow("M0,40 L0,0 L-30,-44 M0,0 L30,-44", BLK, 18)))
add("c-merge-right", "주의", "우합류 도로", caution(arrow("M-10,40 L-10,-50 M28,40 L-8,-10", BLK, 16)))
add("c-roundabout", "주의", "회전형 교차로", caution("".join(
    '<g transform="rotate(%d,0,-4)"><path d="M-20,-24 A30,30 0 0 1 22,-22" fill="none" stroke="%s" stroke-width="9"/>%s</g>' % (a, BLK, head(28, -16, 140, BLK, 12))
    for a in (0, 120, 240))))
add("c-railway", "주의", "철길 건널목", caution(
    '<rect x="-44" y="-14" width="58" height="30" rx="3" fill="%s"/><rect x="14" y="-36" width="30" height="52" rx="3" fill="%s"/>'
    '<rect x="-34" y="-30" width="10" height="16" fill="%s"/><rect x="20" y="-30" width="18" height="12" fill="%s"/>'
    '<rect x="-48" y="16" width="96" height="6" fill="%s"/><circle cx="-30" cy="26" r="8" fill="%s"/><circle cx="-6" cy="26" r="8" fill="%s"/><circle cx="28" cy="26" r="8" fill="%s"/>'
    % (BLK, BLK, BLK, YEL, BLK, BLK, BLK, BLK)))
add("c-curve-right", "주의", "우로 굽은 도로", caution(arrow("M-14,42 L-14,-6 Q-14,-34 18,-34", BLK, 16) + head(26, -34, 90, BLK, 16)))
add("c-curve-left", "주의", "좌로 굽은 도로", caution(arrow("M14,42 L14,-6 Q14,-34 -18,-34", BLK, 16) + head(-26, -34, -90, BLK, 16)))
add("c-two-way", "주의", "2방향 통행", caution(arrow("M-16,-40 L-16,30 M16,40 L16,-30", BLK, 12) + head(-16, 38, 180, BLK, 14) + head(16, -38, 0, BLK, 14)))
add("c-uphill", "주의", "오르막 경사", caution('<line x1="-50" y1="36" x2="44" y2="-24" stroke="%s" stroke-width="9" stroke-linecap="round"/>' % BLK + text("10%", 26, BLK, -24).replace('x="0"', 'x="-22"')))
add("c-downhill", "주의", "내리막 경사", caution('<line x1="-44" y1="-24" x2="50" y2="36" stroke="%s" stroke-width="9" stroke-linecap="round"/>' % BLK + text("10%", 26, BLK, -24).replace('x="0"', 'x="22"')))
add("c-narrow", "주의", "도로 폭이 좁아짐", caution(arrow("M-30,40 L-30,10 L-12,-10 L-12,-48 M30,40 L30,10 L12,-10 L12,-48", BLK, 10)))
add("c-slippery", "주의", "미끄러운 도로", caution(car_icon(BLK, 0.6).replace('<g transform="scale(0.6)">', '<g transform="translate(0,-26) scale(0.6)">') + arrow("M-30,10 Q-14,-6 0,10 T30,10 M-30,32 Q-14,16 0,32 T30,32", BLK, 6)))
add("c-falling-rocks", "주의", "낙석 도로", caution(
    '<path d="M10,-52 L22,-30 L30,-8 L40,16 L50,40" fill="none" stroke="%s" stroke-width="8" stroke-linejoin="round" stroke-linecap="round"/>' % BLK +
    "".join('<circle cx="%d" cy="%d" r="%d" fill="%s"/>' % (x, y, r, BLK) for x, y, r in ((6, -34, 4), (0, -20, 5), (-8, -4, 6), (-18, 14, 7), (-32, 32, 9)))))
add("c-children", "주의", "어린이 보호", caution(person(BLK, -18, 0.85) + person(BLK, 18, 0.7)))
add("c-pedestrian", "주의", "횡단보도", caution(person(BLK, 0, 0.9) + '<path d="M-48,40 L48,40" stroke="%s" stroke-width="6" stroke-dasharray="10 6"/>' % BLK))
add("c-bicycle", "주의", "자전거", caution('<g transform="translate(0,4) scale(0.95)">%s</g>' % bicycle(BLK)))
add("c-roadwork", "주의", "도로 공사 중", caution(person(BLK, -6, 0.9) + '<path d="M2,-4 L30,10 M10,20 L36,36" stroke="%s" stroke-width="7"/><polygon points="22,36 46,36 34,12" fill="%s"/>' % (BLK, BLK)))
add("c-crosswind", "주의", "횡풍", caution(
    '<rect x="-36" y="-50" width="6" height="92" fill="%s"/>' % BLK +
    '<polygon points="-30,-48 34,-38 34,-24 -30,-14" fill="%s"/>' % BLK +
    '<line x1="-8" y1="-44" x2="-8" y2="-18" stroke="%s" stroke-width="4"/><line x1="14" y1="-41" x2="14" y2="-21" stroke="%s" stroke-width="4"/>' % (YEL, YEL)))
add("c-tunnel", "주의", "터널", caution('<path d="M-46,40 L-46,-6 A46,46 0 0 1 46,-6 L46,40 L26,40 L26,0 A26,26 0 0 0 -26,0 L-26,40 Z" fill="%s"/>' % BLK))
add("c-signal", "주의", "신호기", caution('<rect x="-16" y="-48" width="32" height="88" rx="6" fill="%s"/><circle cx="0" cy="-30" r="9" fill="%s"/><circle cx="0" cy="-4" r="9" fill="%s"/><circle cx="0" cy="22" r="9" fill="#1e9e4a"/>' % (BLK, RED, YEL)))
add("c-danger", "주의", "위험", caution(text("위험", 38, BLK, -10) + text("DANGER", 16, BLK, 22).replace(FONT, 'font-family="Arial, sans-serif"')))
# 규제표지 (regulate)
add("r-no-entry-all", "규제", "통행금지", regulate(text("통행금지", 34, BLK)))
add("r-no-cars", "규제", "자동차 통행금지", regulate(car_icon(BLK, 0.9), slash=True))
add("r-no-trucks", "규제", "화물자동차 통행금지", regulate(truck_icon(BLK), slash=True))
add("r-no-buses", "규제", "승합자동차 통행금지", regulate(bus_icon(BLK), slash=True))
add("r-no-straight", "규제", "직진 금지", regulate(arrow("M0,46 L0,-30", BLK, 16) + head(0, -40, 0, BLK, 20), slash=True))
add("r-no-right", "규제", "우회전 금지", regulate(arrow("M-10,46 L-10,-6 Q-10,-24 10,-24 L22,-24", BLK, 16) + head(32, -24, 90, BLK, 20), slash=True))
add("r-no-left", "규제", "좌회전 금지", regulate(arrow("M10,46 L10,-6 Q10,-24 -10,-24 L-22,-24", BLK, 16) + head(-32, -24, -90, BLK, 20), slash=True))
add("r-no-uturn", "규제", "유턴 금지", regulate(arrow("M18,46 L18,-14 A18,18 0 0 0 -18,-14 L-18,10", BLK, 14) + head(-18, 20, 180, BLK, 18), slash=True))
add("r-no-overtake", "규제", "앞지르기 금지", regulate("".join(
    '<g transform="translate(%d,6)"><rect x="-20" y="-26" width="40" height="40" rx="7" fill="%s"/><rect x="-14" y="-20" width="28" height="12" rx="3" fill="%s"/>'
    '<rect x="-24" y="2" width="48" height="12" rx="4" fill="%s"/><rect x="-20" y="14" width="9" height="10" fill="%s"/><rect x="11" y="14" width="9" height="10" fill="%s"/></g>'
    % (x, c, WHT, c, BLK, BLK) for x, c in ((-26, RED), (26, BLK)))))
add("r-no-parking", "규제", "주차금지", regulate("", False).replace('fill="#ffffff"', 'fill="%s"' % BLU, 1) +
    '<line x1="40" y1="40" x2="160" y2="160" stroke="%s" stroke-width="14"/>' % RED +
    '<g transform="translate(100,100)">%s</g>' % text("주차금지", 28, WHT))
add("r-no-stopping", "규제", "정차·주차금지", regulate("", False).replace('fill="#ffffff"', 'fill="%s"' % BLU, 1) +
    '<line x1="40" y1="40" x2="160" y2="160" stroke="%s" stroke-width="14"/><line x1="160" y1="40" x2="40" y2="160" stroke="%s" stroke-width="14"/>' % (RED, RED) +
    '<rect x="38" y="84" width="124" height="32" rx="4" fill="%s"/>' % BLU + '<g transform="translate(100,100)">%s</g>' % text("주정차금지", 25, WHT))
add("r-speed-max-50", "규제", "최고속도 제한(50)", regulate(text("50", 76, BLK)))
add("r-speed-max-80", "규제", "최고속도 제한(80)", regulate(text("80", 76, BLK)))
add("r-speed-min-30", "규제", "최저속도 제한(30)", regulate(text("30", 76, BLK, -6) + '<line x1="-40" y1="40" x2="40" y2="40" stroke="%s" stroke-width="8"/>' % BLK))
add("r-weight-limit", "규제", "차중량 제한", regulate(text("5.5t", 54, BLK)))
add("r-height-limit", "규제", "차높이 제한", regulate(text("3.5m", 50, BLK) + head(0, -50, 180, BLK, 14) + head(0, 50, 0, BLK, 14)))
add("r-width-limit", "규제", "차폭 제한", regulate(text("2.2m", 40, BLK) + head(-62, 0, 90, BLK, 12) + head(62, 0, -90, BLK, 12)))
add("r-stop", "규제", "일시정지", '<polygon points="64,8 136,8 192,64 192,136 136,192 64,192 8,136 8,64" fill="%s"/>' % RED +
    '<polygon points="67,16 133,16 184,67 184,133 133,184 67,184 16,133 16,67" fill="none" stroke="%s" stroke-width="5"/>' % WHT +
    '<text x="100" y="100" font-size="50" font-weight="700" text-anchor="middle" fill="%s" %s>정지</text>' % (WHT, FONT) +
    '<text x="100" y="142" font-size="32" font-weight="700" text-anchor="middle" fill="%s" font-family="Arial, sans-serif">STOP</text>' % WHT)
add("r-slow", "규제", "서행", inverted("천천히", "SLOW"))
add("r-yield", "규제", "양보", inverted("양보", "YIELD"))
add("r-no-pedestrian", "규제", "보행자 보행금지", regulate(person(BLK, 0, 1.1), slash=True))
# 지시표지 (instruct)
add("i-motorway", "지시", "자동차 전용도로", instruct(
    '<g transform="translate(0,-14)"><rect x="-40" y="-8" width="80" height="30" rx="6" fill="%s"/><path d="M-30,-8 L-22,-30 L22,-30 L30,-8 Z" fill="%s"/>'
    '<rect x="-24" y="-26" width="48" height="14" fill="%s"/><circle cx="-26" cy="6" r="6" fill="%s"/><circle cx="26" cy="6" r="6" fill="%s"/>'
    '<rect x="-36" y="22" width="12" height="10" fill="%s"/><rect x="24" y="22" width="12" height="10" fill="%s"/></g>' % (WHT, WHT, BLU, BLU, BLU, WHT, WHT) +
    text("전용", 34, WHT, 46)))
add("i-bicycle-only", "지시", "자전거 전용도로", instruct('<g transform="translate(0,-16) scale(1.0)">%s</g>' % bicycle(WHT) + text("자전거전용", 24, WHT, 46)))
add("i-straight", "지시", "직진", instruct(arrow("M0,50 L0,-30", WHT, 18) + head(0, -42, 0)))
add("i-right", "지시", "우회전", instruct(arrow("M-14,50 L-14,-4 Q-14,-24 8,-24 L20,-24", WHT, 18) + head(32, -24, 90)))
add("i-left", "지시", "좌회전", instruct(arrow("M14,50 L14,-4 Q14,-24 -8,-24 L-20,-24", WHT, 18) + head(-32, -24, -90)))
add("i-straight-right", "지시", "직진 및 우회전", instruct(arrow("M-10,50 L-10,-30 M-10,6 Q-10,-14 12,-14 L22,-14", WHT, 16) + head(-10, -42, 0) + head(34, -14, 90)))
add("i-roundabout", "지시", "회전교차로", instruct("".join(
    '<g transform="rotate(%d)"><path d="M-24,-42 A48,48 0 0 0 -46,4" fill="none" stroke="%s" stroke-width="12"/>%s</g>' % (a, WHT, head(-44, 14, 200, WHT, 15))
    for a in (0, 120, 240))))
add("i-both-sides", "지시", "양측방 통행", instruct(arrow("M0,50 L0,10 L-30,-24 M0,10 L30,-24", WHT, 14) + head(-36, -32, -40, WHT, 18) + head(36, -32, 40, WHT, 18)))
add("i-uturn", "지시", "유턴", instruct(arrow("M18,50 L18,-10 A18,18 0 0 0 -18,-10 L-18,14", WHT, 14) + head(-18, 26, 180, WHT, 18)))
add("i-one-way", "지시", "일방통행", '<rect x="16" y="20" width="168" height="160" rx="10" fill="%s" stroke="%s" stroke-width="4"/>' % (WHT, BLK) +
    '<rect x="22" y="26" width="156" height="82" rx="6" fill="%s"/>' % BLU +
    '<polygon points="36,56 132,56 132,40 168,67 132,94 132,78 36,78" fill="%s"/>' % WHT +
    '<text x="100" y="158" font-size="34" font-weight="700" text-anchor="middle" fill="%s" %s>일방통행</text>' % (BLK, FONT))
add("i-crosswalk", "지시", "횡단보도", '<polygon points="100,10 190,84 190,190 10,190 10,84" fill="%s" stroke="%s" stroke-width="4" stroke-linejoin="round"/>' % (BLU, WHT) +
    '<g transform="translate(100,110)">' + "".join('<rect x="%d" y="18" width="12" height="16" fill="%s"/>' % (x, WHT) for x in (-58, -38, -18, 2, 22, 42)) +
    person(WHT, 4, 1.0).replace('translate(4,0)', 'translate(4,-12)') + '</g>' +
    '<g transform="translate(100,166)">%s</g>' % text("횡단보도", 24, WHT))
add("i-children", "지시", "어린이 보호", '<polygon points="100,10 190,84 190,190 10,190 10,84" fill="%s" stroke="%s" stroke-width="4" stroke-linejoin="round"/>' % (BLU, WHT) +
    '<g transform="translate(100,104)"><g transform="translate(-14,-4)">%s</g><g transform="translate(18,6) scale(0.72)">%s</g>' % (person(WHT, 0, 1.15), person(WHT, 0, 1.0)) +
    '<line x1="-2" y1="-8" x2="10" y2="-2" stroke="%s" stroke-width="5" stroke-linecap="round"/></g>' % WHT +
    '<g transform="translate(100,166)">%s</g>' % text("어린이보호", 24, WHT))
add("i-parking", "지시", "주차장", instruct(text("P", 110, WHT, 4), shape="square"))
add("i-bus-lane", "지시", "버스전용차로", '<rect x="14" y="14" width="172" height="172" rx="10" fill="%s" stroke="%s" stroke-width="4"/>' % (BLU, WHT) +
    '<rect x="26" y="22" width="10" height="156" fill="%s"/><rect x="164" y="22" width="10" height="156" fill="%s"/>' % (WHT, WHT) +
    '<g transform="translate(100,62) scale(0.8)">%s</g>' % bus_icon(WHT) + '<g transform="translate(100,104)">%s</g>' % text("전용", 28, WHT) +
    '<g transform="translate(100,0)">' + arrow("M0,124 L0,150", WHT, 12) + head(0, 160, 180, WHT, 16) + '</g>')
# 보조표지 (aux)
add("a-from-100m", "보조", "100m 앞부터", aux("100m 앞부터"))
add("a-time", "보조", "시간 (08:00~20:00)", aux("08:00~20:00"))
add("a-trucks", "보조", "화물자동차에 한함", aux("화물차에 한함"))
add("a-school-zone", "보조", "어린이보호구역 안", aux("어린이보호구역", "안"))
# 노면표시 (road_mark)
add("m-center-yellow", "노면", "중앙선 (황색 실선)", road_mark('<rect x="94" y="0" width="12" height="200" fill="%s"/>' % YEL))
add("m-center-double", "노면", "중앙선 (황색 복선)", road_mark('<rect x="84" y="0" width="10" height="200" fill="%s"/><rect x="106" y="0" width="10" height="200" fill="%s"/>' % (YEL, YEL)))
add("m-no-lane-change", "노면", "진로변경 제한선 (백색 실선)", road_mark('<rect x="94" y="0" width="12" height="200" fill="%s"/>' % WHT))
add("m-lane-dashed", "노면", "차선 (백색 점선)", road_mark('<line x1="100" y1="0" x2="100" y2="200" stroke="%s" stroke-width="12" stroke-dasharray="40 30"/>' % WHT))
add("m-crosswalk", "노면", "횡단보도", road_mark("".join('<rect x="%d" y="40" width="14" height="120" fill="%s"/>' % (x, WHT) for x in range(14, 200, 28))))
add("m-stop-line", "노면", "정지선", road_mark('<rect x="0" y="120" width="200" height="16" fill="%s"/>' % WHT))
add("m-no-stopping-zone", "노면", "정차금지지대", road_mark('<clipPath id="nsz"><rect x="30" y="40" width="140" height="120"/></clipPath>'
    '<g clip-path="url(#nsz)">' + "".join('<line x1="%d" y1="40" x2="%d" y2="160" stroke="%s" stroke-width="6"/>' % (x, x + 60, YEL) for x in range(-30, 200, 24)) + '</g>'
    '<rect x="30" y="40" width="140" height="120" fill="none" stroke="%s" stroke-width="8"/>' % YEL))
add("m-slow-text", "노면", "서행표시 (천천히)", road_mark('<text x="100" y="122" font-size="56" font-weight="700" text-anchor="middle" fill="%s" %s>천천히</text>' % (WHT, FONT)))
add("m-uturn-zone", "노면", "유턴구역선", road_mark('<line x1="100" y1="0" x2="100" y2="200" stroke="%s" stroke-width="12" stroke-dasharray="30 20"/>' % WHT))

KINDS = ["주의", "규제", "지시", "보조", "노면"]


def svg(sid, size=200):
    kind, name, body = SIGNS[sid]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="%d" height="%d" role="img" aria-label="%s">'
            '<title>%s</title>%s</svg>') % (size, size, html.escape(name), html.escape(name), body)


def group(sid, x, y, size=60):
    """다른 그림(장면) 안에 넣을 표지: 왼쪽 위 (x, y), 한 변 size"""
    return '<g transform="translate(%s,%s) scale(%s)">%s</g>' % (x, y, size / 200.0, SIGNS[sid][2])


def preview(out):
    rows = []
    for k in KINDS:
        items = [(sid, v) for sid, v in SIGNS.items() if v[0] == k]
        cells = "".join('<figure>%s<figcaption><b>%s</b><br><code>%s</code></figcaption></figure>' % (svg(sid, 120), html.escape(v[1]), sid) for sid, v in items)
        rows.append("<h2>%s표지 (%d)</h2><div class=g>%s</div>" % (k, len(items), cells))
    doc = ("<!doctype html><meta charset=utf-8><title>안전표지 도안 미리보기</title>"
           "<style>body{font-family:sans-serif;margin:24px}.g{display:flex;flex-wrap:wrap;gap:14px}figure{margin:0;width:140px;text-align:center;font-size:13px}"
           "figcaption{margin-top:4px}</style><h1>안전표지 도안 미리보기 (%d종)</h1>"
           "<p>도로교통법 시행규칙 별표 6의 도안과 모양·색·기호가 맞는지 대조하세요. 고칠 표지는 ID와 함께 알려 주세요.</p>%s") % (len(SIGNS), "".join(rows))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    return out


def main(argv):
    if len(argv) < 2 or argv[1] == "list":
        for k in KINDS:
            print("[%s] " % k + ", ".join("%s(%s)" % (sid, v[1]) for sid, v in SIGNS.items() if v[0] == k))
        print("합계 %d종" % len(SIGNS))
        return 0
    if argv[1] == "preview":
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = argv[2] if len(argv) > 2 else os.path.join(root, "검수", "표지_미리보기.html")
        print("저장:", preview(out))
        return 0
    if argv[1] == "render" and len(argv) >= 4:
        if argv[2] not in SIGNS:
            print("없는 표지 ID:", argv[2])
            return 1
        with open(argv[3], "w", encoding="utf-8") as f:
            f.write(svg(argv[2]))
        print("저장:", argv[3])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
