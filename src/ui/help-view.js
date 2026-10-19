/* 도움말·이용 안내 화면 (S7) – #/help */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var esc = CDME.util.escapeHtml;

  function renderHelp(ctx, active) {
    var bank = ctx.getBank();
    var cfg = bank ? bank.config.exam : CDME.questions.DEFAULT_CONFIG.exam;
    var total = cfg.subjects.reduce(function (a, s) { return a + s.count; }, 0);
    var cur = ctx.getFont();

    ctx.view.innerHTML = ctx.noticeHtml() +
      '<p><a href="#/' + (active ? 'home' : 'start') + '" class="back">← ' + (active ? '대시보드' : '처음 화면') + '</a></p>' +
      '<h1 class="page-title">도움말 · 이용 안내</h1>' +
      '<div class="help">' +

      '<section class="card"><h2>글자 크기</h2>' +
      '<div class="font-choices" role="group" aria-label="글자 크기">' +
      ctx.fonts.map(function (f) {
        return '<button type="button" class="btn btn-ghost" data-fontset="' + f.v + '" aria-pressed="' + (f.v === cur) + '">' + esc(f.name) + '</button>';
      }).join('') + '</div>' +
      '<p class="muted small">화면 맨 위의 <b>가+</b> 버튼으로도 바꿀 수 있습니다. 이 기기에 저장됩니다.</p></section>' +

      '<section class="card"><h2>사용 방법</h2><ul>' +
      '<li><b>실전 모의시험</b>: ' + total + '문항 · ' + cfg.minutes + '분, 과목별로 무작위 출제됩니다. 보기를 고르면 바로 정답·오답과 해설이 나오고, 고른 답은 바꿀 수 없습니다.</li>' +
      '<li>모든 문항을 풀면 <b>결과 보기</b>, 시간이 끝나면 자동으로 끝납니다. ' + cfg.pass_score + '점 이상이면 합격입니다.</li>' +
      '<li>시험 중 창을 닫아도 <b>이어 풀기</b>로 계속할 수 있습니다. 닫아 둔 동안은 시간이 흐르지 않습니다.</li>' +
      '<li>틀린 문제와 안 푼 문제는 <b>오답노트</b>에 자동으로 모입니다. <b>복습 재시험</b>에서 연속 2번 맞히면 복습 완료로 옮겨집니다.</li>' +
      '<li><b>내 기록</b>에서 점수 추이와 과목별 정답률을 볼 수 있습니다. 복습 성적은 실전 점수에 포함되지 않습니다.</li>' +
      '<li>막히면 답을 고르기 전에 <b>💡 힌트 보기</b>를 누르세요. 정답 대신 생각할 실마리를 알려 주고, 힌트가 없는 문제는 틀린 보기 하나를 지워 줍니다. 점수는 그대로이고 결과에 "힌트 사용"으로 표시됩니다.</li>' +
      '<li>키보드: 숫자 <b>1~4</b>로 답 선택, <b>H</b>로 힌트, <b>← →</b>로 문항 이동</li>' +
      '</ul></section>' +

      '<section class="card"><h2>기록 저장</h2><ul>' +
      '<li>회원가입이 없고, 기록은 <b>지금 쓰는 기기의 브라우저</b>에만 저장됩니다. 개인정보를 수집하지 않습니다.</li>' +
      '<li>브라우저 데이터를 지우거나 시크릿 모드를 쓰면 기록이 사라집니다.</li>' +
      '<li>다른 기기로 옮기려면 <a href="#/data">기록 관리</a>에서 백업 파일을 만들어 그 기기에서 불러오세요.</li>' +
      '<li>한 기기에서 여러 사람이 쓸 때는 닉네임을 따로 만들면 기록이 섞이지 않습니다.</li>' +
      '</ul></section>' +

      '<section class="card"><h2>휴대폰에서 앱처럼 쓰기</h2><ul>' +
      '<li>안드로이드(크롬·삼성 인터넷): 메뉴 → <b>홈 화면에 추가</b> 또는 <b>앱 설치</b></li>' +
      '<li>아이폰(사파리): 공유 버튼 → <b>홈 화면에 추가</b></li>' +
      '<li>한 번 접속한 뒤에는 <b>인터넷이 끊겨도</b> 시험을 계속 풀 수 있습니다. 문제가 새로 추가되면 인터넷에 연결됐을 때 자동으로 받아옵니다.</li>' +
      '</ul></section>' +

      '<section class="card"><h2>안내</h2><ul>' +
      '<li>이 프로그램은 <b>비공식 학습용</b>입니다. 시험 규정·출제 기준은 한국교통안전공단 공지를 확인하세요.</li>' +
      (bank && bank.config.data_date ? '<li>문제 기준일: <b>' + esc(bank.config.data_date) + '</b> (이 날짜 기준 법령·자료로 작성. 이후 개정 내용은 반영되지 않았을 수 있습니다)</li>' : '') +
      '<li>문제는 출제 범위(관련 법령·기준)를 바탕으로 새로 작성하고 검수한 문제이며, 문제마다 출처와 기준 법령을 기록합니다.</li>' +
      '<li>법령이 바뀌면 정답이 달라질 수 있습니다. 잘못된 문제는 해설 아래 <b>오류 신고</b>로 알려 주세요.</li>' +
      '</ul></section>' +
      '</div>';

    ctx.view.querySelectorAll('[data-fontset]').forEach(function (b) {
      b.onclick = function () { ctx.setFont(b.getAttribute('data-fontset')); ctx.render(); };
    });
  }

  CDME.views = CDME.views || {};
  CDME.views.help = renderHelp;
})(window);
