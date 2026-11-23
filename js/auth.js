/* =========================================
   Lagos Updates Directory — auth.js
   Unified Firebase Authentication & Progressive Profiling
   ========================================= */

(function () {
  'use strict';

  const STORAGE_KEY_SESSION = 'lagos_session_token';
  const STORAGE_KEY_USER = 'lagos_auth_user';

  let authConfig = null;
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

  async function initFirebase() {
    try {
      const res = await fetch('/api/auth/config');
      if (res.ok) {
        const data = await res.json();
        authConfig = data;
        if (typeof firebase !== 'undefined' && authConfig.apiKey && !firebase.apps.length) {
          firebase.initializeApp({
            apiKey: authConfig.apiKey,
            authDomain: authConfig.authDomain,
            projectId: authConfig.projectId,
            appId: authConfig.appId
          });
        }
      }
    } catch (e) {
      console.warn('[Auth Config Fetch Failed]:', e);
    }
  }

  async function verifyWithBackend(idToken, extraData = {}) {
    try {
      const res = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_token: idToken,
          email: extraData.email || '',
          display_name: extraData.displayName || '',
          photo_url: extraData.photoURL || ''
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Backend authentication failed.');
      }

      const data = await res.json();
      localStorage.setItem(STORAGE_KEY_SESSION, data.session_token);
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(data.user));
      currentUser = data.user;
      notifyAuthListeners();
      return data;
    } catch (e) {
      console.error('[Verify Error]:', e);
      throw e;
    }
  }

  async function signInWithGoogle() {
    if (typeof firebase !== 'undefined' && firebase.auth) {
      const provider = new firebase.auth.GoogleAuthProvider();
      const result = await firebase.auth().signInWithPopup(provider);
      const idToken = await result.user.getIdToken();
      return verifyWithBackend(idToken, {
        email: result.user.email,
        displayName: result.user.displayName,
        photoURL: result.user.photoURL
      });
    }

    // Fallback prompt for environments without active Firebase SDK credentials
    const email = prompt('Enter your Google Account email for simulation:');
    if (!email) throw new Error('Sign-in cancelled.');
    const mockToken = `mock_token_${btoa(email).replace(/=/g, '')}:${email}:${email.split('@')[0]}`;
    return verifyWithBackend(mockToken, { email, displayName: email.split('@')[0] });
  }

  async function signInWithEmail(email, password) {
    if (typeof firebase !== 'undefined' && firebase.auth && authConfig && authConfig.apiKey) {
      const result = await firebase.auth().signInWithEmailAndPassword(email, password);
      const idToken = await result.user.getIdToken();
      return verifyWithBackend(idToken, {
        email: result.user.email,
        displayName: result.user.displayName || email.split('@')[0]
      });
    }

    // Direct legacy / API fallback
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
    if (typeof firebase !== 'undefined' && firebase.auth && authConfig && authConfig.apiKey) {
      const result = await firebase.auth().createUserWithEmailAndPassword(email, password);
      if (displayName && result.user.updateProfile) {
        await result.user.updateProfile({ displayName });
      }
      const idToken = await result.user.getIdToken();
      return verifyWithBackend(idToken, { email, displayName });
    }

    // Direct registration fallback
    const mockToken = `mock_token_${btoa(email).replace(/=/g, '')}:${email}:${displayName || email.split('@')[0]}`;
    return verifyWithBackend(mockToken, { email, displayName });
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
    if (typeof firebase !== 'undefined' && firebase.auth && firebase.apps.length) {
      try { firebase.auth().signOut(); } catch (e) {}
    }
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
    initFirebase,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    saveVendorProfile,
    signOut,
    getToken,
    getUser,
    onAuthStateChanged
  };

  // Initialize on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFirebase);
  } else {
    initFirebase();
  }
})();
