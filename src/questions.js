/* 문제 데이터 불러오기 (PRD 7.2)
 * - data/config.json 과 과목별 data/questions/<과목코드>.json 을 불러온다
 * - 형식이 잘못된 문제는 제외하고 경고 목록에 기록한다
 * - 출제에는 status = verified 문제만 사용한다 (FR-201)
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});

  var STATUSES = ['draft', 'reviewed', 'verified', 'deprecated'];

  // config.json을 읽지 못할 때 화면 안내용으로만 쓰는 기본 규격
  var DEFAULT_CONFIG = {
    exam: {
      minutes: 80, pass_score: 60,
      subjects: [
        { code: 'LAW', name: '교통 및 화물자동차 운수사업 관련 법규', count: 25 },
        { code: 'CARGO', name: '화물취급요령', count: 15 },
        { code: 'SAFE', name: '안전운행', count: 25 },
        { code: 'SERVICE', name: '운송서비스', count: 15 }
      ]
    }
  };

  function checkQuestion(q, subjectCode) {
    var errs = [];
    if (!q || typeof q !== 'object') return ['문제 형식이 아닙니다'];
    if (typeof q.id !== 'string' || !/^[A-Z]+-\d{4}$/.test(q.id)) errs.push('id 형식 오류(예: LAW-0001)');
    else if (q.id.split('-')[0] !== subjectCode) errs.push('id의 과목코드가 파일과 다름');
    if (q.subject !== subjectCode) errs.push('subject가 파일 과목코드와 다름');
    if (typeof q.question !== 'string' || !q.question.trim()) errs.push('지문 없음');
    if (!Array.isArray(q.choices) || q.choices.length !== 4 || q.choices.some(function (c) { return typeof c !== 'string' || !c.trim(); })) errs.push('보기는 4개가 필요');
    if (!(q.answer >= 1 && q.answer <= 4 && q.answer % 1 === 0)) errs.push('정답은 1~4');
    if (typeof q.explanation !== 'string' || !q.explanation.trim()) errs.push('해설 없음');
    if (STATUSES.indexOf(q.status) < 0) errs.push('status 값 오류');
    if (q.version != null && !(q.version >= 1 && q.version % 1 === 0)) errs.push('version은 1 이상의 정수');
    return errs;
  }

  function buildBank(config, filesBySubject) {
    var bank = { config: config, bySubject: {}, byId: {}, warnings: [] };
    config.exam.subjects.forEach(function (s) {
      var file = filesBySubject[s.code];
      var list = [];
      if (!file) {
        bank.warnings.push(s.code + ': 문제 파일을 불러오지 못했습니다');
      } else {
        (file.questions || []).forEach(function (q, i) {
          var errs = checkQuestion(q, s.code);
          if (errs.length) {
            bank.warnings.push(s.code + ' ' + (q && q.id ? q.id : '#' + (i + 1)) + ': ' + errs.join(', '));
            return;
          }
          if (bank.byId[q.id]) { bank.warnings.push(q.id + ': id 중복'); return; }
          if (q.version == null) q.version = 1;
          bank.byId[q.id] = q;
          list.push(q);
        });
      }
      bank.bySubject[s.code] = list;
    });
    return bank;
  }

  function summarize(bank) {
    var rows = bank.config.exam.subjects.map(function (s) {
      var list = bank.bySubject[s.code] || [];
      var c = { draft: 0, reviewed: 0, verified: 0, deprecated: 0 };
      list.forEach(function (q) { c[q.status]++; });
      return { code: s.code, name: s.name, need: s.count, total: list.length, counts: c, ready: c.verified >= s.count };
    });
    return {
      subjects: rows,
      verified: rows.reduce(function (a, r) { return a + r.counts.verified; }, 0),
      need: rows.reduce(function (a, r) { return a + r.need; }, 0),
      examReady: rows.every(function (r) { return r.ready; })
    };
  }

  function verifiedOf(bank, code) {
    return (bank.bySubject[code] || []).filter(function (q) { return q.status === 'verified'; });
  }

  function fetchJson(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(url + ' (' + r.status + ')');
      return r.json();
    });
  }

  // base: 'data/' 처럼 끝에 / 포함, folder: 'questions/'(실제) 또는 'samples/'(개발 확인용)
  function load(base, folder) {
    base = base || 'data/';
    folder = folder || 'questions/';
    return fetchJson(base + 'config.json').then(function (config) {
      var files = {};
      return Promise.all(config.exam.subjects.map(function (s) {
        return fetchJson(base + folder + s.code + '.json')
          .then(function (j) { files[s.code] = j; })
          .catch(function () { files[s.code] = null; });
      })).then(function () { return buildBank(config, files); });
    });
  }

  CDME.questions = { load: load, buildBank: buildBank, checkQuestion: checkQuestion, summarize: summarize, verifiedOf: verifiedOf, STATUSES: STATUSES, DEFAULT_CONFIG: DEFAULT_CONFIG };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.questions;
})(typeof window !== 'undefined' ? window : globalThis);
