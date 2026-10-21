/* 집중 학습·북마크 화면 (PRD 12.1, v1.1.0)
 * #/study           학습 설정 (과목 여러 개·난이도·범위(전체/북마크)·문항 수)  ?subject=LAW&src=bookmark 로 미리 선택
 * #/study-play      풀이 (즉시 해설, 복습 재시험과 같은 화면 – CDME.views.session)
 * #/study-result    학습 결과 (과목별 정답, 틀린 문제는 오답노트에 담김)
 * #/bookmarks       북마크한 문제 목록 (정답·해설 보기, 해제, 북마크 문제 풀기)
 */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var esc = CDME.util.escapeHtml, fmt = CDME.util.formatDate, S = CDME.study, modal = CDME.modal;
  var UI = CDME.ui;
  var CIRCLED = ['①', '②', '③', '④'];
  function short(code) { return UI.subjectShort(code); }

  function needBank(ctx) {
    if (ctx.getBank()) return true;
    ctx.view.innerHTML = '<p class="muted">문제 데이터를 불러오는 중…</p>';
    return false;
  }
  function pdata(ctx, active) { return ctx.store.getProfileData(active.id) || {}; }

  function filterLabel(f) {
    if (!f) return '집중 학습';
    var parts = [];
    parts.push(f.subjects && f.subjects.length && f.subjects.length < 4 ? f.subjects.map(short).join('·') : '전체 과목');
    if (f.difficulty) parts.push(S.DIFF_NAMES[f.difficulty]);
    if (f.source === 'bookmark') parts.push('북마크');
    return parts.join(' · ');
  }

  /* ================= 학습 설정 ================= */
  var setup = { subjects: [], difficulty: 0, source: 'all', count: 20, shuffle: false };

  function renderSetup(ctx, active) {
    if (!needBank(ctx)) return;
    var view = ctx.view, bank = ctx.getBank(), sample = ctx.sampleMode();
    var d = pdata(ctx, active);
    if (d.studyInProgress) {
      var sip = d.studyInProgress;
      view.innerHTML = ctx.noticeHtml() + '<p><a href="#/home" class="back">← 대시보드</a></p><h1 class="page-title">집중 학습</h1>' +
        '<section class="card resume"><h2>진행 중인 학습이 있습니다</h2><p class="small">' + esc(filterLabel(sip.filter)) + ' · ' +
        S.tally(sip).answered + ' / ' + sip.items.length + '문항 풀이</p>' +
        '<div class="row"><a class="btn btn-primary" href="#/study-play">이어 풀기</a><button type="button" class="btn btn-ghost" id="st-quit">그만하고 새로 시작</button></div></section>';
      document.getElementById('st-quit').onclick = function () { finishStudy(ctx, active, true, true); };
      return;
    }
    var p = ctx.params();
    var codes = bank.config.exam.subjects.map(function (s) { return s.code; });
    if (p.subject && codes.indexOf(p.subject) >= 0) setup.subjects = [p.subject];
    if (p.src === 'bookmark') setup.source = 'bookmark';
    if (p.src === 'all') setup.source = 'all';
    if (p.subject || p.src) history.replaceState(null, '', '#/study');

    var w = S.weakness(d.exams, sample, bank.config, 5);
    var recommend = w.weak.length
      ? '<p class="small">📊 최근 ' + w.count + '회 실전에서 합격선 아래인 과목: ' + w.weak.map(function (s) {
        return '<button type="button" class="link-btn" data-pick="' + s.code + '">' + esc(short(s.code)) + ' ' + s.rate + '%</button>';
      }).join(', ') + '</p>' : '';

    view.innerHTML = ctx.noticeHtml() +
      '<p><a href="#/home" class="back">← 대시보드</a></p>' +
      '<h1 class="page-title">집중 학습' + (sample ? ' <span class="tag tag-wait">샘플</span>' : '') + '</h1>' +
      '<form id="st-form">' +
      '<section class="card"><h2>과목</h2>' + recommend +
      '<div class="chips" role="group" aria-label="과목 (여러 개 선택 가능)" id="st-subj"></div>' +
      '<p class="muted small">여러 과목을 함께 고를 수 있습니다. 아무것도 고르지 않으면 전체 과목입니다.</p></section>' +
      '<section class="card"><h2>난이도</h2><div class="seg" role="radiogroup" aria-label="난이도" id="st-diff"></div></section>' +
      '<section class="card"><h2>문제 범위</h2><div class="opts" id="st-src"></div></section>' +
      '<section class="card"><h2>문항 수</h2><div class="seg" role="radiogroup" aria-label="문항 수">' +
      [10, 20, 40, 'all'].map(function (v) {
        return '<label class="seg-item"><input type="radio" name="count" value="' + v + '"' + (String(setup.count) === String(v) ? ' checked' : '') + '><span>' + (v === 'all' ? '전체' : v + '문항') + '</span></label>';
      }).join('') + '</div>' +
      '<label class="switch"><input type="checkbox" id="st-shuffle"' + (setup.shuffle ? ' checked' : '') + '><span>보기 순서 섞기</span></label></section>' +
      '<section class="card actions"><p class="small" id="st-avail" aria-live="polite"></p>' +
      '<p class="muted small">한 문제씩 풀 때마다 정답·해설이 나옵니다. 틀린 문제는 오답노트에 담기고, 학습 성적은 실전 점수에 포함되지 않습니다.</p>' +
      '<button type="submit" class="btn btn-primary btn-lg" id="st-start">학습 시작</button></section>' +
      '</form>';

    var form = document.getElementById('st-form');
    function paint() {
      var bm = pdata(ctx, active).bookmarks;
      var c = S.poolCounts(bank, setup, bm, sample);
      var all = setup.subjects.length === 0;
      document.getElementById('st-subj').innerHTML =
        '<button type="button" class="chip' + (all ? ' on' : '') + '" data-subj="" aria-pressed="' + all + '">전체</button>' +
        codes.map(function (code) {
          var on = setup.subjects.indexOf(code) >= 0;
          return '<button type="button" class="chip' + (on ? ' on' : '') + '" data-subj="' + code + '" aria-pressed="' + on + '">' + esc(short(code)) + ' <b>' + c.subject[code] + '</b></button>';
        }).join('');
      document.getElementById('st-diff').innerHTML = [0, 1, 2, 3].map(function (v) {
        return '<label class="seg-item"><input type="radio" name="diff" value="' + v + '"' + (setup.difficulty === v ? ' checked' : '') + '><span>' +
          (v ? S.DIFF_NAMES[v] : '전체') + ' <b>' + c.difficulty[v] + '</b></span></label>';
      }).join('');
      var cAll = S.poolCounts(bank, { subjects: setup.subjects, difficulty: setup.difficulty, source: 'all' }, bm, sample).total;
      document.getElementById('st-src').innerHTML =
        '<label class="opt"><input type="radio" name="src" value="all"' + (setup.source === 'all' ? ' checked' : '') + '><span class="opt-main"><span>전체 문제</span><span class="muted small">출제 가능한 모든 문제에서 무작위</span></span><b class="opt-count">' + cAll + '</b></label>' +
        '<label class="opt' + (c.bookmark ? '' : ' disabled') + '"><input type="radio" name="src" value="bookmark"' + (setup.source === 'bookmark' ? ' checked' : '') + (c.bookmark || setup.source === 'bookmark' ? '' : ' disabled') + '><span class="opt-main"><span>★ 북마크한 문제만</span><span class="muted small">풀면서 ☆ 북마크를 눌러 담은 문제</span></span><b class="opt-count">' + c.bookmark + '</b></label>';
      var n = c.total, want = setup.count === 'all' ? n : Math.min(n, setup.count);
      document.getElementById('st-avail').innerHTML = n ? '조건에 맞는 문제 <b>' + n + '</b>개 중 <b>' + want + '</b>문항을 풉니다.' : '<span class="danger-text">조건에 맞는 문제가 없습니다. 조건을 바꿔 보세요.</span>';
      document.getElementById('st-start').disabled = !n;
    }
    paint();

    form.addEventListener('click', function (e) {
      var b = e.target.closest('[data-subj]');
      if (b) {
        var code = b.getAttribute('data-subj');
        if (!code) setup.subjects = [];
        else {
          var i = setup.subjects.indexOf(code);
          if (i >= 0) setup.subjects.splice(i, 1); else setup.subjects.push(code);
          if (setup.subjects.length === codes.length) setup.subjects = [];
        }
        paint();
        var again = form.querySelector('[data-subj="' + code + '"]');
        if (again) again.focus();
        return;
      }
      var pk = e.target.closest('[data-pick]');
      if (pk) { setup.subjects = [pk.getAttribute('data-pick')]; paint(); }
    });
    form.addEventListener('change', function (e) {
      var t = e.target;
      if (t.name === 'diff') setup.difficulty = +t.value;
      if (t.name === 'src') setup.source = t.value;
      if (t.name === 'count') setup.count = t.value === 'all' ? 'all' : +t.value;
      if (t.id === 'st-shuffle') setup.shuffle = t.checked;
      paint();
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var st;
      try {
        st = S.buildStudy(bank, { filter: setup, count: setup.count, sample: sample, bookmarks: pdata(ctx, active).bookmarks, shuffleChoices: setup.shuffle });
      } catch (err) {
        modal.confirm({ title: '문제가 없습니다', message: '조건에 맞는 문제가 없습니다. 과목·난이도·범위를 바꿔 보세요.', okText: '확인', cancelText: '닫기' });
        return;
      }
      if (ctx.devKind()) st.kind = ctx.devKind();
      ctx.store.updateProfileData(active.id, function (dd) { dd.studyInProgress = st; });
      ctx.go('study-play');
    });
  }

  /* ================= 풀이 ================= */
  function finishStudy(ctx, active, quitEarly, stay) {
    var rec = null;
    ctx.store.updateProfileData(active.id, function (dd) {
      var st = dd.studyInProgress;
      if (!st) return;
      dd.studyInProgress = null;
      if (S.tally(st).answered === 0) return;
      rec = S.finish(st);
      if (st.kind) rec.kind = st.kind;
      rec.quit = !!quitEarly;
      if (!dd.studySessions) dd.studySessions = [];
      dd.studySessions.push(rec);
      if (dd.studySessions.length > 200) dd.studySessions = dd.studySessions.slice(-200);
    });
    document.querySelectorAll('.toast').forEach(function (t) { t.remove(); });
    if (stay) { ctx.render(); return; }
    if (rec) ctx.go('study-result?id=' + encodeURIComponent(rec.id)); else ctx.go('study');
  }

  var STUDY_KIND = {
    key: 'studyInProgress', back: 'study', title: '집중 학습', tag: '학습',
    answer: function (st, dd, bank, i, orig) { if (!dd.wrongNotes) dd.wrongNotes = {}; return S.answer(st, dd.wrongNotes, bank, i, orig); },
    tally: S.tally,
    finish: function (ctx, active, quit) { finishStudy(ctx, active, quit); },
    showDifficulty: true
  };
  function renderPlay(ctx, active) { CDME.views.session(ctx, active, STUDY_KIND); }

  /* ================= 결과 ================= */
  function renderResult(ctx, active) {
    if (!needBank(ctx)) return;
    var view = ctx.view, bank = ctx.getBank(), p = ctx.params();
    var d = pdata(ctx, active);
    var list = d.studySessions || [];
    var s = p.id ? list.filter(function (x) { return x.id === p.id; })[0] : list[list.length - 1];
    if (!s) { ctx.go('study'); return; }
    if (ctx.ensureKind(s)) return;
    var rate = s.answered ? Math.round(s.correct * 100 / s.answered) : 0;
    var rows = bank.config.exam.subjects.filter(function (x) { return s.bySubject && s.bySubject[x.code]; }).map(function (x) {
      var b = s.bySubject[x.code];
      return '<tr><th scope="row">' + esc(short(x.code)) + '</th><td class="num">' + b.correct + ' / ' + b.total + '</td><td class="num">' + Math.round(b.correct * 100 / b.total) + '%</td></tr>';
    }).join('');
    var wrong = (s.wrongIds || []).map(function (id) {
      var q = bank.byId[id];
      return q ? '<li><span class="tag tag-skip">' + esc(short(q.subject)) + '</span> ' + esc(q.question) + '</li>' : '';
    }).join('');
    view.innerHTML = ctx.noticeHtml() +
      '<h1 class="page-title">학습 결과</h1>' +
      '<section class="card result-hero ' + (rate >= 60 ? 'pass' : 'fail') + '"><span class="result-badge">' + esc(filterLabel(s.filter)) + '</span>' +
      '<span class="result-score"><b>' + s.correct + '</b> / ' + s.answered + '</span>' +
      '<span class="muted">정답 수 · 정답률 ' + rate + '%' + (s.quit && s.answered < s.total ? ' · 전체 ' + s.total + '문항 중 ' + s.answered + '문항 풀이' : '') + '</span>' +
      (s.hintCount ? '<span class="muted small">💡 힌트 사용 ' + s.hintCount + '문항</span>' : '') + '</section>' +
      (rows ? '<section class="card"><h2>과목별</h2><table class="table"><thead><tr><th scope="col">과목</th><th scope="col" class="num">정답</th><th scope="col" class="num">정답률</th></tr></thead><tbody>' + rows + '</tbody></table></section>' : '') +
      (wrong ? '<section class="card"><h2>틀린 문제 <b>' + s.wrongIds.length + '</b></h2><p class="muted small">오답노트에 담겼습니다.</p><ul class="q-mini">' + wrong + '</ul></section>' : '') +
      '<section class="card"><p class="muted small">학습 결과는 실전 점수·합격 통계에 포함되지 않습니다.</p></section>' +
      '<section class="card actions"><a class="btn btn-primary" href="#/study">한 번 더 학습</a>' +
      (s.wrongIds && s.wrongIds.length ? '<a class="btn btn-outline" href="#/notes">오답노트로</a>' : '') +
      '<a class="btn btn-ghost" href="#/home">대시보드로</a></section>';
  }

  /* ================= 북마크 목록 ================= */
  var bmState = { subject: '' };

  function renderBookmarks(ctx, active) {
    if (!needBank(ctx)) return;
    var view = ctx.view, bank = ctx.getBank(), sample = ctx.sampleMode();
    var d = pdata(ctx, active);
    var all = S.listBookmarks(d.bookmarks, bank, sample);
    var rows = bmState.subject ? all.filter(function (r) { return r.q.subject === bmState.subject; }) : all;
    var verifiedCount = all.filter(function (r) { return r.q.status === 'verified'; }).length;
    var chips = '<button type="button" class="chip' + (bmState.subject === '' ? ' on' : '') + '" data-bsubj="">전체 <b>' + all.length + '</b></button>' +
      bank.config.exam.subjects.map(function (s) {
        var n = all.filter(function (r) { return r.q.subject === s.code; }).length;
        return '<button type="button" class="chip' + (bmState.subject === s.code ? ' on' : '') + '" data-bsubj="' + s.code + '">' + esc(short(s.code)) + ' <b>' + n + '</b></button>';
      }).join('');

    view.innerHTML = ctx.noticeHtml() +
      '<p><a href="#/home" class="back">← 대시보드</a></p>' +
      '<h1 class="page-title">★ 북마크한 문제' + (sample ? ' <span class="tag tag-wait">샘플</span>' : '') + '</h1>' +
      '<section class="card actions">' +
      '<a class="btn btn-primary btn-lg' + (verifiedCount ? '' : ' disabled') + '" href="#/study?src=bookmark"' + (verifiedCount ? '' : ' aria-disabled="true" tabindex="-1"') + '>북마크 문제 풀기</a>' +
      '<p class="muted small">시험·복습·학습 화면에서 ☆ 북마크를 누르면 여기에 모입니다. 오답노트와 달리 맞힌 문제도 담아 둘 수 있습니다.</p></section>' +
      '<div class="filter-row"><div class="chips" role="group" aria-label="과목">' + chips + '</div></div>' +
      '<ul class="note-list" id="bm-list">' + (rows.length ? rows.map(function (r) {
        var q = r.q;
        return '<li class="card note-item" data-id="' + esc(q.id) + '">' +
          '<button type="button" class="note-head" aria-expanded="false"><span class="note-meta"><span class="tag tag-skip">' + esc(short(q.subject)) + '</span>' +
          (q.difficulty ? ' <span class="tag tag-skip">' + esc(S.DIFF_NAMES[q.difficulty]) + '</span>' : '') +
          '</span><span class="note-q">' + esc(q.question) + '</span><span class="muted small">담은 날 ' + esc(fmt(r.mark.added_at)) + '</span></button>' +
          '<div class="note-body" hidden></div></li>';
      }).join('') : '<li class="muted empty">아직 북마크한 문제가 없습니다.</li>') + '</ul>';

    view.querySelectorAll('[data-bsubj]').forEach(function (b) { b.onclick = function () { bmState.subject = b.getAttribute('data-bsubj'); ctx.render(); }; });
    document.getElementById('bm-list').addEventListener('click', function (e) {
      var item = e.target.closest('.note-item');
      if (!item) return;
      var head = e.target.closest('.note-head');
      if (!head) return;
      var q = bank.byId[item.getAttribute('data-id')];
      var body = item.querySelector('.note-body');
      var open = body.hidden;
      if (open) {
        body.innerHTML = '<div class="choices locked">' + q.choices.map(function (txt, k) {
          var right = k + 1 === q.answer;
          return '<div class="choice' + (right ? ' correct' : '') + '"><span class="choice-no" aria-hidden="true">' + CIRCLED[k] + '</span><span class="choice-text">' + esc(txt) + '</span>' + (right ? '<span class="choice-mark">✓ 정답</span>' : '') + '</div>';
        }).join('') + '</div>' +
          '<div class="feedback is-correct"><p class="fb-label">해설</p><p class="fb-text">' + esc(q.explanation) + '</p>' +
          (q.law_ref ? '<p class="fb-law small">관련 법령: ' + esc(q.law_ref) + '</p>' : '') + '</div>' +
          '<div class="rv-actions">' + UI.bookmarkBtnHtml(true, q.id).replace('data-bm=', 'data-bm-rerender data-bm=') + UI.reportLinkHtml(bank, q) + '</div>';
      }
      body.hidden = !open;
      head.setAttribute('aria-expanded', open);
    });
  }

  CDME.views = CDME.views || {};
  CDME.views.study = renderSetup;
  CDME.views.studyPlay = renderPlay;
  CDME.views.studyResult = renderResult;
  CDME.views.bookmarks = renderBookmarks;
})(window);
