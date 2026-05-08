// ============================================
// EXCODE Dashboard — Global JS Utilities
// ============================================

// ---- TOAST NOTIFICATIONS ----
const toastIcons = {
    success: 'fa-circle-check',
    error:   'fa-circle-xmark',
    info:    'fa-circle-info',
    warning: 'fa-triangle-exclamation'
};

function showToast(type = 'info', message = '', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fa-solid ${toastIcons[type] || toastIcons.info} toast-icon"></i>
        <span class="toast-msg">${message}</span>
        <i class="fa-solid fa-xmark toast-close" onclick="dismissToast(this.parentElement)"></i>
        <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
    `;

    container.appendChild(toast);

    // Auto-dismiss
    setTimeout(() => dismissToast(toast), duration);
}

function dismissToast(toast) {
    if (!toast || toast.classList.contains('hiding')) return;
    toast.classList.add('hiding');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
}

// ---- CUSTOM MODAL ----
let _modalConfirmCallback = null;

function showModal(opts = {}) {
    const {
        title = 'Confirm Action',
        message = 'Are you sure?',
        confirmText = 'Confirm',
        cancelText = 'Cancel',
        type = 'info',   // 'info', 'danger'
        onConfirm = null
    } = opts;

    const overlay = document.getElementById('modal-overlay');
    if (!overlay) return;

    overlay.querySelector('.modal-icon').className   = `modal-icon ${type === 'danger' ? 'danger' : ''}`;
    overlay.querySelector('.modal-icon i').className = `fa-solid ${type === 'danger' ? 'fa-triangle-exclamation' : 'fa-circle-question'}`;
    document.getElementById('modal-title').textContent   = title;
    document.getElementById('modal-message').textContent = message;
    document.getElementById('modal-confirm-btn').textContent  = confirmText;
    document.getElementById('modal-confirm-btn').className    = `btn ${type === 'danger' ? 'danger' : 'primary'}`;

    _modalConfirmCallback = onConfirm;
    overlay.classList.add('active');
}

function closeModal() {
    const overlay = document.getElementById('modal-overlay');
    if (overlay) overlay.classList.remove('active');
    _modalConfirmCallback = null;
}

function confirmModal() {
    if (typeof _modalConfirmCallback === 'function') {
        _modalConfirmCallback();
    }
    closeModal();
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('modal-overlay');
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });
    }

    // Keyboard ESC to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    // Add ripple to all buttons
    document.querySelectorAll('.btn').forEach(btn => btn.addEventListener('click', ripple));

    // Animate all page elements on load
    initPageAnimations();
});

// ---- RIPPLE EFFECT ----
function ripple(e) {
    const btn = e.currentTarget;
    const circle = document.createElement('span');
    const diameter = Math.max(btn.clientWidth, btn.clientHeight);
    const radius   = diameter / 2;
    const rect     = btn.getBoundingClientRect();

    Object.assign(circle.style, {
        width:    `${diameter}px`,
        height:   `${diameter}px`,
        left:     `${e.clientX - rect.left - radius}px`,
        top:      `${e.clientY - rect.top  - radius}px`,
        position: 'absolute',
        borderRadius: '50%',
        transform: 'scale(0)',
        background: 'rgba(255,255,255,0.2)',
        animation: 'rippleAnim 0.55s ease-out',
        pointerEvents: 'none'
    });

    // Ensure btn has relative positioning
    if (getComputedStyle(btn).position === 'static') btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
    btn.appendChild(circle);
    circle.addEventListener('animationend', () => circle.remove());
}

// Add ripple keyframe dynamically
const rippleStyle = document.createElement('style');
rippleStyle.textContent = `@keyframes rippleAnim { to { transform: scale(4); opacity: 0; } }`;
document.head.appendChild(rippleStyle);

// ---- PAGE ANIMATIONS ----
function initPageAnimations() {
    // Observe elements to animate them on entry
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animationPlayState = 'running';
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.05 });

    document.querySelectorAll('.slide-up, .fade-in, .scale-in').forEach(el => {
        el.style.animationPlayState = 'paused';
        observer.observe(el);
    });
}

// ---- GLOBAL NUMBER COUNTER ANIMATION ----
function animateCount(el, end, duration = 1200) {
    const start = parseInt(el.innerText) || 0;
    if (start === end) { el.innerText = end; return; }
    let startTime = null;
    const step = (ts) => {
        if (!startTime) startTime = ts;
        const progress = Math.min((ts - startTime) / duration, 1);
        el.innerText = Math.floor(progress * (end - start) + start);
        if (progress < 1) requestAnimationFrame(step);
        else el.innerText = end;
    };
    requestAnimationFrame(step);
}

// ---- GLOBAL SEND ACTION (with Modal) ----
function sendAction(action, guildId, extraPayload = {}) {
    if (!guildId) {
        showToast('warning', '⚠️ Please enter a Guild ID first.');
        return;
    }

    fetch('/api/send_action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guild_id: guildId, action, ...extraPayload })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) showToast('success', `Action <b>${action}</b> queued successfully.`);
        else showToast('error', `Failed: ${data.error || 'Unknown error.'}`);
    })
    .catch(err => {
        showToast('error', `Network error: ${err.message}`);
    });
}

// ============================================
// SMART ID INPUT — Recent history + dropdown
// ============================================

const SmartIdInput = (() => {
    const MAX_ENTRIES = 10;
    const STORAGE_KEY = 'excode_recent_ids';

    function _load() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
        catch { return {}; }
    }
    function _save(db) { localStorage.setItem(STORAGE_KEY, JSON.stringify(db)); }

    function saveId(type, id, label = '') {
        if (!id || !id.trim()) return;
        id = id.trim(); label = (label || '').trim();
        const db = _load();
        if (!db[type]) db[type] = [];
        db[type] = db[type].filter(e => e.id !== id);
        db[type].unshift({ id, label, ts: Date.now() });
        db[type] = db[type].slice(0, MAX_ENTRIES);
        _save(db);
    }

    function getIds(type) { return (_load()[type] || []); }

    function removeId(type, id) {
        const db = _load();
        if (db[type]) { db[type] = db[type].filter(e => e.id !== id); _save(db); }
    }

    function updateLabel(type, id, label) {
        const db = _load();
        if (db[type]) {
            const entry = db[type].find(e => e.id === id);
            if (entry && label) { entry.label = label.trim(); _save(db); }
        }
    }

    let _activeDropdown = null;

    function _removeDropdown() {
        if (_activeDropdown) { _activeDropdown.remove(); _activeDropdown = null; }
    }

    function _buildDropdown(input, type) {
        _removeDropdown();
        const entries = getIds(type);
        if (entries.length === 0) return;

        const rect = input.getBoundingClientRect();
        const dd = document.createElement('div');
        dd.className = 'smart-id-dropdown';
        dd.style.cssText = `position:fixed;top:${rect.bottom + 4}px;left:${rect.left}px;width:${Math.max(rect.width, 320)}px;z-index:9999;`;

        dd.innerHTML = `<div class="sid-header"><i class="fa-solid fa-clock-rotate-left"></i> Recent ${type === 'guild' ? 'Servers' : 'Channels'}</div>`;

        entries.forEach(entry => {
            const item = document.createElement('div');
            item.className = 'sid-item';
            item.innerHTML = `
                <div class="sid-item-main">
                    <span class="sid-id">${entry.id}</span>
                    ${entry.label ? `<span class="sid-label">${entry.label}</span>` : ''}
                </div>
                <span class="sid-remove" data-id="${entry.id}" data-type="${type}" title="Remove from history">
                    <i class="fa-solid fa-xmark"></i>
                </span>`;

            item.querySelector('.sid-item-main').addEventListener('mousedown', (e) => {
                e.preventDefault();
                input.value = entry.id;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                _removeDropdown();
            });

            item.querySelector('.sid-remove').addEventListener('mousedown', (e) => {
                e.preventDefault(); e.stopPropagation();
                removeId(type, entry.id);
                item.style.cssText += 'opacity:0;transform:translateX(10px);transition:all 0.2s ease;';
                setTimeout(() => { item.remove(); if (!dd.querySelectorAll('.sid-item').length) _removeDropdown(); }, 200);
            });

            dd.appendChild(item);
        });

        document.body.appendChild(dd);
        _activeDropdown = dd;

        // flip up if below viewport
        requestAnimationFrame(() => {
            const dr = dd.getBoundingClientRect();
            if (dr.bottom > window.innerHeight) dd.style.top = `${rect.top - dr.height - 4}px`;
        });
    }

    function init(input, type) {
        if (!input || input._smartIdInit) return;
        input._smartIdInit = true;
        input.setAttribute('autocomplete', 'off');

        input.addEventListener('focus', () => _buildDropdown(input, type));

        input.addEventListener('input', () => {
            if (_activeDropdown) {
                const q = input.value.toLowerCase();
                _activeDropdown.querySelectorAll('.sid-item').forEach(item => {
                    const id    = item.querySelector('.sid-id')?.textContent || '';
                    const label = item.querySelector('.sid-label')?.textContent || '';
                    item.style.display = (id.includes(q) || label.toLowerCase().includes(q)) ? '' : 'none';
                });
            }
        });

        input.addEventListener('blur', () => setTimeout(_removeDropdown, 150));
    }

    return { init, saveId, getIds, removeId, updateLabel };
})();

// Auto-init inputs that have data-smart-id attribute
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-smart-id]').forEach(input => {
        SmartIdInput.init(input, input.getAttribute('data-smart-id'));
    });
});
