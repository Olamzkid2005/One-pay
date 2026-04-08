// Password visibility toggle
function togglePassword(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);

    if (input.type === 'password') {
        input.type = 'text';
        icon.textContent = 'visibility';
    } else {
        input.type = 'password';
        icon.textContent = 'visibility_off';
    }
}

// Google OAuth Integration
let googleOAuthConfig = null;
let googleSignInAttempted = false;
let googleSignInAvailable = false;

// Fetch OAuth configuration from backend
async function fetchGoogleOAuthConfig() {
    try {
        const response = await fetch('/auth/google/config');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const config = await response.json();
        return config;
    } catch (error) {
        console.warn('Failed to fetch Google OAuth config:', error.message);
        return { enabled: false, error: 'network_error' };
    }
}

// Check if Google Identity Services is available
function isGoogleGISAvailable() {
    return typeof google !== 'undefined' &&
           google !== null &&
           typeof google.accounts === 'object' &&
           typeof google.accounts.id === 'object';
}

// Check if FedCM is supported (required for One Tap)
function isFedCMSupported() {
    return typeof navigator !== 'undefined' &&
           navigator.credentials &&
           typeof navigator.credentials.get === 'function';
}

// Initialize Google Sign-In with comprehensive error handling
async function initializeGoogleSignIn() {
    // Guard: prevent multiple initialization attempts
    if (googleSignInAttempted) {
        return;
    }
    googleSignInAttempted = true;

    // Guard: Check if GIS script loaded
    if (!isGoogleGISAvailable()) {
        console.log('Google Identity Services not loaded - hiding OAuth UI');
        hideOAuthUI();
        return;
    }

    // Guard: Fetch configuration
    try {
        googleOAuthConfig = await fetchGoogleOAuthConfig();
    } catch (error) {
        console.error('Failed to initialize Google Sign-In:', error.message);
        hideOAuthUI();
        return;
    }

    // Guard: Check if OAuth is enabled
    if (!googleOAuthConfig || !googleOAuthConfig.enabled) {
        console.log('Google OAuth is not configured or disabled');
        hideOAuthUI();
        return;
    }

    // Guard: Validate client_id
    if (!googleOAuthConfig.client_id) {
        console.error('Google OAuth client_id is missing');
        hideOAuthUI();
        return;
    }

    // Show OAuth UI elements
    showOAuthUI();

    try {
        // Initialize Google Identity Services
        google.accounts.id.initialize({
            client_id: googleOAuthConfig.client_id,
            callback: handleGoogleCallback,
            auto_select: false,
            cancel_on_tap_outside: false,
            error_callback: handleGoogleError  // Handle GSI errors
        });

        googleSignInAvailable = true;

        // Skip One Tap / FedCM - use button sign-in directly to avoid FedCM errors
        // FedCM has compatibility issues across browsers and GSI versions
        console.log('Using button sign-in (FedCM/One Tap disabled)');
        renderGoogleButton();
    } catch (error) {
        console.error('Google Sign-In initialization failed:', error.message);
        hideOAuthUI();
    }
}

// Handle Google Identity Services errors
function handleGoogleError(error) {
    console.warn('Google Sign-In error:', error);

    // Common error codes from GSI
    const errorMessages = {
        'idp_pending_initialization': 'Google Sign-In is loading...',
        'opt_out_or_no_account': 'No Google account selected or user opted out',
        'https_required': 'HTTPS is required for Google Sign-In',
        'unknown_client_id': 'Invalid Google OAuth client ID',
        'registration_error': 'Google Sign-In registration failed',
        'network_error': 'Network error - please check your connection',
        'token_result_error': 'Failed to get authentication token'
    };

    const message = errorMessages[error.type] || error.message || 'Google Sign-In unavailable';

    // Show user-friendly message but don't block email/password login
    showOAuthError(message);

    // Always render the button as fallback
    renderGoogleButton();
}

// Show OAuth error message to user
function showOAuthError(message) {
    const errorEl = document.getElementById('oauth-error');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
        // Auto-hide after 5 seconds
        setTimeout(() => errorEl.classList.add('hidden'), 5000);
    }
}

// Show OAuth UI elements
function showOAuthUI() {
    const separator = document.getElementById('oauth-separator');
    const container = document.getElementById('google-signin-container');
    if (separator) separator.classList.remove('hidden');
    if (container) container.classList.remove('hidden');
}

// Hide OAuth UI elements gracefully
function hideOAuthUI() {
    const separator = document.getElementById('oauth-separator');
    const container = document.getElementById('google-signin-container');
    if (separator) separator.classList.add('hidden');
    if (container) container.classList.add('hidden');
}

// Render Google Sign-In button as fallback
function renderGoogleButton() {
    const buttonContainer = document.getElementById('google-signin-button');
    if (!buttonContainer || !isGoogleGISAvailable()) {
        return;
    }

    try {
        google.accounts.id.renderButton(buttonContainer, {
            theme: 'filled_blue',
            size: 'large',
            width: Math.min(400, buttonContainer.offsetWidth || 400),
            text: 'signin_with',
            shape: 'rectangular',
            logo_alignment: 'left'
        });
    } catch (error) {
        console.error('Failed to render Google button:', error.message);
    }
}

// Handle Google OAuth callback
async function handleGoogleCallback(response) {
    console.log('Google callback triggered!', response);
    try {
        // Get CSRF token from page
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;
        console.log('Sending credential to backend...');

        // Send credential to backend
        const result = await fetch('/auth/google/callback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                credential: response.credential,
                csrf_token: csrfToken
            })
        });

        console.log('Backend response status:', result.status);
        const data = await result.json();
        console.log('Backend response data:', data);

        if (data.success) {
            console.log('Success! Redirecting to:', data.redirect_url);
            // Redirect to dashboard
            window.location.href = data.redirect_url;
        } else {
            console.error('Authentication failed:', data.message);
            // Show error message
            showGoogleError(data.message || 'Authentication failed. Please try again.');
        }
    } catch (error) {
        console.error('Google OAuth error:', error);
        showGoogleError('An error occurred. Please try again.');
    }
}

// Show error message for Google OAuth
function showGoogleError(message) {
    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'mt-4 p-4 rounded-xl bg-error-container/10 border border-error/20 text-error';
    errorDiv.innerHTML = `
        <div class="flex items-center gap-2 text-sm">
            <span class="material-symbols-outlined text-lg">error</span>
            <span>${message}</span>
        </div>
    `;

    // Insert after Google Sign-In container
    const container = document.getElementById('google-signin-container');
    container.parentNode.insertBefore(errorDiv, container.nextSibling);

    // Remove after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Initialize Google Sign-In when page loads
// Use load event AND poll for GIS availability since script is async defer
let gisPollInterval = null;

function startGISPolling() {
    if (googleSignInAttempted && googleSignInAvailable) {
        // Already successfully initialized
        return;
    }
    if (googleSignInAttempted && !googleSignInAvailable) {
        // Previous attempt failed - allow retry
        googleSignInAttempted = false;
    }

    // Try to initialize immediately
    initializeGoogleSignIn();

    // If not yet available, poll for up to 10 seconds
    if (!isGoogleGISAvailable()) {
        let pollCount = 0;
        const maxPolls = 100; // 10 seconds worth
        if (gisPollInterval) clearInterval(gisPollInterval);
        gisPollInterval = setInterval(() => {
            pollCount++;
            if (pollCount >= maxPolls) {
                clearInterval(gisPollInterval);
                console.log('GIS polling timeout - Google Sign-In unavailable');
                return;
            }
            if (isGoogleGISAvailable() && !googleSignInAvailable) {
                clearInterval(gisPollInterval);
                initializeGoogleSignIn();
            }
        }, 100);
    }
}

window.addEventListener('load', startGISPolling);

// Apply loading state to login form (Requirements 15.1, 15.2, 15.3)
document.addEventListener('DOMContentLoaded', () => {
  if (typeof LoadingStates === 'undefined') return;
  const loginForm = document.querySelector('form[method="POST"]');
  if (loginForm) {
    LoadingStates.attachToForm(loginForm, { loadingText: 'Signing in...' });
  }
});
