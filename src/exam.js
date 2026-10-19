/* 실전 모의시험 로직 (PRD 7.4) – 화면과 분리해 단위 테스트 가능
 * - 출제: verified 문제에서 과목별 규정 수만큼, 과목 순서대로, 최근 2회 출제 문제는 뒤로 미룸 (FR-201, 202, 209, 211)
 * - 진행 상태(inProgress): 답안·현재 위치·남은 시간을 저장해 이어 풀기 (FR-208)
 * - 채점: 답을 고르는 즉시 문항별 정오 판정(v1.9), 최종 점수 = 정답 수 × (100 ÷ 총 문항), 안 푼 문항은 오답
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var util = CDME.util || (typeof require === 'function' ? require('./util.js') : null);
  var Q = CDME.questions || (typeof require === 'function' ? require('./questions.js') : null);

  var RECENT_EXAMS = 2;

  // Fisher–Yates
  function shuffle(arr, rng) {
    rng = rng || Math.random;
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  // 최근 n회 응시(같은 모드)에 나온 문제 id 집합
  function recentQids(exams, sample, n) {
    n = n == null ? RECENT_EXAMS : n;
    var set = {};
    (exams || []).filter(function (e) { return !!e.sample === !!sample; })
      .slice(-n)
      .forEach(function (e) { (e.answers || []).forEach(function (a) { set[a.qid] = true; }); });
    return set;
  }

  // FR-211: 과목별 verified 문제가 규정 수 이상인지
  function checkReady(bank) {
    var lacking = [];
    bank.config.exam.subjects.forEach(function (s) {
      var have = Q.verifiedOf(bank, s.code).length;
      if (have < s.count) lacking.push({ code: s.code, name: s.name, have: have, need: s.count });
    });
    return { ok: lacking.length === 0, lacking: lacking };
  }

  function buildExam(bank, opts) {
    opts = opts || {};
    var rng = opts.rng || Math.random;
    var recent = opts.recent || {};
    var ready = checkReady(bank);
    if (!ready.ok) {
      var err = new Error('출제 가능한 문제가 부족합니다');
      err.code = 'NOT_READY'; err.lacking = ready.lacking;
      throw err;
    }
    var items = [];
    bank.config.exam.subjects.forEach(function (s) {
      var pool = shuffle(Q.verifiedOf(bank, s.code), rng);
      var fresh = pool.filter(function (q) { return !recent[q.id]; });
      var seen = pool.filter(function (q) { return recent[q.id]; });
      fresh.concat(seen).slice(0, s.count).forEach(function (q) {
        items.push({ qid: q.id, qver: q.version || 1, subject: s.code });
      });
    });
    var totalMs = bank.config.exam.minutes * 60 * 1000;
    return {
      id: util.uuid(),
      sample: !!opts.sample,
      startedAt: opts.now || util.nowISO(),
      totalMs: totalMs,
      remainingMs: totalMs,
      items: items,
      answers: items.map(function () { return null; }),
      hints: items.map(function () { return false; }),
      current: 0,
      alerts: {}
    };
  }

  // opts.lock: 이미 답한 문항은 바꿀 수 없음 (v1.9 즉시 채점 방식)
  function setAnswer(ip, index, choice, opts) {
    if (index < 0 || index >= ip.items.length) return false;
    if (choice !== null && !(choice >= 1 && choice <= 4)) return false;
    if (opts && opts.lock && ip.answers[index] != null) return false;
    ip.answers[index] = choice;
    return true;
  }

  // 한 문항 채점 결과
  function judge(ip, bank, index) {
    var q = bank.byId[ip.items[index].qid];
    var choice = ip.answers[index];
    var answered = choice != null;
    return { answered: answered, choice: choice, answer: q ? q.answer : null, correct: !!(q && answered && choice === q.answer) };
  }

  // 진행 중 정답·오답·남은 문항 수
  function tally(ip, bank) {
    var c = 0, w = 0;
    for (var i = 0; i < ip.items.length; i++) {
      var j = judge(ip, bank, i);
      if (j.answered) { if (j.correct) c++; else w++; }
    }
    return { correct: c, wrong: w, unanswered: ip.items.length - c - w };
  }

  function counts(ip) {
    var answered = ip.answers.filter(function (a) { return a != null; }).length;
    return { total: ip.items.length, answered: answered, unanswered: ip.items.length - answered };
  }

  function firstUnanswered(ip) {
    for (var i = 0; i < ip.answers.length; i++) if (ip.answers[i] == null) return i;
    return -1;
  }

  // 이어 풀기 전 검사: 문제가 삭제되었거나 폐기되었는지
  function missingQuestions(ip, bank) {
    return ip.items.filter(function (it) {
      var q = bank.byId[it.qid];
      return !q || q.status === 'deprecated';
    }).map(function (it) { return it.qid; });
  }

  function round2(x) { return Math.round(x * 100) / 100; }

  function score(ip, bank, opts) {
    opts = opts || {};
    var cfg = bank.config.exam;
    var bySubject = {};
    cfg.subjects.forEach(function (s) { bySubject[s.code] = { correct: 0, total: 0 }; });
    var correct = 0, hintCount = 0;
    var answers = ip.items.map(function (it, i) {
      var q = bank.byId[it.qid];
      var choice = ip.answers[i];
      var ok = !!(q && choice != null && choice === q.answer);
      if (ok) correct++;
      var bs = bySubject[it.subject] || (bySubject[it.subject] = { correct: 0, total: 0 });
      bs.total++; if (ok) bs.correct++;
      var a = { qid: it.qid, qver: it.qver, choice: choice, correct: ok };
      if (hintUsed(ip, i)) { a.hint = true; hintCount++; }
      return a;
    });
    var total = ip.items.length;
    var sc = total ? round2(correct * 100 / total) : 0;
    Object.keys(bySubject).forEach(function (k) {
      var b = bySubject[k];
      b.score = b.total ? round2(b.correct * 100 / b.total) : 0;
    });
    var used = Math.max(0, ip.totalMs - Math.max(0, ip.remainingMs));
    return {
      id: ip.id,
      sample: !!ip.sample,
      startedAt: ip.startedAt,
      finishedAt: opts.now || util.nowISO(),
      durationSec: Math.round(used / 1000),
      timedOut: !!opts.timedOut,
      total: total,
      correct: correct,
      score: sc,
      passed: sc >= cfg.pass_score,
      bySubject: bySubject,
      hintCount: hintCount,
      answers: answers
    };
  }

  /* 힌트 (PRD v1.17 FR-312)
   * - 문제에 hint 글이 있으면 그 글을 보여 줌
   * - 없으면 틀린 보기 하나를 지워 줌 (같은 문제는 늘 같은 보기 → 이어 풀기·다시 열어도 동일)
   */
  function hashStr(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
    return h;
  }
  function hintFor(q) {
    if (!q) return null;
    var text = (q.hint || '').trim();
    if (text) return { type: 'text', text: text };
    var wrongs = [1, 2, 3, 4].filter(function (n) { return n !== q.answer; });
    return { type: 'elim', remove: wrongs[hashStr(String(q.id)) % wrongs.length] };
  }
  // 힌트 사용 기록. 이미 답한 문항은 기록하지 않음 → true/false
  function useHint(ip, index) {
    if (index < 0 || index >= ip.items.length) return false;
    if (ip.answers[index] != null) return false;
    if (!ip.hints) ip.hints = ip.items.map(function () { return false; });   // 예전에 시작한 시험 호환
    ip.hints[index] = true;
    return true;
  }
  function hintUsed(ip, index) { return !!(ip.hints && ip.hints[index]); }

  function formatTime(ms) {
    var s = Math.max(0, Math.ceil(ms / 1000));
    var m = Math.floor(s / 60), r = s % 60;
    return (m < 10 ? '0' + m : m) + ':' + (r < 10 ? '0' + r : r);
  }

  CDME.exam = {
    shuffle: shuffle, recentQids: recentQids, checkReady: checkReady, buildExam: buildExam,
    setAnswer: setAnswer, judge: judge, tally: tally, counts: counts, firstUnanswered: firstUnanswered,
    missingQuestions: missingQuestions, score: score,
    hintFor: hintFor, useHint: useHint, hintUsed: hintUsed, formatTime: formatTime, RECENT_EXAMS: RECENT_EXAMS
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.exam;
})(typeof window !== 'undefined' ? window : globalThis);
