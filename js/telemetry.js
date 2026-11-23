/**
 * Lagos Updates Directory — PostHog Telemetry & Event Tracking
 * Tracks pageviews, user interactions, search queries, WhatsApp leads,
 * questionnaire conversion funnels, and vendor actions.
 */

// PostHog Configuration (Configured securely via /api/telemetry/config)
const savedKey = typeof localStorage !== 'undefined' ? localStorage.getItem('lagos_posthog_key') : null;
const savedHost = typeof localStorage !== 'undefined' ? localStorage.getItem('lagos_posthog_host') : null;

window.POSTHOG_CONFIG = {
  apiKey: window.POSTHOG_API_KEY || savedKey || '',
  apiHost: window.POSTHOG_API_HOST || savedHost || 'https://us.i.posthog.com',
  enabled: true
};

// Auto-load telemetry config from backend environment if not hardcoded
if (!window.POSTHOG_CONFIG.apiKey && typeof fetch !== 'undefined') {
  fetch('/api/telemetry/config')
    .then(r => r.json())
    .then(data => {
      if (data && data.api_key && window.setPostHogKey) {
        window.setPostHogKey(data.api_key, data.api_host);
      }
    })
    .catch(() => {});
}

// Initialize PostHog Web Snippet
(function () {
  if (window.posthog) return;
  var ph = (window.posthog = []);
  ph._i = [];
  ph.init = function (apiKey, config, name) {
    function createStub(obj, method) {
      var parts = method.split('.');
      if (parts.length === 2) {
        obj = obj[parts[0]];
        method = parts[1];
      }
      obj[method] = function () {
        obj.push([method].concat(Array.prototype.slice.call(arguments, 0)));
      };
    }
    var stubList = [
      'capture',
      'identify',
      'alias',
      'people.set',
      'people.set_once',
      'set_config',
      'register',
      'register_once',
      'unregister',
      'opt_out_capturing',
      'opt_in_capturing',
      'has_opted_out_capturing',
      'has_opted_in_capturing',
      'clear_opt_in_out_capturing',
      'reset',
      'isFeatureEnabled',
      'onFeatureFlags',
      'getFeatureFlag',
      'getFeatureFlagPayload',
      'reloadFeatureFlags',
      'group'
    ];
    for (var i = 0; i < stubList.length; i++) {
      createStub(ph, stubList[i]);
    }
    ph._i.push([apiKey, config, name]);
  };
  ph.__SV = 1;
  var script = document.createElement('script');
  script.type = 'text/javascript';
  script.async = true;
  script.src = window.POSTHOG_CONFIG.apiHost + '/static/array.js';
  var firstScript = document.getElementsByTagName('script')[0];
  if (firstScript && firstScript.parentNode) {
    firstScript.parentNode.insertBefore(script, firstScript);
  } else if (document.head) {
    document.head.appendChild(script);
  }
})();

// Safely configure and initialize
if (window.posthog && window.POSTHOG_CONFIG.apiKey && window.POSTHOG_CONFIG.apiKey !== 'phc_PLACEHOLDER_KEY') {
  window.posthog.init(window.POSTHOG_CONFIG.apiKey, {
    api_host: window.POSTHOG_CONFIG.apiHost,
    autocapture: true,
    capture_pageview: true,
    capture_pageleave: true,
    session_recording: {
      maskAllInputs: true,
      maskInputOptions: { password: true }
    }
  });
  console.log('[PostHog] Initialized with live Project API Key.');
} else {
  console.info('[PostHog] Running in Dev/Preview mode. Events logged to console. To send to cloud, set window.POSTHOG_API_KEY or call setPostHogKey("your_key").');
}

/**
 * Runtime helper to configure API key directly from browser console
 */
window.setPostHogKey = function (key, host) {
  if (!key) return;
  localStorage.setItem('lagos_posthog_key', key);
  window.POSTHOG_CONFIG.apiKey = key;
  if (host) {
    localStorage.setItem('lagos_posthog_host', host);
    window.POSTHOG_CONFIG.apiHost = host;
  }
  if (window.posthog && typeof window.posthog.init === 'function') {
    window.posthog.init(key, {
      api_host: window.POSTHOG_CONFIG.apiHost,
      autocapture: true,
      capture_pageview: true,
      session_recording: { maskInputOptions: { password: true } }
    });
    console.log('[PostHog] Live key registered and initialized successfully on:', window.POSTHOG_CONFIG.apiHost);
  }
};

/**
 * Universal Event Tracker (Safe wrapper around posthog.capture)
 * @param {string} eventName 
 * @param {object} properties 
 */
window.trackEvent = function (eventName, properties) {
  properties = properties || {};
  properties.platform = 'lagos_updates_directory';
  properties.timestamp = new Date().toISOString();
  properties.page = document.body ? document.body.dataset.page || window.location.pathname : window.location.pathname;

  // Always log to console in dev mode
  console.log(`[PostHog Track] 📊 ${eventName}:`, properties);

  if (window.posthog && typeof window.posthog.capture === 'function' && window.POSTHOG_CONFIG.apiKey !== 'phc_PLACEHOLDER_KEY') {
    try {
      window.posthog.capture(eventName, properties);
    } catch (err) {
      console.warn('[PostHog] Capture error:', err);
    }
  }
};

/**
 * Identify Vendor (associates events with vendor email upon login)
 * @param {string} vendorId 
 * @param {object} traits 
 */
window.identifyVendor = function (vendorId, traits) {
  traits = traits || {};
  console.log(`[PostHog Identify] 👤 Vendor identified:`, vendorId, traits);
  if (window.posthog && typeof window.posthog.identify === 'function' && window.POSTHOG_CONFIG.apiKey !== 'phc_PLACEHOLDER_KEY') {
    try {
      window.posthog.identify(vendorId, traits);
    } catch (err) {
      console.warn('[PostHog] Identify error:', err);
    }
  }
};
