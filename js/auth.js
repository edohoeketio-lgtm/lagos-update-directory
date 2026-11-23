/* =========================================
   Lagos Updates Directory — auth.js
   Native Supabase & Vendor Authentication
   ========================================= */

(function () {
  'use strict';

  const STORAGE_KEY_SESSION = 'lagos_session_token';
  const STORAGE_KEY_USER = 'lagos_auth_user';
  const SUPABASE_AUTH_URL = 'https://wpfyfommvhopjvwdzjsf.supabase.co/auth/v1';

  let authListeners = [];
  let currentUser = null;

  try {
    const cached = localStorage.getItem(STORAGE_KEY_USER);
    if (cached) currentUser = JSON.parse(cached);
  } catch (e) {
    currentUser = null;
  }

  function notifyAuthListeners() {
    authListeners.forEach(cb => {
      try { cb(currentUser); } catch (err) { console.error('[Auth Listener Error]:', err); }
    });
  }

  // Handle Supabase OAuth callback token in URL hash (e.g. #access_token=...&type=recovery)
  function handleOAuthCallback() {
    const hash = window.location.hash;
    if (hash && hash.includes('access_token=')) {
      const params = new URLSearchParams(hash.substring(1));
      const accessToken = params.get('access_token');
      if (accessToken) {
        try {
          const payloadB64 = accessToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
          const payload = JSON.parse(atob(payloadB64));
          if (payload && payload.email) {
            const u = {
              id: payload.sub || '',
              email: payload.email,
              display_name: (payload.user_metadata && payload.user_metadata.full_name) || payload.email.split('@')[0],
              has_vendor_profile: false
            };
            localStorage.setItem(STORAGE_KEY_SESSION, accessToken);
            localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(u));
            currentUser = u;
            notifyAuthListeners();
            if (window.history && window.history.replaceState) {
              window.history.replaceState(null, '', window.location.pathname + window.location.search);
            }
          }
        } catch (err) {
          console.warn('[Supabase OAuth Callback Error]:', err);
        }
      }
    }
  }

  async function signInWithGoogle() {
    const redirectUrl = encodeURIComponent(window.location.origin + '/vendor.html');
    window.location.href = `${SUPABASE_AUTH_URL}/authorize?provider=google&redirect_to=${redirectUrl}`;
  }

  async function signInWithEmail(email, password) {
    const res = await fetch('/api/vendor/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Login failed.');
    localStorage.setItem(STORAGE_KEY_SESSION, data.token);
    const u = {
      id: data.vendor.id,
      email: data.vendor.email,
      display_name: data.vendor.business_name,
      has_vendor_profile: true,
      vendor_profile: data.vendor
    };
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(u));
    currentUser = u;
    notifyAuthListeners();
    return { success: true, session_token: data.token, user: u };
  }

  async function signUpWithEmail(email, password, displayName = '') {
    const res = await fetch('/api/vendor/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        business_name: displayName || email.split('@')[0],
        email: email,
        password: password,
        whatsapp: ''
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Registration failed.');
    localStorage.setItem(STORAGE_KEY_SESSION, data.token);
    const u = {
      id: data.vendor.id,
      email: data.vendor.email,
      display_name: data.vendor.business_name,
      has_vendor_profile: true,
      vendor_profile: data.vendor
    };
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(u));
    currentUser = u;
    notifyAuthListeners();
    return { success: true, session_token: data.token, user: u };
  }

  async function saveVendorProfile({ business_name, cac_number, whatsapp }) {
    const token = getToken();
    if (!token) throw new Error('You must be signed in to set up a vendor profile.');

    const res = await fetch('/api/vendor/profile', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ business_name, cac_number, whatsapp })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to save vendor profile.');

    if (currentUser) {
      currentUser.has_vendor_profile = true;
      currentUser.vendor_profile = data.vendor_profile;
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(currentUser));
      notifyAuthListeners();
    }
    return data;
  }

  function signOut() {
    localStorage.removeItem(STORAGE_KEY_SESSION);
    localStorage.removeItem(STORAGE_KEY_USER);
    currentUser = null;
    notifyAuthListeners();
  }

  function getToken() {
    return localStorage.getItem(STORAGE_KEY_SESSION) || '';
  }

  function getUser() {
    return currentUser;
  }

  function onAuthStateChanged(cb) {
    if (typeof cb === 'function') {
      authListeners.push(cb);
      cb(currentUser);
    }
  }

  window.LagosAuth = {
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    saveVendorProfile,
    signOut,
    getToken,
    getUser,
    onAuthStateChanged
  };

  // Run callback handler on load
  handleOAuthCallback();
})();
