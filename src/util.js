/* 공통 유틸리티 */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});

  function uuid() {
    try {
      if (root.crypto && typeof root.crypto.randomUUID === 'function') return root.crypto.randomUUID();
    } catch (e) { /* 보안 컨텍스트가 아니면 아래 방식 사용 */ }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  function nowISO() { return new Date().toISOString(); }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatDate(iso) {
    if (!iso) return '-';
    var d = new Date(iso);
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    return d.getFullYear() + '.' + p(d.getMonth() + 1) + '.' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  CDME.util = { uuid: uuid, nowISO: nowISO, escapeHtml: escapeHtml, formatDate: formatDate };
  if (typeof module !== 'undefined' && module.exports) module.exports = CDME.util;
})(typeof window !== 'undefined' ? window : globalThis);
