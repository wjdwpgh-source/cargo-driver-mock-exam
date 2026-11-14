/* 사용자 기록 저장소 (PRD 7.3)
 * - 브라우저 localStorage에 키 'cdme' 하나로 저장
 * - localStorage를 쓸 수 없으면(시크릿 모드·차단) 메모리에 임시 저장하고 mode='memory'로 알림 (NFR-05)
 * - schemaVersion으로 구조 변경 시 자동 변환 (NFR-09)
 * - (v2.0) 시험 종류별 기록: data[닉네임id][시험종류] (cargo·license). 현재 시험은 기기 설정 'cdme_exam'
 *   getProfileData·updateProfileData·replaceProfileData는 '현재 시험'의 기록을 다룬다
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var util = CDME.util || (typeof require === 'function' ? require('./util.js') : null);

  var KEY = 'cdme';
  var SCHEMA_VERSION = 2;
  var EXAM_KEY = 'cdme_exam';
  var BACKUP_V1_KEY = 'cdme_backup_v1';
  var EXAM_KINDS = ['cargo', 'license'];
  var DEFAULT_EXAM = 'cargo';
  var NAME_MAX = 12;

  /* ---------- 저장 어댑터 ---------- */
  function memoryAdapter() {
    var mem = {};
    return {
      mode: 'memory',
      get: function (k) { return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; },
      set: function (k, v) { mem[k] = String(v); },
      remove: function (k) { delete mem[k]; }
    };
  }

  function localStorageAdapter(ls) {
    try {
      var probe = '__cdme_probe__';
      ls.setItem(probe, '1');
      ls.removeItem(probe);
    } catch (e) {
      return null;
    }
    return {
      mode: 'local',
      get: function (k) { return ls.getItem(k); },
      set: function (k, v) { ls.setItem(k, v); },
      remove: function (k) { ls.removeItem(k); }
    };
  }

  function defaultAdapter() {
    var a = null;
    try { if (root.localStorage) a = localStorageAdapter(root.localStorage); } catch (e) { a = null; }
    return a || memoryAdapter();
  }

  /* ---------- 데이터 구조 ---------- */
  function emptyState() {
    return { schemaVersion: SCHEMA_VERSION, activeProfileId: null, profiles: [], data: {} };
  }

  function emptyProfileData() {
    return { exams: [], wrongNotes: {}, reviewSessions: [], inProgress: null, reviewInProgress: null,
      bookmarks: {}, studySessions: [], studyInProgress: null };
  }

  function emptyAllData() {
    var o = {};
    EXAM_KINDS.forEach(function (k) { o[k] = emptyProfileData(); });
    return o;
  }

  // 시험 하나의 기록 보정 (v1.1.0 항목 등 빠진 값 채우기)
  function fixExamData(d) {
    if (!d || typeof d !== 'object' || Array.isArray(d)) d = emptyProfileData();
    var e = emptyProfileData();
    Object.keys(e).forEach(function (k) { if (d[k] === undefined) d[k] = e[k]; });
    if (!Array.isArray(d.exams)) d.exams = [];
    if (!d.wrongNotes || typeof d.wrongNotes !== 'object' || Array.isArray(d.wrongNotes)) d.wrongNotes = {};
    if (!Array.isArray(d.reviewSessions)) d.reviewSessions = [];
    if (!d.bookmarks || typeof d.bookmarks !== 'object' || Array.isArray(d.bookmarks)) d.bookmarks = {};
    if (!Array.isArray(d.studySessions)) d.studySessions = [];
    return d;
  }

  // 단계별 변환 (NFR-09)
  var MIGRATIONS = {
    // v2.0: 닉네임별 기록을 시험 종류별로 나눔 – 기존 기록은 모두 화물(cargo)
    1: function (s) {
      var data = {};
      Object.keys(s.data || {}).forEach(function (pid) {
        var all = emptyAllData();
        all.cargo = s.data[pid];
        data[pid] = all;
      });
      s.data = data;
      s.schemaVersion = 2;
      return s;
    }
  };

  function migrate(state) {
    if (!state || typeof state !== 'object') return emptyState();
    if (typeof state.schemaVersion !== 'number') state.schemaVersion = 1;
    while (state.schemaVersion < SCHEMA_VERSION) {
      var fn = MIGRATIONS[state.schemaVersion];
      if (!fn) throw new Error('지원하지 않는 저장 데이터 버전: ' + state.schemaVersion);
      state = fn(state);
    }
    if (state.schemaVersion > SCHEMA_VERSION) {
      var err = new Error('이 프로그램보다 새로운 버전의 기록입니다. 페이지를 새로고침해 최신 버전을 사용하세요. (기존 기록 보호를 위해 저장이 중지됩니다)');
      err.code = 'NEWER';
      throw err;
    }
    if (!Array.isArray(state.profiles)) state.profiles = [];
    if (!state.data || typeof state.data !== 'object') state.data = {};
    state.profiles.forEach(function (p) {
      var all = state.data[p.id];
      if (!all || typeof all !== 'object' || Array.isArray(all)) all = state.data[p.id] = emptyAllData();
      EXAM_KINDS.forEach(function (k) { all[k] = fixExamData(all[k]); });
    });
    if (state.activeProfileId && !state.data[state.activeProfileId]) state.activeProfileId = null;
    return state;
  }

  /* ---------- 닉네임 검사 (FR-101, 102) ---------- */
  function normalizeName(name) {
    return String(name == null ? '' : name).replace(/\s+/g, ' ').trim();
  }

  function sameName(a, b) {
    return normalizeName(a).toLowerCase() === normalizeName(b).toLowerCase();
  }

  function validateName(name, profiles, exceptId) {
    var n = normalizeName(name);
    if (!n) return { ok: false, error: '닉네임을 입력해 주세요.' };
    if (Array.from(n).length > NAME_MAX) return { ok: false, error: '닉네임은 ' + NAME_MAX + '자 이내로 입력해 주세요.' };
    if (/[<>"'`\\]/.test(n)) return { ok: false, error: '닉네임에 < > " \' ` \\ 기호는 쓸 수 없습니다.' };
    var dup = (profiles || []).some(function (p) { return p.id !== exceptId && sameName(p.name, n); });
    if (dup) return { ok: false, error: '이미 있는 닉네임입니다. 다른 이름을 입력하거나 목록에서 선택해 주세요.' };
    return { ok: true, name: n };
  }

  /* ---------- 저장소 ---------- */
  function createStore(adapter) {
    adapter = adapter || defaultAdapter();
    var state = null;
    var loadError = null;
    var blocked = false;   // 더 새로운 버전의 기록이 있으면 덮어쓰지 않도록 저장 중지
    var listeners = [];
    var examKind = DEFAULT_EXAM;
    try { var ek = adapter.get(EXAM_KEY); if (EXAM_KINDS.indexOf(ek) >= 0) examKind = ek; } catch (e) { /* 무시 */ }

    function read() {
      loadError = null;
      blocked = false;
      var raw = adapter.get(KEY);
      if (!raw) { state = emptyState(); return; }
      try {
        var parsed = JSON.parse(raw);
        // v2.0: 구조 변환 전 원본을 한 번 보관 (NFR-09, 13.4)
        if (parsed && typeof parsed === 'object' && (parsed.schemaVersion || 1) < SCHEMA_VERSION) {
          try { if (!adapter.get(BACKUP_V1_KEY)) adapter.set(BACKUP_V1_KEY, raw); } catch (e3) { /* 무시 */ }
        }
        state = migrate(parsed);
      } catch (e) {
        // 손상된 데이터는 지우지 않고 별도 키로 보관한 뒤 새로 시작
        loadError = e.message || String(e);
        state = emptyState();
        if (e.code === 'NEWER') { blocked = true; return; }
        try { adapter.set(KEY + '_broken_' + Date.now(), raw); } catch (e2) { /* 무시 */ }
      }
    }

    function write() {
      if (blocked) return false;
      try {
        adapter.set(KEY, JSON.stringify(state));
        return true;
      } catch (e) {
        loadError = '기록을 저장하지 못했습니다(저장 공간 부족 등). 백업 후 일부 기록을 정리해 주세요.';
        return false;
      }
    }

    function emit() { listeners.forEach(function (fn) { try { fn(); } catch (e) { /* 무시 */ } }); }

    function findProfile(id) {
      for (var i = 0; i < state.profiles.length; i++) if (state.profiles[i].id === id) return state.profiles[i];
      return null;
    }

    read();
    // 변환한 구조를 바로 저장 (다음 접속부터 변환 없이 읽음)
    if (!blocked && !loadError && state.profiles.length) { try { var cur = adapter.get(KEY); if (cur && JSON.parse(cur).schemaVersion !== SCHEMA_VERSION) write(); } catch (e) { /* 무시 */ } }

    function examData(id, kind) {
      var all = state.data[id];
      return all ? all[kind || examKind] || null : null;
    }

    var api = {
      SCHEMA_VERSION: SCHEMA_VERSION,
      EXAM_KINDS: EXAM_KINDS.slice(),
      get exam() { return examKind; },
      setExam: function (kind) {
        if (EXAM_KINDS.indexOf(kind) < 0) return false;
        examKind = kind;
        try { adapter.set(EXAM_KEY, kind); } catch (e) { /* 무시 */ }
        emit();
        return true;
      },
      NAME_MAX: NAME_MAX,
      get mode() { return adapter.mode; },
      get error() { return loadError; },
      get blocked() { return blocked; },
      reload: function () { read(); emit(); },
      onChange: function (fn) { listeners.push(fn); },

      listProfiles: function () { return state.profiles.slice(); },
      getProfile: function (id) { return findProfile(id); },
      getActiveProfile: function () { return state.activeProfileId ? findProfile(state.activeProfileId) : null; },
      validateName: function (name, exceptId) { return validateName(name, state.profiles, exceptId); },

      createProfile: function (name) {
        var v = validateName(name, state.profiles);
        if (!v.ok) return v;
        var p = { id: util.uuid(), name: v.name, createdAt: util.nowISO(), lastUsedAt: util.nowISO() };
        state.profiles.push(p);
        state.data[p.id] = emptyAllData();
        state.activeProfileId = p.id;
        write(); emit();
        return { ok: true, profile: p };
      },

      selectProfile: function (id) {
        var p = findProfile(id);
        if (!p) return { ok: false, error: '닉네임을 찾을 수 없습니다.' };
        p.lastUsedAt = util.nowISO();
        state.activeProfileId = id;
        write(); emit();
        return { ok: true, profile: p };
      },

      renameProfile: function (id, name) {
        var p = findProfile(id);
        if (!p) return { ok: false, error: '닉네임을 찾을 수 없습니다.' };
        var v = validateName(name, state.profiles, id);
        if (!v.ok) return v;
        p.name = v.name;
        write(); emit();
        return { ok: true, profile: p };
      },

      deleteProfile: function (id) {
        var p = findProfile(id);
        if (!p) return { ok: false, error: '닉네임을 찾을 수 없습니다.' };
        state.profiles = state.profiles.filter(function (x) { return x.id !== id; });
        delete state.data[id];
        if (state.activeProfileId === id) state.activeProfileId = null;
        write(); emit();
        return { ok: true };
      },

      logout: function () {
        state.activeProfileId = null;
        write(); emit();
      },

      // 현재 시험(kind 생략 시)의 기록
      getProfileData: function (id, kind) {
        id = id || state.activeProfileId;
        return id ? examData(id, kind) : null;
      },

      // 모든 시험의 기록 { cargo, license } (백업·닉네임 관리용)
      getProfileAll: function (id) {
        id = id || state.activeProfileId;
        return id ? state.data[id] || null : null;
      },

      updateProfileData: function (id, fn, kind) {
        var d = examData(id, kind);
        if (!d) return false;
        fn(d);
        var ok = write(); emit();
        return ok;
      },

      // 백업 불러오기용: 기록을 가진 새 닉네임 추가 (FR-902). all = { cargo: {...}, license: {...} } (없는 시험은 빈 기록)
      addProfileWithData: function (name, all, meta) {
        var v = validateName(name, state.profiles);
        if (!v.ok) return v;
        meta = meta || {};
        var p = { id: util.uuid(), name: v.name, createdAt: meta.createdAt || util.nowISO(), lastUsedAt: util.nowISO() };
        state.profiles.push(p);
        var a = emptyAllData();
        EXAM_KINDS.forEach(function (k) {
          var src = all && all[k];
          if (src) Object.keys(src).forEach(function (f) { a[k][f] = src[f]; });
        });
        state.data[p.id] = a;
        if (!state.activeProfileId) state.activeProfileId = p.id;
        var ok = write(); emit();
        return { ok: ok, profile: p };
      },

      // 현재 시험(또는 kind) 기록 전체 교체 (덮어쓰기·초기화용)
      replaceProfileData: function (id, data, kind) {
        if (!state.data[id]) return false;
        var d = emptyProfileData();
        Object.keys(data || {}).forEach(function (k) { d[k] = data[k]; });
        state.data[id][kind || examKind] = d;
        var ok = write(); emit();
        return ok;
      },

      emptyProfileData: emptyProfileData,
      emptyAllData: emptyAllData,

      // 테스트·백업용
      _snapshot: function () { return JSON.parse(JSON.stringify(state)); }
    };
    return api;
  }

  CDME.store = {
    createStore: createStore,
    memoryAdapter: memoryAdapter,
    localStorageAdapter: localStorageAdapter,
    validateName: validateName,
    normalizeName: normalizeName,
    migrate: migrate,
    KEY: KEY,
    EXAM_KEY: EXAM_KEY,
    BACKUP_V1_KEY: BACKUP_V1_KEY,
    EXAM_KINDS: EXAM_KINDS,
    DEFAULT_EXAM: DEFAULT_EXAM,
    emptyProfileData: emptyProfileData,
    emptyAllData: emptyAllData,
    SCHEMA_VERSION: SCHEMA_VERSION
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.store;
})(typeof window !== 'undefined' ? window : globalThis);
