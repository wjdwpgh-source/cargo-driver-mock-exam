/* 오답노트·복습 재시험 화면 (S5: FR-604~607, FR-701~709)
 * #/notes          오답노트 (복습 중 / 복습 완료 목록, 과목·정렬, 해설 보기, 제거·완료 처리, 복습 현황)
 * #/review         복습 설정 (범위·문항 수·시간 제한)
 * #/review-play    복습 풀이 (즉시 해설, 보기 순서 섞기, 연속 정답·졸업 표시)
 * #/review-result  복습 결과 (졸업한 문제, 다시 틀린 문제)
 */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var esc = CDME.util.escapeHtml, fmt = CDME.util.formatDate, RV = CDME.review, modal = CDME.modal;
  var UI = CDME.ui;
  var CIRCLED = ['①', '②', '③', '④'];

  function short(code) { return UI.subjectShort(code); }
  function profileData(ctx, active) { return ctx.store.getProfileData(active.id); }

  function needBank(ctx) {
    if (ctx.getBank()) return true;
    ctx.view.innerHTML = '<p class="muted">문제 데이터를 불러오는 중…</p>';
    return false;
  }

  function scopeLabel(bank, scope) {
    if (scope === 'all') return '전체 오답';
    if (scope === 'frequent') return '많이 틀린 문제';
    if (scope === 'recent') return '최근 틀린 문제';
    if (scope === 'mastered') return '복습 완료 문제';
    if (scope && scope.indexOf('subject:') === 0) return short(scope.slice(8));
    return scope;
  }

  /* ================= 오답노트 ================= */
  var noteState = { tab: 'active', subject: '', sort: 'recent' };

  function renderNotes(ctx, active) {
    if (!needBank(ctx)) return;
    var view = ctx.view, store = ctx.store, bank = ctx.getBank(), sample = ctx.sampleMode();
    var d = profileData(ctx, active);
    var sum = RV.summary(d.wrongNotes, bank, sample);
    var sessions = (d.reviewSessions || []).filter(function (s) { return !!s.sample === sample; });
    var rip = d.reviewInProgress;

    var chips = '<button type="button" class="chip' + (noteState.subject === '' ? ' on' : '') + '" data-subj="">전체 <b>' + (noteState.tab === 'active' ? sum.active : sum.mastered) + '</b></button>' +
      bank.config.exam.subjects.map(function (s) {
        var cnt = noteState.tab === 'active' ? sum.bySubject[s.code] : RV.listNotes(d.wrongNotes, bank, sample, { state: 'mastered', subject: s.code }).length;
        return '<button type="button" class="chip' + (noteState.subject === s.code ? ' on' : '') + '" data-subj="' + s.code + '">' + esc(short(s.code)) + ' <b>' + cnt + '</b></button>';
      }).join('');

    var recentSessions = sessions.slice(-5).reverse().map(function (s) {
      return '<li><span>' + esc(fmt(s.at)) + '</span><span class="muted small">' + esc(scopeLabel(bank, s.scope)) + ' · ' + s.correct + '/' + s.answered + ' 정답' +
        (s.mastered.length ? ' · 🎓 ' + s.mastered.length + '문제 완료' : '') + '</span></li>';
    }).join('');

    view.innerHTML = ctx.noticeHtml() +
      '<p><a href="#/home" class="back">← 대시보드</a></p>' +
      '<h1 class="page-title">오답노트' + (sample ? ' <span class="tag tag-wait">샘플</span>' : '') + '</h1>' +
      (rip ? '<section class="card resume"><h2>진행 중인 복습이 있습니다</h2><p class="small">' + RV.tally(rip).answered + ' / ' + rip.items.length + '문항 풀이</p>' +
        '<div class="row"><a class="btn btn-primary" href="#/review-play">이어 풀기</a><button type="button" class="btn btn-ghost" id="rv-quit">그만하기</button></div></section>' : '') +
      '<section class="stats" aria-label="오답 현황">' +
      '<div class="stat"><span class="stat-label">복습할 오답</span><span class="stat-value">' + sum.active + '</span></div>' +
      '<div class="stat"><span class="stat-label">복습 완료</span><span class="stat-value">' + sum.mastered + '</span></div>' +
      '<div class="stat"><span class="stat-label">복습 횟수</span><span class="stat-value">' + sessions.length + '</span></div>' +
      '</section>' +
      '<section class="card actions"><a class="btn btn-primary btn-lg' + (sum.active || sum.mastered ? '' : ' disabled') + '" href="#/review"' + (sum.active || sum.mastered ? '' : ' aria-disabled="true" tabindex="-1"') + '>복습 재시험 시작</a>' +
      '<p class="muted small">복습에서 <b>연속 2번</b> 맞히면 \'복습 완료\'로 옮겨집니다. 복습 성적은 실전 점수에 포함되지 않습니다.</p></section>' +
      '<div class="tabs" role="group" aria-label="목록 선택">' +
      '<button type="button" class="tab' + (noteState.tab === 'active' ? ' on' : '') + '" data-tab="active" aria-pressed="' + (noteState.tab === 'active') + '">복습 중 <b>' + sum.active + '</b></button>' +
      '<button type="button" class="tab' + (noteState.tab === 'mastered' ? ' on' : '') + '" data-tab="mastered" aria-pressed="' + (noteState.tab === 'mastered') + '">복습 완료 <b>' + sum.mastered + '</b></button>' +
      '</div>' +
      '<div class="filter-row"><div class="chips" role="group" aria-label="과목">' + chips + '</div>' +
      '<label class="sort"><span class="sr-only">정렬</span><select id="nt-sort" class="input input-sm">' +
      '<option value="recent"' + (noteState.sort === 'recent' ? ' selected' : '') + '>최근 틀린 순</option>' +
      '<option value="count"' + (noteState.sort === 'count' ? ' selected' : '') + '>많이 틀린 순</option></select></label></div>' +
      '<ul class="note-list" id="nt-list"></ul>' +
      (recentSessions ? '<section class="card"><h2>최근 복습</h2><ul class="session-list">' + recentSessions + '</ul></section>' : '');

    var list = document.getElementById('nt-list');
    function paint() {
      var rows = RV.listNotes(profileData(ctx, active).wrongNotes, bank, sample, { state: noteState.tab, subject: noteState.subject, sort: noteState.sort });
      list.innerHTML = rows.length ? rows.map(function (r) {
        var n = r.note, q = r.q;
        return '<li class="card note-item" data-id="' + esc(r.id) + '">' +
          '<button type="button" class="note-head" aria-expanded="false">' +
          '<span class="note-meta"><span class="tag tag-skip">' + esc(short(n.subject)) + '</span>' +
          (n.added_by === 'manual' ? ' <span class="tag tag-note">직접 담음</span>' : ' <span class="tag tag-bad">' + (n.wrong_count || 0) + '회 틀림</span>') +
          (r.changed ? ' <span class="tag tag-wait">수정된 문제</span>' : '') +
          (noteState.tab === 'active' && n.streak ? ' <span class="tag tag-ok">연속 정답 ' + n.streak + '/2</span>' : '') +
          '</span><span class="note-q">' + esc(q.question) + '</span>' +
          '<span class="muted small">' + (n.last_wrong_at ? '최근 틀림 ' + esc(fmt(n.last_wrong_at)) : n.added_at ? '담은 날 ' + esc(fmt(n.added_at)) : '') +
          (noteState.tab === 'mastered' && n.mastered_at ? ' · 완료 ' + esc(fmt(n.mastered_at)) : '') + '</span></button>' +
          '<div class="note-body" hidden></div></li>';
      }).join('') : '<li class="muted empty">' + (noteState.tab === 'active' ? '복습할 오답이 없습니다. 실전 모의시험에서 틀린 문제가 여기에 모입니다.' : '아직 복습 완료한 문제가 없습니다.') + '</li>';
    }
    function bodyHtml(id) {
      var n = profileData(ctx, active).wrongNotes[id], q = bank.byId[id];
      return '<div class="choices locked">' + q.choices.map(function (txt, k) {
        var no = k + 1, cls = 'choice', mark = '';
        if (no === q.answer) { cls += ' correct'; mark = '<span class="choice-mark">✓ 정답</span>'; }
        else if (no === n.last_choice) { cls += ' wrong'; mark = '<span class="choice-mark">✗ 최근 내 답</span>'; }
        return '<div class="' + cls + '"><span class="choice-no" aria-hidden="true">' + CIRCLED[k] + '</span><span class="choice-text">' + esc(txt) + '</span>' + mark + '</div>';
      }).join('') + '</div>' +
        '<div class="feedback is-correct"><p class="fb-label">해설</p><p class="fb-text">' + esc(q.explanation) + '</p>' +
        (q.law_ref ? '<p class="fb-law small">관련 법령: ' + esc(q.law_ref) + '</p>' : '') + '</div>' +
        '<div class="rv-actions">' +
        UI.bookmarkBtnHtml(CDME.study.isBookmarked(profileData(ctx, active).bookmarks, id, sample), id) +
        (n.state === 'active' ? '<button type="button" class="btn btn-outline btn-sm" data-act="master">복습 완료 처리</button>'
          : '<button type="button" class="btn btn-outline btn-sm" data-act="activate">다시 복습하기</button>') +
        '<button type="button" class="btn btn-ghost btn-sm danger-text" data-act="remove">오답노트에서 제거</button>' +
        UI.reportLinkHtml(bank, q) + '</div>';
    }
    paint();

    view.querySelectorAll('[data-tab]').forEach(function (b) { b.onclick = function () { noteState.tab = b.getAttribute('data-tab'); noteState.subject = ''; ctx.render(); }; });
    view.querySelectorAll('[data-subj]').forEach(function (b) { b.onclick = function () { noteState.subject = b.getAttribute('data-subj'); ctx.render(); }; });
    document.getElementById('nt-sort').onchange = function (e) { noteState.sort = e.target.value; paint(); };
    var quit = document.getElementById('rv-quit');
    if (quit) quit.onclick = function () { finishReview(ctx, active, true); };

    list.addEventListener('click', function (e) {
      var item = e.target.closest('.note-item');
      if (!item) return;
      var id = item.getAttribute('data-id');
      var head = e.target.closest('.note-head');
      if (head) {
        var body = item.querySelector('.note-body');
        var open = body.hidden;
        if (open) body.innerHTML = bodyHtml(id);
        body.hidden = !open;
        head.setAttribute('aria-expanded', open);
        return;
      }
      var act = e.target.closest('[data-act]');
      if (!act) return;
      var a = act.getAttribute('data-act');
      if (a === 'remove') {
        modal.confirm({ title: '오답노트에서 제거', message: '이 문제를 오답노트에서 지웁니다. 틀린 횟수 기록도 함께 지워집니다.', okText: '제거', danger: true })
          .then(function (ok) { if (ok) { store.updateProfileData(active.id, function (dd) { RV.remove(dd.wrongNotes, id); }); UI.toast('오답노트에서 제거했습니다.'); ctx.render(); } });
        return;
      }
      store.updateProfileData(active.id, function (dd) {
        if (a === 'master') RV.setMastered(dd.wrongNotes, id); else RV.setActive(dd.wrongNotes, id);
      });
      UI.toast(a === 'master' ? '복습 완료로 옮겼습니다.' : '다시 복습 목록으로 옮겼습니다.');
      ctx.render();
    });
  }

  /* ================= 복습 설정 ================= */
  var setup = { scope: 'all', count: 20, timed: false };

  function renderSetup(ctx, active) {
    if (!needBank(ctx)) return;
    var view = ctx.view, bank = ctx.getBank(), sample = ctx.sampleMode();
    var d = profileData(ctx, active);
    if (d.reviewInProgress) { ctx.go('review-play'); return; }
    var c = RV.scopeCounts(d.wrongNotes, bank, sample);
    if (!c[setup.scope]) setup.scope = c.all ? 'all' : c.mastered ? 'mastered' : 'all';
    var cfgR = bank.config.review || {};

    function opt(scope, label, desc) {
      var n = c[scope] || 0;
      return '<label class="opt' + (n ? '' : ' disabled') + '"><input type="radio" name="scope" value="' + scope + '"' + (setup.scope === scope ? ' checked' : '') + (n ? '' : ' disabled') + '>' +
        '<span class="opt-main"><span>' + esc(label) + '</span>' + (desc ? '<span class="muted small">' + esc(desc) + '</span>' : '') + '</span><b class="opt-count">' + n + '</b></label>';
    }
    var subjOpts = bank.config.exam.subjects.map(function (s) { return opt('subject:' + s.code, short(s.code), ''); }).join('');

    view.innerHTML = ctx.noticeHtml() +
      '<p><a href="#/notes" class="back">← 오답노트</a></p>' +
      '<h1 class="page-title">복습 재시험</h1>' +
      '<form id="rv-form">' +
      '<section class="card"><h2>출제 범위</h2><div class="opts">' +
      opt('all', '전체 오답', '복습 중인 모든 문제') +
      opt('frequent', '많이 틀린 문제', (cfgR.frequent_count || 2) + '회 이상 틀린 문제') +
      opt('recent', '최근 틀린 문제', '최근 ' + (cfgR.recent_days || 7) + '일') +
      '</div><h3 class="opt-sub">과목별</h3><div class="opts opts-2">' + subjOpts + '</div>' +
      '<h3 class="opt-sub">다시 풀기</h3><div class="opts">' + opt('mastered', '복습 완료 문제', '틀리면 다시 복습 목록으로') + '</div></section>' +
      '<section class="card"><h2>문항 수</h2><div class="seg" role="radiogroup">' +
      [10, 20, 40, 'all'].map(function (v) {
        return '<label class="seg-item"><input type="radio" name="count" value="' + v + '"' + (String(setup.count) === String(v) ? ' checked' : '') + '><span>' + (v === 'all' ? '전체' : v + '문항') + '</span></label>';
      }).join('') + '</div><p class="muted small">범위의 문제가 적으면 있는 만큼 출제합니다.</p></section>' +
      '<section class="card"><h2>시간 제한</h2><label class="switch"><input type="checkbox" id="rv-timed"' + (setup.timed ? ' checked' : '') + '><span>문항당 1분 (끄면 시간 제한 없음)</span></label></section>' +
      '<section class="card actions"><p class="small">한 문제씩 풀 때마다 정답·해설이 나오며, 문제와 보기 순서는 섞여서 나옵니다.</p>' +
      '<button type="submit" class="btn btn-primary btn-lg"' + (c.all || c.mastered ? '' : ' disabled') + '>복습 시작</button></section>' +
      '</form>';

    document.getElementById('rv-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var f = e.target;
      setup.scope = (f.querySelector('[name=scope]:checked') || {}).value || 'all';
      var cv = (f.querySelector('[name=count]:checked') || {}).value || '20';
      setup.count = cv === 'all' ? 'all' : +cv;
      setup.timed = document.getElementById('rv-timed').checked;
      var rv;
      try {
        rv = RV.buildReview(profileData(ctx, active).wrongNotes, bank, { sample: sample, scope: setup.scope, count: setup.count, timed: setup.timed });
      } catch (err) {
        modal.confirm({ title: '복습할 문제가 없습니다', message: '선택한 범위에 문제가 없습니다.', okText: '확인', cancelText: '닫기' });
        return;
      }
      if (ctx.devKind()) rv.kind = ctx.devKind();
      ctx.store.updateProfileData(active.id, function (dd) { dd.reviewInProgress = rv; });
      ctx.go('review-play');
    });
  }

  /* ================= 복습 풀이 ================= */
  function finishReview(ctx, active, quitEarly) {
    var rec = null;
    ctx.store.updateProfileData(active.id, function (dd) {
      var rv = dd.reviewInProgress;
      if (!rv) return;
      dd.reviewInProgress = null;
      if (RV.tally(rv).answered === 0) return;             // 한 문제도 안 풀었으면 기록하지 않음
      rec = RV.finish(rv);
      if (rv.kind) rec.kind = rv.kind;
      rec.quit = !!quitEarly;
      if (!dd.reviewSessions) dd.reviewSessions = [];
      dd.reviewSessions.push(rec);
    });
    document.querySelectorAll('.toast').forEach(function (t) { t.remove(); });
    if (rec) ctx.go('review-result?id=' + encodeURIComponent(rec.id)); else ctx.go('notes');
  }

  // 복습 재시험 설정
  var REVIEW_KIND = {
    key: 'reviewInProgress', back: 'notes', title: '복습 재시험', tag: '복습',
    answer: function (rv, dd, bank, i, orig) { return RV.answer(rv, dd.wrongNotes, bank, i, orig); },
    tally: RV.tally,
    finish: function (ctx, active, quit) { finishReview(ctx, active, quit); },
    showWrongCount: true
  };
  function renderPlay(ctx, active) { renderSession(ctx, active, REVIEW_KIND); }

  /* 즉시 해설 풀이 화면 (복습 재시험·집중 학습 공용) */
  function renderSession(ctx, active, K) {
    if (!needBank(ctx)) return;
    var view = ctx.view, store = ctx.store, bank = ctx.getBank();
    var d = profileData(ctx, active);
    var rv = d[K.key];
    if (!rv) { ctx.go(K.back); return; }
    if (ctx.ensureKind(rv)) return;
    // 진행 중 문제가 삭제·폐기되었으면 그 문항은 건너뜀
    var total = rv.items.length;
    var timerId = null, last = Date.now(), done = false;

    function persist() { store.updateProfileData(active.id, function (dd) { dd[K.key] = rv; }); }

    view.innerHTML =
      '<div class="exam review">' +
      '<div class="exam-bar"><span class="exam-subject" id="rp-subject"></span><span class="exam-progress" id="rp-progress"></span>' +
      (rv.timed ? '<span class="exam-timer" id="rp-timer" role="timer"></span>' : '<span class="tag tag-note">' + esc(K.tag) + '</span>') + '</div>' +
      '<p class="exam-tally small" id="rp-tally" aria-live="polite"></p>' +
      '<h1 class="sr-only">' + esc(K.title) + '</h1>' +
      '<article class="card q-card" id="rp-card"></article>' +
      '<div class="exam-tools"><button type="button" class="btn btn-ghost btn-sm" id="rp-later">나중에 이어 풀기</button>' +
      '<button type="button" class="btn btn-ghost btn-sm" id="rp-quit">그만하고 결과 보기</button></div>' +
      '<nav class="exam-nav" aria-label="문항 이동"><button type="button" class="btn btn-ghost" id="rp-prev">← 이전</button>' +
      '<span></span><button type="button" class="btn btn-primary" id="rp-next">다음 →</button></nav></div>';

    var elCard = document.getElementById('rp-card');
    var elNext = document.getElementById('rp-next');
    var elPrev = document.getElementById('rp-prev');
    var elTimer = document.getElementById('rp-timer');

    function paint(focusFb) {
      var i = rv.current, it = rv.items[i], q = bank.byId[it.qid];
      var t = K.tally(rv);
      document.getElementById('rp-subject').textContent = short(it.subject);
      document.getElementById('rp-progress').innerHTML = '<b>' + (i + 1) + '</b> / ' + total;
      document.getElementById('rp-tally').innerHTML = '<span class="ok-text">정답 ' + t.correct + '</span> · <span class="danger-text">오답 ' + t.wrong + '</span>' +
        (t.mastered ? ' · 🎓 복습 완료 ' + t.mastered : '') + ' · 남은 문항 ' + t.unanswered;
      if (!q || q.status === 'deprecated') {
        elCard.innerHTML = '<p class="muted">이 문제는 수정·폐기되어 건너뜁니다.</p>';
      } else {
        var ans = rv.answers[i], res = rv.results[i];
        var E = CDME.exam, hUsed = E.hintUsed(rv, i), h = E.hintFor(q);
        var elim = ans == null && hUsed && h.type === 'elim' ? h.remove : 0;
        var pd = profileData(ctx, active);
        var n = K.showWrongCount ? pd.wrongNotes[it.qid] : null;
        elCard.innerHTML =
          '<p class="q-num q-num-row"><span>문 ' + (i + 1) + '. ' + (n ? '<span class="tag tag-bad">' + (n.wrong_count || 0) + '회 틀림</span>' : '') +
          (K.showDifficulty && q.difficulty ? '<span class="tag tag-skip">' + esc(CDME.study.DIFF_NAMES[q.difficulty] || '') + '</span>' : '') + '</span>' +
          UI.bookmarkBtnHtml(CDME.study.isBookmarked(pd.bookmarks, q.id, ctx.sampleMode()), q.id) + '</p>' +
          '<p class="q-text">' + esc(q.question) + '</p>' +
          (q.image ? '<img class="q-img" src="' + esc(q.image) + '" alt="문제 그림">' : '') +
          '<div class="choices' + (ans != null ? ' locked' : '') + '" role="group" aria-label="보기">' +
          it.perm.map(function (orig, k) {
            var cls = 'choice', mark = '';
            if (ans != null) {
              if (orig === q.answer) { cls += ' correct'; mark = '<span class="choice-mark">✓</span>'; }
              else if (orig === ans) { cls += ' wrong'; mark = '<span class="choice-mark">✗</span>'; }
            }
            if (orig === elim) { cls += ' eliminated'; mark = '<span class="choice-mark">힌트로 지움</span>'; }
            return '<button type="button" class="' + cls + '" data-pos="' + k + '"' + (ans != null || orig === elim ? ' disabled aria-disabled="true"' : '') + '>' +
              '<span class="choice-no" aria-hidden="true">' + CIRCLED[k] + '</span><span class="choice-text">' + esc(q.choices[orig - 1]) + '</span>' + mark + '</button>';
          }).join('') + '</div>' +
          (ans == null ? UI.hintAreaHtml(h, hUsed, function (orig) { return RV.displayIndexOf(it, orig); }, 'rp') : '') +
          (ans != null ? '<div class="feedback ' + (res.correct ? 'is-correct' : 'is-wrong') + '" id="rp-fb" tabindex="-1" role="status">' +
            '<p class="fb-title">' + (res.correct ? '✓ 정답입니다' : '✗ 오답입니다 <span class="fb-answer">정답은 ' + CIRCLED[RV.displayIndexOf(it, q.answer)] + '번</span>') +
            (hUsed ? ' <span class="tag tag-hint">💡 힌트 사용</span>' : '') + '</p>' +
            (res.mastered ? '<p class="mastered-msg">🎓 연속 2번 맞혀 <b>복습 완료</b>로 옮겼습니다!</p>'
              : res.correct && res.streak ? '<p class="small">연속 정답 ' + res.streak + '/2 – 한 번 더 맞히면 복습 완료</p>'
              : res.reactivated ? '<p class="small">복습 완료였던 문제라 다시 복습 목록으로 옮겼습니다.</p>'
              : res.noted ? '<p class="small">📒 오답노트에 담았습니다. 오답노트에서 다시 복습할 수 있습니다.</p>' : '') +
            '<p class="fb-label">해설</p><p class="fb-text">' + esc(q.explanation) + '</p>' +
            (q.law_ref ? '<p class="fb-law small">관련 법령: ' + esc(q.law_ref) + '</p>' : '') +
            '<div class="fb-actions">' + UI.reportLinkHtml(bank, q) + '</div></div>' : '');
        if (ans == null) {
          elCard.querySelectorAll('[data-pos]').forEach(function (b) { b.onclick = function () { choose(+b.getAttribute('data-pos')); }; });
          var hb = document.getElementById('rp-hint');
          if (hb) hb.onclick = showHint;
        }
      }
      elPrev.disabled = i === 0;
      var allDone = K.tally(rv).unanswered === 0;
      elNext.textContent = i < total - 1 ? '다음 →' : allDone ? '복습 결과 보기' : '안 푼 문항으로';
      if (focusFb === 'hint') { var hbox = document.getElementById('rp-hintbox'); if (hbox) { hbox.focus({ preventScroll: true }); hbox.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } }
      else if (focusFb) { var fb = document.getElementById('rp-fb'); if (fb) { fb.focus({ preventScroll: true }); fb.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } }
    }

    function showHint() {
      var q = bank.byId[rv.items[rv.current].qid];
      if (!q || q.status === 'deprecated') return;
      if (!CDME.exam.useHint(rv, rv.current)) return;
      persist();
      paint('hint');
    }
    function choose(pos) {
      var i = rv.current;
      if (rv.answers[i] != null) return;
      if (CDME.exam.hintUsed(rv, i)) {
        var hh = CDME.exam.hintFor(bank.byId[rv.items[i].qid]);
        if (hh && hh.type === 'elim' && RV.originalChoice(rv.items[i], pos) === hh.remove) return;
      }
      var res;
      store.updateProfileData(active.id, function (dd) {
        res = K.answer(rv, dd, bank, i, RV.originalChoice(rv.items[i], pos));
        dd[K.key] = rv;
      });
      if (res && res.mastered) UI.toast('🎓 복습 완료!');
      paint(true);
    }
    function move(i) { if (i < 0 || i >= total) return; rv.current = i; persist(); paint(); window.scrollTo(0, 0); }
    function next() {
      if (rv.current < total - 1) return move(rv.current + 1);
      // 안 푼 문항(수정·폐기되어 건너뛴 문항 제외)으로 이동, 없으면 결과
      var f = -1;
      rv.items.forEach(function (it, k) { var q = bank.byId[it.qid]; if (f < 0 && rv.answers[k] == null && q && q.status !== 'deprecated') f = k; });
      if (f < 0) end(false); else move(f);
    }
    function end(quit) { if (done) return; done = true; cleanup(); K.finish(ctx, active, quit); }
    function tick() {
      var now = Date.now(); rv.remainingMs -= Math.max(0, Math.min(now - last, 60000)); last = now;
      elTimer.textContent = CDME.exam.formatTime(rv.remainingMs);
      elTimer.classList.toggle('warn', rv.remainingMs <= 60000);
      if (rv.remainingMs <= 0) { UI.toast('복습 시간이 끝났습니다.'); end(false); }
    }
    function onKey(e) {
      if (document.querySelector('.modal-backdrop')) return;
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key >= '1' && e.key <= '4') { e.preventDefault(); choose(+e.key - 1); }
      else if (e.key === 'h' || e.key === 'H' || e.key === 'ㅗ') { e.preventDefault(); showHint(); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); if (rv.current < total - 1) move(rv.current + 1); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); move(rv.current - 1); }
    }
    function onHide() { if (!done) persist(); }
    function cleanup() {
      clearInterval(timerId);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('pagehide', onHide);
      if (!done) persist();
    }

    elPrev.onclick = function () { move(rv.current - 1); };
    elNext.onclick = next;
    document.getElementById('rp-later').onclick = function () { ctx.go(K.back); };
    document.getElementById('rp-quit').onclick = function () {
      var t = K.tally(rv);
      if (!t.unanswered) return end(false);
      modal.confirm({ title: K.tag + '을 마칠까요?', message: '안 푼 ' + t.unanswered + '문항은 기록하지 않고, 지금까지 푼 결과만 저장합니다.', okText: '마치기', cancelText: '계속 풀기' })
        .then(function (ok) { if (ok) end(true); });
    };
    document.addEventListener('keydown', onKey);
    window.addEventListener('pagehide', onHide);
    ctx.setCleanup(cleanup);
    paint();
    if (rv.timed) { elTimer.textContent = CDME.exam.formatTime(rv.remainingMs); if (rv.remainingMs <= 0) { end(false); return; } timerId = setInterval(tick, 1000); }
  }

  /* ================= 복습 결과 ================= */
  function renderReviewResult(ctx, active) {
    if (!needBank(ctx)) return;
    var view = ctx.view, bank = ctx.getBank(), p = ctx.params();
    var d = profileData(ctx, active);
    var list = d.reviewSessions || [];
    var s = p.id ? list.filter(function (x) { return x.id === p.id; })[0] : list[list.length - 1];
    if (!s) { ctx.go('notes'); return; }
    if (ctx.ensureKind(s)) return;
    var sum = RV.summary(d.wrongNotes, bank, ctx.sampleMode());
    function qlist(ids) {
      return ids.map(function (id) { var q = bank.byId[id]; return q ? '<li><span class="tag tag-skip">' + esc(short(q.subject)) + '</span> ' + esc(q.question) + '</li>' : ''; }).join('');
    }
    view.innerHTML = ctx.noticeHtml() +
      '<h1 class="page-title">복습 결과</h1>' +
      '<section class="card result-hero pass"><span class="result-badge">' + esc(scopeLabel(bank, s.scope)) + '</span>' +
      '<span class="result-score"><b>' + s.correct + '</b> / ' + s.answered + '</span>' +
      '<span class="muted">정답 수' + (s.quit && s.answered < s.total ? ' · 전체 ' + s.total + '문항 중 ' + s.answered + '문항 풀이' : '') + '</span>' +
      (s.hintCount ? '<span class="muted small">💡 힌트 사용 ' + s.hintCount + '문항</span>' : '') + '</section>' +
      '<section class="card"><h2>🎓 이번에 복습 완료한 문제 <b>' + s.mastered.length + '</b></h2>' +
      (s.mastered.length ? '<ul class="q-mini">' + qlist(s.mastered) + '</ul>' : '<p class="muted small">연속 2번 맞힌 문제가 복습 완료로 옮겨집니다.</p>') + '</section>' +
      (s.wrongIds.length ? '<section class="card"><h2>다시 틀린 문제 <b>' + s.wrongIds.length + '</b></h2><ul class="q-mini">' + qlist(s.wrongIds) + '</ul></section>' : '') +
      '<section class="card"><p>남은 오답 <b>' + sum.active + '</b>문제 · 복습 완료 <b>' + sum.mastered + '</b>문제</p>' +
      '<p class="muted small">복습 결과는 실전 점수·합격 통계에 포함되지 않습니다.</p></section>' +
      '<section class="card actions">' + (sum.active ? '<a class="btn btn-primary" href="#/review">한 번 더 복습</a>' : '') +
      '<a class="btn btn-ghost" href="#/notes">오답노트로</a><a class="btn btn-ghost" href="#/home">대시보드로</a></section>';
  }

  CDME.views = CDME.views || {};
  CDME.views.notes = renderNotes;
  CDME.views.review = renderSetup;
  CDME.views.reviewPlay = renderPlay;
  CDME.views.session = renderSession;
  CDME.views.reviewResult = renderReviewResult;
})(window);
