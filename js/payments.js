/**
 * Lagos Updates Directory — Flutterwave Payment Integration
 * Seamless card, USSD, and bank transfer checkout via Flutterwave Inline SDK.
 */

window.FLW_PAYMENT_CONFIG = {
  publicKey: 'FLWPUBK_TEST-907fc3ea1f385d5b0a3bd1c0d725a40d-X',
  currency: 'NGN'
};

// Fetch runtime config from backend if available
(async function initPaymentConfig() {
  try {
    const res = await fetch('/api/payments/config');
    if (res.ok) {
      const data = await res.json();
      if (data.public_key) {
        window.FLW_PAYMENT_CONFIG.publicKey = data.public_key;
      }
      if (data.currency) {
        window.FLW_PAYMENT_CONFIG.currency = data.currency;
      }
    }
  } catch (_) {}
})();

/**
 * Universal Flutterwave Checkout Trigger
 * @param {Object} options
 * @param {number} options.amount - Amount in NGN
 * @param {string} options.title - Modal title (e.g. "Lagos Updates Directory")
 * @param {string} options.description - Item description (e.g. "1-Week Featured Boost")
 * @param {string} options.paymentType - 'submission' | 'boost' | 'renewal'
 * @param {string} options.targetId - submission_id or listing_id
 * @param {Object} options.customer - { email, name, phone }
 * @param {Object} options.metadata - Extra details (e.g. { duration: '1_week', days: 7 })
 * @param {Function} options.onSuccess - Callback on verified success
 * @param {Function} options.onError - Callback on failure
 * @param {Function} options.onClose - Callback on modal close
 */
window.payWithFlutterwave = function (options) {
  const amount = Number(options.amount) || 0;
  const paymentType = options.paymentType || 'submission';
  const targetId = options.targetId || '';
  const customer = options.customer || {};
  const metadata = options.metadata || {};
  const txRef = 'LU-' + paymentType.toUpperCase() + '-' + Date.now() + '-' + Math.floor(Math.random() * 10000);

  if (typeof window.FlutterwaveCheckout !== 'function') {
    alert('Flutterwave payment engine is loading. Please check your internet connection and try again.');
    if (typeof options.onError === 'function') {
      options.onError(new Error('FlutterwaveCheckout not loaded'));
    }
    return;
  }

  // Telemetry: Payment initiated
  if (typeof window.trackEvent === 'function') {
    window.trackEvent('flutterwave_checkout_initiated', {
      payment_type: paymentType,
      target_id: targetId,
      amount: amount,
      currency: window.FLW_PAYMENT_CONFIG.currency,
      tx_ref: txRef
    });
  }

  window.FlutterwaveCheckout({
    public_key: window.FLW_PAYMENT_CONFIG.publicKey,
    tx_ref: txRef,
    amount: amount,
    currency: window.FLW_PAYMENT_CONFIG.currency,
    payment_options: 'card,banktransfer,ussd,account',
    customer: {
      email: customer.email || 'customer@lagosupdates.com',
      phone_number: customer.phone || '08000000000',
      name: customer.name || 'Lagos Updates Patron'
    },
    customizations: {
      title: 'Lagos Updates Directory',
      description: options.description || 'Verified Placement & Visibility Boost',
      logo: window.location.origin + '/img/logo.png'
    },
    callback: async function (response) {
      console.log('[Flutterwave] Callback response:', response);

      // Verify on backend
      try {
        const verifyRes = await fetch('/api/payments/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            transaction_id: response.transaction_id || response.id,
            tx_ref: response.tx_ref || txRef,
            flw_ref: response.flw_ref,
            payment_type: paymentType,
            target_id: targetId,
            expected_amount: amount,
            customer: customer,
            metadata: metadata
          })
        });

        const verifyData = await verifyRes.json();

        if (verifyRes.ok && verifyData.success) {
          if (typeof window.trackEvent === 'function') {
            window.trackEvent('flutterwave_payment_verified', {
              payment_type: paymentType,
              target_id: targetId,
              amount: amount,
              tx_ref: txRef,
              transaction_id: response.transaction_id || response.id
            });
          }

          if (typeof options.onSuccess === 'function') {
            options.onSuccess(verifyData);
          }
        } else {
          const err = new Error(verifyData.error || 'Server verification failed');
          if (typeof options.onError === 'function') {
            options.onError(err);
          } else {
            alert('Payment received but verification flagged an issue: ' + (verifyData.error || 'Please contact support.'));
          }
        }
      } catch (err) {
        console.error('[Payment Verification Error]', err);
        if (typeof options.onError === 'function') {
          options.onError(err);
        } else {
          alert('Network issue verifying your transaction. Our team has recorded your reference: ' + txRef);
        }
      }
    },
    onclose: function () {
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('flutterwave_checkout_dismissed', {
          payment_type: paymentType,
          target_id: targetId,
          amount: amount,
          tx_ref: txRef
        });
      }
      if (typeof options.onClose === 'function') {
        options.onClose();
      }
    }
  });
};
