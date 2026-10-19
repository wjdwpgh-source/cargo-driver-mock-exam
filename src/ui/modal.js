/* 확인·입력 창 (브라우저 기본 confirm/prompt 대신 사용) */
(function (root) {
  'use strict';
  var CDME = (root.CDME = root.CDME || {});
  var esc = CDME.util.escapeHtml;

  function open(opts) {
    return new Promise(function (resolve) {
      var prev = document.activeElement;
      var wrap = document.createElement('div');
      wrap.className = 'modal-backdrop';
      wrap.innerHTML =
        '<div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">' +
        '<h2 id="modal-title">' + esc(opts.title) + '</h2>' +
        (opts.message ? '<p class="modal-msg">' + opts.message + '</p>' : '') +
        (opts.input ? '<label class="field"><span class="sr-only">' + esc(opts.inputLabel || '입력') + '</span>' +
          '<input type="text" class="input" id="modal-input" autocomplete="off" maxlength="' + (opts.maxLength || 50) + '" value="' + esc(opts.value || '') + '" placeholder="' + esc(opts.placeholder || '') + '"></label>' +
          '<p class="form-error" id="modal-error" role="alert"></p>' : '') +
        '<div class="modal-actions">' +
        '<button type="button" class="btn btn-ghost" data-act="cancel">' + esc(opts.cancelText || '취소') + '</button>' +
        '<button type="button" class="btn ' + (opts.danger ? 'btn-danger' : 'btn-primary') + '" data-act="ok">' + esc(opts.okText || '확인') + '</button>' +
        '</div></div>';
      document.body.appendChild(wrap);

      var input = wrap.querySelector('#modal-input');
      var errEl = wrap.querySelector('#modal-error');
      var okBtn = wrap.querySelector('[data-act="ok"]');

      function close(val) {
        document.removeEventListener('keydown', onKey);
        wrap.remove();
        if (prev && prev.focus) prev.focus();
        resolve(val);
      }
      function submit() {
        if (!input) return close(true);
        var v = input.value;
        if (opts.validate) {
          var msg = opts.validate(v);
          if (msg) { errEl.textContent = msg; input.focus(); return; }
        }
        close(v);
      }
      function onKey(e) {
        if (e.key === 'Escape') close(input ? null : false);
        if (e.key === 'Enter' && input && document.activeElement === input) { e.preventDefault(); submit(); }
      }
      if (input && opts.validate) {
        input.addEventListener('input', function () { errEl.textContent = ''; });
      }
      wrap.addEventListener('click', function (e) {
        if (e.target === wrap) return close(input ? null : false);
        var act = e.target.getAttribute && e.target.getAttribute('data-act');
        if (act === 'cancel') close(input ? null : false);
        if (act === 'ok') submit();
      });
      document.addEventListener('keydown', onKey);
      (input || okBtn).focus();
      if (input) input.select();
    });
  }

  CDME.modal = {
    confirm: function (opts) { return open(opts); },
    prompt: function (opts) { opts.input = true; return open(opts); }
  };
})(window);
