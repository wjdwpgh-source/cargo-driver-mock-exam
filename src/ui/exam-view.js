/* 실전 시험 화면·결과 화면 (S2, v1.9 개정, S3 결과·다시보기)
 * FR-203 타이머·알림, FR-204 시간 종료 자동 종료, FR-205 이동, FR-206 번호판, FR-208 이어 풀기
 * v1.9: 제출 버튼 삭제, 답을 고르면 즉시 정답/오답·해설 표시(FR-210 개정), 답 고정, 모두 풀면 결과 보기
 */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var esc = CDME.util.escapeHtml, E = CDME.exam, N = CDME.notes, modal = CDME.modal;
  var CIRCLED = ['①', '②', '③', '④'];
  var ALERTS = [{ ms: 5 * 60000, text: '남은 시간 5분입니다.' }, { ms: 60000, text: '남은 시간 1분입니다. 시간이 끝나면 자동으로 종료됩니다.' }];

  function subjectName(bank, code) {
    var s = bank.config.exam.subjects.filter(function (x) { return x.code === code; })[0];
    return s ? s.name : code;
  }

  function subjectShort(code) {
    return { LAW: '법규', CARGO: '화물취급요령', SAFE: '안전운행', SERVICE: '운송서비스' }[code] || code;
  }

  function toast(text) {
    document.querySelectorAll('.toast').forEach(function (old) { old.remove(); });   // 겹치지 않게 하나만
    var t = document.createElement('div');
    t.className = 'toast';
    t.setAttribute('role', 'alert');
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add('hide'); }, 4000);
    setTimeout(function () { t.remove(); }, 4600);
  }

  /* ================= 시험 화면 (v1.9: 한 문제씩 즉시 채점·해설) ================= */
  function renderExam(ctx, active) {
    var view = ctx.view, store = ctx.store, bank = ctx.getBank();
    if (!bank) { view.innerHTML = '<p class="muted">문제 데이터를 불러오는 중…</p>'; return; }
    var data = store.getProfileData(active.id);
    var ip = data && data.inProgress;
    if (!ip) { ctx.go('home'); return; }
    if (ctx.ensureKind(ip)) return;

    var missing = E.missingQuestions(ip, bank);
    if (missing.length) {
      view.innerHTML = '<h1 class="page-title">시험을 이어 풀 수 없습니다</h1>' +
        '<div class="notice notice-error">진행 중이던 시험의 문제 ' + missing.length + '개가 수정·삭제되어 이어 풀 수 없습니다.</div>' +
        '<button class="btn btn-primary" id="discard">이 시험 포기하고 대시보드로</button>';
      document.getElementById('discard').onclick = function () {
        store.updateProfileData(active.id, function (d) { d.inProgress = null; });
        ctx.go('home');
      };
      return;
    }

    var total = ip.items.length;
    var finished = false;
    var tickCount = 0;
    var last = Date.now();
    var timerId = null;

    var saveWarned = false;
    function persist() {
      var ok = store.updateProfileData(active.id, function (d) { d.inProgress = ip; });
      // 저장 공간 부족 등으로 저장에 실패하면 풀이 중에도 한 번 알림 (NFR-05)
      if (ok === false && !saveWarned && store.error) { saveWarned = true; toast(store.error); }
    }

    view.innerHTML =
      '<div class="exam">' +
      '<div class="exam-bar">' +
      '<span class="exam-subject" id="ex-subject"></span>' +
      '<span class="exam-progress" id="ex-progress"></span>' +
      '<span class="exam-timer" id="ex-timer" role="timer" aria-label="남은 시간"></span>' +
      '</div>' +
      '<p class="exam-tally small" id="ex-tally" aria-live="polite"></p>' +
      '<h1 class="sr-only">실전 모의시험</h1>' +
      (ip.sample ? '<p class="notice notice-warn small">' + (ip.kind === 'draft' ? '검수 전(초안) 문제가 포함된 미리보기 시험입니다. 정답·해설이 틀린 것 같으면 해설 아래 오류 신고나 엑셀 비고에 적어 두세요.' : '샘플 문제로 진행 중인 개발 확인용 시험입니다.') + '</p>' : '') +
      '<article class="card q-card" id="ex-card"></article>' +
      '<div class="exam-tools"><button type="button" class="btn btn-ghost btn-sm" id="ex-later">나중에 이어 풀기</button></div>' +
      '<nav class="exam-nav" aria-label="문항 이동">' +
      '<button type="button" class="btn btn-ghost" id="ex-prev">← 이전</button>' +
      '<button type="button" class="btn btn-ghost" id="ex-grid">번호판</button>' +
      '<button type="button" class="btn btn-primary" id="ex-next">다음 →</button>' +
      '</nav></div>';

    var elSubject = document.getElementById('ex-subject');
    var elProgress = document.getElementById('ex-progress');
    var elTally = document.getElementById('ex-tally');
    var elTimer = document.getElementById('ex-timer');
    var elCard = document.getElementById('ex-card');
    var elPrev = document.getElementById('ex-prev');
    var elNext = document.getElementById('ex-next');

    function feedbackHtml(q, choice, hUsed) {
      var ok = choice === q.answer;
      return '<div class="feedback ' + (ok ? 'is-correct' : 'is-wrong') + '" id="ex-feedback" tabindex="-1" role="status">' +
        '<p class="fb-title">' + (ok ? '✓ 정답입니다' : '✗ 오답입니다') +
        (ok ? '' : ' <span class="fb-answer">정답은 ' + CIRCLED[q.answer - 1] + '번</span>') +
        (hUsed ? ' <span class="tag tag-hint">💡 힌트 사용</span>' : '') + '</p>' +
        '<p class="fb-label">해설</p><p class="fb-text">' + esc(q.explanation) + '</p>' +
        (q.law_ref ? '<p class="fb-law small">관련 법령: ' + esc(q.law_ref) + '</p>' : '') +
        '<div class="fb-actions">' + reportLinkHtml(bank, q) + '</div>' +
        '</div>';
    }

    function paint(focusFeedback) {
      var i = ip.current;
      var it = ip.items[i];
      var q = bank.byId[it.qid];
      var t = E.tally(ip, bank);
      var choice = ip.answers[i];
      var answered = choice != null;
      var allDone = t.unanswered === 0;
      var hUsed = E.hintUsed(ip, i);
      var h = E.hintFor(q);
      var elim = !answered && hUsed && h.type === 'elim' ? h.remove : 0;

      elSubject.textContent = subjectShort(it.subject);
      elSubject.title = subjectName(bank, it.subject);
      elProgress.innerHTML = '<b>' + (i + 1) + '</b> / ' + total;
      elTally.innerHTML = '<span class="ok-text">정답 ' + t.correct + '</span> · <span class="danger-text">오답 ' + t.wrong + '</span> · 남은 문항 ' + t.unanswered;

      elCard.innerHTML =
        '<p class="q-num">문 ' + (i + 1) + '.' + (q._status && q._status !== 'verified' ? ' <span class="tag tag-wait">검수 전 · ' + esc(q.id) + '</span>' : '') + '</p>' +
        '<p class="q-text">' + esc(q.question) + '</p>' +
        (q.image ? '<img class="q-img" src="' + esc(q.image) + '" alt="문제 ' + (i + 1) + ' 그림">' : '') +
        '<div class="choices' + (answered ? ' locked' : '') + '" role="group" aria-label="보기">' +
        q.choices.map(function (txt, k) {
          var n = k + 1, cls = 'choice', mark = '';
          if (answered) {
            if (n === q.answer) { cls += ' correct'; mark = '<span class="choice-mark" aria-label="정답">✓</span>'; }
            else if (n === choice) { cls += ' wrong'; mark = '<span class="choice-mark" aria-label="내가 고른 오답">✗</span>'; }
            if (n === choice) cls += ' chosen';
          }
          var off = answered || n === elim;
          if (n === elim) { cls += ' eliminated'; mark = '<span class="choice-mark">힌트로 지움</span>'; }
          return '<button type="button" class="' + cls + '" data-choice="' + n + '"' + (off ? ' disabled aria-disabled="true"' : '') + '>' +
            '<span class="choice-no" aria-hidden="true">' + CIRCLED[k] + '</span><span class="choice-text">' + esc(txt) + '</span>' + mark + '</button>';
        }).join('') + '</div>' +
        (answered ? '' : hintAreaHtml(h, hUsed, function (orig) { return orig - 1; }, 'ex')) +
        (answered ? feedbackHtml(q, choice, hUsed) : '') +
        (allDone ? '<div class="done-box"><p>모든 문항을 풀었습니다.</p><button type="button" class="btn btn-primary btn-lg" id="ex-finish">결과 보기</button></div>' : '');

      if (!answered) {
        elCard.querySelectorAll('[data-choice]').forEach(function (b) {
          b.addEventListener('click', function () { choose(+b.getAttribute('data-choice')); });
        });
        var hb = document.getElementById('ex-hint');
        if (hb) hb.addEventListener('click', showHint);
      }
      var fin = document.getElementById('ex-finish');
      if (fin) fin.addEventListener('click', function () { finish(false); });

      elPrev.disabled = i === 0;
      if (i < total - 1) { elNext.textContent = '다음 →'; elNext.disabled = false; }
      else if (allDone) { elNext.textContent = '결과 보기'; elNext.disabled = false; }
      else { elNext.textContent = '안 푼 문항으로'; elNext.disabled = false; }

      if (focusFeedback === 'hint') {
        var box = document.getElementById('ex-hintbox');
        if (box) { box.focus({ preventScroll: true }); box.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
      } else if (focusFeedback) {
        var fb = document.getElementById('ex-feedback');
        if (fb) { fb.focus({ preventScroll: true }); fb.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
      }
    }

    // 답을 고르면 바로 채점하고 답을 고정한다
    function showHint() {
      if (!E.useHint(ip, ip.current)) return;
      persist();
      paint('hint');
    }

    function choose(n) {
      if (ip.answers[ip.current] != null) return;
      var hq = bank.byId[ip.items[ip.current].qid];
      if (E.hintUsed(ip, ip.current)) { var hh = E.hintFor(hq); if (hh.type === 'elim' && hh.remove === n) return; }
      E.setAnswer(ip, ip.current, n, { lock: true });
      persist();
      paint(true);
    }

    function move(i) {
      if (i < 0 || i >= total) return;
      ip.current = i;
      persist();
      paint();
      window.scrollTo(0, 0);
    }

    function next() {
      if (ip.current < total - 1) return move(ip.current + 1);
      var f = E.firstUnanswered(ip);
      if (f < 0) finish(false); else move(f);
    }

    function tick() {
      var now = Date.now();
      var delta = Math.max(0, Math.min(now - last, 60000));
      last = now;
      ip.remainingMs -= delta;
      var ms = Math.max(0, ip.remainingMs);
      elTimer.textContent = E.formatTime(ms);
      elTimer.classList.toggle('warn', ms <= 5 * 60000);
      // 알림 시점을 지나면 한 번만 알림. 이어 풀기 등으로 1분 넘게 지나친 알림은 조용히 표시 처리
      var fire = null;
      ALERTS.forEach(function (a) {
        if (ms > 0 && ms <= a.ms && !ip.alerts[a.ms]) {
          ip.alerts[a.ms] = true;
          if (ms > a.ms - 60000) fire = a;
        }
      });
      if (fire) { toast(fire.text); persist(); }
      if (ip.remainingMs <= 0) { finish(true); return; }
      if (++tickCount % 5 === 0) persist();
    }

    function openGrid() {
      var t = E.tally(ip, bank);
      var html = '<div class="modal-backdrop grid-backdrop"><div class="modal grid-modal" role="dialog" aria-modal="true" aria-labelledby="grid-title">' +
        '<h2 id="grid-title">문항 번호판</h2>' +
        '<p class="small">정답 <b class="ok-text">' + t.correct + '</b> · 오답 <b class="danger-text">' + t.wrong + '</b> · 안 푼 문항 <b>' + t.unanswered + '</b> · 남은 시간 ' + E.formatTime(ip.remainingMs) + '</p>' +
        '<p class="legend small"><span class="cell sample correct"></span> 정답 <span class="cell sample wrong"></span> 오답 <span class="cell sample"></span> 안 푼 문항 <span class="cell sample current"></span> 현재</p>';
      bank.config.exam.subjects.forEach(function (s) {
        var idx = [];
        for (var i = 0; i < total; i++) if (ip.items[i].subject === s.code) idx.push(i);
        if (!idx.length) return;
        html += '<h3 class="grid-sub">' + esc(subjectShort(s.code)) + '</h3><div class="grid">' +
          idx.map(function (i) {
            var j = E.judge(ip, bank, i);
            var state = !j.answered ? '안 푼 문항' : j.correct ? '정답' : '오답';
            var cls = 'cell' + (j.answered ? (j.correct ? ' correct' : ' wrong') : '') + (i === ip.current ? ' current' : '');
            return '<button type="button" class="' + cls + '" data-go="' + i + '" aria-label="' + (i + 1) + '번 ' + state + '">' + (i + 1) + '</button>';
          }).join('') + '</div>';
      });
      html += '<div class="modal-actions"><button type="button" class="btn btn-ghost" data-close>닫기</button>' +
        (t.unanswered ? '<button type="button" class="btn btn-primary" data-first>안 푼 문항으로</button>'
          : '<button type="button" class="btn btn-primary" data-finish>결과 보기</button>') +
        '</div></div></div>';
      var wrap = document.createElement('div');
      wrap.innerHTML = html;
      var bd = wrap.firstChild;
      document.body.appendChild(bd);
      function close() { bd.remove(); document.removeEventListener('keydown', onEsc, true); }
      function onEsc(e) { if (e.key === 'Escape') { e.stopPropagation(); close(); } }
      document.addEventListener('keydown', onEsc, true);
      bd.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('button') : null;
        if (e.target === bd || (b && b.hasAttribute('data-close'))) return close();
        if (!b) return;
        if (b.hasAttribute('data-go')) { close(); move(+b.getAttribute('data-go')); }
        if (b.hasAttribute('data-first')) { close(); move(E.firstUnanswered(ip)); }
        if (b.hasAttribute('data-finish')) { close(); finish(false); }
      });
      var cur = bd.querySelector('.cell.current');
      (cur || bd.querySelector('[data-close]')).focus();
    }

    function finish(timedOut) {
      if (finished) return;
      finished = true;
      cleanup(false);
      if (timedOut) ip.remainingMs = 0;
      var record = E.score(ip, bank, { timedOut: timedOut });
      store.updateProfileData(active.id, function (d) {
        // 틀린 문제·안 푼 문제를 오답노트에 자동 등록 (FR-601~603)
        if (ip.kind) record.kind = ip.kind;
        record.noteReg = N.registerWrong(d.wrongNotes, record, bank, record.finishedAt);
        d.exams.push(record);
        d.inProgress = null;
      });
      document.querySelectorAll('.modal-backdrop, .toast').forEach(function (m) { m.remove(); });
      ctx.go('result?id=' + encodeURIComponent(record.id) + (timedOut ? '&timeout=1' : ''));
    }

    function onKey(e) {
      if (document.querySelector('.modal-backdrop')) return;
      var tag = (e.target && e.target.tagName) || '';
      if (tag === 'INPUT' || tag === 'TEXTAREA' || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key >= '1' && e.key <= '4') { e.preventDefault(); choose(+e.key); }
      else if (e.key === 'h' || e.key === 'H' || e.key === 'ㅗ') { e.preventDefault(); showHint(); }
      else if (e.key === 'ArrowRight' || (e.key === 'Enter' && ip.answers[ip.current] != null && tag !== 'BUTTON')) { e.preventDefault(); if (ip.current < total - 1) move(ip.current + 1); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); move(ip.current - 1); }
    }
    function onHide() { if (!finished) persist(); }
    function onVis() { if (document.visibilityState === 'hidden') onHide(); else { tick(); } }

    function cleanup(save) {
      clearInterval(timerId);
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('pagehide', onHide);
      if (save !== false && !finished) persist();
    }

    elPrev.onclick = function () { move(ip.current - 1); };
    elNext.onclick = next;
    document.getElementById('ex-grid').onclick = openGrid;
    document.getElementById('ex-later').onclick = function () { ctx.go('home'); };
    document.addEventListener('keydown', onKey);
    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('pagehide', onHide);
    ctx.setCleanup(cleanup);

    if (ip.current >= total) ip.current = 0;
    paint();
    elTimer.textContent = E.formatTime(ip.remainingMs);
    if (ip.remainingMs <= 0) { finish(true); return; }
    timerId = setInterval(tick, 1000);
  }

  /* ================= 결과 화면 (S3: 문제별 다시보기·오답노트·오류 신고) ================= */
  /* 힌트 영역 (FR-312): 답하기 전에만 보임
   * h: CDME.exam.hintFor 결과, used: 이미 봤는지, posOf(원래 번호) → 화면 위치(0~3), pre: id 앞머리 */
  function hintAreaHtml(h, used, posOf, pre) {
    if (!h) return '';
    if (!used) {
      return '<div class="hint-area"><button type="button" class="btn btn-hint btn-sm" id="' + pre + '-hint">💡 힌트 보기</button>' +
        '<span class="muted small hint-note">힌트를 봐도 점수는 그대로이고, 결과에 "힌트 사용"으로 표시됩니다.</span></div>';
    }
    var body = h.type === 'text'
      ? '<p class="hint-text">' + esc(h.text) + '</p>'
      : '<p class="hint-text">이 문제는 준비된 힌트 글이 없어, 틀린 보기 하나(<b>' + CIRCLED[posOf(h.remove)] + '번</b>)를 지웠습니다. 남은 보기 중에서 골라 보세요.</p>';
    return '<div class="hint-box" id="' + pre + '-hintbox" tabindex="-1" role="note" aria-label="힌트"><p class="hint-title">💡 힌트</p>' + body + '</div>';
  }

  function reportLinkHtml(bank, q) {
    var url = N.issueUrl(bank.config, q);
    return url
      ? '<a class="btn btn-ghost btn-sm" href="' + esc(url) + '" target="_blank" rel="noopener">오류 신고</a>'
      : '<button type="button" class="btn btn-ghost btn-sm" disabled title="GitHub 저장소 공개 후 사용할 수 있습니다">오류 신고 (준비 중)</button>';
  }

  function reviewCardHtml(bank, notes, a, i) {
    var q = bank.byId[a.qid];
    var head = '<p class="rv-head"><span class="q-num">문 ' + (i + 1) + '.</span> <span class="muted small">' +
      esc(subjectShort(q ? q.subject : a.qid.split('-')[0])) + '</span> ' +
      (a.correct ? '<span class="tag tag-ok">✓ 정답</span>' : a.choice == null ? '<span class="tag tag-skip">안 푼 문제</span>' : '<span class="tag tag-bad">✗ 오답</span>');
    if (!q) return '<li class="card rv-card">' + head + '</p><p class="muted">이 문제는 삭제되어 볼 수 없습니다.</p></li>';
    if (a.hint) head += ' <span class="tag tag-hint">💡 힌트 사용</span>';
    if (q.version !== a.qver) head += ' <span class="tag tag-wait">시험 후 수정된 문제</span>';
    if (q.status === 'deprecated') head += ' <span class="tag tag-wait">폐기된 문제</span>';
    head += '</p>';
    var n = notes[q.id];
    var inNote = n && n.state === 'active';
    return '<li class="card rv-card" data-qid="' + esc(q.id) + '">' + head +
      '<p class="q-text">' + esc(q.question) + '</p>' +
      (q.image ? '<img class="q-img" src="' + esc(q.image) + '" alt="문제 ' + (i + 1) + ' 그림">' : '') +
      '<div class="choices locked">' + q.choices.map(function (txt, k) {
        var no = k + 1, cls = 'choice', mark = '';
        if (no === q.answer) { cls += ' correct'; mark = '<span class="choice-mark">✓ 정답</span>'; }
        else if (no === a.choice) { cls += ' wrong'; mark = '<span class="choice-mark">✗ 내 답</span>'; }
        if (no === a.choice && no === q.answer) mark = '<span class="choice-mark">✓ 정답 · 내 답</span>';
        return '<div class="' + cls + '"><span class="choice-no" aria-hidden="true">' + CIRCLED[k] + '</span><span class="choice-text">' + esc(txt) + '</span>' + mark + '</div>';
      }).join('') + '</div>' +
      '<div class="feedback ' + (a.correct ? 'is-correct' : 'is-wrong') + '"><p class="fb-label">해설</p><p class="fb-text">' + esc(q.explanation) + '</p>' +
      (q.law_ref ? '<p class="fb-law small">관련 법령: ' + esc(q.law_ref) + '</p>' : '') + '</div>' +
      '<div class="rv-actions">' +
      (inNote ? '<span class="tag tag-note">📒 오답노트에 있음</span>'
        : '<button type="button" class="btn btn-outline btn-sm" data-add-note="' + esc(q.id) + '" data-choice="' + (a.choice == null ? '' : a.choice) + '">오답노트에 담기</button>') +
      reportLinkHtml(bank, q) + '</div></li>';
  }

  function renderResult(ctx, active) {
    var view = ctx.view, store = ctx.store, bank = ctx.getBank();
    var params = ctx.params();
    var data = store.getProfileData(active.id);
    var exams = (data && data.exams) || [];
    var ex = params.id ? exams.filter(function (e) { return e.id === params.id; })[0] : exams[exams.length - 1];
    if (!ex) { ctx.go('home'); return; }
    if (ctx.ensureKind(ex)) return;
    if (!bank) { view.innerHTML = '<p class="muted">문제 데이터를 불러오는 중…</p>'; return; }
    var cfg = bank.config.exam;
    var mins = Math.floor(ex.durationSec / 60), secs = ex.durationSec % 60;

    var wrong = ex.answers.filter(function (a) { return !a.correct && a.choice != null; }).length;
    var skipped = ex.answers.filter(function (a) { return a.choice == null; }).length;
    var filter = params.f || (wrong ? 'wrong' : skipped ? 'skip' : 'all');

    var rows = cfg.subjects.map(function (s) {
      var b = ex.bySubject[s.code] || { correct: 0, total: 0, score: 0 };
      return '<tr><th scope="row">' + esc(subjectShort(s.code)) + '</th><td class="num">' + b.correct + ' / ' + b.total + '</td>' +
        '<td class="num">' + b.score + '점</td><td class="bar-cell"><span class="bar" style="width:' + b.score + '%"></span></td></tr>';
    }).join('');

    var reg = ex.noteReg;
    var noteInfo = (wrong + skipped)
      ? '<section class="card note-info"><p>📒 틀린 문제 <b>' + wrong + '</b>개' + (skipped ? ', 안 푼 문제 <b>' + skipped + '</b>개' : '') + '가 <b>오답노트</b>에 등록되었습니다.' +
        (reg ? ' <span class="muted small">(새로 등록 ' + reg.added + ' · 다시 틀림 ' + reg.updated + ')</span>' : '') + '</p>' +
        '<p class="muted small">오답노트 화면과 복습 재시험은 S5 단계에서 추가됩니다.</p></section>'
      : '<section class="card note-info"><p>🎉 모든 문제를 맞혔습니다.</p></section>';

    function tab(key, label, count) {
      return '<button type="button" class="tab' + (filter === key ? ' on' : '') + '" data-filter="' + key + '" aria-pressed="' + (filter === key) + '">' + label + ' <b>' + count + '</b></button>';
    }

    view.innerHTML =
      (params.timeout ? '<div class="notice notice-warn" role="alert">시험 시간이 끝나 자동으로 종료되었습니다. 안 푼 문제는 오답으로 처리됩니다.</div>' : '') +
      (ex.sample ? '<div class="notice notice-warn small">' + (ex.kind === 'draft' ? '검수 전 문제가 포함된 미리보기 시험입니다. 실제 성적에는 포함되지 않습니다.' : '샘플 문제로 본 개발 확인용 시험입니다.') + '</div>' : '') +
      '<h1 class="page-title">시험 결과</h1>' +
      '<section class="card result-hero ' + (ex.passed ? 'pass' : 'fail') + '">' +
      '<span class="result-badge">' + (ex.passed ? '합격' : '불합격') + '</span>' +
      '<span class="result-score"><b>' + ex.score + '</b>점</span>' +
      '<span class="muted">정답 ' + ex.correct + ' / ' + ex.total + '문항 · 합격 기준 ' + cfg.pass_score + '점 · 소요 ' + mins + '분 ' + secs + '초</span>' +
      (ex.hintCount ? '<span class="muted small">💡 힌트 사용 ' + ex.hintCount + '문항 (점수에는 영향 없음)</span>' : '') +
      '<span class="muted small">' + esc(CDME.util.formatDate(ex.finishedAt)) + '</span>' +
      '</section>' +
      noteInfo +
      '<section class="card"><h2>과목별 점수</h2><div class="table-wrap" tabindex="0" role="region" aria-label="표 (좌우로 밀어 볼 수 있음)"><table class="table">' +
      '<thead><tr><th scope="col">과목</th><th scope="col" class="num">정답</th><th scope="col" class="num">점수</th><th scope="col"><span class="sr-only">막대</span></th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div></section>' +
      '<section aria-labelledby="rv-title"><h2 id="rv-title" class="section-title">문제별 다시보기</h2>' +
      '<div class="tabs" role="group" aria-label="보기 필터">' +
      tab('wrong', '틀린 문제', wrong) + tab('skip', '안 푼 문제', skipped) + tab('all', '전체', ex.total) + '</div>' +
      '<ul class="rv-list" id="rv-list"></ul></section>' +
      '<section class="card actions">' +
      '<a class="btn btn-primary" href="#/home">대시보드로</a>' +
      '<a class="btn btn-ghost" href="#/records">내 기록 보기</a>' +
      '</section>';

    var list = document.getElementById('rv-list');
    function paintList() {
      var notes = (store.getProfileData(active.id) || {}).wrongNotes || {};
      var html = '';
      ex.answers.forEach(function (a, i) {
        var show = filter === 'all' || (filter === 'wrong' && !a.correct && a.choice != null) || (filter === 'skip' && a.choice == null);
        if (show) html += reviewCardHtml(bank, notes, a, i);
      });
      list.innerHTML = html || '<li class="muted empty">해당하는 문제가 없습니다.</li>';
    }
    paintList();

    view.querySelectorAll('[data-filter]').forEach(function (b) {
      b.addEventListener('click', function () {
        filter = b.getAttribute('data-filter');
        view.querySelectorAll('[data-filter]').forEach(function (x) {
          var on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on);
        });
        paintList();
      });
    });
    list.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-add-note]') : null;
      if (!b) return;
      var q = bank.byId[b.getAttribute('data-add-note')];
      var ch = b.getAttribute('data-choice');
      var res;
      store.updateProfileData(active.id, function (d) {
        res = N.addManual(d.wrongNotes, q, { sample: !!ex.sample, choice: ch === '' ? null : +ch });
      });
      paintList();
      toast(res === 'exists' ? '이미 오답노트에 있는 문제입니다.' : '오답노트에 담았습니다.');
    });
  }

  // 다른 화면에서 함께 쓰는 도구
  CDME.ui = { subjectShort: subjectShort, toast: toast, reportLinkHtml: reportLinkHtml, hintAreaHtml: hintAreaHtml };

  CDME.views = CDME.views || {};
  CDME.views.exam = renderExam;
  CDME.views.result = renderResult;
})(window);
