/* 학습 기능 로직 (PRD 12.1, v1.1.0) – 화면과 분리
 * - 북마크: bookmarks { [qid]: { subject, added_at, sample } }
 * - 집중 학습: 과목(여러 개)·난이도·범위(전체/북마크)·문항 수를 골라 즉시 해설로 풀기
 *   studyInProgress: { id, sample, filter, startedAt, items[{qid,qver,subject,perm}], answers[], results[], hints[], current }
 *   studySessions:   [{ id, sample, filter, at, total, answered, correct, hintCount, bySubject, wrongIds }]
 *   틀린 문제는 오답노트에 자동으로 담긴다(added_by 'study'). 학습 성적은 실전 점수에 포함되지 않는다.
 * - 취약 과목 분석: 최근 N회(기본 5회) 실전 기록의 과목별 정답률을 합격선(60점)과 비교
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var util = CDME.util || (typeof require === 'function' ? require('./util.js') : null);
  var shuffle = (CDME.exam || (typeof require === 'function' ? require('./exam.js') : null)).shuffle;

  var DIFF_NAMES = { 1: '쉬움', 2: '보통', 3: '어려움' };

  /* ---------- 북마크 ---------- */
  function isBookmarked(bm, id, sample) {
    var b = bm && bm[id];
    return !!(b && !!b.sample === !!sample);
  }

  // 켜고 끄기. 반환: 바뀐 뒤 북마크 상태(true/false)
  function toggleBookmark(bm, q, sample, now) {
    if (isBookmarked(bm, q.id, sample)) { delete bm[q.id]; return false; }
    bm[q.id] = { subject: q.subject, added_at: now || util.nowISO(), sample: !!sample };
    return true;
  }

  // 현재 모드의 북마크 목록 (폐기·삭제된 문제 제외), 최근 담은 순
  function listBookmarks(bm, bank, sample, subject) {
    return Object.keys(bm || {}).filter(function (id) {
      var b = bm[id], q = bank.byId[id];
      return b && !!b.sample === !!sample && q && q.status !== 'deprecated' && (!subject || q.subject === subject);
    }).map(function (id) { return { id: id, q: bank.byId[id], mark: bm[id] }; })
      .sort(function (a, b) { return (Date.parse(b.mark.added_at || '') || 0) - (Date.parse(a.mark.added_at || '') || 0); });
  }

  function bookmarkCount(bm, bank, sample) { return listBookmarks(bm, bank, sample).length; }

  /* ---------- 출제 범위 ---------- */
  // filter: { subjects: [코드…](비면 전체), difficulty: 0(전체)|1|2|3, source: 'all'|'bookmark' }
  function normFilter(f, bank) {
    f = f || {};
    var codes = bank.config.exam.subjects.map(function (s) { return s.code; });
    var subjects = (f.subjects || []).filter(function (c) { return codes.indexOf(c) >= 0; });
    return { subjects: subjects.length ? subjects : codes.slice(), difficulty: +f.difficulty || 0, source: f.source === 'bookmark' ? 'bookmark' : 'all' };
  }

  // 조건에 맞는 출제 가능(verified) 문제 id
  function pool(bank, filter, bm, sample) {
    var f = normFilter(filter, bank);
    var out = [];
    f.subjects.forEach(function (code) {
      (bank.bySubject[code] || []).forEach(function (q) {
        if (q.status !== 'verified') return;
        if (f.difficulty && q.difficulty !== f.difficulty) return;
        if (f.source === 'bookmark' && !isBookmarked(bm, q.id, sample)) return;
        out.push(q.id);
      });
    });
    return out;
  }

  // 화면 표시용: 과목별·난이도별 문제 수 (다른 조건은 그대로 둔 채)
  function poolCounts(bank, filter, bm, sample) {
    var f = normFilter(filter, bank);
    var out = { total: pool(bank, f, bm, sample).length, subject: {}, difficulty: {}, bookmark: 0 };
    bank.config.exam.subjects.forEach(function (s) {
      out.subject[s.code] = pool(bank, { subjects: [s.code], difficulty: f.difficulty, source: f.source }, bm, sample).length;
    });
    [0, 1, 2, 3].forEach(function (d) {
      out.difficulty[d] = pool(bank, { subjects: f.subjects, difficulty: d, source: f.source }, bm, sample).length;
    });
    out.bookmark = pool(bank, { subjects: f.subjects, difficulty: f.difficulty, source: 'bookmark' }, bm, sample).length;
    return out;
  }

  /* ---------- 집중 학습 세션 ---------- */
  // opts: { filter, count(숫자|'all'), sample, bookmarks, shuffleChoices, rng, now }
  function buildStudy(bank, opts) {
    opts = opts || {};
    var rng = opts.rng || Math.random;
    var f = normFilter(opts.filter, bank);
    var ids = shuffle(pool(bank, f, opts.bookmarks, opts.sample), rng);
    if (opts.count !== 'all' && opts.count > 0) ids = ids.slice(0, opts.count);
    if (!ids.length) { var e = new Error('조건에 맞는 문제가 없습니다'); e.code = 'EMPTY'; throw e; }
    var items = ids.map(function (id) {
      var q = bank.byId[id];
      return { qid: id, qver: q.version || 1, subject: q.subject, perm: opts.shuffleChoices ? shuffle([1, 2, 3, 4], rng) : [1, 2, 3, 4] };
    });
    return {
      id: util.uuid(), type: 'study', sample: !!opts.sample, filter: f,
      startedAt: opts.now || util.nowISO(),
      items: items,
      answers: items.map(function () { return null; }),
      results: items.map(function () { return null; }),
      hints: items.map(function () { return false; }),
      current: 0
    };
  }

  // 한 문항 답하기. 틀리면 오답노트에 담음. 이미 답했으면 null
  function answer(st, notes, bank, index, original, now) {
    if (st.answers[index] != null) return null;
    now = now || util.nowISO();
    var it = st.items[index], q = bank.byId[it.qid];
    var correct = original === q.answer;
    var res = { correct: correct, noted: false };
    st.answers[index] = original;
    if (!correct && notes) {
      var n = notes[it.qid];
      if (!n) {
        notes[it.qid] = {
          subject: q.subject, question_version: q.version || 1, wrong_count: 1, streak: 0, last_choice: original,
          first_wrong_at: now, last_wrong_at: now, added_by: 'study', state: 'active', sample: !!st.sample
        };
      } else {
        n.wrong_count = (n.wrong_count || 0) + 1;
        n.last_wrong_at = now; n.last_choice = original; n.streak = 0; n.state = 'active';
        if (!n.first_wrong_at) n.first_wrong_at = now;
      }
      res.noted = true;
    }
    st.results[index] = res;
    return res;
  }

  function tally(st) {
    var c = 0, w = 0;
    st.results.forEach(function (r) { if (!r) return; if (r.correct) c++; else w++; });
    return { correct: c, wrong: w, mastered: 0, answered: c + w, total: st.items.length, unanswered: st.items.length - c - w };
  }

  function finish(st, now) {
    var t = tally(st), by = {};
    st.items.forEach(function (it, i) {
      var r = st.results[i];
      if (!r) return;
      var b = by[it.subject] || (by[it.subject] = { correct: 0, total: 0 });
      b.total++; if (r.correct) b.correct++;
    });
    return {
      id: st.id, type: 'study', sample: st.sample, filter: st.filter,
      startedAt: st.startedAt, at: now || util.nowISO(),
      total: t.total, answered: t.answered, correct: t.correct,
      hintCount: (st.hints || []).filter(function (h, i) { return h && st.answers[i] != null; }).length,
      bySubject: by,
      wrongIds: st.items.filter(function (it, i) { return st.results[i] && !st.results[i].correct; }).map(function (it) { return it.qid; })
    };
  }

  /* ---------- 취약 과목 분석 ---------- */
  // exams: 실전 기록, config: bank.config, n: 최근 몇 회(기본 5)
  function weakness(exams, sample, config, n) {
    n = n || 5;
    var list = (exams || []).filter(function (e) { return !!e.sample === !!sample; }).slice(-n);
    var line = (config.exam && config.exam.pass_score) || 60;
    var subjects = config.exam.subjects.map(function (s) {
      var c = 0, t = 0;
      list.forEach(function (e) { var b = e.bySubject && e.bySubject[s.code]; if (b) { c += b.correct; t += b.total; } });
      var rate = t ? Math.round(c * 1000 / t) / 10 : null;
      return {
        code: s.code, name: s.name, correct: c, total: t, rate: rate,
        weak: rate != null && rate < line,
        // 시험 1회(이 과목 s.count문항) 기준으로 합격선까지 더 맞혀야 할 문항 수
        need: rate != null && rate < line ? Math.ceil(s.count * (line - rate) / 100) : 0
      };
    });
    var rated = subjects.filter(function (s) { return s.rate != null; });
    var weakest = rated.length ? rated.slice().sort(function (a, b) { return a.rate - b.rate; })[0] : null;
    return {
      count: list.length, n: n, line: line, subjects: subjects,
      weak: subjects.filter(function (s) { return s.weak; }).sort(function (a, b) { return a.rate - b.rate; }),
      weakest: weakest
    };
  }

  CDME.study = {
    DIFF_NAMES: DIFF_NAMES,
    isBookmarked: isBookmarked, toggleBookmark: toggleBookmark, listBookmarks: listBookmarks, bookmarkCount: bookmarkCount,
    normFilter: normFilter, pool: pool, poolCounts: poolCounts,
    buildStudy: buildStudy, answer: answer, tally: tally, finish: finish,
    weakness: weakness
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.study;
})(typeof window !== 'undefined' ? window : globalThis);
