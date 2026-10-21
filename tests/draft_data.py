"""브라우저 테스트용: 문제 데이터를 '검수 전(draft)' 상태로 바꿔서 보여 준다.
검수 미리보기·문제 부족 안내 등 verified 0 상태를 확인하는 테스트가 실제 검수 진행과 관계없이 돌도록 한다.
(Service Worker가 켜져 있으면 가로채기가 안 되므로 service_workers="block" 문맥에서 사용)
"""
import re

PAT = re.compile(r".*/data/questions/[A-Z]+\.json.*")


def dev_on(ctx):
    """공개 사이트에서 숨긴 개발·검수 모드를 테스트에서 쓸 수 있게 함 (= 주소에 ?dev=1)"""
    ctx.add_init_script("try { sessionStorage.setItem('cdme_dev', '1'); } catch (e) {}")


def as_drafts(ctx, dev=True):
    if dev:
        dev_on(ctx)
    def handle(route):
        try:
            resp = route.fetch()
            body = re.sub(r'"status":\s*"(verified|reviewed)"', '"status": "draft"', resp.text())
            route.fulfill(response=resp, body=body)
        except Exception:   # 화면을 닫는 중이라 응답이 사라진 경우 – 무시
            pass
    ctx.route(PAT, handle)
