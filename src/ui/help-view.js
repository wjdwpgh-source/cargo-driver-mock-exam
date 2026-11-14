/* 도움말·이용 안내 화면 (S7) – #/help */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var esc = CDME.util.escapeHtml;

  var BANK_URL = 'https://www.safedriving.or.kr/notice/rerBankList.do?menuCode=MN-PO-1151';
  var helpTab = null;   // 시험별 안내에서 고른 시험 (처음은 지금 시험)

  // 시험별 안내 (v2.0 L3, FR-L14)
  function examGuideHtml(rawCfg, kind) {
    var c = CDME.questions.normalizeConfig(rawCfg || {}, kind);
    var e = c.exam;
    var total = e.subjects.reduce(function (a, x) { return a + x.count; }, 0);
    var gl = e.group_label || '과목';
    var rows = e.subjects.map(function (g) {
      var form = g.choices ? g.choices + '지 ' + (g.answers || 1) + '답' : '4지 1답';
      return '<tr><td>' + esc(g.name) + '</td><td class="num">' + g.count + '</td><td>' + esc(form) + '</td></tr>';
    }).join('');
    var common = '<div class="table-wrap" tabindex="0" role="region" aria-label="표 (좌우로 밀어 볼 수 있음)"><table class="table"><caption class="sr-only">' + esc(e.name) + ' 출제 구성</caption>' +
      '<thead><tr><th scope="col">' + esc(gl) + '</th><th scope="col" class="num">문항</th><th scope="col">형식</th></tr></thead><tbody>' + rows +
      '<tr class="total"><td>합계</td><td class="num">' + total + '</td><td>' + e.minutes + '분</td></tr></tbody></table></div>';
    if (kind === 'license') {
      return common + '<ul>' +
        '<li>100점 만점 · <b>' + e.pass_score + '점 이상 합격</b>(' + Math.ceil(total * e.pass_score / 100) + '문항 이상 정답). 1종 보통·대형·특수 학과시험은 같은 문제은행에서 출제되며, 1종은 70점, 2종은 60점이 합격선입니다.</li>' +
        '<li><b>학습용 점수</b>: 이 프로그램은 모든 문항을 2.5점으로 계산합니다. 실제 시험은 유형별 배점이 다를 수 있습니다.</li>' +
        '<li><b>정답 2개 문항</b>: 보기 두 개를 모두 골라야 채점되고, 둘 다 맞아야 정답입니다(부분 점수 없음). 첫 번째 선택은 다시 눌러 취소할 수 있습니다.</li>' +
        '<li>실제 시험의 <b>사진형·동영상형</b> 자리는 이 프로그램에서 <b>일러스트형</b> 문항으로 대신 출제합니다. 그림을 누르면 크게 볼 수 있습니다.</li>' +
        '<li>1종 대형면허는 만 19세 이상이고, 이륜자동차를 뺀 자동차 운전경험이 1년 이상이어야 응시할 수 있습니다(도로교통법 제82조). 응시 전 도로교통공단 안내로 확인하세요.</li>' +
        '<li>실제 학과시험은 <b>도로교통공단이 공개한 문제은행</b>에서 출제됩니다. 이 프로그램의 문제는 출제 범위를 바탕으로 새로 작성한 연습 문제이므로, <a href="' + BANK_URL + '" target="_blank" rel="noopener">공단 학과시험 문제은행</a>도 함께 보세요.</li>' +
        (e.data_date ? '<li>문제 기준일: <b>' + esc(e.data_date) + '</b></li>' : '') +
        '</ul>';
    }
    return common + '<ul>' +
      '<li>4지선다 · 100점 만점 · <b>' + e.pass_score + '점 이상 합격</b>(' + Math.ceil(total * e.pass_score / 100) + '문항 이상 정답)</li>' +
      '<li>시험 규정·출제 기준은 한국교통안전공단 공지를 확인하세요.</li>' +
      (e.data_date ? '<li>문제 기준일: <b>' + esc(e.data_date) + '</b></li>' : '') +
      '</ul>';
  }

  function renderHelp(ctx, active) {
    var bank = ctx.getBank();
    var cfg = bank ? bank.config.exam : CDME.questions.normalizeConfig({}, ctx.store.exam).exam;
    var tab = helpTab && CDME.questions.EXAM_KINDS.indexOf(helpTab) >= 0 ? helpTab : ctx.store.exam;
    var gl = cfg.group_label || '과목';
    var agency = cfg.id_prefix === 'DL' ? '도로교통공단' : '한국교통안전공단';
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

      '<section class="card"><h2>시험별 안내</h2>' +
      '<div class="tabs" role="group" aria-label="시험 선택">' +
      CDME.questions.EXAM_KINDS.map(function (k) {
        var on = k === tab;
        return '<button type="button" class="tab' + (on ? ' on' : '') + '" data-help-exam="' + k + '" aria-pressed="' + on + '">' + esc(CDME.questions.examName(k, bank && bank.config)) + '</button>';
      }).join('') + '</div>' +
      '<div id="help-exam">' + examGuideHtml(bank && bank.config, tab) + '</div></section>' +

      '<section class="card"><h2>시험 고르기</h2><ul>' +
      '<li>면허문제의 모든것은 <b>화물운송종사자격</b>과 <b>대형운전면허(1종) 학과</b> 두 시험을 지원합니다. 지금 시험: <b>' + esc(cfg.name || '') + '</b></li>' +
      '<li>화면 위의 시험 배지나 대시보드의 <b>시험 바꾸기</b>로 언제든 바꿀 수 있습니다. 닉네임은 같이 쓰고, 기록·오답노트·북마크는 시험별로 따로 저장됩니다.</li>' +
      '</ul></section>' +

      '<section class="card"><h2>사용 방법</h2><ul>' +
      '<li><b>실전 모의시험</b>: ' + total + '문항 · ' + cfg.minutes + '분, ' + esc(gl) + '별로 무작위 출제됩니다. 보기를 고르면 바로 정답·오답과 해설이 나오고, 고른 답은 바꿀 수 없습니다.</li>' +
      '<li>모든 문항을 풀면 <b>결과 보기</b>, 시간이 끝나면 자동으로 끝납니다. ' + cfg.pass_score + '점 이상이면 합격입니다.</li>' +
      '<li>시험 중 창을 닫아도 <b>이어 풀기</b>로 계속할 수 있습니다. 닫아 둔 동안은 시간이 흐르지 않습니다.</li>' +
      '<li>틀린 문제와 안 푼 문제는 <b>오답노트</b>에 자동으로 모입니다. <b>복습 재시험</b>에서 연속 2번 맞히면 복습 완료로 옮겨집니다.</li>' +
      '<li><b>내 기록</b>에서 점수 추이와 ' + esc(gl) + '별 정답률을 볼 수 있습니다. 복습 성적은 실전 점수에 포함되지 않습니다.</li>' +
      '<li>막히면 답을 고르기 전에 <b>💡 힌트 보기</b>를 누르세요. 정답 대신 생각할 실마리를 알려 주고, 힌트가 없는 문제는 틀린 보기 하나를 지워 줍니다. 점수는 그대로이고 결과에 "힌트 사용"으로 표시됩니다.</li>' +
      '<li><b>집중 학습</b>: ' + esc(gl) + '(여러 개)·난이도·문항 수를 골라 바로 해설을 보며 풉니다. 틀린 문제는 오답노트에 담기고, 실전 점수에는 들어가지 않습니다.</li>' +
      '<li><b>☆ 북마크</b>: 시험·복습·학습·결과 화면에서 다시 보고 싶은 문제를 담아 두고, <a href="#/bookmarks">북마크한 문제</a>만 모아 풀 수 있습니다.</li>' +
      '<li><b>취약 ' + esc(gl) + ' 분석</b>: 최근 실전 5회의 ' + esc(gl) + '별 정답률을 합격선(' + cfg.pass_score + '%)과 비교해 부족한 ' + esc(gl) + '을 알려 주고, 집중 학습으로 연결합니다.</li>' +
      '<li>키보드: 숫자 <b>1~4</b>(5지 문항은 1~5)로 답 선택, <b>H</b>로 힌트, <b>← →</b>로 문항 이동</li>' +
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
      '<li>이 프로그램은 <b>비공식 학습용</b>입니다. 시험 규정·출제 기준은 ' + agency + ' 공지를 확인하세요.</li>' +
      (cfg.score_note ? '<li>' + esc(cfg.score_note) + ' – 실제 시험은 유형별 배점이 다를 수 있습니다.</li>' : '') +
      (bank && bank.config.data_date ? '<li>문제 기준일: <b>' + esc(bank.config.data_date) + '</b> (이 날짜 기준 법령·자료로 작성. 이후 개정 내용은 반영되지 않았을 수 있습니다)</li>' : '') +
      '<li>문제는 출제 범위(관련 법령·기준)를 바탕으로 새로 작성하고 검수한 문제이며, 문제마다 출처와 기준 법령을 기록합니다.</li>' +
      '<li>법령이 바뀌면 정답이 달라질 수 있습니다. 잘못된 문제는 해설 아래 <b>오류 신고</b>로 알려 주세요.</li>' +
      '</ul></section>' +
      '</div>';

    ctx.view.querySelectorAll('[data-help-exam]').forEach(function (b) {
      b.onclick = function () {
        helpTab = b.getAttribute('data-help-exam');
        ctx.view.querySelectorAll('[data-help-exam]').forEach(function (x) { var on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on); });
        document.getElementById('help-exam').innerHTML = examGuideHtml(bank && bank.config, helpTab);
      };
    });
    ctx.view.querySelectorAll('[data-fontset]').forEach(function (b) {
      b.onclick = function () { ctx.setFont(b.getAttribute('data-fontset')); ctx.render(); };
    });
  }

  CDME.views = CDME.views || {};
  CDME.views.help = renderHelp;
})(window);
