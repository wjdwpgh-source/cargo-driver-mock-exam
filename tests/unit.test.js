// 단위 테스트: node --test tests/
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../src/util.js');
const S = require('../src/store.js');
const Q = require('../src/questions.js');

/* ---------- 닉네임 ---------- */
test('닉네임 검사: 공백 정리, 길이, 금지 기호, 중복(대소문자 무시)', () => {
  assert.equal(S.validateName('  화물  왕 ', []).name, '화물 왕');
  assert.equal(S.validateName('   ', []).ok, false);
  assert.equal(S.validateName('가'.repeat(12), []).ok, true);
  assert.equal(S.validateName('가'.repeat(13), []).ok, false);
  assert.equal(S.validateName('a<b', []).ok, false);
  const ps = [{ id: '1', name: 'Kim' }];
  assert.equal(S.validateName('kim', ps).ok, false);
  assert.equal(S.validateName('kim', ps, '1').ok, true, '자기 자신 이름 변경은 허용');
});

test('닉네임 생성·선택·이름 변경·삭제 후 저장소에 유지', () => {
  const ad = S.memoryAdapter();
  const st = S.createStore(ad);
  const a = st.createProfile('화물왕').profile;
  const b = st.createProfile('홍길동').profile;
  assert.equal(st.getActiveProfile().id, b.id, '새로 만든 닉네임이 활성화');
  assert.equal(st.createProfile('화물왕').ok, false, '중복 생성 차단');

  st.selectProfile(a.id);
  st.updateProfileData(a.id, d => d.exams.push({ score: 70 }));
  st.renameProfile(a.id, '화물대장');

  // 새로고침 흉내: 같은 저장소에서 다시 읽기
  const st2 = S.createStore(ad);
  assert.equal(st2.getActiveProfile().id, a.id);
  assert.equal(st2.getActiveProfile().name, '화물대장');
  assert.equal(st2.getProfileData(a.id).exams.length, 1, '이름 변경 후에도 기록 유지');

  st2.deleteProfile(a.id);
  const st3 = S.createStore(ad);
  assert.equal(st3.listProfiles().length, 1);
  assert.equal(st3.getActiveProfile(), null, '활성 닉네임 삭제 시 선택 해제');
  assert.equal(st3.getProfileData(a.id), null, '기록도 함께 삭제');
});

test('손상된 저장 데이터는 별도 키로 보관하고 새로 시작', () => {
  const ad = S.memoryAdapter();
  ad.set(S.KEY, '{깨진 데이터');
  const st = S.createStore(ad);
  assert.ok(st.error);
  assert.equal(st.listProfiles().length, 0);
  assert.equal(st.createProfile('새출발').ok, true);
});

test('더 새로운 schemaVersion 데이터는 덮어쓰지 않음', () => {
  const ad = S.memoryAdapter();
  const raw = JSON.stringify({ schemaVersion: 99, profiles: [], data: {} });
  ad.set(S.KEY, raw);
  const st = S.createStore(ad);
  assert.ok(st.error);
  assert.equal(st.blocked, true);
  st.createProfile('테스트');
  assert.equal(ad.get(S.KEY), raw, '기존 기록이 그대로 보존됨');
});

test('migrate: 빠진 필드 보완, 없는 활성 ID 정리', () => {
  const s = S.migrate({ profiles: [{ id: 'x', name: 'A' }], activeProfileId: 'zzz' });
  assert.equal(s.schemaVersion, 1);
  assert.deepEqual(Object.keys(s.data), ['x']);
  assert.equal(s.activeProfileId, null);
});

test('localStorage 사용 불가 시 null 반환(메모리 모드로 대체)', () => {
  const broken = { setItem() { throw new Error('denied'); }, getItem() { return null; }, removeItem() {} };
  assert.equal(S.localStorageAdapter(broken), null);
});

/* ---------- 문제 데이터 ---------- */
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/config.json'), 'utf8'));
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/questions/LAW.json'), 'utf8'));

test('config.json 규격: 25/15/25/15, 80분, 60점', () => {
  assert.deepEqual(cfg.exam.subjects.map(s => s.count), [25, 15, 25, 15]);
  assert.equal(cfg.exam.minutes, 80);
  assert.equal(cfg.exam.pass_score, 60);
  assert.deepEqual(cfg.exam.subjects, Q.DEFAULT_CONFIG.exam.subjects, '기본 규격과 config 일치');
});

test('문제 불러오기: 형식 오류·id 중복 제외, verified만 출제 대상', () => {
  const bank = Q.buildBank(cfg, { LAW: fixture, CARGO: { questions: [] }, SAFE: { questions: [] } });
  assert.deepEqual(bank.bySubject.LAW.map(q => q.id), ['LAW-0001', 'LAW-0002']);
  assert.equal(bank.warnings.length, 4, 'id 중복 1 + 보기 오류 1 + 과목 불일치 1 + SERVICE 파일 없음 1');
  assert.deepEqual(Q.verifiedOf(bank, 'LAW').map(q => q.id), ['LAW-0001']);
  assert.equal(bank.byId['LAW-0002'].version, 1, 'version 없으면 1');
  const sum = Q.summarize(bank);
  assert.equal(sum.verified, 1);
  assert.equal(sum.need, 80);
  assert.equal(sum.examReady, false);
});

test('저장소의 실제 문제 파일 4개가 모두 올바른 형식', () => {
  const files = {};
  for (const s of cfg.exam.subjects) {
    files[s.code] = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/questions', s.code + '.json'), 'utf8'));
    assert.equal(files[s.code].subject, s.code);
  }
  const bank = Q.buildBank(cfg, files);
  assert.deepEqual(bank.warnings, []);
});

/* ---------- S2 실전 시험 ---------- */
const E = require('../src/exam.js');
function loadSampleBank() {
  const files = {};
  for (const s of cfg.exam.subjects) files[s.code] = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/samples', s.code + '.json'), 'utf8'));
  return Q.buildBank(cfg, files);
}
function seeded(seed) { let x = seed; return () => { x = (x * 1103515245 + 12345) % 2147483648; return x / 2147483648; }; }

test('출제: 과목 순서·규정 수(25/15/25/15)·중복 없음·verified만, 100회 반복 (TC-02)', () => {
  const bank = loadSampleBank();
  for (let k = 0; k < 100; k++) {
    const ip = E.buildExam(bank, { rng: seeded(k + 1) });
    assert.equal(ip.items.length, 80);
    const order = ip.items.map(i => i.subject);
    assert.deepEqual(order, [...Array(25).fill('LAW'), ...Array(15).fill('CARGO'), ...Array(25).fill('SAFE'), ...Array(15).fill('SERVICE')]);
    assert.equal(new Set(ip.items.map(i => i.qid)).size, 80);
    assert.ok(ip.items.every(i => bank.byId[i.qid].status === 'verified' && i.qid.startsWith(i.subject + '-')));
    assert.equal(ip.remainingMs, 80 * 60 * 1000);
    assert.ok(ip.answers.every(a => a === null));
  }
});

test('출제: 최근 출제 문제는 뒤로 미룸 (FR-209)', () => {
  const bank = loadSampleBank();
  const first = E.buildExam(bank, { rng: seeded(7) });
  const recent = E.recentQids([{ answers: first.items.map(i => ({ qid: i.qid })) }], false);
  const second = E.buildExam(bank, { rng: seeded(8), recent });
  // CARGO: 풀 25개, 직전 15개 사용 → 새 문제 10개가 모두 포함되어야 함
  const cargoNew = second.items.filter(i => i.subject === 'CARGO' && !recent[i.qid]).length;
  assert.equal(cargoNew, 10);
  // LAW: 풀 40개, 직전 25개 → 새 문제 15개 모두 포함
  assert.equal(second.items.filter(i => i.subject === 'LAW' && !recent[i.qid]).length, 15);
});

test('recentQids: 같은 모드의 최근 2회만', () => {
  const ex = [
    { sample: false, answers: [{ qid: 'A' }] },
    { sample: true, answers: [{ qid: 'S' }] },
    { sample: false, answers: [{ qid: 'B' }] },
    { sample: false, answers: [{ qid: 'C' }] }
  ];
  assert.deepEqual(Object.keys(E.recentQids(ex, false)).sort(), ['B', 'C']);
  assert.deepEqual(Object.keys(E.recentQids(ex, true)), ['S']);
});

test('문제 부족 시 시작 차단 (FR-211)', () => {
  const bank = Q.buildBank(cfg, { LAW: fixture });
  const r = E.checkReady(bank);
  assert.equal(r.ok, false);
  assert.equal(r.lacking.length, 4);
  assert.throws(() => E.buildExam(bank), e => e.code === 'NOT_READY');
});

test('채점: 48개 정답 60점 합격 / 47개 58.75점 불합격, 미응답은 오답 (TC-05)', () => {
  const bank = loadSampleBank();
  const ip = E.buildExam(bank, { rng: seeded(3) });
  ip.items.forEach((it, i) => { if (i < 48) E.setAnswer(ip, i, bank.byId[it.qid].answer); });
  let r = E.score(ip, bank);
  assert.equal(r.correct, 48); assert.equal(r.score, 60); assert.equal(r.passed, true);
  assert.equal(r.answers.filter(a => a.choice === null).length, 32);
  E.setAnswer(ip, 47, (bank.byId[ip.items[47].qid].answer % 4) + 1); // 오답으로 변경
  r = E.score(ip, bank);
  assert.equal(r.correct, 47); assert.equal(r.score, 58.75); assert.equal(r.passed, false);
  const law = r.bySubject.LAW;
  assert.equal(law.total, 25); assert.equal(law.correct, 25); assert.equal(law.score, 100);
  assert.equal(r.bySubject.SERVICE.correct, 0);
});

test('setAnswer 범위 검사, 응답 수, 첫 미응답, 시간 표시', () => {
  const bank = loadSampleBank();
  const ip = E.buildExam(bank, { rng: seeded(1) });
  assert.equal(E.setAnswer(ip, 0, 5), false);
  assert.equal(E.setAnswer(ip, 80, 1), false);
  E.setAnswer(ip, 0, 2); E.setAnswer(ip, 1, 3);
  assert.deepEqual(E.counts(ip), { total: 80, answered: 2, unanswered: 78 });
  assert.equal(E.firstUnanswered(ip), 2);
  E.setAnswer(ip, 0, null);
  assert.equal(E.firstUnanswered(ip), 0);
  assert.equal(E.formatTime(80 * 60000), '80:00');
  assert.equal(E.formatTime(61001), '01:02');
  assert.equal(E.formatTime(-5), '00:00');
});

test('이어 풀기 전 검사: 삭제·폐기된 문제 감지', () => {
  const bank = loadSampleBank();
  const ip = E.buildExam(bank, { rng: seeded(2) });
  assert.deepEqual(E.missingQuestions(ip, bank), []);
  bank.byId[ip.items[0].qid].status = 'deprecated';
  delete bank.byId[ip.items[1].qid];
  assert.equal(E.missingQuestions(ip, bank).length, 2);
});

test('샘플 문제 파일 형식 정상, 9000번대 id', () => {
  const bank = loadSampleBank();
  assert.deepEqual(bank.warnings, []);
  assert.ok(Object.keys(bank.byId).every(id => +id.split('-')[1] > 9000));
});

/* ---------- v1.9 즉시 채점 ---------- */
test('즉시 채점: 답 고정(lock), 문항별 판정, 정답·오답 집계', () => {
  const bank = loadSampleBank();
  const ip = E.buildExam(bank, { rng: seeded(11) });
  const ans0 = bank.byId[ip.items[0].qid].answer;
  assert.equal(E.setAnswer(ip, 0, ans0, { lock: true }), true);
  assert.equal(E.setAnswer(ip, 0, ans0 % 4 + 1, { lock: true }), false, '이미 답한 문항은 변경 불가');
  assert.equal(ip.answers[0], ans0);
  E.setAnswer(ip, 1, bank.byId[ip.items[1].qid].answer % 4 + 1, { lock: true });
  assert.deepEqual(E.judge(ip, bank, 0), { answered: true, choice: ans0, answer: ans0, correct: true });
  assert.equal(E.judge(ip, bank, 1).correct, false);
  assert.equal(E.judge(ip, bank, 2).answered, false);
  assert.deepEqual(E.tally(ip, bank), { correct: 1, wrong: 1, unanswered: 78 });
});

/* ---------- S3 오답노트 ---------- */
const N = require('../src/notes.js');

test('오답 자동 등록: 오답·안 푼 문항 신규 등록, 정답은 제외 (FR-601)', () => {
  const bank = loadSampleBank();
  const ip = E.buildExam(bank, { rng: seeded(21) });
  ip.items.forEach((it, i) => {
    const a = bank.byId[it.qid].answer;
    if (i < 70) E.setAnswer(ip, i, i < 60 ? a : a % 4 + 1, { lock: true }); // 60 정답, 10 오답, 10 안 품
  });
  const rec = E.score(ip, bank);
  const notes = {};
  const r = N.registerWrong(notes, rec, bank, '2026-10-19T10:00:00Z');
  assert.deepEqual(r, { added: 20, updated: 0 });
  const wrongQid = ip.items[60].qid;
  assert.equal(notes[wrongQid].wrong_count, 1);
  assert.equal(notes[wrongQid].added_by, 'auto');
  assert.equal(notes[wrongQid].state, 'active');
  assert.equal(notes[wrongQid].last_choice, ip.answers[60]);
  assert.equal(notes[ip.items[75].qid].last_choice, null, '안 푼 문항은 last_choice null');
  assert.equal(notes[ip.items[0].qid], undefined, '정답 문항은 등록 안 함');
});

test('다시 틀리면 횟수 +1, 복습 완료 문제는 재등록 (FR-602, 603)', () => {
  const bank = loadSampleBank();
  const q = bank.bySubject.LAW[0];
  const notes = { [q.id]: { subject: 'LAW', question_version: 1, wrong_count: 2, streak: 2, last_choice: 1, first_wrong_at: 'A', last_wrong_at: 'B', added_by: 'auto', state: 'mastered' } };
  const rec = { answers: [{ qid: q.id, qver: 1, choice: 3, correct: false }] };
  const r = N.registerWrong(notes, rec, bank, 'C');
  assert.deepEqual(r, { added: 0, updated: 1 });
  assert.equal(notes[q.id].wrong_count, 3);
  assert.equal(notes[q.id].streak, 0);
  assert.equal(notes[q.id].state, 'active');
  assert.equal(notes[q.id].first_wrong_at, 'A');
  assert.equal(notes[q.id].last_wrong_at, 'C');
  assert.equal(notes[q.id].last_choice, 3);
});

test('오답노트에 담기: 신규/이미 있음/복습 완료 재활성 (FR-403)', () => {
  const bank = loadSampleBank();
  const q = bank.bySubject.SAFE[0];
  const notes = {};
  assert.equal(N.addManual(notes, q, { sample: true, choice: 2 }), 'added');
  assert.equal(notes[q.id].added_by, 'manual');
  assert.equal(notes[q.id].wrong_count, 0);
  assert.equal(N.addManual(notes, q), 'exists');
  notes[q.id].state = 'mastered';
  assert.equal(N.addManual(notes, q), 'reactivated');
  assert.equal(notes[q.id].state, 'active');
});

test('복습할 오답 수: 모드 분리, 폐기 문제 제외 (FR-606)', () => {
  const bank = loadSampleBank();
  const [a, b, c] = bank.bySubject.LAW;
  const notes = {
    [a.id]: { state: 'active', sample: true },
    [b.id]: { state: 'mastered', sample: true },
    [c.id]: { state: 'active', sample: true },
    'LAW-0001': { state: 'active', sample: false }
  };
  assert.equal(N.activeCount(notes, bank, true), 2);
  c.status = 'deprecated';
  assert.equal(N.activeCount(notes, bank, true), 1);
  assert.equal(N.activeCount(notes, null, false), 1);
});

test('오류 신고 주소: 저장소 미정이면 null, 정해지면 제목·본문 포함 (FR-404)', () => {
  const q = { id: 'LAW-0001', version: 2, question: '지문' };
  assert.equal(N.issueUrl({ issue_url: 'https://github.com/<계정>/x/issues/new' }, q), null);
  const u = N.issueUrl({ issue_url: 'https://github.com/me/x/issues/new' }, q);
  assert.ok(u.startsWith('https://github.com/me/x/issues/new?title='));
  assert.ok(decodeURIComponent(u).includes('[문제 오류] LAW-0001'));
  assert.ok(decodeURIComponent(u).includes('문제 버전: 2'));
});

/* ---------- S4 내 기록 ---------- */
const R = require('../src/records.js');
test('내 기록 집계: 모드 분리, 평균·최고·합격률, 과목별 평균, 최신순 이력, 최근 20회 추이', () => {
  const mk = (score, passed, sample, law) => ({ id: 'e' + Math.random(), score, passed, sample, finishedAt: 'T', bySubject: { LAW: { correct: law, total: 25 }, CARGO: { correct: 15, total: 15 } } });
  const exams = [mk(50, false, false, 10), mk(70, true, false, 20), mk(99, true, true, 25), mk(60, true, false, 15)];
  const r = R.summarize(exams, false, cfg.exam);
  assert.equal(r.count, 3);
  assert.equal(r.avg, 60);
  assert.equal(r.best, 70);
  assert.equal(r.passRate, 67);
  assert.equal(r.recent, 60);
  assert.equal(r.subjects[0].avg, 60, 'LAW (10+20+15)/75');
  assert.equal(r.subjects[1].avg, 100);
  assert.equal(r.subjects[2].avg, null, '기록 없는 과목');
  assert.deepEqual(r.history.map(h => h.no), [3, 2, 1]);
  assert.equal(R.summarize(exams, true, cfg.exam).count, 1, '샘플 모드는 따로');
  const many = Array.from({ length: 25 }, (_, i) => mk(i * 4, i * 4 >= 60, false, 10));
  const t = R.summarize(many, false, cfg.exam).trend;
  assert.equal(t.length, 20);
  assert.equal(t[0].no, 6);
  assert.equal(t[19].score, 96);
  assert.equal(R.summarize([], false, cfg.exam).avg, null);
});

/* ---------- S5 복습 재시험 ---------- */
const RV = require('../src/review.js');
function notesFor(bank, ids, extra) {
  const n = {};
  ids.forEach(id => { n[id] = Object.assign({ subject: bank.byId[id].subject, question_version: 1, wrong_count: 1, streak: 0, last_choice: 1,
    first_wrong_at: '2026-10-18T00:00:00Z', last_wrong_at: '2026-10-18T00:00:00Z', added_by: 'auto', state: 'active', sample: true }, extra || {}); });
  return n;
}
const NOW = Date.parse('2026-10-19T12:00:00Z');

test('복습 범위: 전체/과목/많이 틀림/최근 7일/복습 완료, 모드·폐기 제외 (FR-701, 606)', () => {
  const bank = loadSampleBank();
  const law = bank.bySubject.LAW.slice(0, 5).map(q => q.id);
  const safe = bank.bySubject.SAFE.slice(0, 3).map(q => q.id);
  const notes = notesFor(bank, law.concat(safe));
  notes[law[0]].wrong_count = 3;
  notes[law[1]].last_wrong_at = '2026-10-01T00:00:00Z';
  notes[law[2]].state = 'mastered';
  notes[safe[0]].sample = false;
  bank.byId[safe[1]].status = 'deprecated';
  const c = RV.scopeCounts(notes, bank, true, NOW);
  assert.equal(c.all, 5);            // law 4 active + safe[2]
  assert.equal(c['subject:LAW'], 4);
  assert.equal(c['subject:SAFE'], 1);
  assert.equal(c.frequent, 1);
  assert.equal(c.recent, 4);         // law[1]은 18일 전
  assert.equal(c.mastered, 1);
});

test('복습 출제: 문항 수 제한, 보기 순서 섞기(원래 번호 보존) (FR-702, 705)', () => {
  const bank = loadSampleBank();
  const ids = bank.bySubject.LAW.slice(0, 15).map(q => q.id);
  const notes = notesFor(bank, ids);
  const rv = RV.buildReview(notes, bank, { sample: true, scope: 'all', count: 10, rng: seeded(5) });
  assert.equal(rv.items.length, 10);
  assert.ok(rv.items.every(it => it.perm.slice().sort().join() === '1,2,3,4'));
  assert.ok(rv.items.some(it => it.perm.join() !== '1,2,3,4'), '일부는 섞임');
  const all = RV.buildReview(notes, bank, { sample: true, scope: 'all', count: 'all', rng: seeded(6) });
  assert.equal(all.items.length, 15);
  assert.throws(() => RV.buildReview({}, bank, { sample: true }), e => e.code === 'EMPTY');
  const it = rv.items[0];
  const pos = RV.displayIndexOf(it, bank.byId[it.qid].answer);
  assert.equal(RV.originalChoice(it, pos), bank.byId[it.qid].answer, '화면 위치 ↔ 원래 번호');
});

test('복습 채점: 연속 2회 정답 졸업, 오답 시 연속 0·횟수 +1, 완료 문제 오답 시 재활성 (FR-706, 708)', () => {
  const bank = loadSampleBank();
  const id = bank.bySubject.LAW[0].id, ans = bank.byId[id].answer;
  const notes = notesFor(bank, [id]);
  let rv = RV.buildReview(notes, bank, { sample: true, count: 'all' });
  let r = RV.answer(rv, notes, bank, 0, ans, 'T1');
  assert.deepEqual([r.correct, r.mastered, notes[id].streak, notes[id].state], [true, false, 1, 'active']);
  assert.equal(RV.answer(rv, notes, bank, 0, ans), null, '이미 답한 문항');
  rv = RV.buildReview(notes, bank, { sample: true, count: 'all' });
  r = RV.answer(rv, notes, bank, 0, ans % 4 + 1, 'T2');
  assert.deepEqual([r.correct, notes[id].streak, notes[id].wrong_count, notes[id].last_choice, notes[id].last_wrong_at], [false, 0, 2, ans % 4 + 1, 'T2']);
  for (const k of [1, 2]) {
    rv = RV.buildReview(notes, bank, { sample: true, count: 'all' });
    r = RV.answer(rv, notes, bank, 0, ans, 'T' + (k + 2));
  }
  assert.equal(r.mastered, true);
  assert.equal(notes[id].state, 'mastered');
  rv = RV.buildReview(notes, bank, { sample: true, scope: 'mastered', count: 'all' });
  r = RV.answer(rv, notes, bank, 0, ans % 4 + 1, 'T5');
  assert.equal(r.reactivated, true);
  assert.equal(notes[id].state, 'active');
  const rec = RV.finish(rv, 'T6');
  assert.deepEqual([rec.total, rec.answered, rec.correct, rec.mode, rec.wrongIds.length], [1, 1, 0, 'instant', 1]);
});

test('오답노트 목록·요약·직접 관리 (FR-604, 605)', () => {
  const bank = loadSampleBank();
  const ids = bank.bySubject.LAW.slice(0, 3).map(q => q.id).concat(bank.bySubject.CARGO.slice(0, 1).map(q => q.id));
  const notes = notesFor(bank, ids);
  notes[ids[0]].wrong_count = 5; notes[ids[1]].last_wrong_at = '2026-10-19T09:00:00Z';
  bank.byId[ids[2]].version = 2;
  assert.equal(RV.listNotes(notes, bank, true, { sort: 'count' })[0].id, ids[0]);
  assert.equal(RV.listNotes(notes, bank, true, { sort: 'recent' })[0].id, ids[1]);
  assert.equal(RV.listNotes(notes, bank, true, { subject: 'CARGO' }).length, 1);
  assert.equal(RV.listNotes(notes, bank, true).filter(r => r.changed).length, 1, '수정된 문제 표시 (FR-607)');
  RV.setMastered(notes, ids[0]); RV.remove(notes, ids[3]);
  const s = RV.summary(notes, bank, true);
  assert.deepEqual([s.active, s.mastered, s.bySubject.LAW, s.bySubject.CARGO], [2, 1, 2, 0]);
  RV.setActive(notes, ids[0]);
  assert.equal(notes[ids[0]].streak, 0);
});

/* ---------- S6 백업·초기화 ---------- */
const B = require('../src/backup.js');
function mkData() {
  return {
    exams: [{ id: 'x1', score: 50, passed: false, finishedAt: '2026-10-01T00:00:00Z', answers: [] },
            { id: 'x2', score: 70, passed: true, finishedAt: '2026-10-03T00:00:00Z', answers: [] }],
    wrongNotes: { 'LAW-0001': { state: 'active', wrong_count: 2, last_wrong_at: '2026-10-03T00:00:00Z' },
                  'LAW-0002': { state: 'mastered', wrong_count: 1, mastered_at: '2026-10-02T00:00:00Z' } },
    reviewSessions: [{ id: 'r1', at: '2026-10-02T00:00:00Z' }],
    inProgress: { id: 'ip' }, reviewInProgress: { id: 'rip' }
  };
}

test('백업 만들기·읽기: 진행 중 상태 제외, 왕복 보존 (FR-901, 902)', () => {
  const b = B.buildBackup([{ name: '화물왕', createdAt: 'C', data: mkData() }], 'NOW');
  assert.equal(b.app, 'cdme'); assert.equal(b.schemaVersion, 1);
  assert.equal(b.profiles[0].data.inProgress, undefined);
  const r = B.parse(JSON.stringify(b));
  assert.equal(r.ok, true);
  assert.equal(r.backup.profiles[0].data.exams.length, 2);
  assert.deepEqual(B.summarizeData(r.backup.profiles[0].data), { exams: 2, notes: 1, mastered: 1, reviews: 1, bookmarks: 0, studies: 0 });
  assert.ok(B.fileName('화물 왕', '2026-10-19T03:04:00Z').startsWith('화물모의시험_백업_화물_왕_20261019_'));
});

test('백업 형식 검사: 깨진 파일·다른 파일·신버전·잘못된 기록 거부 (FR-902)', () => {
  assert.equal(B.parse('').ok, false);
  assert.equal(B.parse('{abc').ok, false);
  assert.equal(B.parse('{"app":"other"}').ok, false);
  assert.ok(/새로운 버전/.test(B.parse(JSON.stringify({ app: 'cdme', kind: 'backup', schemaVersion: 99, profiles: [{ name: 'a' }] })).error));
  assert.equal(B.parse(JSON.stringify({ app: 'cdme', kind: 'backup', schemaVersion: 1, profiles: [] })).ok, false);
  assert.equal(B.parse(JSON.stringify({ app: 'cdme', kind: 'backup', schemaVersion: 1, profiles: [{ name: 'a', data: { exams: [{ id: 1 }] } }] })).ok, false);
  assert.equal(B.parse('﻿' + JSON.stringify(B.buildBackup([{ name: 'a', data: {} }]))).ok, true, 'BOM 허용');
});

test('합치기: 기록 합집합·시간순, 오답은 최근 상태 + 틀린 횟수 큰 값', () => {
  const a = mkData();
  const b = { exams: [{ id: 'x2', score: 70, finishedAt: '2026-10-03T00:00:00Z', answers: [] }, { id: 'x3', score: 80, finishedAt: '2026-10-02T00:00:00Z', answers: [] }],
    wrongNotes: { 'LAW-0001': { state: 'mastered', wrong_count: 1, mastered_at: '2026-10-05T00:00:00Z' }, 'LAW-0009': { state: 'active', wrong_count: 1 } },
    reviewSessions: [{ id: 'r2', at: '2026-10-04T00:00:00Z' }] };
  const m = B.merge(a, b);
  assert.deepEqual(m.exams.map(e => e.id), ['x1', 'x3', 'x2']);
  assert.deepEqual(m.reviewSessions.map(r => r.id), ['r1', 'r2']);
  assert.equal(m.wrongNotes['LAW-0001'].state, 'mastered', '더 최근 상태');
  assert.equal(m.wrongNotes['LAW-0001'].wrong_count, 2, '틀린 횟수는 큰 값');
  assert.ok(m.wrongNotes['LAW-0009']);
  assert.deepEqual(m.inProgress, { id: 'ip' }, '이 기기의 진행 중 시험 유지');
});

test('불러오기 계획·실행: 새 닉네임 / 합치기 / 덮어쓰기 / 이름 바꿔 가져오기 (FR-902, 903)', () => {
  const st = S.createStore(S.memoryAdapter());
  const a = st.createProfile('화물왕').profile;
  st.replaceProfileData(a.id, mkData());
  const bk = B.parse(JSON.stringify(B.buildBackup([
    { name: '화물왕', data: { exams: [{ id: 'y1', score: 90, finishedAt: '2026-10-09T00:00:00Z', answers: [] }] } },
    { name: '홍길동', data: { exams: [] } }
  ]))).backup;
  let steps = B.plan(bk, st.listProfiles());
  assert.deepEqual(steps.map(s => s.action), ['merge', 'new']);
  B.apply(st, steps);
  assert.equal(st.listProfiles().length, 2);
  assert.equal(st.getProfileData(a.id).exams.length, 3, '합치기');
  steps = B.plan(bk, st.listProfiles());
  steps[0].action = 'rename'; steps[1].action = 'overwrite';
  const res = B.apply(st, steps);
  assert.equal(res[0].newName, '화물왕 (2)');
  assert.equal(st.listProfiles().length, 3);
  steps = B.plan(bk, st.listProfiles()); steps[0].action = 'overwrite'; steps[1].action = 'skip';
  B.apply(st, steps);
  const d = st.getProfileData(a.id);
  assert.deepEqual([d.exams.length, Object.keys(d.wrongNotes).length, d.inProgress], [1, 0, null], '덮어쓰기');
  assert.equal(B.freeName('화물왕', ['화물왕', '화물왕 (2)']), '화물왕 (3)');
});

test('초기화 범위·개별 삭제 (FR-801, 802)', () => {
  let d = B.resetData(mkData(), 'exams');
  assert.deepEqual([d.exams.length, d.inProgress, Object.keys(d.wrongNotes).length, d.reviewSessions.length], [0, null, 2, 1]);
  d = B.resetData(mkData(), 'notes');
  assert.deepEqual([d.exams.length, Object.keys(d.wrongNotes).length, d.reviewInProgress, d.reviewSessions.length], [2, 0, null, 1]);
  d = B.resetData(mkData(), 'all');
  assert.deepEqual([d.exams.length, Object.keys(d.wrongNotes).length, d.reviewSessions.length, d.inProgress, d.reviewInProgress], [0, 0, 0, null, null]);
  const e = mkData();
  assert.equal(B.deleteExam(e, 'x1'), true);
  assert.equal(B.deleteExam(e, 'nope'), false);
  assert.deepEqual(e.exams.map(x => x.id), ['x2']);
});

/* ---------- v1.17 힌트 (FR-312) ---------- */
test('힌트: 글 힌트 우선, 없으면 늘 같은 틀린 보기 하나 지우기', () => {
  assert.deepEqual(E.hintFor({ id: 'LAW-0001', answer: 2, hint: '  생각해 보세요 ' }), { type: 'text', text: '생각해 보세요' });
  for (const id of ['LAW-0001', 'SAFE-0002', 'X-9', 'CARGO-0033']) {
    for (let a = 1; a <= 4; a++) {
      const h1 = E.hintFor({ id, answer: a, hint: '' });
      const h2 = E.hintFor({ id, answer: a });
      assert.equal(h1.type, 'elim');
      assert.notEqual(h1.remove, a, '정답은 지우지 않음');
      assert.ok(h1.remove >= 1 && h1.remove <= 4);
      assert.deepEqual(h1, h2, '같은 문제는 같은 보기');
    }
  }
  assert.equal(E.hintFor(null), null);
});

test('힌트 사용 기록: 답하기 전만, 예전 진행 데이터 호환, 결과에 문항 표시·개수 (점수 영향 없음)', () => {
  const bank = loadSampleBank();
  const ip = E.buildExam(bank, { rng: seeded(31) });
  assert.equal(ip.hints.length, 80);
  assert.equal(E.useHint(ip, 0), true);
  E.setAnswer(ip, 1, bank.byId[ip.items[1].qid].answer, { lock: true });
  assert.equal(E.useHint(ip, 1), false, '이미 답한 문항은 힌트 기록 안 함');
  assert.equal(E.useHint(ip, 99), false);
  E.setAnswer(ip, 0, bank.byId[ip.items[0].qid].answer, { lock: true });
  const r = E.score(ip, bank);
  assert.equal(r.hintCount, 1);
  assert.equal(r.answers[0].hint, true);
  assert.equal(r.answers[1].hint, undefined);
  assert.equal(r.correct, 2, '힌트를 봐도 정답 처리');
  const old = E.buildExam(bank, { rng: seeded(32) });
  delete old.hints;                                  // v1.16 이전에 시작한 시험
  assert.equal(E.hintUsed(old, 3), false);
  assert.equal(E.useHint(old, 3), true);
  assert.equal(E.hintUsed(old, 3), true);
  assert.equal(E.score(old, bank).hintCount, 1);
});

test('복습 힌트: 복습 세션에도 기록, 결과에 개수 (졸업 판정 영향 없음)', () => {
  const bank = loadSampleBank();
  const notes = {};
  const ip = E.buildExam(bank, { rng: seeded(41) });
  N.registerWrong(notes, E.score(ip, bank), bank, '2026-10-19T10:00:00Z');
  const rv = RV.buildReview(notes, bank, { count: 3, rng: seeded(5) });
  assert.equal(rv.hints.length, 3);
  E.useHint(rv, 0);
  const q = bank.byId[rv.items[0].qid];
  const res = RV.answer(rv, notes, bank, 0, q.answer);
  assert.equal(res.correct, true);
  assert.equal(RV.finish(rv).hintCount, 1);
});


/* ---------- v1.1.0: 북마크·집중 학습·취약 과목 (PRD 12.1) ---------- */
const ST = require('../src/study.js');

test('북마크: 켜기·끄기, 모드(실제/샘플) 분리, 폐기 문제 제외', () => {
  const bank = loadSampleBank();
  const bm = {};
  const q1 = bank.bySubject.LAW[0], q2 = bank.bySubject.SAFE[0];
  assert.equal(ST.toggleBookmark(bm, q1, false, '2026-10-21T01:00:00Z'), true);
  assert.equal(ST.toggleBookmark(bm, q2, false, '2026-10-21T02:00:00Z'), true);
  assert.equal(ST.isBookmarked(bm, q1.id, false), true);
  assert.equal(ST.isBookmarked(bm, q1.id, true), false, '샘플 모드에서는 따로');
  assert.deepEqual(ST.listBookmarks(bm, bank, false).map(r => r.id), [q2.id, q1.id], '최근 담은 순');
  assert.equal(ST.listBookmarks(bm, bank, false, 'LAW').length, 1);
  assert.equal(ST.toggleBookmark(bm, q1, false), false, '다시 누르면 해제');
  assert.equal(ST.bookmarkCount(bm, bank, false), 1);
  bank.byId[q2.id].status = 'deprecated';
  assert.equal(ST.bookmarkCount(bm, bank, false), 0, '폐기된 문제는 목록에서 빠짐');
  bank.byId[q2.id].status = 'verified';
});

test('집중 학습 범위: 과목 여러 개·난이도·북마크, 출제 가능(verified)만', () => {
  const bank = loadSampleBank();
  const all = ST.pool(bank, {}, {}, false);
  assert.equal(all.length, Object.values(bank.byId).filter(q => q.status === 'verified').length);
  const law = ST.pool(bank, { subjects: ['LAW'] }, {}, false);
  assert.ok(law.length > 0 && law.every(id => id.startsWith('LAW-')));
  const two = ST.pool(bank, { subjects: ['LAW', 'CARGO'] }, {}, false);
  assert.ok(two.some(id => id.startsWith('CARGO-')) && two.every(id => /^(LAW|CARGO)-/.test(id)));
  const d1 = ST.pool(bank, { difficulty: 1 }, {}, false);
  assert.ok(d1.every(id => bank.byId[id].difficulty === 1));
  assert.equal(ST.pool(bank, { subjects: ['NOPE'] }, {}, false).length, all.length, '모르는 과목 코드는 무시(전체)');
  const bm = {}; ST.toggleBookmark(bm, bank.byId[law[0]], false);
  assert.deepEqual(ST.pool(bank, { source: 'bookmark' }, bm, false), [law[0]]);
  const c = ST.poolCounts(bank, { subjects: ['LAW'] }, bm, false);
  assert.equal(c.total, law.length); assert.equal(c.bookmark, 1);
  assert.equal(c.subject.CARGO, ST.pool(bank, { subjects: ['CARGO'] }, {}, false).length, '과목 칩 숫자는 다른 조건만 반영');
  assert.equal(c.difficulty[0], law.length);
});

test('집중 학습 풀이: 문항 수 제한, 틀리면 오답노트에 담김, 결과 과목별 집계', () => {
  const bank = loadSampleBank();
  assert.throws(() => ST.buildStudy(bank, { filter: { source: 'bookmark' }, bookmarks: {} }), /없습니다/);
  const st = ST.buildStudy(bank, { filter: { subjects: ['LAW', 'SAFE'] }, count: 4, rng: seeded(7) });
  assert.equal(st.items.length, 4);
  assert.ok(st.items.every(it => it.perm.join() === '1,2,3,4'), '기본은 보기 순서 그대로');
  const notes = {};
  const q0 = bank.byId[st.items[0].qid], q1 = bank.byId[st.items[1].qid];
  assert.equal(ST.answer(st, notes, bank, 0, q0.answer, 'T1').correct, true);
  const wrong = q1.answer === 1 ? 2 : 1;
  const r1 = ST.answer(st, notes, bank, 1, wrong, 'T2');
  assert.equal(r1.correct, false); assert.equal(r1.noted, true);
  assert.equal(notes[q1.id].added_by, 'study'); assert.equal(notes[q1.id].state, 'active');
  assert.equal(notes[q0.id], undefined, '맞힌 문제는 담지 않음');
  assert.equal(ST.answer(st, notes, bank, 1, q1.answer), null, '답은 바꿀 수 없음');
  E.useHint(st, 2); ST.answer(st, notes, bank, 2, bank.byId[st.items[2].qid].answer);
  const rec = ST.finish(st, 'T9');
  assert.equal(rec.total, 4); assert.equal(rec.answered, 3); assert.equal(rec.correct, 2); assert.equal(rec.hintCount, 1);
  assert.deepEqual(rec.wrongIds, [q1.id]);
  const sum = Object.values(rec.bySubject).reduce((a, b) => a + b.total, 0);
  assert.equal(sum, 3);
  const sh = ST.buildStudy(bank, { count: 'all', shuffleChoices: true, rng: seeded(3) });
  assert.ok(sh.items.some(it => it.perm.join() !== '1,2,3,4'), '보기 섞기 선택 시 섞임');
});

test('취약 과목 분석: 최근 5회, 합격선(60%) 미만 표시, 부족 문항 수', () => {
  const config = { exam: { pass_score: 60, subjects: [{ code: 'LAW', count: 25, name: '법규' }, { code: 'CARGO', count: 15, name: '화물' }] } };
  assert.equal(ST.weakness([], false, config).count, 0);
  const mk = (law, cargo, sample) => ({ sample, bySubject: { LAW: { correct: law, total: 25 }, CARGO: { correct: cargo, total: 15 } } });
  const exams = [mk(0, 0), mk(25, 15), mk(10, 12), mk(12, 12), mk(14, 9), mk(11, 9), mk(13, 12), mk(5, 5, true)];
  const w = ST.weakness(exams, false, config, 5);
  assert.equal(w.count, 5, '최근 5회만 (샘플 제외)');
  const law = w.subjects[0], cargo = w.subjects[1];
  assert.equal(law.correct, 60); assert.equal(law.rate, 48); assert.equal(law.weak, true);
  assert.equal(law.need, 3, '25문항 × (60-48)% = 3문항');
  assert.equal(cargo.rate, 72); assert.equal(cargo.weak, false); assert.equal(cargo.need, 0);
  assert.deepEqual(w.weak.map(s => s.code), ['LAW']);
  assert.equal(w.weakest.code, 'LAW');
});

test('예전 기록에 북마크·학습 항목 자동 추가, 백업·합치기·초기화에 포함', () => {
  const ad = S.memoryAdapter();
  ad.set('cdme', JSON.stringify({ schemaVersion: 1, activeProfileId: 'p', profiles: [{ id: 'p', name: '옛날' }],
    data: { p: { exams: [], wrongNotes: {}, reviewSessions: [], inProgress: null, reviewInProgress: null } } }));
  const st = S.createStore(ad);
  const d = st.getProfileData('p');
  assert.deepEqual(d.bookmarks, {}); assert.deepEqual(d.studySessions, []); assert.equal(d.studyInProgress, null);
  const data = Object.assign(mkData(), { bookmarks: { 'LAW-0001': { subject: 'LAW', added_at: 'A' } }, studySessions: [{ id: 's1', at: '2026-10-05T00:00:00Z' }], studyInProgress: { id: 'sip' } });
  const b = B.parse(JSON.stringify(B.buildBackup([{ name: 'a', data }]))).backup.profiles[0].data;
  assert.equal(b.studyInProgress, undefined, '진행 중 학습은 백업 안 함');
  assert.equal(Object.keys(b.bookmarks).length, 1); assert.equal(b.studySessions.length, 1);
  const m = B.merge({ exams: [], wrongNotes: {}, bookmarks: { 'SAFE-0001': { subject: 'SAFE' } }, studySessions: [{ id: 's0', at: '2026-10-01T00:00:00Z' }] }, b);
  assert.deepEqual(Object.keys(m.bookmarks).sort(), ['LAW-0001', 'SAFE-0001']);
  assert.deepEqual(m.studySessions.map(x => x.id), ['s0', 's1']);
  assert.equal(B.parse(JSON.stringify({ app: 'cdme', kind: 'backup', schemaVersion: 1, profiles: [{ name: 'a', data: { bookmarks: [] } }] })).ok, false);
  const r1 = B.resetData(data, 'notes');
  assert.equal(Object.keys(r1.bookmarks).length, 1, '오답노트만 지우면 북마크는 남음');
  const r2 = B.resetData(data, 'all');
  assert.deepEqual(r2.bookmarks, {}); assert.deepEqual(r2.studySessions, []); assert.equal(r2.studyInProgress, null);
});
