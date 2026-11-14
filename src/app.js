/* 앱 시작·화면 전환 (S1: 시작/닉네임, 대시보드, 닉네임 관리 · S2: 실전 시험, 간이 결과)
 * (v2.0 L1) 시험 종류(화물·대형면허) 선택·전환, 시험 선택 화면 #/exams, 현재 시험 배지 */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var util = CDME.util, esc = util.escapeHtml, modal = CDME.modal;

  var store = CDME.store.createStore();
  var bank = null;          // 문제 데이터 (불러오기 전 null)
  var bankError = null;     // 불러오기 실패 사유
  var view = document.getElementById('view');
  var userChip = document.getElementById('user-chip');
  var examChip = document.getElementById('exam-chip');
  var examStatus = {};      // 시험 선택 화면용: 다른 시험의 문제 준비 현황 { kind: summary | 'loading' | 'error' }
  var cleanupFn = null;
  var lastRoute = null;     // 현재 화면이 떠날 때 실행할 정리 함수(타이머 등)

  /* ---------- 개발·검수용 모드 (기기별 설정) ----------
   * devKind: ''(실제 – verified 문제만) | 'sample'(가짜 샘플 문제) | 'draft'(검수 미리보기 – 초안·1차 검수 문제도 출제)
   * 샘플·미리보기 모드의 시험·오답 기록은 sample 표시로 실제 성적과 분리된다.
   */
  var SAMPLE_KEY = 'cdme_sample';
  var devKind = '';
  try {
    var sv = root.localStorage.getItem(SAMPLE_KEY);
    devKind = sv === '1' ? 'sample' : sv === 'draft' ? 'draft' : '';
  } catch (e) { devKind = ''; }
  var sampleMode = !!devKind;

  function setDevKind(kind) {
    devKind = kind === 'sample' || kind === 'draft' ? kind : '';
    if (devKind === 'sample' && store.exam !== 'cargo') devKind = '';   // 샘플 문제는 화물만 (FR-L16)
    sampleMode = !!devKind;
    try {
      if (devKind) root.localStorage.setItem(SAMPLE_KEY, devKind === 'sample' ? '1' : 'draft');
      else root.localStorage.removeItem(SAMPLE_KEY);
    } catch (e) { /* 무시 */ }
    loadBank();
  }
  function setSampleMode(on) { setDevKind(on ? 'sample' : ''); }

  /* 공개 사이트에서는 개발·검수용 모드를 숨긴다 (PRD v1.21, config.json "dev_modes": false)
   * 운영자는 주소 뒤에 ?dev=1 을 붙여 열면(그 창을 닫을 때까지) 미리보기·샘플 모드를 쓸 수 있다. */
  var DEV_KEY = 'cdme_dev';
  try {
    if (/[?&]dev=1(&|$)/.test(root.location.search)) root.sessionStorage.setItem(DEV_KEY, '1');
  } catch (e) { /* 무시 */ }
  function devAllowed(b) {
    try { if (root.sessionStorage.getItem(DEV_KEY) === '1') return true; } catch (e) { /* 무시 */ }
    b = b || bank;
    return !(b && b.config && b.config.dev_modes === false);
  }

  // 기록·진행 상태가 만들어진 모드로 맞춤. 바꿨으면 true
  function ensureKind(obj) {
    var want = obj && obj.sample ? (obj.kind || 'sample') : '';
    if (want && !devAllowed()) return false;   // 공개 모드: 예전 미리보기·샘플 기록은 실제 모드에서 그대로 보여 줌
    if (want === devKind) return false;
    setDevKind(want);
    return true;
  }

  /* ---------- 화면 전환 ---------- */
  var ROUTES = {
    start: renderStart, home: renderHome, profiles: renderProfiles, exams: renderExams,
    exam: function (a) { CDME.views.exam(ctx, a); },
    result: function (a) { CDME.views.result(ctx, a); },
    records: function (a) { CDME.views.records(ctx, a); },
    notes: function (a) { CDME.views.notes(ctx, a); },
    review: function (a) { CDME.views.review(ctx, a); },
    'review-play': function (a) { CDME.views.reviewPlay(ctx, a); },
    'review-result': function (a) { CDME.views.reviewResult(ctx, a); },
    study: function (a) { CDME.views.study(ctx, a); },
    'study-play': function (a) { CDME.views.studyPlay(ctx, a); },
    'study-result': function (a) { CDME.views.studyResult(ctx, a); },
    bookmarks: function (a) { CDME.views.bookmarks(ctx, a); },
    data: function (a) { CDME.views.data(ctx, a); },
    help: function (a) { CDME.views.help(ctx, a); }
  };

  function hashParts() {
    var h = (location.hash || '').replace(/^#\/?/, '');
    var i = h.indexOf('?');
    return { route: i < 0 ? h : h.slice(0, i), query: i < 0 ? '' : h.slice(i + 1) };
  }

  function currentRoute() {
    var h = hashParts().route;
    return ROUTES[h] ? h : '';
  }

  function params() {
    var out = {};
    hashParts().query.split('&').forEach(function (kv) {
      if (!kv) return;
      var p = kv.split('=');
      out[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || '');
    });
    return out;
  }

  function go(route) {
    if (location.hash === '#/' + route) render();
    else location.hash = '#/' + route;
  }

  function render() {
    if (cleanupFn) { var f = cleanupFn; cleanupFn = null; try { f(); } catch (e) { console.error(e); } }
    document.querySelectorAll('.modal-backdrop').forEach(function (m) { m.remove(); });
    var route = currentRoute();
    var active = store.getActiveProfile();
    // 닉네임이 선택되지 않았으면 시작 화면으로 (FR-101, 106)
    if (!active && route !== 'start' && route !== 'profiles' && route !== 'help') route = 'start';
    if (!active && route === 'profiles' && store.listProfiles().length === 0) route = 'start';
    if (active && (route === '' || route === 'start')) route = 'home';
    if (!route) route = 'start';
    if (hashParts().route !== route) history.replaceState(null, '', '#/' + route);
    document.body.classList.toggle('in-exam', route === 'exam' || route === 'review-play' || route === 'study-play');
    // 다른 화면으로 옮기면 이전 화면의 알림은 지움 (같은 화면 다시 그리기는 유지)
    var changed = lastRoute !== route;
    if (changed) document.querySelectorAll('.toast').forEach(function (t) { t.remove(); });
    lastRoute = route;

    renderUserChip(active);
    renderExamChip(active);
    ROUTES[route](active);
    var h = view.querySelector('h1, h2');
    if (h) { h.setAttribute('tabindex', '-1'); }
    if (changed) {
      // 화면이 바뀌면 맨 위로, 화면 읽기 프로그램이 새 제목부터 읽도록 제목에 포커스 (입력칸에 포커스가 간 경우는 그대로)
      window.scrollTo(0, 0);
      if (h && (document.activeElement === document.body || !view.contains(document.activeElement)) && document.activeElement !== document.getElementById('font-btn')) {
        try { h.focus({ preventScroll: true }); } catch (e) { /* 무시 */ }
      }
    }
  }

  /* ---------- 글자 크기 (NFR-07) ---------- */
  var FONT_KEY = 'cdme_font';
  var FONTS = [{ v: '', name: '보통' }, { v: 'l', name: '크게' }, { v: 'xl', name: '아주 크게' }];
  function getFont() { var a = document.documentElement.getAttribute('data-font') || ''; return a; }
  function setFont(v) {
    if (v) document.documentElement.setAttribute('data-font', v); else document.documentElement.removeAttribute('data-font');
    try { if (v) root.localStorage.setItem(FONT_KEY, v); else root.localStorage.removeItem(FONT_KEY); } catch (e) { /* 무시 */ }
    updateFontBtn();
    window.dispatchEvent(new Event('resize'));   // 그래프 등 크기 다시 계산
  }
  function updateFontBtn() {
    var b = document.getElementById('font-btn');
    if (!b) return;
    var i = 0; FONTS.forEach(function (f, k) { if (f.v === getFont()) i = k; });
    var next = FONTS[(i + 1) % FONTS.length];
    b.setAttribute('aria-label', '글자 크기: ' + FONTS[i].name + '. 누르면 ' + next.name);
    b.title = '글자 크기: ' + FONTS[i].name;
  }
  function cycleFont() {
    var i = 0; FONTS.forEach(function (f, k) { if (f.v === getFont()) i = k; });
    var next = FONTS[(i + 1) % FONTS.length];
    setFont(next.v);
    if (CDME.ui && CDME.ui.toast) CDME.ui.toast('글자 크기: ' + next.name);
  }
  document.getElementById('font-btn').addEventListener('click', cycleFont);
  updateFontBtn();

  /* ---------- 오프라인 표시·오프라인 동작 (NFR-04) ---------- */
  var offBadge = document.getElementById('offline-badge');
  function updateOnline() { offBadge.hidden = navigator.onLine !== false; }
  window.addEventListener('online', updateOnline);
  window.addEventListener('offline', updateOnline);
  updateOnline();
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function (e) { console.warn('[오프라인 준비 실패]', e); });
    });
  }

  function renderExamChip(active) {
    if (!examChip) return;
    if (active) {
      var k = store.exam;
      examChip.hidden = false;
      examChip.className = 'exam-chip exam-' + k;
      examChip.textContent = CDME.questions.examShort(k, bank && bank.config);
      examChip.setAttribute('aria-label', '현재 시험: ' + CDME.questions.examName(k, bank && bank.config) + ' – 누르면 시험 바꾸기');
    } else {
      examChip.hidden = true;
    }
  }

  function renderUserChip(active) {
    if (active) {
      userChip.hidden = false;
      userChip.innerHTML = '<span class="chip-label">닉네임</span> <strong>' + esc(active.name) + '</strong>';
    } else {
      userChip.hidden = true;
      userChip.innerHTML = '';
    }
  }

  /* ---------- 공통 안내 ---------- */
  function noticeHtml() {
    var out = '';
    if (devKind === 'sample') {
      out += '<div class="notice notice-warn" role="status"><strong>샘플 문제 모드</strong> – 개발 확인용 가짜 문제로 동작 중입니다. ' +
        '<button type="button" class="link-btn" data-sample-off>샘플 모드 끄기</button></div>';
    } else if (devKind === 'draft') {
      out += '<div class="notice notice-warn" role="status"><strong>검수 미리보기 모드</strong> – 검수가 끝나지 않은 초안 문제도 출제됩니다. 정답·해설이 틀릴 수 있으며, 기록은 실제 성적과 따로 저장됩니다. ' +
        '<button type="button" class="link-btn" data-sample-off>미리보기 끄기</button></div>';
    }
    if (store.mode === 'memory') {
      out += '<div class="notice notice-warn" role="status"><strong>기록이 저장되지 않는 환경입니다.</strong> ' +
        '시크릿 모드이거나 브라우저 저장이 차단되어 있어, 창을 닫으면 기록이 사라집니다.</div>';
    }
    if (store.error) {
      out += '<div class="notice notice-error" role="alert">' + esc(store.error) + '</div>';
    }
    return out;
  }

  function bankStatusHtml() {
    if (bankError) {
      var fileHint = location.protocol === 'file:'
        ? ' 파일을 직접 열면 문제 데이터를 읽을 수 없습니다. 폴더의 <b>실행.bat</b>으로 열어 주세요.'
        : '';
      return '<div class="notice notice-error" role="alert">문제 데이터를 불러오지 못했습니다.' + fileHint + '</div>';
    }
    if (!bank) return '<p class="muted">문제 데이터를 불러오는 중…</p>';
    var s = CDME.questions.summarize(bank);
    var rows = s.subjects.map(function (r) {
      return '<tr><th scope="row">' + esc(r.name) + '</th>' +
        '<td class="num">' + r.counts.verified + ' / ' + r.need + '</td>' +
        '<td>' + (r.ready ? '<span class="tag tag-ok">✓ 준비됨</span>' : '<span class="tag tag-wait">준비 중</span>') + '</td></tr>';
    }).join('');
    var gl = bank.config.exam.group_label || '과목';
    return '<div class="table-wrap" tabindex="0" role="region" aria-label="표 (좌우로 밀어 볼 수 있음)"><table class="table"><caption class="sr-only">' + esc(gl) + '별 출제 가능 문제 수</caption>' +
      '<thead><tr><th scope="col">' + esc(gl) + '</th><th scope="col" class="num">출제 가능 / 필요</th><th scope="col">상태</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>' +
      (bank.warnings.length ? '<p class="muted small">형식 오류로 제외된 문제 ' + bank.warnings.length + '건 (개발자 도구 콘솔 참고)</p>' : '');
  }

  /* ---------- 시작 화면 (FR-101~103, 106) ---------- */
  function renderStart() {
    // 다시 그려도 입력 중이던 닉네임·커서는 유지 (문제 데이터 불러오기가 끝나 화면이 갱신될 때)
    var prevInput = document.getElementById('nick');
    var keep = prevInput ? { value: prevInput.value, focused: document.activeElement === prevInput, err: (document.getElementById('nick-err') || {}).textContent || '' } : null;
    var cfg = bank ? bank.config.exam : (bankError ? CDME.questions.normalizeConfig({}, store.exam).exam : null);
    var prevPick = view.querySelector('[name=start-exam]:checked');
    var pick = prevPick ? prevPick.value : store.exam;
    var profiles = store.listProfiles().sort(function (a, b) { return (b.lastUsedAt || '').localeCompare(a.lastUsedAt || ''); });

    var list = profiles.length
      ? '<section class="card"><h2>내 닉네임으로 계속하기</h2><ul class="profile-list">' +
        profiles.map(function (p) {
          return '<li><button type="button" class="profile-btn" data-select="' + esc(p.id) + '">' +
            '<span class="avatar" aria-hidden="true">' + esc(Array.from(p.name)[0]) + '</span>' +
            '<span class="pname">' + esc(p.name) + '</span>' +
            '<span class="pmeta">최근 사용 ' + esc(util.formatDate(p.lastUsedAt)) + '</span></button></li>';
        }).join('') + '</ul>' +
        '<p class="small"><a href="#/profiles">닉네임 관리(이름 변경·삭제)</a></p></section>'
      : '';

    view.innerHTML =
      noticeHtml() +
      '<section class="hero">' +
      '<h1>면허문제의 모든것</h1>' +
      '<p class="lead">화물운송종사자격 · 대형운전면허(1종) 학과<br>가입 없이 닉네임만 입력하면 바로 시작합니다.<br>실전 모의시험 · 해설 · 오답 복습 · 성적 관리</p>' +
      '</section>' +
      '<section class="card"><h2>' + (profiles.length ? '새 닉네임 만들기' : '닉네임 입력') + '</h2>' +
      '<form id="new-form" novalidate>' +
      '<fieldset class="exam-pick"><legend class="field">준비할 시험</legend><div class="opts">' +
      CDME.questions.EXAM_KINDS.map(function (k) {
        var e = CDME.questions.normalizeConfig(bank ? bank.config : {}, k).exam;
        var total = e.subjects.reduce(function (a, x) { return a + x.count; }, 0);
        return '<label class="opt"><input type="radio" name="start-exam" value="' + k + '"' + (k === pick ? ' checked' : '') + '>' +
          '<span class="opt-main"><span>' + esc(e.name) + '</span><span class="muted small">' + total + '문항 · ' + e.minutes + '분 · ' + e.pass_score + '점 이상 합격</span></span></label>';
      }).join('') +
      '</div><p class="muted small">닉네임 하나로 두 시험을 모두 쓸 수 있고, 나중에 언제든 바꿀 수 있습니다.</p></fieldset>' +
      '<label class="field" for="nick">닉네임 <span class="muted small">(1~' + store.NAME_MAX + '자)</span></label>' +
      '<div class="row"><input id="nick" class="input" type="text" maxlength="' + (store.NAME_MAX + 4) + '" autocomplete="off" placeholder="예: 화물왕" aria-describedby="nick-err nick-help">' +
      '<button class="btn btn-primary" type="submit">시작하기</button></div>' +
      '<p id="nick-err" class="form-error" role="alert"></p>' +
      '<p id="nick-help" class="muted small">기록은 이 기기의 브라우저에만 저장됩니다. 다른 기기로 옮기려면 백업 기능을 사용하세요.</p>' +
      '</form></section>' +
      list +
      '<section class="card"><h2>시험 안내</h2>' + examInfoHtml(cfg, bank && bank.config.data_date) + '</section>';

    var form = document.getElementById('new-form');
    var input = document.getElementById('nick');
    var err = document.getElementById('nick-err');
    input.addEventListener('input', function () { err.textContent = ''; });
    view.querySelectorAll('[name=start-exam]').forEach(function (r) {
      r.addEventListener('change', function () { if (r.checked && r.value !== store.exam) switchExam(r.value, null); });
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var r = store.createProfile(input.value);
      if (!r.ok) { err.textContent = r.error; input.focus(); return; }
      var chosen = (view.querySelector('[name=start-exam]:checked') || {}).value;
      if (chosen && chosen !== store.exam) switchExam(chosen, 'home'); else go('home');
    });
    view.querySelectorAll('[data-select]').forEach(function (b) {
      b.addEventListener('click', function () {
        store.selectProfile(b.getAttribute('data-select'));
        go('home');
      });
    });
    if (keep) {
      input.value = keep.value;
      err.textContent = keep.err;
      if (keep.focused) { input.focus(); try { input.setSelectionRange(keep.value.length, keep.value.length); } catch (e) { /* 무시 */ } }
    } else if (!profiles.length) input.focus();
  }

  function examInfoHtml(cfg, dataDate) {
    if (!cfg) return '<p class="muted">시험 규격을 불러오는 중…</p>';
    var total = cfg.subjects.reduce(function (a, s) { return a + s.count; }, 0);
    var gl = cfg.group_label || '과목';
    var agency = cfg.agency || (cfg.id_prefix === 'DL' ? '도로교통공단' : '한국교통안전공단');
    return '<p class="small"><b>' + esc(cfg.name || '') + '</b></p>' +
      '<table class="table"><thead><tr><th scope="col">' + esc(gl) + '</th><th scope="col" class="num">문항</th></tr></thead><tbody>' +
      cfg.subjects.map(function (s) { return '<tr><td>' + esc(s.name) + '</td><td class="num">' + s.count + '</td></tr>'; }).join('') +
      '<tr class="total"><td>합계</td><td class="num">' + total + '문항 / ' + cfg.minutes + '분</td></tr></tbody></table>' +
      '<p class="small">' + esc(cfg.choices || '4지선다') + ' · 100점 만점 · <b>' + cfg.pass_score + '점 이상 합격</b> (' + Math.ceil(total * cfg.pass_score / 100) + '문항 이상 정답)</p>' +
      (cfg.score_note ? '<p class="muted small">' + esc(cfg.score_note) + ' – 실제 시험은 유형별 배점이 다를 수 있습니다.</p>' : '') +
      '<p class="muted small">비공식 학습용 프로그램입니다.' + (dataDate ? ' 문제 기준일: <b>' + esc(dataDate) + '</b>.' : '') + ' 시험 규정은 ' + agency + ' 공지를 확인하세요.</p>';
  }

  /* ---------- 대시보드 ---------- */
  function renderHome(active) {
    var d = store.getProfileData(active.id) || { exams: [], wrongNotes: {} };
    // 현재 모드(실제/샘플) 기록만 통계에 사용
    var exams = (d.exams || []).filter(function (e) { return !!e.sample === sampleMode; });
    var last = exams.length ? exams[exams.length - 1] : null;
    var avg = exams.length ? (exams.reduce(function (a, e) { return a + e.score; }, 0) / exams.length) : null;
    var wrongActive = CDME.notes.activeCount(d.wrongNotes, bank, sampleMode);
    var ready = bank ? CDME.exam.checkReady(bank).ok : false;
    var ip = d.inProgress;

    var resume = '';
    if (ip) {
      var c = CDME.exam.counts(ip);
      resume = '<section class="card resume" aria-label="진행 중인 시험">' +
        '<h2>진행 중인 시험이 있습니다</h2>' +
        '<p class="small">' + (ip.sample ? '[샘플] ' : '') + '응답 ' + c.answered + ' / ' + c.total + '문항 · 남은 시간 <b>' + CDME.exam.formatTime(ip.remainingMs) + '</b></p>' +
        '<div class="row"><button type="button" class="btn btn-primary" id="resume-exam">이어 풀기</button>' +
        '<button type="button" class="btn btn-ghost" id="abandon-exam">포기하기</button></div></section>';
    }

    var hint = !bank ? (bankError ? '문제 데이터를 불러오지 못했습니다.' : '문제 데이터를 불러오는 중…')
      : ready ? bank.config.exam.subjects.reduce(function (a, s) { return a + s.count; }, 0) + '문항 · ' + bank.config.exam.minutes + '분 · ' + (bank.config.exam.group_label || '과목') + '별 랜덤 출제'
      : '출제 가능한 문제가 아직 부족합니다. 아래 "문제 준비 현황"을 확인하세요.';

    view.innerHTML =
      noticeHtml() +
      '<h1 class="page-title">' + esc(active.name) + '님, 반갑습니다</h1>' +
      '<div class="exam-bar"><span class="exam-chip exam-' + store.exam + '">' + esc(CDME.questions.examShort(store.exam, bank && bank.config)) + '</span> ' +
      '<b>' + esc(CDME.questions.examName(store.exam, bank && bank.config)) + '</b> ' +
      '<a class="btn btn-sm btn-ghost" href="#/exams" id="switch-exam">시험 바꾸기</a></div>' +
      resume +
      '<a class="stats stats-link" href="#/records" aria-label="내 성적 요약 – 누르면 내 기록">' +
      stat('응시 횟수', exams.length + '회') +
      stat('최근 점수', last ? last.score + '점' : '-') +
      stat('평균 점수', avg == null ? '-' : (Math.round(avg * 10) / 10) + '점') +
      '</a>' +
      '<section class="card actions">' +
      '<button type="button" class="btn btn-primary btn-lg" id="start-exam" aria-describedby="exam-hint">실전 모의시험 시작</button>' +
      '<p id="exam-hint" class="muted small">' + esc(hint) + '</p>' +
      (last ? '<a class="btn btn-ghost" href="#/result?id=' + encodeURIComponent(last.id) + '">최근 시험 결과 보기</a>' : '') +
      '<button type="button" class="btn btn-outline" id="go-review">복습할 오답 <b>' + wrongActive + '</b>문제</button>' +
      '</section>' +
      studyCardHtml(d, exams) +
      '<section class="card"><h2>문제 준비 현황' + (devKind === 'sample' ? ' <span class="tag tag-wait">샘플</span>' : devKind === 'draft' ? ' <span class="tag tag-wait">미리보기</span>' : '') + '</h2>' + bankStatusHtml() +
      (!sampleMode && bank && !ready && devAllowed() && (draftReady() || store.exam === 'cargo') ? '<p class="small">검수가 끝나기 전에 시험을 풀어 보려면 ' +
        (draftReady() ? '<button type="button" class="link-btn" data-draft-on>검수 전 실제 문제로 미리보기</button>' : '') +
        (draftReady() && store.exam === 'cargo' ? ' 또는 ' : '') +
        (store.exam === 'cargo' ? '<button type="button" class="link-btn" data-sample-on>샘플 문제로 체험하기</button>' : '') + ' (개발·검수용)</p>' : '') +
      '</section>' +
      '<section class="card"><h2>메뉴</h2><ul class="menu">' +
      '<li><a href="#/notes">오답노트 · 복습 재시험</a></li>' +
      '<li><a href="#/study">집중 학습 (' + esc(bank ? bank.config.exam.group_label || '과목' : '과목') + '별 · 난이도별 · 북마크)</a></li>' +
      '<li><a href="#/exams">시험 바꾸기 (화물운송종사자격 · 대형운전면허)</a></li>' +
      '<li><a href="#/bookmarks">북마크한 문제</a></li>' +
      '<li><a href="#/records">내 기록 (응시 이력 · 점수 추이 · ' + esc(bank ? bank.config.exam.group_label || '과목' : '과목') + '별 평균)</a></li>' +
      '<li><a href="#/data">기록 관리 (백업 · 불러오기 · 초기화)</a></li>' +
      '<li><a href="#/help">도움말 · 글자 크기 · 이용 안내</a></li>' +
      '<li><a href="#/profiles">닉네임 관리 / 다른 닉네임으로 전환</a></li>' +
      '</ul></section>';

    document.getElementById('start-exam').addEventListener('click', function () { startExam(active); });
    document.getElementById('go-review').addEventListener('click', function () { go('notes'); });
    var r = document.getElementById('resume-exam');
    if (r) r.addEventListener('click', function () { go('exam'); });
    var ab = document.getElementById('abandon-exam');
    if (ab) ab.addEventListener('click', function () {
      modal.confirm({ title: '시험 포기', message: '진행 중인 시험을 포기합니다. 답안은 저장되지 않고 기록에도 남지 않습니다.', okText: '포기', danger: true })
        .then(function (ok) {
          if (!ok) return;
          store.updateProfileData(active.id, function (dd) { dd.inProgress = null; });
          render();
        });
    });
  }

  function startExam(active) {
    if (!bank) return;
    var check = CDME.exam.checkReady(bank);
    if (!check.ok) {
      modal.confirm({
        title: '아직 시험을 볼 수 없습니다',
        message: '출제 가능한(검수 완료) 문제가 부족한 ' + esc(bank.config.exam.group_label || '과목') + '이 있습니다.<br>' +
          check.lacking.map(function (l) { return '· ' + esc(l.name) + ': ' + l.have + ' / ' + l.need; }).join('<br>') +
          (sampleMode || !devAllowed() || store.exam !== 'cargo' ? '<br><br>문제를 검수하고 있습니다. 잠시 후 다시 이용해 주세요.' +
            (devAllowed() && !sampleMode && draftReady() ? '<br>검수 전 실제 문제를 풀어 보려면 대시보드의 <b>검수 전 실제 문제로 미리보기</b>를 누르세요.' : '')
            : '<br><br>개발 확인용 <b>샘플 문제</b>로 체험해 볼 수 있습니다.' +
            (draftReady() ? '<br>검수 전 실제 문제를 풀어 보려면 대시보드의 <b>검수 전 실제 문제로 미리보기</b>를 누르세요.' : '')),
        okText: sampleMode || !devAllowed() || store.exam !== 'cargo' ? '확인' : '샘플로 체험', cancelText: '닫기'
      }).then(function (ok) { if (ok && !sampleMode && devAllowed() && store.exam === 'cargo') setSampleMode(true); });
      return;
    }
    var d = store.getProfileData(active.id);
    var begin = function () {
      var ip = CDME.exam.buildExam(bank, { recent: CDME.exam.recentQids(d.exams, sampleMode), sample: sampleMode });
      if (devKind) ip.kind = devKind;
      store.updateProfileData(active.id, function (dd) { dd.inProgress = ip; });
      go('exam');
    };
    if (d.inProgress) {
      modal.confirm({ title: '새 시험 시작', message: '진행 중인 시험이 있습니다. 포기하고 새로 시작할까요?', okText: '새로 시작', danger: true })
        .then(function (ok) { if (ok) begin(); });
      return;
    }
    modal.confirm({
      title: '실전 모의시험을 시작합니다',
      message: bank.config.exam.subjects.reduce(function (a, s) { return a + s.count; }, 0) + '문항 · ' + bank.config.exam.minutes + '분<br>' +
        '답을 고르면 바로 <b>정답·오답과 해설</b>이 나오며, 고른 답은 바꿀 수 없습니다.<br>' +
        (bank.config.exam.subjects.some(function (s) { return (s.answers || 1) > 1; })
          ? '<b>정답 2개</b> 문항은 두 개를 모두 고르면 채점되며, 둘 다 맞아야 정답입니다(첫 번째 선택은 다시 눌러 취소 가능).<br>' : '') +
        '모든 문항을 풀면 결과를 볼 수 있고, 시간이 끝나면 자동으로 종료됩니다.<br>' +
        '창을 닫으면 그 시점의 남은 시간이 저장되어 나중에 이어 풀 수 있습니다.',
      okText: '시작'
    }).then(function (ok) { if (ok) begin(); });
  }

  /* 대시보드: 집중 학습·취약 과목 카드 (PRD 12.1) */
  function studyCardHtml(d, exams) {
    if (!bank) return '';
    var S = CDME.study;
    var w = S.weakness(exams, sampleMode, bank.config, 5);
    var bmCount = S.bookmarkCount(d.bookmarks, bank, sampleMode);
    var sip = d.studyInProgress;
    var gl = bank.config.exam.group_label || '과목';
    var weakHtml;
    if (!w.count || (!w.weak.length && !w.weakest)) {
      weakHtml = '<p class="muted small">실전 모의시험을 보면 최근 5회 기록으로 취약 ' + esc(gl) + '을 알려 드립니다.</p>';
    } else if (w.weak.length) {
      weakHtml = '<p class="small">최근 ' + w.count + '회 기준 <b>합격선(' + w.line + '%) 아래</b> ' + esc(gl) + ': ' +
        w.weak.map(function (s) { return '<b>' + esc(CDME.ui.subjectShort(s.code)) + '</b> ' + s.rate + '%'; }).join(', ') + '</p>' +
        '<a class="btn btn-outline" href="#/study?subject=' + encodeURIComponent(w.weak[0].code) + '">' + esc(CDME.ui.subjectShort(w.weak[0].code)) + ' 집중 학습</a>';
    } else {
      weakHtml = '<p class="small">최근 ' + w.count + '회 기준 모든 ' + esc(gl) + '이 합격선(' + w.line + '%) 이상입니다. 가장 낮은 ' + esc(gl) + ': <b>' +
        esc(CDME.ui.subjectShort(w.weakest.code)) + '</b> ' + w.weakest.rate + '%</p>';
    }
    return '<section class="card" aria-labelledby="study-h"><h2 id="study-h">집중 학습</h2>' +
      (sip ? '<p class="small">진행 중인 학습이 있습니다 (' + CDME.study.tally(sip).answered + ' / ' + sip.items.length + '문항). <a href="#/study-play">이어 풀기</a></p>' : '') +
      weakHtml +
      '<div class="row wrap"><a class="btn btn-primary" href="#/study">' + esc(gl) + '·난이도 골라 풀기</a>' +
      '<a class="btn btn-ghost" href="#/bookmarks">★ 북마크 <b>' + bmCount + '</b></a>' +
      (w.count ? '<a class="btn btn-ghost" href="#/records?focus=weak">취약 ' + esc(gl) + ' 분석</a>' : '') + '</div></section>';
  }

  function stat(label, value) {
    return '<div class="stat"><span class="stat-label">' + esc(label) + '</span><span class="stat-value">' + esc(value) + '</span></div>';
  }

  /* ---------- 닉네임 관리 (FR-103~105) ---------- */
  function renderProfiles(active) {
    var profiles = store.listProfiles();
    view.innerHTML =
      noticeHtml() +
      '<p><a href="#/' + (active ? 'home' : 'start') + '" class="back">← ' + (active ? '대시보드' : '처음 화면') + '</a></p>' +
      '<h1 class="page-title">닉네임 관리</h1>' +
      '<section class="card"><ul class="manage-list">' +
      profiles.map(function (p) {
        var isActive = active && active.id === p.id;
        return '<li class="manage-item' + (isActive ? ' is-active' : '') + '">' +
          '<div class="mi-main"><span class="pname">' + esc(p.name) + '</span>' +
          (isActive ? ' <span class="tag tag-ok">사용 중</span>' : '') +
          '<span class="pmeta">' + esc(examCountsText(p.id)) + ' · 만든 날 ' + esc(util.formatDate(p.createdAt)) + '</span></div>' +
          '<div class="mi-actions">' +
          (isActive ? '' : '<button type="button" class="btn btn-sm btn-primary" data-act="select" data-id="' + esc(p.id) + '">선택</button>') +
          '<button type="button" class="btn btn-sm btn-ghost" data-act="rename" data-id="' + esc(p.id) + '">이름 변경</button>' +
          '<button type="button" class="btn btn-sm btn-ghost danger-text" data-act="delete" data-id="' + esc(p.id) + '">삭제</button>' +
          '</div></li>';
      }).join('') +
      '</ul>' +
      '<button type="button" class="btn btn-outline" id="add-profile">+ 새 닉네임 추가</button>' +
      (active ? ' <button type="button" class="btn btn-ghost" id="logout">닉네임 선택 화면으로</button>' : '') +
      '</section>';

    view.querySelectorAll('[data-act]').forEach(function (b) {
      b.addEventListener('click', function () { onProfileAction(b.getAttribute('data-act'), b.getAttribute('data-id')); });
    });
    document.getElementById('add-profile').addEventListener('click', function () {
      modal.prompt({
        title: '새 닉네임', placeholder: '1~' + store.NAME_MAX + '자', okText: '만들기', maxLength: store.NAME_MAX + 4,
        validate: function (v) { var r = store.validateName(v); return r.ok ? '' : r.error; }
      }).then(function (v) {
        if (v == null) return;
        var r = store.createProfile(v);
        if (r.ok) go('home');
      });
    });
    var lo = document.getElementById('logout');
    if (lo) lo.addEventListener('click', function () { store.logout(); go('start'); });
  }

  // "화물 응시 3회 · 대형 응시 1회" (기록 없는 시험은 생략, 둘 다 없으면 "응시 0회")
  function examCountsText(id) {
    var all = store.getProfileAll(id) || {};
    var parts = CDME.questions.EXAM_KINDS.filter(function (k) { return all[k] && (all[k].exams || []).length; })
      .map(function (k) { return CDME.questions.examShort(k, bank && bank.config) + ' 응시 ' + all[k].exams.length + '회'; });
    return parts.length ? parts.join(' · ') : '응시 0회';
  }

  function onProfileAction(act, id) {
    var p = store.getProfile(id);
    if (!p) return;
    if (act === 'select') { store.selectProfile(id); go('home'); return; }
    if (act === 'rename') {
      modal.prompt({
        title: '닉네임 이름 변경', value: p.name, okText: '변경', maxLength: store.NAME_MAX + 4,
        message: '이름을 바꿔도 기록은 그대로 유지됩니다.',
        validate: function (v) { var r = store.validateName(v, id); return r.ok ? '' : r.error; }
      }).then(function (v) {
        if (v == null) return;
        store.renameProfile(id, v);
        render();
      });
      return;
    }
    if (act === 'delete') {
      var all = store.getProfileAll(id) || {};
      var detail = CDME.questions.EXAM_KINDS.map(function (k) {
        var d = all[k] || { exams: [], wrongNotes: {} };
        return esc(CDME.questions.examShort(k, bank && bank.config)) + ' 응시 ' + (d.exams || []).length + '회 · 오답노트 ' + Object.keys(d.wrongNotes || {}).length + '문제';
      }).join(' / ');
      modal.confirm({
        title: '닉네임 삭제',
        message: '<b>' + esc(p.name) + '</b> 닉네임과 두 시험의 모든 기록(' + detail + ')이 삭제됩니다.<br>삭제한 기록은 되돌릴 수 없습니다.',
        okText: '삭제', danger: true
      }).then(function (ok) {
        if (!ok) return;
        var wasActive = (store.getActiveProfile() || {}).id === id;
        store.deleteProfile(id);
        if (wasActive) go('start'); else render();
      });
    }
  }

  /* ---------- 문제 데이터 불러오기 ---------- */
  var loadSeq = 0;
  function loadBank() {
    var seq = ++loadSeq;
    bank = null; bankError = null;
    render();
    var kind = store.exam;
    CDME.questions.load('data/', devKind === 'sample' && kind === 'cargo' ? 'samples/' : null, kind).then(function (b) {
      if (seq !== loadSeq) return;
      // 공개 모드인데 예전에 켜 둔 미리보기·샘플 모드가 남아 있으면 실제 모드로 되돌림
      if (devKind && !devAllowed(b)) { setDevKind(''); return; }
      if (devKind === 'draft') promoteDrafts(b);
      bank = b;
      if (b.warnings.length) console.warn('[문제 데이터 경고]', b.warnings);
      render();
      try { prefetchImages(b); } catch (e) { /* 무시 */ }
    }).catch(function (e) {
      if (seq !== loadSeq) return;
      bankError = e.message || String(e);
      console.error('[문제 데이터 오류]', e);
      render();
    });
  }

  // 검수 미리보기: 폐기되지 않은 모든 문제를 출제 대상으로 (원래 상태는 _status에 보관)
  function promoteDrafts(b) {
    Object.keys(b.byId).forEach(function (id) {
      var q = b.byId[id];
      if (q.status !== 'deprecated') { q._status = q.status; q.status = 'verified'; }
    });
  }
  // 초안까지 포함하면 시험 1회 구성이 가능한지
  function draftReady() {
    if (!bank) return false;
    return bank.config.exam.subjects.every(function (s) {
      return (bank.bySubject[s.code] || []).filter(function (q) { return q.status !== 'deprecated'; }).length >= s.count;
    });
  }

  /* ---------- 시험 종류 선택·전환 (FR-L01, L02) ---------- */
  // kind로 바꾸고 문제 데이터를 다시 불러온 뒤 next 화면으로 (next가 null이면 지금 화면 다시 그리기)
  function switchExam(kind, next) {
    if (kind !== store.exam) {
      store.setExam(kind);
      if (devKind === 'sample' && kind !== 'cargo') { devKind = ''; sampleMode = false; try { root.localStorage.removeItem(SAMPLE_KEY); } catch (e) { /* 무시 */ } }
      examStatus = {};
      if (next) history.replaceState(null, '', '#/' + next);
      loadBank();
    } else if (next) go(next);
  }

  // 시험 선택 화면용: 다른 시험의 문제 준비 현황을 한 번 불러옴
  function ensureExamStatus(kind) {
    if (bank && bank.config.kind === kind && !devKind) { examStatus[kind] = CDME.questions.summarize(bank); return; }
    if (examStatus[kind]) return;
    examStatus[kind] = 'loading';
    CDME.questions.load('data/', null, kind).then(function (b) {
      examStatus[kind] = CDME.questions.summarize(b);
      if (currentRoute() === 'exams') render();
    }).catch(function () { examStatus[kind] = 'error'; if (currentRoute() === 'exams') render(); });
  }

  function renderExams(active) {
    var kinds = CDME.questions.EXAM_KINDS;
    kinds.forEach(ensureExamStatus);
    var cfg = bank ? bank.config : {};
    var progress = active ? (store.getProfileData(active.id) || {}) : {};
    var busy = progress.inProgress || progress.reviewInProgress || progress.studyInProgress;
    view.innerHTML = noticeHtml() +
      '<p><a href="#/home" class="back">← 대시보드</a></p>' +
      '<h1 class="page-title">시험 선택</h1>' +
      '<p class="muted small">닉네임 <b>' + esc(active.name) + '</b>의 기록은 시험별로 따로 저장됩니다.' +
      (busy ? ' 지금 시험의 진행 중인 풀이는 저장되어, 돌아오면 이어 풀 수 있습니다.' : '') + '</p>' +
      kinds.map(function (k) {
        var e = CDME.questions.normalizeConfig(cfg, k).exam;
        var total = e.subjects.reduce(function (a, x) { return a + x.count; }, 0);
        var d = store.getProfileData(active.id, k) || { exams: [], wrongNotes: {} };
        var ex = (d.exams || []).filter(function (x) { return !x.sample; });
        var last = ex.length ? ex[ex.length - 1] : null;
        var notes = d.wrongNotes || {};
        var wrong = Object.keys(notes).filter(function (id) { return notes[id].state === 'active' && !notes[id].sample; }).length;
        var st = examStatus[k];
        var status = st === 'loading' || !st ? '<span class="muted small">문제 준비 현황 확인 중…</span>'
          : st === 'error' ? '<span class="tag tag-wait">문제 데이터를 불러오지 못함</span>'
          : st.examReady ? '<span class="tag tag-ok">✓ 시험 가능 (검수 완료 ' + st.verified + '문항)</span>'
          : '<span class="tag tag-wait">문제 검수 중 (' + st.verified + ' / ' + st.need + ')</span>';
        var cur = k === store.exam;
        return '<section class="card exam-card' + (cur ? ' is-current' : '') + '" aria-label="' + esc(e.name) + '">' +
          '<h2><span class="exam-chip exam-' + k + '">' + esc(e.short || e.name) + '</span> ' + esc(e.name) + (cur ? ' <span class="tag tag-ok">사용 중</span>' : '') + '</h2>' +
          '<p class="small">' + total + '문항 · ' + e.minutes + '분 · ' + esc(e.choices || '4지선다') + ' · <b>' + e.pass_score + '점 이상 합격</b></p>' +
          '<p class="small">' + status + '</p>' +
          '<p class="small muted">내 기록: 응시 ' + ex.length + '회' + (last ? ' · 최근 ' + last.score + '점' : '') + ' · 복습할 오답 ' + wrong + '문제</p>' +
          (cur ? '<a class="btn btn-outline" href="#/home">대시보드로</a>'
            : '<button type="button" class="btn btn-primary" data-exam="' + k + '">이 시험으로 바꾸기</button>') +
          '</section>';
      }).join('');
    view.querySelectorAll('[data-exam]').forEach(function (b) {
      b.addEventListener('click', function () {
        var k = b.getAttribute('data-exam');
        switchExam(k, 'home');
        if (CDME.ui && CDME.ui.toast) CDME.ui.toast(CDME.questions.examName(k, bank && bank.config) + '(으)로 바꿨습니다.');
      });
    });
  }

  var ctx = {
    switchExam: switchExam,
    store: store, view: view, go: go, render: render, params: params, modal: modal, noticeHtml: noticeHtml,
    fonts: FONTS, getFont: getFont, setFont: setFont,
    getBank: function () { return bank; },
    sampleMode: function () { return sampleMode; },
    devAllowed: function () { return devAllowed(); },
    devKind: function () { return devKind; },
    setDevKind: setDevKind,
    ensureKind: ensureKind,
    setSampleMode: setSampleMode,
    setCleanup: function (fn) { cleanupFn = fn; }
  };

  // 북마크 켜고 끄기 (시험·복습·학습·결과·오답노트 화면 공통, PRD 12.1)
  view.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-bm]') : null;
    if (!b) return;
    var active = store.getActiveProfile();
    if (!active || !bank) return;
    var q = bank.byId[b.getAttribute('data-bm')];
    if (!q) return;
    var on = false;
    store.updateProfileData(active.id, function (dd) {
      if (!dd.bookmarks) dd.bookmarks = {};
      on = CDME.study.toggleBookmark(dd.bookmarks, q, sampleMode);
    });
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.innerHTML = '<span aria-hidden="true">' + (on ? '★' : '☆') + '</span> <span class="bm-label">' + (on ? '북마크됨' : '북마크') + '</span>';
    if (CDME.ui && CDME.ui.toast) CDME.ui.toast(on ? '★ 북마크에 담았습니다.' : '북마크를 해제했습니다.');
    if (b.hasAttribute('data-bm-rerender')) render();
  });

  /* 그림 크게 보기 (v2.0 L3, FR-L08): 문제 그림을 누르면 화면 가득 보여 줌. 닫기·Esc·바깥 누르기로 닫고 원래 그림 버튼으로 초점 복귀 */
  function openZoom(src, alt, opener) {
    document.querySelectorAll('.zoom-backdrop').forEach(function (m) { m.remove(); });
    var bd = document.createElement('div');
    bd.className = 'modal-backdrop zoom-backdrop';
    bd.innerHTML = '<div class="zoom-box" role="dialog" aria-modal="true" aria-label="그림 크게 보기">' +
      '<div class="zoom-top"><p class="zoom-cap">' + esc(alt) + '</p>' +
      '<button type="button" class="btn btn-ghost btn-sm zoom-close" data-zoom-close>닫기 ✕</button></div>' +
      '<div class="zoom-img-wrap"><img class="zoom-img" src="' + esc(src) + '" alt="' + esc(alt) + '"></div></div>';
    document.body.appendChild(bd);
    function close() {
      bd.remove();
      document.removeEventListener('keydown', onKey, true);
      if (opener && document.body.contains(opener)) { try { opener.focus({ preventScroll: true }); } catch (e) { /* 무시 */ } }
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
      else if (e.key === 'Tab') { e.preventDefault(); bd.querySelector('[data-zoom-close]').focus(); }   // 초점은 닫기 버튼에 머묾
      else if (e.key !== 'Enter' && e.key !== ' ') { e.stopPropagation(); }   // 시험 화면 숫자키 등이 뒤에서 동작하지 않게
    }
    document.addEventListener('keydown', onKey, true);
    bd.addEventListener('click', function (e) {
      if (e.target === bd || (e.target.closest && e.target.closest('[data-zoom-close]'))) close();
    });
    bd.querySelector('[data-zoom-close]').focus();
  }
  view.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-zoom]') : null;
    if (!b) return;
    e.preventDefault();
    openZoom(b.getAttribute('data-zoom'), b.getAttribute('data-alt') || '문제 그림', b);
  });

  /* 오프라인 대비: 지금 시험의 문제 그림을 미리 받아 둠 (Service Worker가 받은 파일을 저장, NFR-04) */
  var prefetched = {};
  function prefetchImages(b) {
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller || !root.fetch) return;
    var list = [];
    Object.keys(b.byId).forEach(function (id) {
      var q = b.byId[id];
      if (q.image && q.status !== 'deprecated') {
        var src = CDME.ui.imgSrc(q);
        if (!prefetched[src]) { prefetched[src] = true; list.push(src); }
      }
    });
    var k = 0;
    function nextOne() {
      if (k >= list.length) return;
      var src = list[k++];
      fetch(src).catch(function () { prefetched[src] = false; }).then(nextOne);
    }
    for (var n = 0; n < 3; n++) nextOne();   // 동시에 3개씩
  }

  // 샘플 모드 켜기/끄기 버튼(공통 안내 영역)
  view.addEventListener('click', function (e) {
    var t = e.target;
    if (t.hasAttribute && t.hasAttribute('data-sample-off')) setSampleMode(false);
    if (t.hasAttribute && t.hasAttribute('data-sample-on') && devAllowed()) setSampleMode(true);
    if (t.hasAttribute && t.hasAttribute('data-draft-on') && devAllowed()) setDevKind('draft');
  });

  /* ---------- 시작 ---------- */
  window.addEventListener('hashchange', render);
  // 다른 탭에서 기록이 바뀌면 다시 읽기
  window.addEventListener('storage', function (e) {
    if (e.key === CDME.store.KEY) { store.reload(); render(); }
  });

  loadBank();

  // 개발·테스트용
  CDME.app = { store: store, render: render, ctx: ctx, getBank: function () { return bank; } };
})(window);
