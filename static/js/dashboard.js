/**
 * OnePay — Dashboard JavaScript
 * Handles: Create Link, Check Status, Transaction History, Settings tabs.
 */

// ── Tab switching ──────────────────────────────────────────────────────────────

function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    const isTarget = panel.id === `panel-${tab}`;
    if (isTarget) {
      panel.classList.remove('hidden');
      // Trigger fade-in by toggling the class
      panel.classList.remove('tab-fade-in');
      void panel.offsetWidth; // force reflow
      panel.classList.add('tab-fade-in');
    } else {
      panel.classList.add('hidden');
      panel.classList.remove('tab-fade-in');
    }
  });
  // Always manage history auto-refresh based on active tab
  if (tab === 'history') {
    loadHistory(currentPage || 1);
    setHistoryAutoRefresh(true);
  } else {
    setHistoryAutoRefresh(false);
  }
}

function enforceMaxAmount(input) {
  const MAX = 100000000;
  let val = parseFloat(input.value);
  if (val > MAX) {
    input.value = MAX;
    showToast('Maximum amount is ₦100,000,000', 'error');
  }
  if (val < 0) input.value = '';
}

const CSRF_TOKEN = window.ONEPAY_CSRF_TOKEN || '';


// ── Toast notifications ────────────────────────────────────────────────────────

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = {
    success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
    error:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    info:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  };
  const iconEl = document.createElement('span');
  iconEl.innerHTML = icons[type] || icons.info;
  const msgEl = document.createElement('span');
  msgEl.textContent = message;
  toast.appendChild(iconEl);
  toast.appendChild(msgEl);
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity .3s';
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// ── Format helpers ─────────────────────────────────────────────────────────────

function fmtAmount(amount, currency = 'NGN') {
  try {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: String(currency).toUpperCase(),
      minimumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${parseFloat(amount).toFixed(2)}`;
  }
}

function fmtNumber(value) {
  // Remove existing commas and parse as number
  const rawValue = value.replace(/,/g, '');
  const num = parseFloat(rawValue);

  // Return empty if not a valid number
  if (isNaN(num) || rawValue === '' || rawValue === '-') {
    return value; // Preserve as-is for partial input
  }

  // Format with commas, preserving decimal places
  const parts = rawValue.split('.');
  const integerPart = parts[0];
  const decimalPart = parts[1];

  // Format integer part with commas
  const formatted = parseInt(integerPart, 10).toLocaleString('en-NG');

  // Reattach decimal part if exists
  if (decimalPart !== undefined) {
    return formatted + '.' + decimalPart;
  }
  return formatted;
}

function formatAmountInput(input) {
  // Get current cursor position
  const cursorPos = input.selectionStart;
  const beforeLength = input.value.length;

  // Get raw value (without commas)
  const rawValue = input.value.replace(/,/g, '');

  // Only format if there's a numeric value
  if (rawValue !== '' && rawValue !== '-') {
    const num = parseFloat(rawValue);
    if (!isNaN(num)) {
      const formatted = fmtNumber(input.value);

      // Only update if formatting changed
      if (formatted !== input.value) {
        input.value = formatted;

        // Adjust cursor position for added/removed commas
        const afterLength = formatted.length;
        const diff = afterLength - beforeLength;

        // Calculate new cursor position
        let newCursorPos = cursorPos + diff;

        // Handle cursor at end or beyond bounds
        if (cursorPos >= beforeLength) {
          newCursorPos = afterLength;
        } else {
          // Clamp to valid range
          newCursorPos = Math.max(0, Math.min(newCursorPos, afterLength));
        }

        // Restore cursor position
        input.setSelectionRange(newCursorPos, newCursorPos);
      }
    }
  }
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-NG', { dateStyle: 'medium', timeStyle: 'short' });
}

function handleAmountInput(input) {
  // Get raw value (strip commas for processing)
  const rawValue = input.value.replace(/,/g, '');

  // Store cursor position relative to raw value
  const cursorPos = input.selectionStart;
  const charsBeforeCursor = input.value.substring(0, cursorPos).replace(/,/g, '').length;

  // Validate: only allow numbers, minus sign, and decimal point
  if (rawValue !== '' && rawValue !== '-' && !/^-?[\d]*\.?[\d]*$/.test(rawValue)) {
    // Invalid character - revert to last valid value
    input.value = input.dataset.lastValid || '';
    const lastValid = input.dataset.lastValid || '';
    const newCursor = Math.min(cursorPos, lastValid.length);
    input.setSelectionRange(newCursor, newCursor);
    return;
  }

  // Parse and validate numeric value
  const numValue = parseFloat(rawValue);

  // Clear if empty or just minus sign
  if (rawValue === '' || rawValue === '-') {
    input.dataset.lastValid = rawValue;
    updateAmountInWords('');
    return;
  }

  // Apply min/max validation
  let validValue = rawValue;
  if (!isNaN(numValue)) {
    if (numValue < 0) {
      validValue = Math.abs(numValue).toString();
      input.value = validValue; // Show positive value
    }
    if (numValue > 100000000) {
      validValue = '100000000';
      input.value = validValue;
    }
    updateAmountInWords(validValue);
  }

  // Format with commas if we have a valid number
  if (!isNaN(numValue) && validValue !== '' && validValue !== '-') {
    const parts = validValue.split('.');
    const intPart = parseInt(parts[0], 10).toLocaleString('en-NG');
    let formatted = parts[1] !== undefined ? intPart + '.' + parts[1] : intPart;

    // Only update if formatted differs
    if (formatted !== input.value) {
      input.value = formatted;

      // Recalculate cursor position
      const newRawCursor = Math.min(charsBeforeCursor, validValue.length);
      let newDisplayCursor = 0;
      let rawCount = 0;

      // Find display position that corresponds to raw cursor
      for (let i = 0; i < formatted.length && rawCount < newRawCursor; i++) {
        if (formatted[i] !== ',') {
          rawCount++;
        }
        newDisplayCursor = i + 1;
      }

      input.setSelectionRange(newDisplayCursor, newDisplayCursor);
    }
  }

  // Save last valid value
  input.dataset.lastValid = input.value;
}

// ── Amount in words ─────────────────────────────────────────────────────────────

function fmtDateShort(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-NG', { dateStyle: 'short', timeStyle: 'short' });
}

// ── Amount to words converter ──────────────────────────────────────────────────

function numberToWords(num) {
  if (num === 0) return 'zero';
  
  const ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
  const tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
  const teens = ['ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
  
  function convertLessThanThousand(n) {
    if (n === 0) return '';
    if (n < 10) return ones[n];
    if (n < 20) return teens[n - 10];
    if (n < 100) {
      const ten = Math.floor(n / 10);
      const one = n % 10;
      return tens[ten] + (one ? ' ' + ones[one] : '');
    }
    const hundred = Math.floor(n / 100);
    const rest = n % 100;
    return ones[hundred] + ' hundred' + (rest ? ' and ' + convertLessThanThousand(rest) : '');
  }
  
  if (num < 1000) return convertLessThanThousand(num);
  if (num < 1000000) {
    const thousands = Math.floor(num / 1000);
    const rest = num % 1000;
    return convertLessThanThousand(thousands) + ' thousand' + (rest ? ' ' + convertLessThanThousand(rest) : '');
  }
  if (num < 1000000000) {
    const millions = Math.floor(num / 1000000);
    const rest = num % 1000000;
    let result = convertLessThanThousand(millions) + ' million';
    if (rest >= 1000) {
      const thousands = Math.floor(rest / 1000);
      const remainder = rest % 1000;
      result += ' ' + convertLessThanThousand(thousands) + ' thousand';
      if (remainder) result += ' ' + convertLessThanThousand(remainder);
    } else if (rest > 0) {
      result += ' ' + convertLessThanThousand(rest);
    }
    return result;
  }
  // Billions
  const billions = Math.floor(num / 1000000000);
  const rest = num % 1000000000;
  let result = convertLessThanThousand(billions) + ' billion';
  if (rest >= 1000000) {
    const millions = Math.floor(rest / 1000000);
    result += ' ' + convertLessThanThousand(millions) + ' million';
  }
  return result;
}

function updateAmountInWords(value) {
  const display = document.getElementById('amount-in-words');
  if (!display) return;
  
  const amount = parseFloat(value);
  if (!value || isNaN(amount) || amount <= 0) {
    display.textContent = '';
    return;
  }
  
  const naira = Math.floor(amount);
  const kobo = Math.round((amount - naira) * 100);
  
  let words = numberToWords(naira) + ' naira';
  if (kobo > 0) {
    words += ' and ' + numberToWords(kobo) + ' kobo';
  }
  
  // Capitalize first letter
  words = words.charAt(0).toUpperCase() + words.slice(1);
  display.textContent = words;
}

// ── Health bar ─────────────────────────────────────────────────────────────────

async function checkHealth() {
  const bar = document.getElementById('health-bar');
  if (!bar) return;
  try {
    const res  = await fetch('/health');
    const data = await res.json();

    if (data.mock_mode) {
      bar.className = 'health-bar mock';
      bar.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             style="width:13px;height:13px;flex-shrink:0">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <strong>Demo mode</strong> — no Quickteller credentials set. Payment will auto-confirm after ~15 seconds.
      `;
    } else {
      bar.className = 'health-bar ok';
      const dot = ok => `<span style="width:7px;height:7px;border-radius:50%;background:${ok ? '#3fb950' : '#e3b341'};display:inline-block;"></span>`;
      bar.innerHTML = `${dot(true)} OnePay v1.0 &nbsp;·&nbsp; ${dot(data.transfer_configured)} ${data.transfer_configured ? 'Transfer ready' : 'Transfer not configured'} &nbsp;·&nbsp; ${dot(data.database === 'ok')} DB`;
    }
  } catch {
    bar.className = 'health-bar error';
    bar.textContent = 'Backend offline';
  }
}

// ── Create payment link ────────────────────────────────────────────────────────

let createdLink = '';

async function createLink(event) {
  event.preventDefault();

  const btn    = document.getElementById('create-btn');
  const amount = document.getElementById('amount').value;
  const normalizedAmount = parseFloat(amount.replace(/,/g, ''));

  if (!CSRF_TOKEN) {
    showToast('Security token missing — please refresh the page.', 'error');
    return;
  }
  if (!normalizedAmount || normalizedAmount <= 0) {
    showToast('Please enter a valid amount', 'error');
    return;
  }
  if (normalizedAmount > 100000000) {
    showToast('Amount cannot exceed ₦100,000,000', 'error');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-sm"></span> Generating…`;

  const body = {
    amount:         normalizedAmount,
    description:    document.getElementById('description').value || null,
    customer_email: document.getElementById('email').value       || null,
    customer_phone: document.getElementById('phone').value       || null,
    return_url:     document.getElementById('return_url').value  || null,
  };

  // Generate a client-side idempotency key so double-clicks don't create duplicates
  const idempotencyKey = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  try {
    const res  = await fetch('/api/payments/link', {
      method:  'POST',
      headers: {
        'Content-Type':    'application/json',
        'X-CSRFToken':     CSRF_TOKEN,
        'X-Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.status === 403 || res.status === 401) {
      showToast('Session expired — please refresh the page.', 'error');
      setTimeout(() => window.location.href = '/login', 2000);
      return;
    }
    if (!res.ok) throw new Error(data.message || 'Failed to create link');

    createdLink = data.payment_url;
    showLinkResult(data);
    showToast('Payment link created!', 'success');
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.textContent = 'Generate Secure Link';
  }
}

function showLinkResult(data) {
  document.getElementById('create-form').classList.add('hidden');

  const panel = document.getElementById('link-result');
  panel.classList.remove('hidden');
  panel.classList.add('fade-in');

  document.getElementById('res-amount').textContent  = fmtAmount(data.amount, data.currency);
  document.getElementById('res-ref').textContent     = data.tx_ref;
  document.getElementById('res-expires').textContent = fmtDate(data.expires_at);
  document.getElementById('res-url').value           = data.payment_url;

  if (data.description) {
    document.getElementById('res-desc-row').classList.remove('hidden');
    document.getElementById('res-desc').textContent = data.description;
  }

  if (data.virtual_account_number) {
    document.getElementById('res-bank-section').classList.remove('hidden');
    document.getElementById('res-bank-name').textContent   = data.virtual_bank_name   || '—';
    document.getElementById('res-bank-acct').textContent   = data.virtual_account_number;
    document.getElementById('res-bank-label').textContent  = data.virtual_account_name || 'OnePay Payment';
    document.getElementById('res-bank-amount').textContent = fmtAmount(data.amount, data.currency);
  }

  // Show QR code status section
  const qrSection = document.getElementById('res-qr-section');
  const vaQrIndicator = document.getElementById('va-qr-indicator');
  
  if (qrSection) {
    qrSection.classList.remove('hidden');
    
    // Show virtual account QR indicator if available
    if (data.virtual_account_number && data.qr_code_virtual_account) {
      vaQrIndicator.classList.remove('hidden');
    } else {
      vaQrIndicator.classList.add('hidden');
    }
  }

  // Start polling for live status updates
  updateLiveStatus('pending');
  startStatusPolling(data.tx_ref);
}

function copyLink() {
  if (!createdLink) return;
  const btn = document.getElementById('copy-btn');
  const icon = btn.querySelector('.material-symbols-outlined');
  const originalText = btn.innerHTML;

  const markOk = () => {
    // Change button appearance
    btn.classList.add('bg-success/20', 'text-success', 'border-success/30');
    btn.classList.remove('bg-primary/10', 'text-primary');
    icon.textContent = 'check_circle';
    icon.style.fontVariationSettings = "'FILL' 1";
    btn.querySelector('span:last-child').textContent = 'Copied!';
    
    showToast('Link copied!', 'success');
    
    // Reset after 2 seconds
    setTimeout(() => {
      btn.classList.remove('bg-success/20', 'text-success', 'border-success/30');
      btn.classList.add('bg-primary/10', 'text-primary');
      icon.textContent = 'content_copy';
      icon.style.fontVariationSettings = '';
      btn.querySelector('span:last-child').textContent = 'Copy';
    }, 2000);
  };

  // navigator.clipboard requires HTTPS or localhost — use fallback for LAN IPs
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(createdLink).then(markOk).catch(() => fallbackCopy());
  } else {
    fallbackCopy();
  }

  function fallbackCopy() {
    const el = document.getElementById('res-url');
    el.select();
    el.setSelectionRange(0, 99999);
    try {
      document.execCommand('copy');
      markOk();
    } catch {
      showToast('Copy failed — select the link manually', 'error');
    }
  }
}

function resetCreate() {
  stopStatusPolling();
  document.getElementById('create-form').reset();
  document.getElementById('create-form').classList.remove('hidden');
  document.getElementById('link-result').classList.add('hidden');
  document.getElementById('res-bank-section').classList.add('hidden');
  document.getElementById('res-desc-row').classList.add('hidden');
  document.getElementById('res-qr-section').classList.add('hidden');

  const btn = document.getElementById('create-btn');
  btn.disabled = false;
  btn.textContent = 'Generate Secure Link';
  createdLink = '';
}

// ── Live status polling after link creation ────────────────────────────────────

let statusPollTimer = null;

function startStatusPolling(txRef) {
  stopStatusPolling();
  statusPollTimer = setInterval(async () => {
    try {
      const res  = await fetch(`/api/payments/status/${encodeURIComponent(txRef)}`);
      const data = await res.json();
      if (!res.ok) return;
      updateLiveStatus(data.status);
      if (data.status === 'verified') {
        // Payment confirmed — refresh performance stats immediately
        loadPerformanceStats();
      }
      if (data.status !== 'pending') stopStatusPolling();
    } catch { /* silent */ }
  }, 5000);
}

function stopStatusPolling() {
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
}

function updateLiveStatus(status) {
  const el = document.getElementById('res-live-status');
  if (!el) return;
  const map = {
    pending:  { cls: 'text-tertiary-fixed-dim', icon: 'schedule',      label: 'Awaiting payment…' },
    verified: { cls: 'text-primary',            icon: 'check_circle',   label: 'Payment confirmed!' },
    expired:  { cls: 'text-outline',            icon: 'timer_off',      label: 'Link expired' },
    failed:   { cls: 'text-error',              icon: 'cancel',         label: 'Payment failed' },
  };
  const m = map[status] || map.pending;
  el.className = `flex items-center gap-2 text-sm font-medium ${m.cls}`;
  el.innerHTML = `<span class="material-symbols-outlined text-base" style="font-variation-settings:'FILL' 1">${m.icon}</span><span>${m.label}</span>`;
}

function extractTxRef(input) {
  const trimmed = input.trim();
  if (!trimmed) return '';
  try {
    const url = new URL(trimmed);
    const segments = url.pathname.split('/').filter(Boolean);
    // Support both /pay/<tx_ref> (new) and /verify/<tx_ref> (legacy)
    const idx = segments.findIndex(s => s === 'pay' || s === 'verify');
    if (idx >= 0 && segments.length > idx + 1) return segments[idx + 1];
  } catch { /* not a URL */ }
  return trimmed;
}

async function checkStatus(event) {
  event.preventDefault();

  const txRef = extractTxRef(document.getElementById('check-ref').value);
  if (!txRef) {
    showToast('Please enter a transaction reference or payment link.', 'error');
    return;
  }

  const btn = document.getElementById('check-btn');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-sm"></span> Checking…`;

  try {
    const res  = await fetch(`/api/payments/status/${encodeURIComponent(txRef)}`);
    const data = await res.json();
    if (res.status === 403 || res.status === 401) {
      showToast('Session expired — please refresh the page.', 'error');
      setTimeout(() => window.location.href = '/login', 2000);
      return;
    }
    if (!res.ok) throw new Error(data.message || 'Transaction not found');
    showStatusResult(data);
  } catch (err) {
    showToast(err.message || 'Could not check transaction', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Check Status';
  }
}

const STATUS_META = {
  pending:  { cls: 'icon-yellow', label: 'Pending'  },
  verified: { cls: 'icon-green',  label: 'Verified' },
  failed:   { cls: 'icon-red',    label: 'Failed'   },
  expired:  { cls: 'icon-gray',   label: 'Expired'  },
};

function showStatusResult(data) {
  document.getElementById('status-form-wrap').classList.add('hidden');

  const panel = document.getElementById('status-result');
  panel.classList.remove('hidden');
  panel.classList.add('fade-in');

  const meta = STATUS_META[data.status] || STATUS_META.pending;
  const icon = document.getElementById('status-icon');
  icon.className = `result-icon ${meta.cls}`;
  icon.innerHTML = statusIcon(data.status);

  document.getElementById('status-label').textContent   = meta.label;
  document.getElementById('status-amount').textContent  = fmtAmount(data.amount, data.currency);
  document.getElementById('status-ref').textContent     = data.tx_ref;
  document.getElementById('status-created').textContent = fmtDate(data.created_at);
  document.getElementById('status-expires').textContent = fmtDate(data.expires_at);
}

function statusIcon(s) {
  if (s === 'verified') return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
  if (s === 'failed' || s === 'expired') return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
}

function resetStatus() {
  document.getElementById('check-form').reset();
  document.getElementById('status-result').classList.add('hidden');
  document.getElementById('status-form-wrap').classList.remove('hidden');
}

// ── Transaction history (paginated) ────────────────────────────────────────────

const STATUS_CONFIG = {
  pending:  { class: 'badge-yellow', label: 'Pending' },
  verified: { class: 'badge-green', label: 'Verified' },
  failed:   { class: 'badge-red', label: 'Failed' },
  expired:  { class: 'badge-gray', label: 'Expired' },
};

let currentPage = 1;
let historyRefreshTimer = null;

function setHistoryAutoRefresh(on) {
  if (on) {
    if (historyRefreshTimer) return;
    historyRefreshTimer = setInterval(() => loadHistory(currentPage, true), 15000);
    return;
  }
  clearInterval(historyRefreshTimer);
  historyRefreshTimer = null;
}

async function loadHistory(page = 1, silent = false) {
  currentPage = page;

  if (!silent) {
    document.getElementById('history-loading').classList.remove('hidden');
    document.getElementById('history-empty').classList.add('hidden');
    document.getElementById('history-table-wrap').classList.add('hidden');
  }

  try {
    const res  = await fetch(`/api/payments/history?page=${page}`);
    
    // Session expired — redirect to login
    if (res.status === 401 || res.status === 403) {
      window.location.href = '/login';
      return;
    }
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'Failed to load');

    const txns = data.transactions || [];
    document.getElementById('history-loading').classList.add('hidden');

    if (txns.length === 0 && page === 1) {
      document.getElementById('history-empty').classList.remove('hidden');
    } else {
      renderHistory(txns);
      renderPagination(data.pagination);
      document.getElementById('history-table-wrap').classList.remove('hidden');
    }
  } catch (err) {
    document.getElementById('history-loading').classList.add('hidden');
    document.getElementById('history-empty').classList.remove('hidden');
    document.getElementById('history-empty').querySelector('p').textContent =
      'Failed to load transactions — ' + err.message;
    if (!silent) showToast('Failed to load history', 'error');
  }
}

function renderHistory(txns) {
  const tbody = document.getElementById('history-tbody');
  tbody.innerHTML = '';
  txns.forEach(t => {
    const tr = document.createElement('tr');
    
    // Date cell
    const dateCell = document.createElement('td');
    dateCell.style.whiteSpace = 'nowrap';
    dateCell.style.color = 'var(--text2)';
    dateCell.textContent = fmtDateShort(t.created_at);
    tr.appendChild(dateCell);
    
    // Amount cell
    const amountCell = document.createElement('td');
    amountCell.style.fontWeight = '600';
    amountCell.textContent = fmtAmount(t.amount, t.currency);
    tr.appendChild(amountCell);
    
    // Description cell
    const descCell = document.createElement('td');
    if (t.description) {
      const descSpan = document.createElement('span');
      descSpan.style.color = 'var(--text)';
      descSpan.textContent = t.description;
      descCell.appendChild(descSpan);
    } else {
      const emptySpan = document.createElement('span');
      emptySpan.style.color = 'var(--text3)';
      emptySpan.textContent = '—';
      descCell.appendChild(emptySpan);
    }
    tr.appendChild(descCell);
    
    // Status badge cell (XSS-safe)
    const statusCell = document.createElement('td');
    const badge = document.createElement('span');
    // Normalize status to lowercase for matching
    const normalizedStatus = (t.status || 'pending').toLowerCase();
    const statusConfig = STATUS_CONFIG[normalizedStatus] || STATUS_CONFIG.pending;
    badge.className = `badge ${statusConfig.class}`;
    badge.textContent = statusConfig.label;
    statusCell.appendChild(badge);
    tr.appendChild(statusCell);
    
    // Reference cell
    const refCell = document.createElement('td');
    refCell.className = 'mono';
    refCell.title = t.tx_ref;
    const refShort = t.tx_ref.slice(-8);
    refCell.textContent = `…${refShort}`;
    tr.appendChild(refCell);
    
    tbody.appendChild(tr);
  });
}

function renderPagination(p) {
  const el = document.getElementById('history-pagination');
  if (!el) return;
  if (p.total_pages <= 1) { el.classList.add('hidden'); return; }

  el.classList.remove('hidden');
  el.innerHTML = '';

  const prev = document.createElement('button');
  prev.className = 'page-btn';
  prev.textContent = '← Prev';
  prev.disabled = !p.has_prev;
  prev.onclick = () => loadHistory(p.page - 1);
  el.appendChild(prev);

  const info = document.createElement('span');
  info.className = 'page-info';
  info.textContent = `Page ${p.page} of ${p.total_pages}`;
  el.appendChild(info);

  const next = document.createElement('button');
  next.className = 'page-btn';
  next.textContent = 'Next →';
  next.disabled = !p.has_next;
  next.onclick = () => loadHistory(p.page + 1);
  el.appendChild(next);
}

function escHtml(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function escUrl(url) {
  if (!url) return '';
  // Validate URL using URL constructor and check protocol and hostname
  try {
    const parsed = new URL(url);
    // Case-insensitive protocol check
    const proto = parsed.protocol.toLowerCase();
    if (proto !== 'http:' && proto !== 'https:') {
      return '';
    }
    // Ensure hostname exists and is not empty
    if (!parsed.hostname || parsed.hostname.length === 0) {
      return '';
    }
    // Additional check for dangerous patterns (case-insensitive)
    const lower = url.toLowerCase();
    if (lower.includes('javascript:') || lower.includes('data:') || lower.includes('vbscript:') || lower.includes('file:')) {
      return '';
    }
    return url;
  } catch {
    // Invalid URL
    return '';
  }
}

// ── Settings ───────────────────────────────────────────────────────────────────

async function saveSettings() {
  const btn = document.getElementById('save-settings-btn');
  const msg = document.getElementById('settings-msg');
  const url = document.getElementById('webhook-url').value.trim();

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-sm"></span> Saving…`;

  try {
    const res  = await fetch('/api/account/settings', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
      body:    JSON.stringify({ webhook_url: url || null }),
    });
    const data = await res.json();
    if (res.status === 403 || res.status === 401) {
      showToast('Session expired — please refresh the page.', 'error');
      setTimeout(() => window.location.href = '/login', 2000);
      return;
    }
    if (!res.ok) throw new Error(data.message || 'Failed to save');

    msg.className = '';
    msg.style.color = '#3fb950';
    msg.textContent = 'Settings saved.';
    msg.classList.remove('hidden');
    showToast('Settings saved!', 'success');
  } catch (err) {
    msg.className = '';
    msg.style.color = '#f85149';
    msg.textContent = err.message;
    msg.classList.remove('hidden');
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save settings';
    setTimeout(() => msg.classList.add('hidden'), 4000);
  }
}

// ── Init ────────────────────────────────────────────────────────────────────────

async function loadPerformanceStats() {
  try {
    const res = await fetch('/api/payments/summary');
    if (!res.ok) {
      console.error('Failed to load stats:', res.status, res.statusText);
      return;
    }
    
    const data = await res.json();
    console.log('API Response:', data);
    
    if (!data.success) {
      console.error('Stats API returned success=false:', data);
      return;
    }
    
    const amount = parseFloat(data.this_month.total_collected);
    const statsEl = document.getElementById('stats-amount');
    
    if (!statsEl) {
      console.error('stats-amount element not found');
      return;
    }
    
    console.log('Performance stats loaded:', amount, 'NGN');
    console.log('Amount >= 1M?', amount >= 1000000);
    
    // Format: if >= 1 million, show as "1.2M", otherwise show full amount
    if (amount >= 1000000) {
      const millions = (amount / 1000000).toFixed(1);
      const formatted = `₦${millions}M`;
      console.log('Formatted as:', formatted);
      statsEl.textContent = formatted;
    } else {
      const formatted = fmtAmount(amount, 'NGN');
      console.log('Formatted as:', formatted);
      statsEl.textContent = formatted;
    }
    
    console.log('Final display value:', statsEl.textContent);
  } catch (err) {
    console.error('Failed to load performance stats:', err);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadPerformanceStats();
  
  // Periodic health re-check every 60 seconds
  setInterval(checkHealth, 60000);
  
  // Refresh stats every 30 seconds
  setInterval(loadPerformanceStats, 30000);

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  const createForm = document.getElementById('create-form');
  if (createForm) createForm.addEventListener('submit', createLink);

  const checkForm = document.getElementById('check-form');
  if (checkForm) checkForm.addEventListener('submit', checkStatus);
});
