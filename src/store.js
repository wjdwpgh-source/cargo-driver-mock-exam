/* 사용자 기록 저장소 (PRD 7.3)
 * - 브라우저 localStorage에 키 'cdme' 하나로 저장
 * - localStorage를 쓸 수 없으면(시크릿 모드·차단) 메모리에 임시 저장하고 mode='memory'로 알림 (NFR-05)
 * - schemaVersion으로 구조 변경 시 자동 변환 (NFR-09)
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var util = CDME.util || (typeof require === 'function' ? require('./util.js') : null);

  var KEY = 'cdme';
  var SCHEMA_VERSION = 1;
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

  // 이후 버전에서 구조가 바뀌면 여기에 단계별 변환을 추가한다.
  var MIGRATIONS = {
    // 예) 1: function (s) { ...; s.schemaVersion = 2; return s; }
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
      if (!state.data[p.id]) state.data[p.id] = emptyProfileData();
      // v1.1.0에서 추가된 항목 (북마크·집중 학습) – 예전 기록에는 없으므로 빈 값으로 채움
      var d = state.data[p.id];
      if (!d.bookmarks || typeof d.bookmarks !== 'object' || Array.isArray(d.bookmarks)) d.bookmarks = {};
      if (!Array.isArray(d.studySessions)) d.studySessions = [];
      if (d.studyInProgress === undefined) d.studyInProgress = null;
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

    function read() {
      loadError = null;
      blocked = false;
      var raw = adapter.get(KEY);
      if (!raw) { state = emptyState(); return; }
      try {
        state = migrate(JSON.parse(raw));
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

    var api = {
      SCHEMA_VERSION: SCHEMA_VERSION,
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
        state.data[p.id] = emptyProfileData();
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

      getProfileData: function (id) {
        id = id || state.activeProfileId;
        return id ? state.data[id] || null : null;
      },

      // 이후 스프린트(시험·오답노트)에서 사용할 저장 함수
      updateProfileData: function (id, fn) {
        var d = state.data[id];
        if (!d) return false;
        fn(d);
        var ok = write(); emit();
        return ok;
      },

      // 백업 불러오기용: 기록을 가진 새 닉네임 추가 (FR-902)
      addProfileWithData: function (name, data, meta) {
        var v = validateName(name, state.profiles);
        if (!v.ok) return v;
        meta = meta || {};
        var p = { id: util.uuid(), name: v.name, createdAt: meta.createdAt || util.nowISO(), lastUsedAt: util.nowISO() };
        state.profiles.push(p);
        var d = emptyProfileData();
        Object.keys(data || {}).forEach(function (k) { d[k] = data[k]; });
        state.data[p.id] = d;
        if (!state.activeProfileId) state.activeProfileId = p.id;
        var ok = write(); emit();
        return { ok: ok, profile: p };
      },

      // 닉네임 기록 전체 교체 (덮어쓰기·초기화용)
      replaceProfileData: function (id, data) {
        if (!state.data[id]) return false;
        var d = emptyProfileData();
        Object.keys(data || {}).forEach(function (k) { d[k] = data[k]; });
        state.data[id] = d;
        var ok = write(); emit();
        return ok;
      },

      emptyProfileData: emptyProfileData,

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
    SCHEMA_VERSION: SCHEMA_VERSION
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.store;
})(typeof window !== 'undefined' ? window : globalThis);
