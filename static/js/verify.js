/**
 * OnePay — Verify Page JavaScript
 *
 * Flow:
 *  1. Page loads → fetch /api/payments/preview/{tx_ref} to show bank details
 *  2. Start countdown timer from expires_at
 *  3. Auto-poll /api/payments/transfer-status/{tx_ref} every 5 seconds
 *  4. When responseCode "00" comes back → show success state
 *  5. On expiry → show expired state
 */

// tx_ref is embedded by Jinja2 in verify.html via window.ONEPAY_TX_REF

const TX_REF   = window.ONEPAY_TX_REF || '';
const POLL_MS  = 5000;   // poll every 5 seconds

let pollTimer     = null;
let countdownTimer = null;
let pollCount     = 0;
const MAX_POLLS   = 60;  // stop after 5 minutes (60 × 5s)

// Restore poll count from sessionStorage to survive page refreshes
const STORAGE_KEY = `onepay_poll_${TX_REF}`;
try {
  const stored = sessionStorage.getItem(STORAGE_KEY);
  if (stored) {
    pollCount = parseInt(stored, 10) || 0;
  }
} catch {
  // sessionStorage not available (private browsing, etc.)
}

// ── State management ──────────────────────────────────────────────────────────

function showState(id) {
  ['state-loading', 'state-details',
   'state-success', 'state-expired', 'state-used', 'state-error', 'state-failed']
    .forEach(s => {
      const el = document.getElementById(s);
      if (el) el.classList.toggle('hidden', s !== id);
    });
}

function showError(title, message) {
  showState('state-error');
  const titleEl = document.getElementById('error-title');
  const msgEl   = document.getElementById('error-msg');
  if (titleEl) titleEl.textContent = title;
  if (msgEl)   msgEl.textContent   = message;
}

// ── Format helpers ─────────────────────────────────────────────────────────────

function fmtAmount(amount, currency = 'NGN') {
  try {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${parseFloat(amount).toFixed(2)}`;
  }
}

// ── Countdown timer ────────────────────────────────────────────────────────────

function startCountdown(expiresAt) {
  const el = document.getElementById('countdown');
  if (!el) return;

  countdownTimer = setInterval(() => {
    const remaining = Math.max(0, Math.floor((new Date(expiresAt) - Date.now()) / 1000));
    const mins = Math.floor(remaining / 60);
    const secs = remaining % 60;
    el.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;

    if (remaining === 0) {
      clearInterval(countdownTimer);
      clearInterval(pollTimer);
      // Brief fade transition before switching to expired state
      const card = document.querySelector('.card');
      if (card) {
        card.style.transition = 'opacity .3s';
        card.style.opacity = '0.6';
        setTimeout(() => {
          card.style.opacity = '1';
          showState('state-expired');
        }, 300);
      } else {
        showState('state-expired');
      }
    }
  }, 1000);
}

// ── Step 1: Load preview ───────────────────────────────────────────────────────

async function loadPreview() {
  showState('state-loading');

  if (window.ONEPAY_LINK_ERROR) {
    showError('Invalid payment link', window.ONEPAY_LINK_ERROR);
    return;
  }

  if (!TX_REF) {
    showError('Invalid payment link', 'Missing transaction reference. Please use the full link from the merchant.');
    return;
  }

  try {
    const res  = await fetch(`/api/payments/preview/${TX_REF}`);
    const data = await res.json();

    if (!res.ok || !data.success) {
      showError('Could not load payment details', data.message || 'Transaction not found.');
      return;
    }

    // Already expired or used — skip straight to that state
    if (data.is_expired) {
      showState('state-expired');
      return;
    }
    if (data.is_used) {
      showState('state-used');
      return;
    }

    // Populate bank transfer details
    const currency = data.currency || 'NGN';
    const detailAmountEl = document.getElementById('detail-amount');
    if (detailAmountEl) detailAmountEl.textContent = fmtAmount(data.amount, currency);

    if (data.description) {
      const descRow = document.getElementById('detail-desc-row');
      const descEl  = document.getElementById('detail-desc');
      if (descRow) descRow.classList.remove('hidden');
      if (descEl)  descEl.textContent = data.description;
    }
    const detailRef = document.getElementById('detail-ref');
    if (detailRef) detailRef.textContent = data.tx_ref;

    if (data.virtual_account_number) {
      const bankSection = document.getElementById('bank-section');
      if (bankSection) bankSection.classList.remove('hidden');
      const bankName   = document.getElementById('bank-name');
      const bankAcct   = document.getElementById('bank-acct');
      const bankLabel  = document.getElementById('bank-label');
      const bankAmount = document.getElementById('bank-amount');
      if (bankName)   bankName.textContent   = data.virtual_bank_name || '—';
      if (bankAcct)   bankAcct.textContent   = data.virtual_account_number;
      if (bankLabel)  bankLabel.textContent  = data.virtual_account_name || 'OnePay';
      if (bankAmount) bankAmount.textContent = fmtAmount(data.amount, currency);
    } else {
      // No virtual account — show a note that transfer is not yet configured
      const noBankNote = document.getElementById('no-bank-note');
      if (noBankNote) noBankNote.classList.remove('hidden');
    }

    // Show QR codes if available
    if (typeof showQRCodes === 'function') {
      showQRCodes(data.qr_code_payment_url, data.qr_code_virtual_account);
    }

    // Show the details panel and start countdown + polling
    showState('state-details');
    startCountdown(data.expires_at);
    startPolling();

    // Show demo banner if running without real credentials
    try {
      const hres  = await fetch('/health');
      const hdata = await hres.json();
      if (hdata.mock_mode) {
        const banner = document.getElementById('demo-banner');
        if (banner) banner.classList.remove('hidden');
      }
    } catch { /* non-fatal */ }

  } catch (err) {
    showError('Could not load payment details', err.message || 'An unexpected error occurred while loading this payment link.');
  }
}

// ── Step 2: Poll for transfer confirmation ────────────────────────────────────

function startPolling() {
  updatePollStatus('Waiting for your transfer…');
  pollTimer = setInterval(poll, POLL_MS);
}

async function poll() {
  pollCount++;
  
  // Persist poll count to sessionStorage
  try {
    sessionStorage.setItem(STORAGE_KEY, pollCount.toString());
  } catch {
    // Ignore storage errors
  }

  // Safety cap — stop polling after MAX_POLLS
  if (pollCount > MAX_POLLS) {
    clearInterval(pollTimer);
    updatePollStatus('');
    // Clear storage when done
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {}
    // Show a "check again" button instead of silently stopping
    const waitEl = document.getElementById('state-waiting');
    if (waitEl) {
      waitEl.innerHTML = `
        <p class="result-sub" style="font-size:.78rem;color:var(--text2)">
          Still waiting for your transfer. Click below to keep checking.
        </p>
        <button class="btn-ghost" style="margin-top:.5rem;max-width:220px"
                onclick="resumePolling()">Check again</button>
      `;
    }
    return;
  }

  try {
    const res  = await fetch(`/api/payments/transfer-status/${TX_REF}`);
    const data = await res.json();

    if (!res.ok) {
      clearInterval(pollTimer);
      clearInterval(countdownTimer);
      showError('Payment confirmation failed', data.message || 'Please try again shortly.');
      return;
    }

    if (data.status === 'confirmed') {
      clearInterval(pollTimer);
      clearInterval(countdownTimer);
      // Clear storage on success
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {}
      showSuccess();
      return;
    }

    if (data.status === 'expired') {
      clearInterval(pollTimer);
      clearInterval(countdownTimer);
      // Clear storage on expiry
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {}
      showState('state-expired');
      return;
    }

    if (data.status === 'used') {
      clearInterval(pollTimer);
      // Clear storage
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {}
      showState('state-used');
      return;
    }

    if (data.status === 'error') {
      // Provider error or temporary issue — stop polling and show an error.
      clearInterval(pollTimer);
      clearInterval(countdownTimer);
      showError('Payment status unavailable', data.message || 'Please try again shortly.');
      return;
    }

    // Still pending — update the poll counter shown to user
    updatePollStatus(`Checking for transfer… (${pollCount})`);

  } catch {
    // Network error — keep polling, don't stop
    updatePollStatus('Checking connection…');
  }
}

function updatePollStatus(msg) {
  const el = document.getElementById('poll-status');
  if (el) el.textContent = msg;
}

// ── Step 3: Success state ──────────────────────────────────────────────────────

function showSuccess() {
  // Move from details → waiting → success
  showState('state-success');

  // Populate success details
  const detailAmount = document.getElementById('detail-amount');
  const successAmount = document.getElementById('success-amount');
  const successRef = document.getElementById('success-ref');
  const successDate = document.getElementById('success-date');
  const successMessage = document.getElementById('success-message');
  
  if (detailAmount && successAmount) {
    const amount = detailAmount.textContent;
    successAmount.textContent = amount;
    if (successMessage) {
      successMessage.innerHTML = `Your transfer of <span class="text-on-surface font-bold">${amount}</span> has been verified successfully.`;
    }
  }
  
  if (successRef) {
    const refEl = document.getElementById('detail-ref');
    successRef.textContent = refEl ? refEl.textContent : TX_REF;
  }
  
  if (successDate) {
    const now = new Date();
    successDate.textContent = now.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  // Redirect to return_url if the page has one
  const returnUrl = document.getElementById('return-url-meta')?.content;
  const cta = document.getElementById('return-url-cta');
  const redirectMsg = document.getElementById('redirect-msg');

  if (returnUrl) {
    if (cta) {
      cta.classList.remove('hidden');
      cta.href = returnUrl;
    }
    if (redirectMsg) {
      redirectMsg.innerHTML = '<div class="w-3 h-3 border-2 border-outline-variant border-t-primary rounded-full animate-spin"></div><span class="text-xs text-outline font-medium">Redirecting in 5 seconds...</span>';
    }
    setTimeout(() => { window.location.href = returnUrl; }, 5000);
    return;
  }

  if (redirectMsg) {
    redirectMsg.innerHTML = '<span class="text-xs text-outline font-medium">Payment confirmed. The merchant will update your payment status shortly.</span>';
  }
  if (cta) {
    cta.classList.add('hidden');
  }
}

// ── Resume polling after cap ───────────────────────────────────────────────────

function resumePolling() {
  // Clear any existing timer before starting fresh
  if (pollTimer) clearInterval(pollTimer);
  pollCount = 0;
  // Clear storage and start fresh
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {}
  const waitEl = document.getElementById('state-waiting');
  if (waitEl) {
    waitEl.innerHTML = `
      <div class="polling-status">
        <div class="spinner-poll"></div>
        <span id="poll-status">Waiting for your transfer…</span>
      </div>
      <p class="result-sub" style="font-size:.72rem">
        This page updates automatically once we detect your transfer.
      </p>
    `;
  }
  startPolling();
}

// ── Init ────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', loadPreview);
