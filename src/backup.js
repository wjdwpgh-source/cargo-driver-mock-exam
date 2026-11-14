/* 기록 백업·불러오기·초기화 (FR-801~803, FR-901~903) – 화면과 분리
 * 백업 파일 형식:
 * { "app": "cdme", "kind": "backup", "schemaVersion": 1, "exportedAt": ISO,
 *   "profiles": [ { "name": "닉네임", "createdAt": ISO, "data": { exams, wrongNotes, reviewSessions, bookmarks, studySessions } } ] }
 *   (bookmarks·studySessions는 v1.1.0 추가 – 없는 예전 백업도 그대로 불러옴)
 * (v2.0) schemaVersion 2: profiles[].data = { cargo: {...}, license: {...} } – 시험 종류별 기록
 *   schemaVersion 1 백업은 화물(cargo) 기록으로 읽는다
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var util = CDME.util || (typeof require === 'function' ? require('./util.js') : null);
  var S = CDME.store || (typeof require === 'function' ? require('./store.js') : null);

  var APP = 'cdme', KIND = 'backup';
  var MAX_BYTES = 20 * 1024 * 1024;

  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  // 진행 중인 시험·복습은 백업하지 않음 (기기를 옮기면 이어 풀 수 없으므로)
  function cleanData(d) {
    d = d || {};
    return {
      exams: Array.isArray(d.exams) ? clone(d.exams) : [],
      wrongNotes: d.wrongNotes && typeof d.wrongNotes === 'object' && !Array.isArray(d.wrongNotes) ? clone(d.wrongNotes) : {},
      reviewSessions: Array.isArray(d.reviewSessions) ? clone(d.reviewSessions) : [],
      bookmarks: d.bookmarks && typeof d.bookmarks === 'object' && !Array.isArray(d.bookmarks) ? clone(d.bookmarks) : {},
      studySessions: Array.isArray(d.studySessions) ? clone(d.studySessions) : []
    };
  }

  function kinds() { return S.EXAM_KINDS || ['cargo']; }

  // 시험별 기록 묶음 정리. all = { cargo, license } (없는 시험은 빠짐)
  function cleanAll(all) {
    var out = {};
    kinds().forEach(function (k) { if (all && all[k]) out[k] = cleanData(all[k]); });
    return out;
  }

  // FR-901: profiles = [{ name, createdAt, data: { cargo, license } }]
  function buildBackup(profiles, now) {
    return {
      app: APP, kind: KIND, schemaVersion: S.SCHEMA_VERSION,
      exportedAt: now || util.nowISO(),
      profiles: profiles.map(function (p) { return { name: p.name, createdAt: p.createdAt || null, data: cleanAll(p.data) }; })
    };
  }

  function fileName(label, now) {
    var d = now ? new Date(now) : new Date();
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    var stamp = d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '_' + p(d.getHours()) + p(d.getMinutes());
    var safe = String(label || '전체').replace(/[\\/:*?"<>|\s]+/g, '_');
    return '면허문제_백업_' + safe + '_' + stamp + '.json';
  }

  // 시험별 요약 { cargo: {...}, license: {...} }
  function summarizeAll(all) {
    var out = {};
    kinds().forEach(function (k) { if (all && all[k]) out[k] = summarizeData(all[k]); });
    return out;
  }

  function summarizeData(d) {
    d = d || {};
    var notes = d.wrongNotes || {};
    return {
      exams: (d.exams || []).length,
      notes: Object.keys(notes).filter(function (k) { return notes[k].state === 'active'; }).length,
      mastered: Object.keys(notes).filter(function (k) { return notes[k].state === 'mastered'; }).length,
      reviews: (d.reviewSessions || []).length,
      bookmarks: Object.keys(d.bookmarks || {}).length,
      studies: (d.studySessions || []).length
    };
  }

  // FR-902: 형식·버전 검사. 반환 { ok, backup } | { ok:false, error }
  function parse(text) {
    if (typeof text !== 'string' || !text.trim()) return { ok: false, error: '빈 파일입니다.' };
    if (text.length > MAX_BYTES) return { ok: false, error: '파일이 너무 큽니다.' };
    var j;
    try { j = JSON.parse(text.replace(/^﻿/, '')); } catch (e) { return { ok: false, error: '백업 파일 형식이 아닙니다(JSON 읽기 실패).' }; }
    if (!j || j.app !== APP || j.kind !== KIND) return { ok: false, error: '이 프로그램의 백업 파일이 아닙니다.' };
    if (typeof j.schemaVersion !== 'number') return { ok: false, error: '백업 파일 버전 정보가 없습니다.' };
    if (j.schemaVersion > S.SCHEMA_VERSION) return { ok: false, error: '더 새로운 버전의 프로그램에서 만든 백업입니다. 페이지를 새로고침해 최신 버전으로 불러오세요.' };
    if (!Array.isArray(j.profiles) || !j.profiles.length) return { ok: false, error: '백업 파일에 닉네임 기록이 없습니다.' };
    function badData(d) {
      if ((d.exams && !Array.isArray(d.exams)) || (d.reviewSessions && !Array.isArray(d.reviewSessions)) ||
          (d.studySessions && !Array.isArray(d.studySessions)) || (d.bookmarks && (typeof d.bookmarks !== 'object' || Array.isArray(d.bookmarks))) ||
          (d.wrongNotes && (typeof d.wrongNotes !== 'object' || Array.isArray(d.wrongNotes)))) return '기록 형식이 올바르지 않습니다.';
      var bad = (d.exams || []).some(function (e) { return !e || typeof e.id !== 'string' || typeof e.score !== 'number' || !Array.isArray(e.answers); });
      return bad ? '시험 기록 형식이 올바르지 않습니다.' : null;
    }
    var profiles = [];
    for (var i = 0; i < j.profiles.length; i++) {
      var p = j.profiles[i];
      var name = S.normalizeName(p && p.name);
      if (!name) return { ok: false, error: (i + 1) + '번째 닉네임 이름이 없습니다.' };
      var raw = p.data || {};
      if (typeof raw !== 'object' || Array.isArray(raw)) return { ok: false, error: '"' + name + '"의 기록 형식이 올바르지 않습니다.' };
      // schemaVersion 1 백업 = 화물 기록 하나
      var all = j.schemaVersion < 2 ? { cargo: raw } : raw;
      var data = {};
      for (var k = 0; k < kinds().length; k++) {
        var kind = kinds()[k];
        if (!all[kind]) continue;
        var msg = typeof all[kind] !== 'object' || Array.isArray(all[kind]) ? '기록 형식이 올바르지 않습니다.' : badData(all[kind]);
        if (msg) return { ok: false, error: '"' + name + '"의 ' + msg };
        data[kind] = cleanData(all[kind]);
      }
      profiles.push({ name: name, createdAt: p.createdAt || null, data: data });
    }
    return { ok: true, backup: { schemaVersion: j.schemaVersion, exportedAt: j.exportedAt || null, profiles: profiles } };
  }

  function noteTime(n) {
    return Math.max(Date.parse(n.last_wrong_at || '') || 0, Date.parse(n.last_review_at || '') || 0,
      Date.parse(n.mastered_at || '') || 0, Date.parse(n.added_at || '') || 0, Date.parse(n.first_wrong_at || '') || 0);
  }

  // 합치기: 시험·복습 기록은 id 기준 합집합, 오답노트는 최근에 바뀐 쪽을 쓰되 틀린 횟수는 큰 값
  function merge(target, src) {
    var out = cleanData(target);
    out.inProgress = target.inProgress || null;
    out.reviewInProgress = target.reviewInProgress || null;
    out.studyInProgress = target.studyInProgress || null;
    function unionById(a, b, timeKey) {
      var seen = {};
      a.forEach(function (x) { seen[x.id] = true; });
      var res = a.concat(b.filter(function (x) { return x && !seen[x.id]; }));
      res.sort(function (x, y) { return (Date.parse(x[timeKey] || '') || 0) - (Date.parse(y[timeKey] || '') || 0); });
      return res;
    }
    out.exams = unionById(out.exams, src.exams || [], 'finishedAt');
    out.reviewSessions = unionById(out.reviewSessions, src.reviewSessions || [], 'at');
    out.studySessions = unionById(out.studySessions, src.studySessions || [], 'at');
    Object.keys(src.bookmarks || {}).forEach(function (id) { if (!out.bookmarks[id]) out.bookmarks[id] = clone(src.bookmarks[id]); });
    Object.keys(src.wrongNotes || {}).forEach(function (id) {
      var a = out.wrongNotes[id], b = src.wrongNotes[id];
      if (!a) { out.wrongNotes[id] = clone(b); return; }
      var newer = noteTime(b) > noteTime(a) ? clone(b) : a;
      newer.wrong_count = Math.max(a.wrong_count || 0, b.wrong_count || 0);
      out.wrongNotes[id] = newer;
    });
    return out;
  }

  // 이름이 겹치지 않는 새 이름 (예: 화물왕 (2))
  function freeName(name, existing) {
    var taken = existing.map(function (n) { return S.normalizeName(n).toLowerCase(); });
    var base = Array.from(S.normalizeName(name)).slice(0, 8).join('');
    for (var k = 2; k < 100; k++) {
      var cand = base + ' (' + k + ')';
      if (taken.indexOf(cand.toLowerCase()) < 0) return cand;
    }
    return base + ' ' + Date.now() % 1000;
  }

  // 불러오기 계획: 같은 이름이 있으면 기본 '합치기' (FR-903)
  function plan(backup, existingProfiles) {
    return backup.profiles.map(function (p) {
      var hit = existingProfiles.filter(function (e) { return S.normalizeName(e.name).toLowerCase() === p.name.toLowerCase(); })[0];
      return { name: p.name, data: p.data, createdAt: p.createdAt, existingId: hit ? hit.id : null, action: hit ? 'merge' : 'new', summary: summarizeAll(p.data) };
    });
  }

  // 계획 실행. store API 사용. 반환 [{ name, action, ok, profileId, newName? }]
  function apply(store, steps) {
    return steps.map(function (st) {
      if (st.action === 'skip') return { name: st.name, action: 'skip', ok: true };
      if (st.action === 'new' || st.action === 'rename') {
        var name = st.action === 'rename' ? (st.newName || freeName(st.name, store.listProfiles().map(function (x) { return x.name; }))) : st.name;
        var r = store.addProfileWithData(name, cleanAll(st.data), { createdAt: st.createdAt });
        return { name: st.name, action: st.action, ok: !!r.ok, error: r.error, profileId: r.profile && r.profile.id, newName: name };
      }
      // 덮어쓰기·합치기는 백업에 들어 있는 시험만 바꾸고, 없는 시험의 기록은 그대로 둔다
      if (st.action === 'overwrite') {
        var ok1 = true;
        Object.keys(st.data || {}).forEach(function (kind) {
          var d = cleanData(st.data[kind]); d.inProgress = null; d.reviewInProgress = null; d.studyInProgress = null;
          ok1 = store.replaceProfileData(st.existingId, d, kind) && ok1;
        });
        return { name: st.name, action: 'overwrite', ok: ok1, profileId: st.existingId };
      }
      if (st.action === 'merge') {
        var ok2 = true;
        Object.keys(st.data || {}).forEach(function (kind) {
          var m = merge(store.getProfileData(st.existingId, kind) || {}, st.data[kind]);
          ok2 = store.replaceProfileData(st.existingId, m, kind) && ok2;
        });
        return { name: st.name, action: 'merge', ok: ok2, profileId: st.existingId };
      }
      return { name: st.name, action: st.action, ok: false, error: '알 수 없는 처리 방식' };
    });
  }

  /* ---------- 초기화 (FR-801~803) ---------- */
  // scope: 'exams'(실전 기록만) | 'notes'(오답노트만) | 'all'(실전 + 오답노트 + 복습·학습 기록 + 북마크)
  function resetData(d, scope) {
    var out = {
      exams: d.exams || [], wrongNotes: d.wrongNotes || {}, reviewSessions: d.reviewSessions || [],
      inProgress: d.inProgress || null, reviewInProgress: d.reviewInProgress || null,
      bookmarks: d.bookmarks || {}, studySessions: d.studySessions || [], studyInProgress: d.studyInProgress || null
    };
    if (scope === 'exams' || scope === 'all') { out.exams = []; out.inProgress = null; }
    if (scope === 'notes' || scope === 'all') { out.wrongNotes = {}; out.reviewInProgress = null; }
    if (scope === 'all') { out.reviewSessions = []; out.bookmarks = {}; out.studySessions = []; out.studyInProgress = null; }
    return out;
  }

  // 실전 기록 1건 삭제 (오답노트는 그대로 둠)
  function deleteExam(d, examId) {
    var before = (d.exams || []).length;
    d.exams = (d.exams || []).filter(function (e) { return e.id !== examId; });
    return d.exams.length < before;
  }

  CDME.backup = {
    buildBackup: buildBackup, fileName: fileName, parse: parse, plan: plan, apply: apply, merge: merge,
    freeName: freeName, summarizeData: summarizeData, summarizeAll: summarizeAll, cleanAll: cleanAll, resetData: resetData, deleteExam: deleteExam, cleanData: cleanData
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.backup;
})(typeof window !== 'undefined' ? window : globalThis);
