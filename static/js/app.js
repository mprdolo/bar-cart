/* ===========================
   Bar Cart — Shared Utilities
   =========================== */

window.BarCart = (function () {
    'use strict';

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    async function api(url, method, body) {
        method = method || 'GET';
        const opts = { method };
        if (body !== undefined && body !== null) {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(body);
        }
        const resp = await fetch(url, opts);
        const data = await resp.json();
        if (!resp.ok || !data.success) {
            throw new Error(data.message || 'Request failed (' + resp.status + ')');
        }
        return data;
    }

    function showToast(message, isError) {
        const container = $('#toast-container');
        if (!container) return;
        const el = document.createElement('div');
        el.className = 'toast' + (isError ? ' error' : '');
        el.textContent = message;
        container.appendChild(el);
        setTimeout(function () {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.3s';
            setTimeout(function () { el.remove(); }, 300);
        }, 3000);
    }

    return { $: $, $$: $$, api: api, showToast: showToast };
})();
