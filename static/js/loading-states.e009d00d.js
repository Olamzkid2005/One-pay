/**
 * OnePay Loading States Utility
 * Prevents double submission and provides visual feedback during form submission.
 * Requirements: 15.1, 15.4
 */

const LoadingStates = {
  // Track submission state per form (Requirement 15.4)
  _submitting: new WeakSet(),

  /**
   * Disable a button and show loading indicator.
   * @param {HTMLButtonElement} btn
   * @param {string} loadingText - Text to show while loading
   */
  disableButton(btn, loadingText = 'Processing...') {
    if (!btn) return;
    btn.disabled = true;
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = `<span class="inline-block animate-spin mr-2">⟳</span>${loadingText}`;
    btn.classList.add('opacity-70', 'cursor-not-allowed');
  },

  /**
   * Re-enable a button and restore original content.
   * @param {HTMLButtonElement} btn
   */
  enableButton(btn) {
    if (!btn) return;
    btn.disabled = false;
    if (btn.dataset.originalText) {
      btn.innerHTML = btn.dataset.originalText;
      delete btn.dataset.originalText;
    }
    btn.classList.remove('opacity-70', 'cursor-not-allowed');
  },

  /**
   * Attach loading state to a form's submit button.
   * Prevents double submission (Requirement 15.4).
   * @param {HTMLFormElement} form
   * @param {object} options
   */
  attachToForm(form, options = {}) {
    if (!form) return;
    const { loadingText = 'Processing...' } = options;

    form.addEventListener('submit', (e) => {
      // Prevent double submission
      if (this._submitting.has(form)) {
        e.preventDefault();
        return;
      }

      const submitBtn = form.querySelector('[type="submit"]');
      this._submitting.add(form);
      this.disableButton(submitBtn, loadingText);

      // For non-AJAX forms, re-enable on page navigation error (Requirement 15.3)
      window.addEventListener('pageshow', () => {
        this._submitting.delete(form);
        this.enableButton(submitBtn);
      }, { once: true });
    });
  },

  /**
   * Wrap an async function with loading state on a button.
   * Re-enables button on error (Requirement 15.3).
   * @param {HTMLButtonElement} btn
   * @param {Function} asyncFn - Async function to execute
   * @param {object} options
   */
  async withLoading(btn, asyncFn, options = {}) {
    const { loadingText = 'Processing...', onSuccess, onError } = options;

    if (btn && btn.disabled) return; // Already in progress

    this.disableButton(btn, loadingText);
    try {
      const result = await asyncFn();
      if (onSuccess) onSuccess(result);
      return result;
    } catch (err) {
      this.enableButton(btn);  // Re-enable on error (Requirement 15.3)
      if (onError) onError(err);
      throw err;
    }
  }
};

// Auto-attach to all forms with data-loading attribute on page load
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-loading]').forEach(form => {
    LoadingStates.attachToForm(form, {
      loadingText: form.dataset.loadingText || 'Processing...'
    });
  });
});
