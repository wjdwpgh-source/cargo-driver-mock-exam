/* 문제 데이터 불러오기 (PRD 7.2)
 * - data/config.json 과 과목별 data/questions/<과목코드>.json 을 불러온다
 * - 형식이 잘못된 문제는 제외하고 경고 목록에 기록한다
 * - 출제에는 status = verified 문제만 사용한다 (FR-201)
 * - (v2.0) config.json v2: exams.{cargo|license}. load(base, folder, kind)는 고른 시험의 규격을
 *   예전 형태(config.exam.subjects …)로 펼쳐 넘겨, 출제·채점·기록 코드는 그대로 쓴다 (PRD 13.6.1)
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});

  var STATUSES = ['draft', 'reviewed', 'verified', 'deprecated'];

  // config.json을 읽지 못할 때 화면 안내용으로만 쓰는 기본 규격
  var DEFAULT_EXAMS = {
    cargo: {
      name: '화물운송종사자격', short: '화물', minutes: 80, pass_score: 60, group_label: '과목', folder: 'questions/', choices: '4지선다',
      groups: [
        { code: 'LAW', name: '교통 및 화물자동차 운수사업 관련 법규', count: 25 },
        { code: 'CARGO', name: '화물취급요령', count: 15 },
        { code: 'SAFE', name: '안전운행', count: 25 },
        { code: 'SERVICE', name: '운송서비스', count: 15 }
      ]
    },
    license: {
      name: '대형운전면허(1종) 학과', short: '대형', minutes: 40, pass_score: 70, group_label: '유형', folder: 'license/questions/', id_prefix: 'DL',
      choices: '4지·5지선다(1답·2답)', score_note: '학습용 점수: 전 문항 2.5점',
      groups: [
        { code: 'TEXT1', name: '문장형', count: 17, choices: 4, answers: 1 },
        { code: 'TEXT2', name: '문장형(2답)', count: 4, choices: 4, answers: 2 },
        { code: 'SIGN', name: '안전표지형', count: 5, choices: 4, answers: 1 },
        { code: 'ILLUST2', name: '일러스트형(2답)', count: 13, choices: 5, answers: 2 },
        { code: 'ILLUST1', name: '일러스트형(상황)', count: 1, choices: 4, answers: 1 }
      ]
    }
  };
  var EXAM_KINDS = ['cargo', 'license'];

  // 시험 하나의 규격을 예전 config.exam 형태로 (subjects = groups)
  function examView(e) {
    var o = {};
    Object.keys(e).forEach(function (k) { o[k] = e[k]; });
    o.groups = e.groups || e.subjects || [];
    o.subjects = o.groups;
    return o;
  }

  // config.json(v1 또는 v2) → 고른 시험의 펼친 설정
  function normalizeConfig(raw, kind) {
    raw = raw || {};
    var exams = {};
    if (raw.exams) {
      EXAM_KINDS.forEach(function (k) { if (raw.exams[k]) exams[k] = raw.exams[k]; });
    } else if (raw.exam) {
      // v1 형식(화물 하나)
      var c = {}; Object.keys(DEFAULT_EXAMS.cargo).forEach(function (k) { c[k] = DEFAULT_EXAMS.cargo[k]; });
      Object.keys(raw.exam).forEach(function (k) { c[k] = raw.exam[k]; });
      c.groups = raw.exam.subjects || c.groups;
      if (raw.data_date) c.data_date = raw.data_date;
      exams.cargo = c;
    }
    if (!Object.keys(exams).length) exams = DEFAULT_EXAMS;
    if (!exams[kind]) kind = exams[raw.default_exam] ? raw.default_exam : Object.keys(exams)[0];
    var e = examView(exams[kind]);
    var out = {};
    Object.keys(raw).forEach(function (k) { if (k !== 'exam') out[k] = raw[k]; });
    out.kind = kind;
    out.exams = exams;
    out.exam = e;
    out.data_date = e.data_date || raw.data_date || null;
    out.site_name = raw.site_name || '면허문제의 모든것';
    return out;
  }

  var DEFAULT_CONFIG = normalizeConfig({ exams: DEFAULT_EXAMS }, 'cargo');

  // 시험 이름 (config가 없으면 기본값)
  function examName(kind, config) {
    var e = (config && config.exams && config.exams[kind]) || DEFAULT_EXAMS[kind];
    return e ? e.name : kind;
  }
  function examShort(kind, config) {
    var e = (config && config.exams && config.exams[kind]) || DEFAULT_EXAMS[kind];
    return e ? (e.short || e.name) : kind;
  }

  // idPrefix: 대형면허처럼 id 앞머리가 과목(그룹) 코드와 다른 시험 (예: DL-0001, 그룹 TEXT1)
  // rule: 출제 그룹 규칙 { choices: 보기 수, answers: 정답 수 } (없으면 화물 기준 4지 1답)
  function checkQuestion(q, subjectCode, idPrefix, rule) {
    var nc = (rule && rule.choices) || 4, na = (rule && rule.answers) || 1;
    var errs = [];
    var pre = idPrefix || subjectCode;
    if (!q || typeof q !== 'object') return ['문제 형식이 아닙니다'];
    if (typeof q.id !== 'string' || !/^[A-Z]+-\d{4}$/.test(q.id)) errs.push('id 형식 오류(예: ' + pre + '-0001)');
    else if (q.id.split('-')[0] !== pre) errs.push('id의 앞머리가 ' + pre + '가 아님');
    if (q.subject !== subjectCode) errs.push('subject가 파일 과목코드와 다름');
    if (typeof q.question !== 'string' || !q.question.trim()) errs.push('지문 없음');
    if (!Array.isArray(q.choices) || q.choices.length !== nc || q.choices.some(function (c) { return typeof c !== 'string' || !c.trim(); })) errs.push('보기는 ' + nc + '개가 필요');
    // 정답: 1답은 정수(또는 원소 1개 배열), 2답은 서로 다른 번호 2개 배열 (v2.0)
    var ans = Array.isArray(q.answer) ? q.answer : [q.answer];
    var okNum = ans.every(function (n) { return n >= 1 && n <= nc && n % 1 === 0; });
    var uniq = ans.filter(function (n, i) { return ans.indexOf(n) === i; }).length === ans.length;
    if (!okNum || !uniq || ans.length !== na) errs.push(na > 1 ? '정답은 1~' + nc + ' 중 서로 다른 ' + na + '개' : '정답은 1~' + nc);
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
          var errs = checkQuestion(q, s.code, config.exam.id_prefix, s);
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

  // base: 'data/' 처럼 끝에 / 포함, folder: 생략하면 시험별 폴더(화물 'questions/', 대형 'license/questions/'),
  // 'samples/'면 개발 확인용 샘플(화물만), kind: 'cargo' | 'license'
  function load(base, folder, kind) {
    base = base || 'data/';
    return fetchJson(base + 'config.json').then(function (raw) {
      var config = normalizeConfig(raw, kind);
      folder = folder || config.exam.folder || 'questions/';
      var files = {};
      return Promise.all(config.exam.subjects.map(function (s) {
        return fetchJson(base + folder + s.code + '.json')
          .then(function (j) { files[s.code] = j; })
          .catch(function () { files[s.code] = null; });
      })).then(function () { return buildBank(config, files); });
    });
  }

  CDME.questions = { load: load, buildBank: buildBank, checkQuestion: checkQuestion, summarize: summarize, verifiedOf: verifiedOf, STATUSES: STATUSES,
    DEFAULT_CONFIG: DEFAULT_CONFIG, DEFAULT_EXAMS: DEFAULT_EXAMS, EXAM_KINDS: EXAM_KINDS, normalizeConfig: normalizeConfig, examName: examName, examShort: examShort };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.questions;
})(typeof window !== 'undefined' ? window : globalThis);
