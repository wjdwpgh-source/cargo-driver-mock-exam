/* 오프라인 동작 (NFR-04) – Service Worker
 * - 설치 시 화면 파일·문제 데이터를 미리 저장
 * - 평소에는 인터넷에서 최신 파일을 받고(받은 파일은 저장), 인터넷이 안 되면 저장된 파일 사용
 * - 파일 구성이 바뀌면 VERSION을 올린다
 */
var VERSION = 'cdme-v1.26';
var FILES = [
  './', 'index.html', 'manifest.webmanifest',
  'src/styles.css', 'src/util.js', 'src/store.js', 'src/questions.js', 'src/exam.js', 'src/notes.js',
  'src/records.js', 'src/review.js', 'src/study.js', 'src/backup.js',
  'src/ui/modal.js', 'src/ui/exam-view.js', 'src/ui/records-view.js', 'src/ui/review-view.js', 'src/ui/study-view.js',
  'src/ui/data-view.js', 'src/ui/help-view.js', 'src/app.js',
  'data/config.json',
  'data/questions/LAW.json', 'data/questions/CARGO.json', 'data/questions/SAFE.json', 'data/questions/SERVICE.json',
  'data/samples/LAW.json', 'data/samples/CARGO.json', 'data/samples/SAFE.json', 'data/samples/SERVICE.json',
  'images/icon-192.png', 'images/icon-512.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) {
    // 하나가 없어도 나머지는 저장되도록 개별 저장
    return Promise.all(FILES.map(function (f) {
      return fetch(f, { cache: 'no-cache' }).then(function (r) { if (r.ok) return c.put(f, r); }).catch(function () {});
    }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  e.respondWith(
    fetch(req).then(function (res) {
      if (res && res.ok) {
        var copy = res.clone();
        caches.open(VERSION).then(function (c) { c.put(req, copy); });
      }
      return res;
    }).catch(function () {
      return caches.match(req, { ignoreSearch: true }).then(function (hit) {
        if (hit) return hit;
        if (req.mode === 'navigate') return caches.match('index.html');
        return new Response('오프라인', { status: 503, statusText: 'offline' });
      });
    })
  );
});
