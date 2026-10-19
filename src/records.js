/* 내 기록 집계 (FR-501~505) – 화면과 분리 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});

  function round1(x) { return Math.round(x * 10) / 10; }

  // exams: 저장된 실전 응시 기록, sample: 현재 모드, config: config.exam
  // 복습 재시험 기록(reviewSessions)은 별도 저장이라 여기 들어오지 않음 (FR-505)
  function summarize(exams, sample, config, trendN) {
    trendN = trendN || 20;
    var list = (exams || []).filter(function (e) { return !!e.sample === !!sample; });
    var n = list.length;
    var sum = 0, best = null, passed = 0;
    list.forEach(function (e) {
      sum += e.score;
      if (best === null || e.score > best) best = e.score;
      if (e.passed) passed++;
    });
    var subjects = config.subjects.map(function (s) {
      var c = 0, t = 0;
      list.forEach(function (e) {
        var b = e.bySubject && e.bySubject[s.code];
        if (b) { c += b.correct; t += b.total; }
      });
      return { code: s.code, name: s.name, correct: c, total: t, avg: t ? round1(c * 100 / t) : null };
    });
    var startNo = Math.max(0, n - trendN);
    var trend = list.slice(startNo).map(function (e, i) {
      return { no: startNo + i + 1, id: e.id, score: e.score, passed: e.passed, at: e.finishedAt };
    });
    var history = list.map(function (e, i) { return { no: i + 1, exam: e }; }).reverse(); // 최신순
    return {
      count: n,
      avg: n ? round1(sum / n) : null,
      best: best,
      passCount: passed,
      passRate: n ? Math.round(passed * 100 / n) : null,
      recent: n ? list[n - 1].score : null,
      subjects: subjects,
      trend: trend,
      history: history
    };
  }

  CDME.records = { summarize: summarize };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.records;
})(typeof window !== 'undefined' ? window : globalThis);
