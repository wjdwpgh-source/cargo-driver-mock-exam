/* 내 기록 화면 (S4: FR-501~505)
 * - 요약(응시 횟수·평균·최고·합격률), 점수 추이 그래프(최근 20회, 합격선 표시), 과목별 평균 정답률, 응시 이력
 * - 그래프는 외부 라이브러리 없이 SVG로 그려 오프라인에서도 동작
 */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var esc = CDME.util.escapeHtml, fmt = CDME.util.formatDate;
  var SVGNS = 'http://www.w3.org/2000/svg';

  function subjectShort(code) {
    return { LAW: '법규', CARGO: '화물취급요령', SAFE: '안전운행', SERVICE: '운송서비스' }[code] || code;
  }

  function stat(label, value, sub) {
    return '<div class="stat"><span class="stat-label">' + esc(label) + '</span><span class="stat-value">' + esc(value) + '</span>' +
      (sub ? '<span class="stat-sub">' + esc(sub) + '</span>' : '') + '</div>';
  }

  function el(name, attrs, parent) {
    var e = document.createElementNS(SVGNS, name);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }

  /* ---------- 점수 추이 (선 그래프, 단일 계열) ---------- */
  function drawTrend(box, trend, passScore, onOpen) {
    box.innerHTML = '';
    var W = Math.max(280, box.clientWidth || 320), H = 220;
    var m = { l: 34, r: 12, t: 14, b: 28 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var n = trend.length;
    function x(i) { return m.l + (n === 1 ? iw / 2 : iw * i / (n - 1)); }
    function y(v) { return m.t + ih * (1 - v / 100); }

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: '100%', height: H, role: 'group',
      'aria-label': '최근 ' + n + '회 점수 추이 그래프. 자세한 값은 아래 응시 이력 표에 있습니다.' }, null);
    svg.classList.add('trend-svg');

    // 격자·눈금 (0, 20 … 100)
    [0, 20, 40, 60, 80, 100].forEach(function (v) {
      el('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: 'grid' }, svg);
      var t = el('text', { x: m.l - 6, y: y(v) + 4, class: 'axis-label', 'text-anchor': 'end' }, svg);
      t.textContent = v;
    });
    // 합격선
    el('line', { x1: m.l, x2: W - m.r, y1: y(passScore), y2: y(passScore), class: 'pass-line' }, svg);
    var pl = el('text', { x: W - m.r, y: y(passScore) - 5, class: 'pass-label', 'text-anchor': 'end' }, svg);
    pl.textContent = '합격선 ' + passScore + '점';

    // x축 회차 라벨 (처음·끝, 많으면 일부만)
    var step = n <= 10 ? 1 : n <= 20 ? 2 : 5;
    trend.forEach(function (d, i) {
      if (i % step !== 0 && i !== n - 1) return;
      var t = el('text', { x: x(i), y: H - 8, class: 'axis-label', 'text-anchor': 'middle' }, svg);
      t.textContent = d.no + '회';
    });

    // 선 + 점
    if (n > 1) {
      el('polyline', { points: trend.map(function (d, i) { return x(i) + ',' + y(d.score); }).join(' '), class: 'trend-line' }, svg);
    }
    var cross = el('line', { y1: m.t, y2: m.t + ih, class: 'crosshair', visibility: 'hidden' }, svg);
    var dots = trend.map(function (d, i) {
      return el('circle', { cx: x(i), cy: y(d.score), r: 5, class: 'trend-dot' + (d.passed ? '' : ' fail') }, svg);
    });
    // 마지막 점 값 라벨 (선택적 직접 라벨)
    var lastD = trend[n - 1];
    var lv = el('text', { x: x(n - 1), y: y(lastD.score) - 10, class: 'value-label', 'text-anchor': n === 1 ? 'middle' : 'end' }, svg);
    lv.textContent = lastD.score + '점';

    // 넓은 히트 영역 + 가장 가까운 회차로 스냅하는 크로스헤어·툴팁
    var hit = el('rect', { x: m.l - 10, y: 0, width: iw + 20, height: H, fill: 'transparent', tabindex: '0', role: 'slider',
      'aria-label': '점수 그래프. 좌우 화살표로 회차를 살펴볼 수 있습니다.',
      'aria-valuemin': '1', 'aria-valuemax': String(n), 'aria-valuenow': String(n),
      'aria-valuetext': trend[n - 1].no + '회차 ' + trend[n - 1].score + '점' }, svg);
    box.appendChild(svg);
    var tip = document.createElement('div');
    tip.className = 'chart-tip';
    tip.hidden = true;
    box.appendChild(tip);

    var cur = -1;
    function show(i) {
      cur = i;
      var d = trend[i];
      hit.setAttribute('aria-valuenow', String(i + 1));
      hit.setAttribute('aria-valuetext', d.no + '회차 ' + d.score + '점 ' + (d.passed ? '합격' : '불합격'));
      cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i));
      cross.setAttribute('visibility', 'visible');
      dots.forEach(function (c, k) { c.classList.toggle('on', k === i); });
      tip.textContent = '';
      var v = document.createElement('strong'); v.textContent = d.score + '점';
      var s = document.createElement('span'); s.textContent = (d.passed ? '합격' : '불합격') + ' · ' + d.no + '회차';
      var t = document.createElement('span'); t.className = 'muted'; t.textContent = fmt(d.at);
      tip.appendChild(v); tip.appendChild(s); tip.appendChild(t);
      tip.hidden = false;
      var px = x(i) / W * box.clientWidth;
      var tw = tip.offsetWidth;
      tip.style.left = Math.min(Math.max(0, px - tw / 2), box.clientWidth - tw) + 'px';
      tip.style.top = Math.max(0, y(d.score) / H * svg.getBoundingClientRect().height - tip.offsetHeight - 14) + 'px';
    }
    function hide() {
      cur = -1; tip.hidden = true; cross.setAttribute('visibility', 'hidden');
      dots.forEach(function (c) { c.classList.remove('on'); });
    }
    function nearest(evt) {
      var r = svg.getBoundingClientRect();
      var px = (evt.clientX - r.left) / r.width * W;
      var best = 0, bd = Infinity;
      for (var i = 0; i < n; i++) { var dd = Math.abs(x(i) - px); if (dd < bd) { bd = dd; best = i; } }
      return best;
    }
    hit.addEventListener('pointermove', function (e) { show(nearest(e)); });
    hit.addEventListener('pointerleave', hide);
    hit.addEventListener('click', function (e) { var i = nearest(e); if (cur === i && onOpen) onOpen(trend[i]); else show(i); });
    hit.addEventListener('focus', function () { show(n - 1); });
    hit.addEventListener('blur', hide);
    hit.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { e.preventDefault(); show(Math.max(0, (cur < 0 ? n - 1 : cur) - 1)); }
      if (e.key === 'ArrowRight') { e.preventDefault(); show(Math.min(n - 1, (cur < 0 ? n - 1 : cur) + 1)); }
      if (e.key === 'Enter' && cur >= 0 && onOpen) onOpen(trend[cur]);
    });
  }

  /* ---------- 화면 ---------- */
  function renderRecords(ctx, active) {
    var view = ctx.view, store = ctx.store, bank = ctx.getBank();
    var cfg = bank ? bank.config.exam : CDME.questions.DEFAULT_CONFIG.exam;
    var d = store.getProfileData(active.id) || { exams: [] };
    var sample = ctx.sampleMode();
    var r = CDME.records.summarize(d.exams, sample, cfg);

    var head = ctx.noticeHtml() +
      '<p><a href="#/home" class="back">← 대시보드</a></p>' +
      '<h1 class="page-title">내 기록' + (sample ? ' <span class="tag tag-wait">샘플</span>' : '') + '</h1>';

    if (!r.count) {
      view.innerHTML = head + '<section class="card empty-card"><p>아직 응시한 실전 모의시험이 없습니다.</p>' +
        '<a class="btn btn-primary" href="#/home">시험 보러 가기</a>' +
        '<p class="small" style="margin-top:12px">다른 기기의 기록이 있다면 <a href="#/data">백업 불러오기</a></p></section>';
      return;
    }

    var subjRows = r.subjects.map(function (s) {
      var low = s.avg !== null && s.avg < cfg.pass_score;
      return '<tr><th scope="row">' + esc(subjectShort(s.code)) +
        (low ? '<br><span class="tag tag-bad">보완 필요</span>' : '') + '</th>' +
        '<td class="num">' + (s.avg === null ? '-' : s.avg + '%') + '</td>' +
        '<td class="bar-cell"><span class="hbar" style="width:' + (s.avg || 0) + '%" title="' + esc(s.name + ' ' + (s.avg || 0) + '%') + '"></span>' +
        '<span class="hbar-pass" style="left:' + cfg.pass_score + '%"></span></td></tr>';
    }).join('');

    var hist = r.history.map(function (h) {
      var e = h.exam, mm = Math.floor(e.durationSec / 60);
      return '<li class="hist-row"><a class="hist-item" href="#/result?id=' + encodeURIComponent(e.id) + '">' +
        '<span class="hist-no">' + h.no + '회</span>' +
        '<span class="hist-main"><span class="hist-date">' + esc(fmt(e.finishedAt)) + '</span>' +
        '<span class="muted small">정답 ' + e.correct + '/' + e.total + ' · ' + mm + '분' + (e.timedOut ? ' · 시간 종료' : '') + '</span></span>' +
        '<span class="hist-score"><b>' + e.score + '</b>점</span>' +
        '<span class="tag ' + (e.passed ? 'tag-ok' : 'tag-bad') + '">' + (e.passed ? '합격' : '불합격') + '</span>' +
        '</a><button type="button" class="hist-del" data-del="' + esc(e.id) + '" data-no="' + h.no + '" aria-label="' + h.no + '회 기록 삭제" title="이 기록 삭제">✕</button></li>';
    }).join('');

    view.innerHTML = head +
      '<section class="stats stats-4" aria-label="실전 성적 요약">' +
      stat('응시 횟수', r.count + '회') +
      stat('평균 점수', r.avg + '점') +
      stat('최고 점수', r.best + '점') +
      stat('합격률', r.passRate + '%', r.passCount + '/' + r.count + '회') +
      '</section>' +
      '<section class="card"><h2>점수 추이 <span class="muted small">최근 ' + r.trend.length + '회</span></h2>' +
      '<div class="chart-box" id="trend"></div>' +
      '<p class="muted small chart-note">점을 누르면 회차 정보가 나오고, 한 번 더 누르면 그 시험 결과로 이동합니다.</p></section>' +
      '<section class="card"><h2>과목별 평균 정답률</h2>' +
      '<div class="table-wrap" tabindex="0" role="region" aria-label="표 (좌우로 밀어 볼 수 있음)"><table class="table subj-table"><caption class="sr-only">과목별 평균 정답률 (세로선은 합격선 ' + cfg.pass_score + '%)</caption>' +
      '<thead><tr><th scope="col">과목</th><th scope="col" class="num">정답률</th><th scope="col"><span class="sr-only">막대</span></th></tr></thead>' +
      '<tbody>' + subjRows + '</tbody></table></div>' +
      '<p class="muted small">세로선은 합격선(' + cfg.pass_score + '%)입니다. 실제 시험은 총점으로 합격을 판정합니다.</p></section>' +
      '<section class="card"><h2>응시 이력 <span class="muted small">최신순 · 누르면 다시보기</span></h2>' +
      '<ul class="hist-list">' + hist + '</ul></section>' +
      '<p class="muted small center">복습 재시험 기록은 실전 성적에 포함되지 않습니다.</p>' +
      '<p class="center"><a class="btn btn-ghost" href="#/data">기록 관리 (백업 · 불러오기 · 초기화)</a></p>';

    // 개별 실전 기록 삭제 (FR-801)
    view.querySelectorAll('[data-del]').forEach(function (b) {
      b.onclick = function () {
        var id = b.getAttribute('data-del');
        var ex = (store.getProfileData(active.id).exams || []).filter(function (e) { return e.id === id; })[0];
        if (!ex) return;
        CDME.modal.confirm({
          title: b.getAttribute('data-no') + '회 기록 삭제', danger: true, okText: '삭제',
          message: esc(fmt(ex.finishedAt)) + ' · ' + ex.score + '점 기록을 삭제합니다.<br>오답노트에 등록된 문제는 그대로 남습니다. 삭제한 기록은 되돌릴 수 없습니다.'
        }).then(function (ok) {
          if (!ok) return;
          store.updateProfileData(active.id, function (dd) { CDME.backup.deleteExam(dd, id); });
          CDME.ui.toast('기록을 삭제했습니다.');
          ctx.render();
        });
      };
    });

    var box = document.getElementById('trend');
    function draw() { drawTrend(box, r.trend, cfg.pass_score, function (d) { ctx.go('result?id=' + encodeURIComponent(d.id)); }); }
    draw();
    var t = null;
    function onResize() { clearTimeout(t); t = setTimeout(draw, 150); }
    window.addEventListener('resize', onResize);
    ctx.setCleanup(function () { window.removeEventListener('resize', onResize); });
  }

  CDME.views = CDME.views || {};
  CDME.views.records = renderRecords;
})(window);
