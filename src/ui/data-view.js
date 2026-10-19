/* 기록 관리 화면 (S6: FR-802, 803, 901~903) – #/data
 * - 백업 내보내기(현재 닉네임 / 이 기기 전체), 백업 불러오기(합치기·덮어쓰기·이름 바꿔 가져오기·건너뛰기)
 * - 기록 초기화(실전 기록만 / 오답노트만 / 전체), 백업 후 초기화, 전체 초기화는 닉네임 다시 입력
 */
(function (root) {
  'use strict';
  var CDME = root.CDME;
  var esc = CDME.util.escapeHtml, B = CDME.backup, modal = CDME.modal;

  function download(obj, name) {
    var blob = new Blob([JSON.stringify(obj, null, 1)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  }

  function backupProfiles(store, ids) {
    return ids.map(function (id) { var p = store.getProfile(id); return { name: p.name, createdAt: p.createdAt, data: store.getProfileData(id) }; });
  }

  function exportFor(store, ids, label) {
    var obj = B.buildBackup(backupProfiles(store, ids));
    download(obj, B.fileName(label));
    return obj;
  }

  function sumText(s) {
    return '실전 ' + s.exams + '회 · 오답 ' + s.notes + ' · 복습 완료 ' + s.mastered + ' · 복습 ' + s.reviews + '회';
  }

  function renderData(ctx, active) {
    var view = ctx.view, store = ctx.store, toast = CDME.ui.toast;
    var profiles = store.listProfiles();
    var d = store.getProfileData(active.id);
    var s = B.summarizeData(d);
    var reviewCount = (d.reviewSessions || []).length;

    view.innerHTML = ctx.noticeHtml() +
      '<p><a href="#/records" class="back">← 내 기록</a></p>' +
      '<h1 class="page-title">기록 관리</h1>' +
      '<p class="muted small">기록은 이 기기의 브라우저에만 저장됩니다. 다른 기기로 옮기거나 초기화하기 전에 백업 파일을 만들어 두세요.</p>' +

      '<section class="card"><h2>백업 파일 만들기</h2>' +
      '<p class="small"><b>' + esc(active.name) + '</b> · ' + esc(sumText(s)) + '</p>' +
      '<div class="btn-col"><button type="button" class="btn btn-primary" id="exp-me">' + esc(active.name) + ' 기록 백업</button>' +
      (profiles.length > 1 ? '<button type="button" class="btn btn-outline" id="exp-all">이 기기 전체 백업 (닉네임 ' + profiles.length + '개)</button>' : '') +
      '</div><p class="muted small">진행 중인 시험·복습은 백업에 포함되지 않습니다. 파일은 브라우저의 다운로드 폴더에 저장됩니다.</p></section>' +

      '<section class="card"><h2>백업 불러오기</h2>' +
      '<p class="small">다른 기기에서 만든 백업 파일(.json)을 선택하세요.</p>' +
      '<label class="file-pick btn btn-outline"><input type="file" id="imp-file" accept=".json,application/json"><span>백업 파일 선택</span></label>' +
      '<p class="form-error" id="imp-err" role="alert"></p>' +
      '<div id="imp-plan"></div></section>' +

      '<section class="card danger-zone"><h2>기록 초기화</h2>' +
      '<p class="small">초기화할 범위를 고르세요. <b>' + esc(active.name) + '</b> 닉네임의 기록만 지워집니다.</p>' +
      '<div class="opts">' +
      '<label class="opt"><input type="radio" name="rs" value="exams" checked><span class="opt-main"><span>실전 기록만</span><span class="muted small">응시 이력·점수 그래프 (' + s.exams + '회)' + (d.inProgress ? ' + 진행 중 시험' : '') + '</span></span></label>' +
      '<label class="opt"><input type="radio" name="rs" value="notes"><span class="opt-main"><span>오답노트만</span><span class="muted small">오답 ' + s.notes + '문제 · 복습 완료 ' + s.mastered + '문제' + (d.reviewInProgress ? ' + 진행 중 복습' : '') + '</span></span></label>' +
      '<label class="opt"><input type="radio" name="rs" value="all"><span class="opt-main"><span>전체</span><span class="muted small">실전 기록 + 오답노트 + 복습 기록(' + reviewCount + '회)</span></span></label>' +
      '</div>' +
      '<div class="btn-col"><button type="button" class="btn btn-primary" id="rs-backup">백업 후 초기화 (권장)</button>' +
      '<button type="button" class="btn btn-ghost danger-text" id="rs-only">백업 없이 초기화</button></div>' +
      '<p class="muted small">닉네임 자체를 지우려면 <a href="#/profiles">닉네임 관리</a>에서 삭제하세요.</p></section>';

    document.getElementById('exp-me').onclick = function () { exportFor(store, [active.id], active.name); toast('백업 파일을 저장했습니다.'); };
    var ea = document.getElementById('exp-all');
    if (ea) ea.onclick = function () { exportFor(store, profiles.map(function (p) { return p.id; }), '전체'); toast('전체 백업 파일을 저장했습니다.'); };

    /* ----- 불러오기 ----- */
    var errEl = document.getElementById('imp-err');
    var planEl = document.getElementById('imp-plan');
    document.getElementById('imp-file').addEventListener('change', function (e) {
      errEl.textContent = ''; planEl.innerHTML = '';
      var f = e.target.files && e.target.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onerror = function () { errEl.textContent = '파일을 읽지 못했습니다.'; };
      rd.onload = function () {
        var r = B.parse(String(rd.result));
        e.target.value = '';
        if (!r.ok) { errEl.textContent = r.error; return; }
        showPlan(r.backup, f.name);
      };
      rd.readAsText(f, 'utf-8');
    });

    function showPlan(backup, fname) {
      var steps = B.plan(backup, store.listProfiles());
      planEl.innerHTML = '<div class="imp-box"><p class="small"><b>' + esc(fname) + '</b>' + (backup.exportedAt ? ' · ' + esc(CDME.util.formatDate(backup.exportedAt)) + ' 백업' : '') + '</p>' +
        '<ul class="imp-list">' + steps.map(function (st, i) {
          var opts = st.existingId
            ? '<option value="merge" selected>기존 기록과 합치기</option><option value="overwrite">기존 기록을 백업으로 덮어쓰기</option><option value="rename">다른 이름으로 따로 가져오기</option><option value="skip">가져오지 않기</option>'
            : '<option value="new" selected>새 닉네임으로 추가</option><option value="skip">가져오지 않기</option>';
          return '<li><div><b>' + esc(st.name) + '</b>' + (st.existingId ? ' <span class="tag tag-wait">같은 닉네임 있음</span>' : '') +
            '<span class="muted small d-block">' + esc(sumText(st.summary)) + '</span></div>' +
            '<label><span class="sr-only">' + esc(st.name) + ' 처리 방법</span><select class="input input-sm" data-step="' + i + '">' + opts + '</select></label></li>';
        }).join('') + '</ul>' +
        '<div class="row"><button type="button" class="btn btn-primary" id="imp-apply">불러오기</button><button type="button" class="btn btn-ghost" id="imp-cancel">취소</button></div></div>';
      planEl.querySelectorAll('[data-step]').forEach(function (sel) { sel.onchange = function () { steps[+sel.getAttribute('data-step')].action = sel.value; }; });
      document.getElementById('imp-cancel').onclick = function () { planEl.innerHTML = ''; };
      document.getElementById('imp-apply').onclick = function () {
        var over = steps.filter(function (st) { return st.action === 'overwrite'; });
        var go = function () {
          var res = B.apply(store, steps);
          var bad = res.filter(function (r) { return !r.ok; });
          planEl.innerHTML = '';
          if (bad.length) {
            errEl.textContent = bad.map(function (r) { return r.name + ': ' + (r.error || '실패'); }).join(' / ');
          }
          var done = res.filter(function (r) { return r.ok && r.action !== 'skip'; }).length;
          toast(done ? '백업 ' + done + '개 닉네임을 불러왔습니다.' : '불러온 기록이 없습니다.');
          if (!bad.length) ctx.render();
        };
        if (!over.length) return go();
        modal.confirm({ title: '기존 기록 덮어쓰기', danger: true, okText: '덮어쓰기',
          message: over.map(function (st) { return '<b>' + esc(st.name) + '</b>'; }).join(', ') + ' 닉네임의 지금 기록이 백업 내용으로 바뀝니다. 되돌릴 수 없습니다.' })
          .then(function (ok) { if (ok) go(); });
      };
    }

    /* ----- 초기화 ----- */
    var LABEL = { exams: '실전 기록', notes: '오답노트', all: '전체 기록' };
    function scope() { return (view.querySelector('[name=rs]:checked') || {}).value || 'exams'; }
    function doReset(sc) {
      store.replaceProfileData(active.id, B.resetData(store.getProfileData(active.id), sc));
      toast(LABEL[sc] + '을(를) 초기화했습니다.');
      ctx.render();
    }
    function ask(withBackup) {
      var sc = scope();
      var msg = '<b>' + esc(active.name) + '</b>의 ' + LABEL[sc] + '을(를) 지웁니다. 지운 기록은 되돌릴 수 없습니다.' +
        (withBackup ? '<br>먼저 백업 파일을 저장한 뒤 초기화합니다.' : '<br><b class="danger-text">백업 없이</b> 초기화합니다.');
      var run = function () { if (withBackup) exportFor(store, [active.id], active.name + '_초기화전'); doReset(sc); };
      if (sc === 'all') {
        modal.prompt({
          title: '전체 기록 초기화', message: msg + '<br>확인을 위해 닉네임 <b>' + esc(active.name) + '</b>을(를) 입력하세요.',
          okText: '초기화', danger: true, placeholder: active.name, maxLength: 20,
          validate: function (v) { return CDME.store.normalizeName(v) === active.name ? '' : '닉네임이 일치하지 않습니다.'; }
        }).then(function (v) { if (v != null) run(); });
      } else {
        modal.confirm({ title: LABEL[sc] + ' 초기화', message: msg, okText: '초기화', danger: true }).then(function (ok) { if (ok) run(); });
      }
    }
    document.getElementById('rs-backup').onclick = function () { ask(true); };
    document.getElementById('rs-only').onclick = function () { ask(false); };
  }

  CDME.views = CDME.views || {};
  CDME.views.data = renderData;
})(window);
