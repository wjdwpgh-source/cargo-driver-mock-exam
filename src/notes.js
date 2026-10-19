/* 오답노트 로직 (PRD 7.4 (3), FR-601~603, FR-403) – 화면과 분리
 * wrongNotes: { [qid]: { subject, question_version, wrong_count, streak, last_choice,
 *                        first_wrong_at, last_wrong_at, added_by, state, sample } }
 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var util = CDME.util || (typeof require === 'function' ? require('./util.js') : null);

  // 시험 결과(record)의 오답·안 푼 문항을 오답노트에 반영. 반환: { added, updated }
  function registerWrong(notes, record, bank, now) {
    now = now || util.nowISO();
    var added = 0, updated = 0;
    (record.answers || []).forEach(function (a) {
      if (a.correct) return;
      var q = bank.byId[a.qid];
      var n = notes[a.qid];
      if (!n) {
        notes[a.qid] = {
          subject: q ? q.subject : a.qid.split('-')[0],
          question_version: a.qver || (q && q.version) || 1,
          wrong_count: 1,
          streak: 0,
          last_choice: a.choice,
          first_wrong_at: now,
          last_wrong_at: now,
          added_by: 'auto',
          state: 'active',
          sample: !!record.sample
        };
        added++;
      } else {
        n.wrong_count = (n.wrong_count || 0) + 1;
        n.last_wrong_at = now;
        if (!n.first_wrong_at) n.first_wrong_at = now;
        n.last_choice = a.choice;
        n.streak = 0;
        n.state = 'active';                       // 복습 완료 문제를 다시 틀리면 재등록 (FR-603)
        n.question_version = a.qver || n.question_version;
        updated++;
      }
    });
    return { added: added, updated: updated };
  }

  // 맞힌 문제라도 직접 담기 (FR-403). 반환: 'added' | 'exists' | 'reactivated'
  function addManual(notes, q, opts) {
    opts = opts || {};
    var now = opts.now || util.nowISO();
    var n = notes[q.id];
    if (n) {
      if (n.state === 'active') return 'exists';
      n.state = 'active'; n.streak = 0;
      return 'reactivated';
    }
    notes[q.id] = {
      subject: q.subject,
      question_version: q.version || 1,
      wrong_count: 0,
      streak: 0,
      last_choice: opts.choice == null ? null : opts.choice,
      first_wrong_at: null,
      last_wrong_at: null,
      added_at: now,
      added_by: 'manual',
      state: 'active',
      sample: !!opts.sample
    };
    return 'added';
  }

  function isActive(n) { return n && n.state === 'active'; }

  // 현재 모드(실제/샘플)의 복습할 오답 수. 폐기·삭제된 문제는 제외 (FR-606)
  function activeCount(notes, bank, sample) {
    return Object.keys(notes || {}).filter(function (id) {
      var n = notes[id];
      if (!isActive(n) || !!n.sample !== !!sample) return false;
      if (bank) { var q = bank.byId[id]; if (!q || q.status === 'deprecated') return false; }
      return true;
    }).length;
  }

  // 오류 신고용 GitHub Issue 주소 (FR-404). 저장소 주소가 아직 정해지지 않았으면 null
  function issueUrl(config, q, extra) {
    var base = config && config.issue_url;
    if (!base || /[<>]/.test(base)) return null;
    var title = '[문제 오류] ' + q.id;
    var body = [
      '## 문제 정보',
      '- 문제 ID: ' + q.id,
      '- 문제 버전: ' + (q.version || 1),
      '- 지문: ' + q.question,
      '',
      '## 오류 내용',
      '(어떤 부분이 잘못되었는지 적어 주세요. 근거 자료가 있으면 함께 적어 주세요.)',
      '',
      extra ? '---\n' + extra : ''
    ].join('\n');
    return base + (base.indexOf('?') < 0 ? '?' : '&') + 'title=' + encodeURIComponent(title) + '&body=' + encodeURIComponent(body) + '&labels=' + encodeURIComponent('문제오류');
  }

  CDME.notes = { registerWrong: registerWrong, addManual: addManual, activeCount: activeCount, issueUrl: issueUrl };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.notes;
})(typeof window !== 'undefined' ? window : globalThis);
