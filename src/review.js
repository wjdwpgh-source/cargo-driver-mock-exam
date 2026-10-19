/* 복습 재시험 로직 (PRD 4.3, 7.4 (4), FR-701~708) – 화면과 분리
 * - 범위: all(전체 오답) / subject:CODE / frequent(틀린 횟수 2회 이상) / recent(최근 7일) / mastered(복습 완료 문제)
 * - 문제 순서와 보기 순서를 섞고, 채점·저장은 원래 보기 번호 기준 (FR-705)
 * - 답할 때마다 오답노트에 바로 반영 (즉시 해설 방식): 정답 → 연속 정답 +1, 2회면 복습 완료 / 오답 → 연속 0, 틀린 횟수 +1
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var util = CDME.util || (typeof require === 'function' ? require('./util.js') : null);
  var shuffle = (CDME.exam || (typeof require === 'function' ? require('./exam.js') : null)).shuffle;

  var DEFAULTS = { mastery_streak: 2, recent_days: 7, frequent_count: 2 };
  function opt(cfg) {
    var r = (cfg && cfg.review) || {};
    return {
      mastery: r.mastery_streak || DEFAULTS.mastery_streak,
      recentDays: r.recent_days || DEFAULTS.recent_days,
      frequent: r.frequent_count || DEFAULTS.frequent_count
    };
  }

  function usable(bank, id) {
    var q = bank.byId[id];
    return !!(q && q.status !== 'deprecated');
  }

  // 범위에 맞는 오답노트 문제 id 목록
  function candidates(notes, bank, sample, scope, nowMs) {
    var o = opt(bank.config);
    nowMs = nowMs || Date.now();
    var since = nowMs - o.recentDays * 86400000;
    return Object.keys(notes || {}).filter(function (id) {
      var n = notes[id];
      if (!n || !!n.sample !== !!sample || !usable(bank, id)) return false;
      if (scope === 'mastered') return n.state === 'mastered';
      if (n.state !== 'active') return false;
      if (scope === 'all' || !scope) return true;
      if (scope === 'frequent') return (n.wrong_count || 0) >= o.frequent;
      if (scope === 'recent') {
        var t = Date.parse(n.last_wrong_at || n.added_at || '');
        return !isNaN(t) && t >= since;
      }
      if (scope.indexOf('subject:') === 0) return n.subject === scope.slice(8);
      return false;
    });
  }

  // 범위별 문제 수 (설정 화면 표시용)
  function scopeCounts(notes, bank, sample, nowMs) {
    var out = {
      all: candidates(notes, bank, sample, 'all', nowMs).length,
      frequent: candidates(notes, bank, sample, 'frequent', nowMs).length,
      recent: candidates(notes, bank, sample, 'recent', nowMs).length,
      mastered: candidates(notes, bank, sample, 'mastered', nowMs).length
    };
    bank.config.exam.subjects.forEach(function (s) {
      out['subject:' + s.code] = candidates(notes, bank, sample, 'subject:' + s.code, nowMs).length;
    });
    return out;
  }

  // count: 숫자 또는 'all'
  function buildReview(notes, bank, opts) {
    opts = opts || {};
    var rng = opts.rng || Math.random;
    var ids = shuffle(candidates(notes, bank, opts.sample, opts.scope, opts.nowMs), rng);
    if (opts.count !== 'all' && opts.count > 0) ids = ids.slice(0, opts.count);
    if (!ids.length) { var e = new Error('복습할 문제가 없습니다'); e.code = 'EMPTY'; throw e; }
    var items = ids.map(function (id) {
      var q = bank.byId[id];
      return { qid: id, qver: q.version || 1, subject: q.subject, perm: shuffle([1, 2, 3, 4], rng) };
    });
    return {
      id: util.uuid(),
      sample: !!opts.sample,
      scope: opts.scope || 'all',
      startedAt: opts.now || util.nowISO(),
      timed: !!opts.timed,
      totalMs: opts.timed ? items.length * 60000 : null,
      remainingMs: opts.timed ? items.length * 60000 : null,
      items: items,
      answers: items.map(function () { return null; }),   // 원래 보기 번호
      results: items.map(function () { return null; }),   // { correct, mastered, reactivated }
      hints: items.map(function () { return false; }),    // 힌트를 본 문항 (FR-312)
      current: 0
    };
  }

  // 화면에 k번째(0~3)로 보인 보기 → 원래 보기 번호
  function originalChoice(item, displayIndex) { return item.perm[displayIndex]; }
  // 원래 번호 → 화면 위치(0~3)
  function displayIndexOf(item, original) { return item.perm.indexOf(original); }

  // 한 문항 답하기 + 오답노트 즉시 반영. 이미 답했으면 null
  function answer(rv, notes, bank, index, original, now) {
    if (rv.answers[index] != null) return null;
    now = now || util.nowISO();
    var o = opt(bank.config);
    var it = rv.items[index];
    var q = bank.byId[it.qid];
    var correct = original === q.answer;
    var n = notes[it.qid];
    var res = { correct: correct, mastered: false, reactivated: false, streak: 0 };
    rv.answers[index] = original;
    if (n) {
      if (correct) {
        if (n.state === 'active') {
          n.streak = (n.streak || 0) + 1;
          if (n.streak >= o.mastery) { n.state = 'mastered'; n.mastered_at = now; res.mastered = true; }
        }
      } else {
        if (n.state === 'mastered') res.reactivated = true;
        n.state = 'active';
        n.streak = 0;
        n.wrong_count = (n.wrong_count || 0) + 1;
        n.last_choice = original;
        n.last_wrong_at = now;
      }
      n.last_review_at = now;
      res.streak = n.streak || 0;
    }
    rv.results[index] = res;
    return res;
  }

  function tally(rv) {
    var c = 0, w = 0, m = 0;
    rv.results.forEach(function (r) { if (!r) return; if (r.correct) c++; else w++; if (r.mastered) m++; });
    return { correct: c, wrong: w, mastered: m, answered: c + w, total: rv.items.length, unanswered: rv.items.length - c - w };
  }

  // 복습 세션 기록 (실전 기록과 분리 저장, FR-505)
  function finish(rv, now) {
    var t = tally(rv);
    return {
      id: rv.id, sample: rv.sample, scope: rv.scope, mode: 'instant',
      startedAt: rv.startedAt, at: now || util.nowISO(),
      total: t.total, answered: t.answered, correct: t.correct,
      hintCount: (rv.hints || []).filter(function (h, i) { return h && rv.answers[i] != null; }).length,
      mastered: rv.items.filter(function (it, i) { return rv.results[i] && rv.results[i].mastered; }).map(function (it) { return it.qid; }),
      wrongIds: rv.items.filter(function (it, i) { return rv.results[i] && !rv.results[i].correct; }).map(function (it) { return it.qid; })
    };
  }

  // 오답노트 직접 관리
  function setMastered(notes, id, now) { var n = notes[id]; if (!n) return false; n.state = 'mastered'; n.mastered_at = now || util.nowISO(); return true; }
  function setActive(notes, id) { var n = notes[id]; if (!n) return false; n.state = 'active'; n.streak = 0; return true; }
  function remove(notes, id) { if (!notes[id]) return false; delete notes[id]; return true; }

  // 오답노트 목록 (FR-604): state 'active'|'mastered', subject 코드 또는 '', sort 'recent'|'count'
  function listNotes(notes, bank, sample, opts) {
    opts = opts || {};
    var rows = Object.keys(notes || {}).filter(function (id) {
      var n = notes[id];
      return n && !!n.sample === !!sample && usable(bank, id) && n.state === (opts.state || 'active') &&
        (!opts.subject || n.subject === opts.subject);
    }).map(function (id) {
      var n = notes[id], q = bank.byId[id];
      return { id: id, note: n, q: q, changed: (q.version || 1) !== (n.question_version || 1) };
    });
    function t(r) { return Date.parse(r.note.last_wrong_at || r.note.added_at || r.note.first_wrong_at || '') || 0; }
    rows.sort(opts.sort === 'count'
      ? function (a, b) { return (b.note.wrong_count || 0) - (a.note.wrong_count || 0) || t(b) - t(a); }
      : function (a, b) { return t(b) - t(a) || (b.note.wrong_count || 0) - (a.note.wrong_count || 0); });
    return rows;
  }

  function summary(notes, bank, sample) {
    var bySubject = {};
    bank.config.exam.subjects.forEach(function (s) { bySubject[s.code] = 0; });
    var active = 0, mastered = 0;
    Object.keys(notes || {}).forEach(function (id) {
      var n = notes[id];
      if (!n || !!n.sample !== !!sample || !usable(bank, id)) return;
      if (n.state === 'active') { active++; bySubject[n.subject] = (bySubject[n.subject] || 0) + 1; }
      else if (n.state === 'mastered') mastered++;
    });
    return { active: active, mastered: mastered, bySubject: bySubject };
  }

  CDME.review = {
    candidates: candidates, scopeCounts: scopeCounts, buildReview: buildReview,
    originalChoice: originalChoice, displayIndexOf: displayIndexOf, answer: answer, tally: tally, finish: finish,
    setMastered: setMastered, setActive: setActive, remove: remove, listNotes: listNotes, summary: summary
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.review;
})(typeof window !== 'undefined' ? window : globalThis);
