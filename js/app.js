/* =========================================
   Lagos Updates Directory — app.js
   Frontend Client & Questionnaire Controller
   Clean Architecture with Production API Integration
   ========================================= */

const CATEGORY_META = {
  hotel:               { label: 'Hotels',            emoji: '🏨' },
  apartment:           { label: 'Apartments',        emoji: '🏢' },
  restaurant:          { label: 'Restaurants',       emoji: '🍽️' },
  lounge:              { label: 'Lounges',           emoji: '🥂' },
  'private-chef':      { label: 'Private Chefs',     emoji: '🧑‍🍳' },
  'personal-security': { label: 'Personal Security', emoji: '🛡️' },
  service:             { label: 'Services',          emoji: '🔧' },
  'airport-pickup':    { label: 'Airport Pickups',   emoji: '✈️' }
};

/* ---- Shared: load listings from REST API (with static fallback) ---- */
async function fetchListings() {
  try {
    const res = await fetch('/api/listings');
    if (res.ok) {
      const data = await res.json();
      if (data && data.listings) return data.listings;
    }
  } catch (err) {
    console.warn('Backend API unavailable, falling back to static JSON:', err);
  }

  // Fallback to static JSON file
  const staticRes = await fetch('/data/listings.json');
  if (!staticRes.ok) throw new Error('Failed to load listings: ' + staticRes.status);
  return staticRes.json();
}

/* ---- Sort: promoted first, then rest ---- */
function sortListings(listings) {
  return [...listings].sort((a, b) => {
    if (a.promoted && !b.promoted) return -1;
    if (!a.promoted && b.promoted) return 1;
    return 0;
  });
}

/* ---- Format Price in Airbnb style ---- */
function formatPriceAirbnb(priceRange, category) {
  if (!priceRange) return '<strong>Price on request</strong>';

  if (priceRange.includes('/')) {
    const parts = priceRange.split('/');
    const main = parts[0].trim();
    const period = parts.slice(1).join('/').trim();
    return `<strong>${main}</strong> <span>/ ${period}</span>`;
  }
  if (priceRange.includes(' avg')) {
    const base = priceRange.replace(' avg', '').trim();
    return `<strong>${base}</strong> <span>/ avg</span>`;
  }
  if (priceRange.includes(' callout')) {
    const base = priceRange.replace(' callout', '').trim();
    return `<strong>${base}</strong> <span>/ callout</span>`;
  }
  if (priceRange.includes(' service')) {
    const base = priceRange.replace(' service', '').trim();
    return `<strong>${base}</strong> <span>/ service</span>`;
  }
  if (priceRange.includes(' session')) {
    const base = priceRange.replace(' session', '').trim();
    return `<strong>${base}</strong> <span>/ session</span>`;
  }
  
  let unit = 'night';
  if (['private-chef', 'personal-security', 'service'].includes(category)) {
    unit = 'day';
  } else if (category === 'restaurant' || category === 'lounge') {
    unit = 'avg spend';
  } else if (category === 'airport-pickup') {
    unit = 'trip';
  }

  return `<strong>${priceRange}</strong> <span>/ ${unit}</span>`;
}

/* ---- Build an Airbnb-style card element ---- */
function buildCard(listing) {
  const meta = CATEGORY_META[listing.category] || { label: listing.category, emoji: '📍' };
  const card = document.createElement('article');
  card.className = 'card';
  card.setAttribute('data-id', listing.id);

  const hasPhoto = Boolean(listing.image);
  card.innerHTML = `
    <div class="card-img">
      ${hasPhoto ? `<img src="${listing.image}" alt="${listing.name}" class="card-img-photo" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">` : ''}
      <span class="card-img-placeholder" style="${hasPhoto ? 'display:none;' : ''}">${meta.emoji}</span>
      <span class="card-category-badge">${meta.label}</span>
      ${listing.promoted ? '<span class="card-promoted-tag"><span>★</span> Featured</span>' : ''}
      ${listing.verified ? '<span class="card-verified-badge">Verified</span>' : ''}
    </div>
    <div class="card-body">
      <div class="card-top-row">
        <div class="card-name">${listing.name}</div>
        <div class="card-rating-clean"><span class="star">★</span> ${listing.rating ? listing.rating.replace(/[^0-9.]/g, '') || '4.9' : '4.9'}</div>
      </div>
      <div class="card-area">${listing.area}, Lagos</div>
      <div class="card-desc-snippet">${listing.description}</div>
      <div class="card-price-row">${formatPriceAirbnb(listing.priceRange, listing.category)}</div>
    </div>
  `;

  card.addEventListener('click', () => {
    if (typeof window.trackEvent === 'function') {
      window.trackEvent('listing_card_clicked', {
        listing_id: listing.id,
        name: listing.name,
        category: listing.category,
        area: listing.area,
        promoted: Boolean(listing.promoted),
        verified: Boolean(listing.verified)
      });
    }
    window.location.href = `listing?id=${listing.id}`;
  });

  return card;
}

/* ---- Custom Category and Neighborhood UI handlers ---- */
window.handleCategoryChange = function(select) {
  const customWrap = document.getElementById('wrap-custom-category');
  if (customWrap) {
    customWrap.style.display = (select.value === 'other') ? 'block' : 'none';
    if (select.value === 'other') {
      const input = document.getElementById('form-custom-category');
      if (input) input.focus();
    }
  }
};

window.handleAreaChange = function(select) {
  const customWrap = document.getElementById('wrap-custom-area');
  if (customWrap) {
    customWrap.style.display = (select.value === 'Other') ? 'block' : 'none';
    if (select.value === 'Other') {
      const input = document.getElementById('form-custom-area');
      if (input) input.focus();
    }
  }
};

/* ========================================
   HOME PAGE (AIRBNB FEED EXPERIENCE)
   ======================================== */
async function initHome() {
  let listings;
  try {
    listings = await fetchListings();
  } catch (e) {
    console.error('Lagos Directory: could not load listings.', e);
    return;
  }

  const grid         = document.getElementById('home-listings-grid');
  const resultsMeta  = document.getElementById('home-results-meta');
  const searchInput  = document.getElementById('home-search-input');
  const areaSelect   = document.getElementById('home-area-select');
  const chipVerified = document.getElementById('chip-verified');
  const chipFeatured = document.getElementById('chip-featured');
  const priceSelect  = document.getElementById('filter-price-select');
  const btnReset     = document.getElementById('btn-reset-filters');
  const catItems     = document.querySelectorAll('.category-scroll-wrap .cat-item');

  let activeCategory = 'all';
  let searchQuery    = '';
  let activeArea     = 'all';
  let activePrice    = 'all';
  let verifiedOnly   = false;
  let featuredOnly   = false;

  function parseNumericPrice(priceStr) {
    if (!priceStr) return 0;
    // Extract first numeric match, e.g. "₦150,000 / night" or "₦45,000 - ₦75,000 avg" -> 45000
    const match = priceStr.match(/(\d[\d,]*)/);
    if (!match) return 0;
    const clean = match[1].replace(/,/g, '');
    return parseInt(clean, 10) || 0;
  }

  function matchesPriceTier(priceStr, tier) {
    if (tier === 'all') return true;
    const num = parseNumericPrice(priceStr);
    if (!num) return true; // Keep flexible for price on request
    if (tier === 'under-50k') return num < 50000;
    if (tier === '50k-150k') return num >= 50000 && num <= 150000;
    if (tier === '150k-300k') return num > 150000 && num <= 300000;
    if (tier === '300k-plus') return num > 300000;
    return true;
  }

  function updateResetButtonVisibility() {
    if (!btnReset) return;
    const isFiltered = activeCategory !== 'all' || activeArea !== 'all' || activePrice !== 'all' || verifiedOnly || featuredOnly || Boolean(searchQuery);
    btnReset.style.display = isFiltered ? 'inline-flex' : 'none';
  }

  function render() {
    updateResetButtonVisibility();
    let filtered = sortListings(listings);

    if (activeCategory !== 'all') {
      filtered = filtered.filter(l => l.category === activeCategory);
    }
    if (activeArea !== 'all') {
      filtered = filtered.filter(l => l.area.toLowerCase().includes(activeArea.toLowerCase()));
    }
    if (verifiedOnly) {
      filtered = filtered.filter(l => l.verified);
    }
    if (featuredOnly) {
      filtered = filtered.filter(l => l.promoted);
    }
    if (activePrice !== 'all') {
      filtered = filtered.filter(l => matchesPriceTier(l.priceRange, activePrice));
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(l =>
        l.name.toLowerCase().includes(q) ||
        l.area.toLowerCase().includes(q) ||
        l.description.toLowerCase().includes(q)
      );
    }

    grid.innerHTML = '';

    if (filtered.length === 0) {
      grid.innerHTML = `
        <div class="no-results">
          <div class="no-results-emoji">🔍</div>
          <h3>No places found in Lagos</h3>
          <p>Try resetting your filters or search for another neighborhood.</p>
        </div>`;
      if (resultsMeta) resultsMeta.innerHTML = 'Showing <strong>0</strong> places';
      return;
    }

    const promoted = filtered.filter(l => l.promoted);
    const regular  = filtered.filter(l => !l.promoted);

    /* --- Featured section --- */
    if (promoted.length > 0) {
      const label = document.createElement('div');
      label.className = 'grid-section-label';
      label.innerHTML = '<span class="star-tag">★</span> Featured in Lagos';
      grid.appendChild(label);
      promoted.forEach(l => grid.appendChild(buildCard(l)));
    }

    /* --- All listings section --- */
    if (regular.length > 0) {
      const label = document.createElement('div');
      label.className = 'grid-section-label regular';
      label.textContent = promoted.length > 0 ? 'All Lagos Listings' : 'Listings';
      grid.appendChild(label);
      regular.forEach(l => grid.appendChild(buildCard(l)));
    }

    if (resultsMeta) {
      resultsMeta.innerHTML = `Showing <strong>${filtered.length}</strong> verified spot${filtered.length !== 1 ? 's' : ''} in Lagos${promoted.length ? ` &nbsp;·&nbsp; <span>${promoted.length} featured</span>` : ''}`;
    }
  }

  /* Category click */
  catItems.forEach(item => {
    item.addEventListener('click', () => {
      catItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      activeCategory = item.dataset.category || 'all';
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('filter_category_selected', { category: activeCategory });
      }
      render();
    });
  });

  /* Capsule Nav Search Bar (Airbnb header) */
  const capsuleKeyword = document.getElementById('capsule-keyword');
  const capsuleArea    = document.getElementById('capsule-area');
  const capsuleBtn     = document.querySelector('.capsule-search-btn');

  function syncCapsuleAndSearch() {
    if (capsuleKeyword && capsuleKeyword.value.trim() !== searchQuery) {
      capsuleKeyword.value = searchQuery;
    }
    if (capsuleArea && activeArea !== 'all' && capsuleArea.value !== activeArea) {
      capsuleArea.value = activeArea;
    }
  }

  if (capsuleKeyword) {
    capsuleKeyword.addEventListener('input', e => {
      searchQuery = e.target.value.trim();
      if (searchInput) searchInput.value = searchQuery;
      render();
      clearTimeout(searchDebounceTimer);
      if (searchQuery.length >= 2) {
        searchDebounceTimer = setTimeout(() => {
          if (typeof window.trackEvent === 'function') {
            window.trackEvent('search_performed', { query: searchQuery, area: activeArea, source: 'nav_capsule' });
          }
        }, 600);
      }
    });

    capsuleKeyword.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (grid) {
          grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  }

  if (capsuleArea) {
    // Populate capsuleArea options if missing
    const existingCapsule = new Set(Array.from(capsuleArea.options).map(o => o.value.toLowerCase()));
    listings.forEach(l => {
      if (l.area && !existingCapsule.has(l.area.toLowerCase())) {
        existingCapsule.add(l.area.toLowerCase());
        const opt = document.createElement('option');
        opt.value = l.area;
        opt.textContent = l.area;
        capsuleArea.appendChild(opt);
      }
    });

    capsuleArea.addEventListener('change', e => {
      activeArea = e.target.value || 'all';
      if (areaSelect) areaSelect.value = activeArea;
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('filter_area_selected', { area: activeArea, source: 'nav_capsule' });
      }
      render();
      if (grid) {
        grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }

  if (capsuleBtn) {
    capsuleBtn.addEventListener('click', e => {
      e.preventDefault();
      if (capsuleKeyword) {
        searchQuery = capsuleKeyword.value.trim();
        if (searchInput) searchInput.value = searchQuery;
      }
      if (capsuleArea) {
        activeArea = capsuleArea.value || 'all';
        if (areaSelect) areaSelect.value = activeArea;
      }
      render();
      if (grid) {
        grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('search_capsule_submitted', { query: searchQuery, area: activeArea });
      }
    });
  }

  /* Search Input */
  let searchDebounceTimer = null;
  if (searchInput) {
    searchInput.addEventListener('input', e => {
      searchQuery = e.target.value.trim();
      render();
      clearTimeout(searchDebounceTimer);
      if (searchQuery.length >= 2) {
        searchDebounceTimer = setTimeout(() => {
          if (typeof window.trackEvent === 'function') {
            window.trackEvent('search_performed', { query: searchQuery, area: activeArea });
          }
        }, 600);
      }
    });
  }

  /* Area Dropdown */
  if (areaSelect) {
    // Dynamically add any unique neighborhoods from listings
    const existingValues = new Set(Array.from(areaSelect.options).map(o => o.value.toLowerCase()));
    listings.forEach(l => {
      if (l.area && !existingValues.has(l.area.toLowerCase())) {
        existingValues.add(l.area.toLowerCase());
        const opt = document.createElement('option');
        opt.value = l.area;
        opt.textContent = l.area;
        areaSelect.appendChild(opt);
      }
    });

    areaSelect.addEventListener('change', e => {
      activeArea = e.target.value;
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('filter_area_selected', { area: activeArea });
      }
      render();
    });
  }

  /* Price Tier Filter */
  if (priceSelect) {
    priceSelect.addEventListener('change', e => {
      activePrice = e.target.value;
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('filter_price_selected', { price_tier: activePrice });
      }
      render();
    });
  }

  /* Verified Filter Chip */
  if (chipVerified) {
    chipVerified.addEventListener('click', () => {
      verifiedOnly = !verifiedOnly;
      chipVerified.classList.toggle('active', verifiedOnly);
      render();
    });
  }

  /* Featured Filter Chip */
  if (chipFeatured) {
    chipFeatured.addEventListener('click', () => {
      featuredOnly = !featuredOnly;
      chipFeatured.classList.toggle('active', featuredOnly);
      render();
    });
  }

  /* Reset Filters Button */
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      activeCategory = 'all';
      searchQuery = '';
      activeArea = 'all';
      activePrice = 'all';
      verifiedOnly = false;
      featuredOnly = false;

      if (searchInput) searchInput.value = '';
      if (areaSelect) areaSelect.value = 'all';
      if (priceSelect) priceSelect.value = 'all';
      if (chipVerified) chipVerified.classList.remove('active');
      if (chipFeatured) chipFeatured.classList.remove('active');
      catItems.forEach(i => i.classList.remove('active'));
      const allCat = document.querySelector('.cat-item[data-category="all"]');
      if (allCat) allCat.classList.add('active');

      render();
    });
  }

  /* Pre-select category if specified in URL */
  const params = new URLSearchParams(window.location.search);
  const catParam = params.get('category');
  if (catParam) {
    const target = document.querySelector(`.cat-item[data-category="${catParam}"]`);
    if (target) {
      target.click();
      return;
    }
  }

  render();
}

/* ========================================
   AIRBNB-STYLE QUESTIONNAIRE MODAL CONTROLLER
   ======================================== */
function initBusinessModal() {
  const backdrop     = document.getElementById('business-modal-backdrop');
  const btnOpen      = document.getElementById('btn-open-list-modal');
  const btnClose     = document.getElementById('btn-close-modal');
  const form         = document.getElementById('business-listing-form');
  const errAlert     = document.getElementById('modal-error-alert');
  const errMsg       = document.getElementById('modal-error-msg');

  if (!backdrop) return;

  const step1        = document.getElementById('modal-step-1');
  const step2        = document.getElementById('modal-step-2');
  const step3        = document.getElementById('modal-step-3');
  const stepSuccess  = document.getElementById('modal-step-success');

  const seg1         = document.getElementById('step-seg-1');
  const seg2         = document.getElementById('step-seg-2');
  const seg3         = document.getElementById('step-seg-3');

  const btnPrev      = document.getElementById('btn-modal-prev');
  const btnNext      = document.getElementById('btn-modal-next');
  const btnSubmit    = document.getElementById('btn-modal-submit');
  const btnDone      = document.getElementById('btn-success-done');
  const footerCtrl   = document.getElementById('modal-footer-controls');

  const cardVerified = document.getElementById('card-plan-verified');
  const cardFeatured = document.getElementById('card-plan-featured');

  let currentStep = 1;
  let selectedPlan = 'verified';
  let uploadedPhotos = []; // stores base64 strings

  const dropZone     = document.getElementById('photo-drop-zone');
  const photosInput  = document.getElementById('form-photos-input');
  const previewGrid  = document.getElementById('photo-preview-grid');

  // Photo Upload & Preview Logic
  if (dropZone && photosInput && previewGrid) {
    dropZone.addEventListener('click', () => photosInput.click());

    dropZone.addEventListener('dragover', e => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      if (e.dataTransfer && e.dataTransfer.files) {
        handleFiles(e.dataTransfer.files);
      }
    });

    photosInput.addEventListener('change', e => {
      if (e.target.files) {
        handleFiles(e.target.files);
      }
    });

    function handleFiles(files) {
      hideError();
      const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
      
      Array.from(files).forEach(file => {
        if (uploadedPhotos.length >= 3) {
          showError('You can upload a maximum of 3 photos.');
          return;
        }
        if (!validTypes.includes(file.type)) {
          showError('Only JPEG, PNG, or WebP images are allowed.');
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          showError('Each photo must be smaller than 5MB.');
          return;
        }

        const reader = new FileReader();
        reader.onload = ev => {
          if (uploadedPhotos.length < 3) {
            uploadedPhotos.push(ev.target.result);
            renderPreviews();
          }
        };
        reader.readAsDataURL(file);
      });
    }

    function renderPreviews() {
      previewGrid.innerHTML = '';
      uploadedPhotos.forEach((src, idx) => {
        const thumb = document.createElement('div');
        thumb.className = 'photo-thumb-card';
        thumb.innerHTML = `
          <img src="${src}" alt="Uploaded preview ${idx + 1}">
          <button type="button" class="photo-thumb-delete" title="Remove photo" data-idx="${idx}">✕</button>
        `;
        thumb.querySelector('.photo-thumb-delete').addEventListener('click', (ev) => {
          ev.stopPropagation();
          uploadedPhotos.splice(idx, 1);
          renderPreviews();
        });
        previewGrid.appendChild(thumb);
      });
    }
  }

  function showError(msg) {
    errMsg.textContent = msg;
    errAlert.style.display = 'flex';
  }

  function hideError() {
    errAlert.style.display = 'none';
  }

  function openModal() {
    backdrop.classList.add('open');
    document.body.style.overflow = 'hidden';
    hideError();
    loadDraft();
    if (typeof window.trackEvent === 'function') {
      window.trackEvent('onboarding_modal_opened', { step: currentStep });
    }
  }

  function closeModal() {
    if (backdrop.classList.contains('open') && typeof window.trackEvent === 'function') {
      window.trackEvent('onboarding_modal_closed', { step_abandoned: currentStep });
    }
    backdrop.classList.remove('open');
    document.body.style.overflow = '';
  }

  // Open triggers
  if (btnOpen) btnOpen.addEventListener('click', openModal);
  if (btnClose) btnClose.addEventListener('click', closeModal);
  if (btnDone) btnDone.addEventListener('click', closeModal);

  // Prevent accidental backdrop dismissals while filling the application:
  // The modal stays open until the user explicitly clicks the ✕ close button or completes registration.

  // Prevent accidental Enter key submissions from closing or prematurely validating step 3
  form.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
      if (currentStep < 3) {
        btnNext.click();
      } else {
        btnSubmit.click();
      }
    }
  });

  // Close on ESC key
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && backdrop.classList.contains('open')) {
      closeModal();
    }
  });

  // Dynamic Plan selection (supports standard verified, 1-week boost, and 1-month featured)
  const allPlanCards = document.querySelectorAll('.plan-selection-grid .plan-card');
  allPlanCards.forEach(card => {
    card.addEventListener('click', () => {
      allPlanCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      selectedPlan = card.dataset.plan || 'verified';
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('onboarding_plan_selected', { plan_tier: selectedPlan });
      }
      saveDraft();
      if (currentStep === 3) {
        updateStepUI();
      }
    });
  });

  function updateStepUI() {
    hideError();
    step1.style.display = currentStep === 1 ? 'block' : 'none';
    step2.style.display = currentStep === 2 ? 'block' : 'none';
    step3.style.display = currentStep === 3 ? 'block' : 'none';

    seg1.className = 'step-segment ' + (currentStep >= 1 ? 'active' : '');
    seg2.className = 'step-segment ' + (currentStep >= 2 ? 'active' : '');
    seg3.className = 'step-segment ' + (currentStep >= 3 ? 'active' : '');

    btnPrev.style.visibility = currentStep > 1 ? 'visible' : 'hidden';

    if (typeof window.trackEvent === 'function') {
      window.trackEvent('onboarding_step_viewed', { step: currentStep });
    }

    if (currentStep === 1) {
      btnNext.style.display = 'inline-flex';
      btnNext.textContent = 'Next: Rates & Socials →';
      btnSubmit.style.display = 'none';
    } else if (currentStep === 2) {
      btnNext.style.display = 'inline-flex';
      btnNext.textContent = 'Next: Owner & Plan →';
      btnSubmit.style.display = 'none';
    } else if (currentStep === 3) {
      btnNext.style.display = 'none';
      btnSubmit.style.display = 'inline-flex';
      let planPrice = '₦30,000';
      if (selectedPlan === 'featured_1w') planPrice = '₦35,000';
      if (selectedPlan === 'featured') planPrice = '₦100,000';
      btnSubmit.textContent = `💳 Pay ${planPrice} with Flutterwave ✓`;
    }
  }

  function validateStep(step) {
    hideError();
    if (step === 1) {
      const name = document.getElementById('form-name').value.trim();
      let cat  = document.getElementById('form-category').value;
      if (cat === 'other') {
        const customCat = (document.getElementById('form-custom-category')?.value || '').trim();
        if (!customCat) { showError('Please type your custom category.'); return false; }
        cat = customCat;
      }

      let area = document.getElementById('form-area').value;
      if (area === 'Other') {
        const customArea = (document.getElementById('form-custom-area')?.value || '').trim();
        if (!customArea) { showError('Please type your neighborhood / area.'); return false; }
        area = customArea;
      }

      const desc = document.getElementById('form-desc').value.trim();

      if (!name) { showError('Please enter your business or brand name.'); return false; }
      if (!cat)  { showError('Please choose or enter a category.'); return false; }
      if (!area) { showError('Please select or enter a neighborhood in Lagos.'); return false; }
      if (!desc || desc.length < 10) { showError('Please provide a short description (at least 10 characters).'); return false; }
      return true;
    }

    if (step === 2) {
      const wa = document.getElementById('form-whatsapp').value.trim();
      if (!wa) { showError('Please provide a valid WhatsApp or phone number.'); return false; }
      return true;
    }

    if (step === 3) {
      const contactName  = document.getElementById('form-contact-name').value.trim();
      const contactEmail = document.getElementById('form-contact-email').value.trim();
      if (!contactName) { showError('Please provide your name.'); return false; }
      if (!contactEmail || !contactEmail.includes('@')) { showError('Please provide a valid contact email.'); return false; }
      return true;
    }

    return true;
  }

  btnNext.addEventListener('click', () => {
    if (validateStep(currentStep)) {
      saveDraft();
      currentStep++;
      updateStepUI();
    }
  });

  btnPrev.addEventListener('click', () => {
    if (currentStep > 1) {
      currentStep--;
      updateStepUI();
    }
  });

  // Local storage auto-save draft
  function saveDraft() {
    try {
      const draft = {
        name: document.getElementById('form-name').value,
        category: document.getElementById('form-category').value,
        area: document.getElementById('form-area').value,
        description: document.getElementById('form-desc').value,
        price: document.getElementById('form-price').value,
        whatsapp: document.getElementById('form-whatsapp').value,
        instagram: document.getElementById('form-instagram').value,
        contactName: document.getElementById('form-contact-name').value,
        contactEmail: document.getElementById('form-contact-email').value,
        plan: selectedPlan
      };
      localStorage.setItem('lagos_listing_draft', JSON.stringify(draft));
    } catch (_) {}
  }

  function loadDraft() {
    try {
      // 1. If vendor is logged in, prefill from vendor profile
      const rawVendor = localStorage.getItem('lagos_vendor_user');
      if (rawVendor) {
        try {
          const v = JSON.parse(rawVendor);
          const emailEl = document.getElementById('form-contact-email');
          const nameEl  = document.getElementById('form-contact-name');
          const waEl    = document.getElementById('form-whatsapp');
          if (emailEl && !emailEl.value && v.email) emailEl.value = v.email;
          if (nameEl && !nameEl.value && v.business_name) nameEl.value = v.business_name;
          if (waEl && !waEl.value && v.whatsapp) waEl.value = v.whatsapp;
        } catch (_) {}
      }

      const raw = localStorage.getItem('lagos_listing_draft');
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (draft.name) document.getElementById('form-name').value = draft.name;
      if (draft.category) document.getElementById('form-category').value = draft.category;
      if (draft.area) document.getElementById('form-area').value = draft.area;
      if (draft.description) document.getElementById('form-desc').value = draft.description;
      if (draft.price) document.getElementById('form-price').value = draft.price;
      if (draft.whatsapp) document.getElementById('form-whatsapp').value = draft.whatsapp;
      if (draft.instagram) document.getElementById('form-instagram').value = draft.instagram;
      if (draft.contactName) document.getElementById('form-contact-name').value = draft.contactName;
      if (draft.contactEmail) document.getElementById('form-contact-email').value = draft.contactEmail;
      if (draft.plan === 'featured') {
        cardFeatured.click();
      }
    } catch (_) {}
  }

  // Submit Handler
  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!validateStep(3)) return;

    btnSubmit.disabled = true;
    btnSubmit.textContent = 'Submitting…';
    hideError();

    const driveLinkEl = document.getElementById('form-drive-link');
    let finalCat = document.getElementById('form-category').value;
    if (finalCat === 'other') {
      const customCat = (document.getElementById('form-custom-category')?.value || '').trim();
      if (customCat) finalCat = customCat;
    }

    let finalArea = document.getElementById('form-area').value;
    if (finalArea === 'Other') {
      const customArea = (document.getElementById('form-custom-area')?.value || '').trim();
      if (customArea) finalArea = customArea;
    }

    const payload = {
      business_name: document.getElementById('form-name').value.trim(),
      category: finalCat,
      area: finalArea,
      description: document.getElementById('form-desc').value.trim(),
      price_range: document.getElementById('form-price').value.trim(),
      whatsapp: document.getElementById('form-whatsapp').value.trim(),
      instagram: document.getElementById('form-instagram').value.trim(),
      drive_link: driveLinkEl ? driveLinkEl.value.trim() : '',
      photos: uploadedPhotos,
      contact_name: document.getElementById('form-contact-name').value.trim(),
      contact_email: document.getElementById('form-contact-email').value.trim(),
      plan_tier: selectedPlan,
      website_url_hp: document.getElementById('form-hp').value // Honeypot
    };

    try {
      const res = await fetch('/api/submissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok) {
        showError(data.error || 'Submission failed. Please check your information and try again.');
        btnSubmit.disabled = false;
        btnSubmit.textContent = 'Submit Application ✓';
        return;
      }

      // Success! Track and clear draft
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('onboarding_submitted', {
          submission_id: data.submission_id,
          business_name: payload.business_name,
          category: payload.category,
          area: payload.area,
          plan_tier: payload.plan_tier,
          has_photos: (payload.photos && payload.photos.length > 0)
        });
      }

      localStorage.removeItem('lagos_listing_draft');
      form.reset();
      uploadedPhotos = [];
      if (previewGrid) previewGrid.innerHTML = '';

      function transitionToSuccess(isPaid, flwTxRef) {
        step1.style.display = 'none';
        step2.style.display = 'none';
        step3.style.display = 'none';
        footerCtrl.style.display = 'none';
        stepSuccess.style.display = 'block';

        const refEl = document.getElementById('success-ref-id');
        if (refEl) refEl.textContent = 'Ref: ' + (data.submission_id ? data.submission_id.slice(0, 8).toUpperCase() : 'LU-REC');

        const payStatusEl = document.getElementById('success-payment-status');
        if (payStatusEl) {
          if (isPaid) {
            payStatusEl.innerHTML = `<span style="color:#008A05;">✓ Flutterwave Payment Confirmed (${flwTxRef || 'Verified'})</span>`;
          } else {
            payStatusEl.innerHTML = `<span style="color:#B45309;">⏳ Payment Pending (Review & Invoice will be sent via WhatsApp)</span>`;
          }
        }
      }

      // Calculate amount for Flutterwave checkout
      let planAmount = 30000;
      let planDesc = 'Standard Verified Placement (₦30,000)';
      if (selectedPlan === 'featured_1w') {
        planAmount = 35000;
        planDesc = '1-Week Boost Placement (₦35,000)';
      } else if (selectedPlan === 'featured') {
        planAmount = 100000;
        planDesc = '1-Month Featured Placement (₦100,000)';
      }

      // Launch Flutterwave popup
      if (typeof window.payWithFlutterwave === 'function') {
        window.payWithFlutterwave({
          amount: planAmount,
          title: 'Lagos Updates Directory',
          description: planDesc,
          paymentType: 'submission',
          targetId: data.submission_id,
          customer: {
            email: payload.contact_email,
            name: payload.contact_name,
            phone: payload.whatsapp
          },
          metadata: {
            business_name: payload.business_name,
            category: payload.category,
            plan_tier: payload.plan_tier
          },
          onSuccess: function (verifyData) {
            transitionToSuccess(true, verifyData.tx_ref);
          },
          onClose: function () {
            transitionToSuccess(false);
          },
          onError: function () {
            transitionToSuccess(false);
          }
        });
      } else {
        transitionToSuccess(false);
      }

    } catch (err) {
      console.error(err);
      showError('Connection error. Please check your internet connection and try again.');
      btnSubmit.disabled = false;
      btnSubmit.textContent = 'Submit Application ✓';
    }
  });

  // Deep-link trigger: #list-business opens the modal immediately
  if (window.location.hash === '#list-business') {
    openModal();
  }
}

/* ========================================
   DIRECTORY PAGE — directory.html
   ======================================== */
async function initDirectory() {
  let listings;
  try {
    listings = await fetchListings();
  } catch (e) {
    console.error(e);
    return;
  }

  const grid        = document.getElementById('listings-grid');
  const resultsMeta = document.getElementById('results-meta');
  const searchInput = document.getElementById('search-input');
  const filterTabs  = document.querySelectorAll('.filter-tab');

  let activeCategory = 'all';
  let searchQuery    = '';

  function render() {
    let filtered = sortListings(listings);
    if (activeCategory !== 'all') {
      filtered = filtered.filter(l => l.category === activeCategory);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(l =>
        l.name.toLowerCase().includes(q) ||
        l.area.toLowerCase().includes(q) ||
        l.description.toLowerCase().includes(q)
      );
    }

    grid.innerHTML = '';
    if (filtered.length === 0) {
      grid.innerHTML = `
        <div class="no-results">
          <div class="no-results-emoji">🔍</div>
          <h3>Nothing found</h3>
          <p>Try a different search</p>
        </div>`;
      if (resultsMeta) resultsMeta.textContent = 'No results';
      return;
    }

    filtered.forEach(l => grid.appendChild(buildCard(l)));
    if (resultsMeta) {
      resultsMeta.innerHTML = `Showing <strong>${filtered.length}</strong> listings`;
    }
  }

  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeCategory = tab.dataset.category;
      render();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', e => {
      searchQuery = e.target.value.trim();
      render();
    });
  }

  const params = new URLSearchParams(window.location.search);
  const catParam = params.get('category');
  if (catParam) {
    const tab = document.querySelector(`.filter-tab[data-category="${catParam}"]`);
    if (tab) { tab.click(); return; }
  }

  render();
}

/* ========================================
   LISTING DETAIL PAGE — listing.html
   ======================================== */
async function initListing() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get('id');
  if (!id) { window.location.href = 'directory'; return; }

  const listings = await fetchListings();
  const listing  = listings.find(l => l.id === id);
  if (!listing)  { window.location.href = 'directory'; return; }

  const meta = CATEGORY_META[listing.category] || { label: listing.category, emoji: '📍' };

  document.title = `${listing.name} — Lagos Updates Directory`;

  const heroImg = document.getElementById('listing-hero-img');
  if (heroImg) {
    if (listing.image) {
      heroImg.innerHTML = `<img src="${listing.image}" alt="${listing.name}" class="listing-hero-photo" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"><span class="listing-hero-emoji" style="display:none;">${meta.emoji}</span>`;
    } else {
      heroImg.innerHTML = `<span class="listing-hero-emoji">${meta.emoji}</span>`;
    }
  }

  const nameEl = document.getElementById('listing-name');
  if (nameEl) nameEl.textContent = listing.name;

  const areaEl = document.getElementById('listing-area');
  if (areaEl) areaEl.textContent = listing.area;

  const priceEl = document.getElementById('listing-price');
  if (priceEl) priceEl.textContent = listing.priceRange;

  const catEl = document.getElementById('listing-category');
  if (catEl) catEl.textContent = meta.label;

  const descEl = document.getElementById('listing-desc');
  if (descEl) descEl.textContent = listing.description;

  const ratingEl = document.getElementById('listing-rating');
  if (ratingEl) ratingEl.textContent = listing.rating;

  // Info Grid Elements
  const areaInfo = document.getElementById('listing-area-info');
  if (areaInfo) areaInfo.textContent = `${listing.area}, Lagos`;

  const priceInfo = document.getElementById('listing-price-info');
  if (priceInfo) priceInfo.textContent = listing.priceRange || 'On Request';

  const catInfo = document.getElementById('listing-category-info');
  if (catInfo) catInfo.textContent = `${meta.emoji} ${meta.label}`;

  const statusInfo = document.getElementById('listing-status-info');
  if (statusInfo) {
    statusInfo.textContent = listing.verified ? '✓ Verified by Lagos Updates' : 'Active Listing';
    statusInfo.style.color = listing.verified ? '#008A05' : 'inherit';
  }

  // Telemetry: track listing view
  if (typeof window.trackEvent === 'function') {
    window.trackEvent('listing_detail_viewed', {
      listing_id: listing.id,
      name: listing.name,
      category: listing.category,
      area: listing.area,
      promoted: Boolean(listing.promoted),
      verified: Boolean(listing.verified)
    });
  }

  const phoneBtn = document.getElementById('btn-phone');
  const waBtn    = document.getElementById('btn-whatsapp');
  const igBtn    = document.getElementById('btn-instagram');

  const waPreFill = encodeURIComponent(`Hello ${listing.name}, I found your business on Lagos Updates Directory and would like to inquire about your availability and rates.`);
  const waDigits = listing.whatsapp ? listing.whatsapp.replace(/[^0-9]/g, '') : '';

  if (phoneBtn) {
    phoneBtn.href = `tel:${listing.phone || listing.whatsapp}`;
    phoneBtn.addEventListener('click', () => {
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('lead_phone_call_clicked', { listing_id: listing.id, name: listing.name });
      }
    });
  }

  if (waBtn) {
    waBtn.href = `https://wa.me/${waDigits}?text=${waPreFill}`;
    waBtn.addEventListener('click', () => {
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('lead_whatsapp_chat_clicked', {
          listing_id: listing.id,
          name: listing.name,
          category: listing.category,
          area: listing.area
        });
      }
    });
  }

  if (igBtn) {
    igBtn.href = `https://instagram.com/${(listing.instagram || '').replace('@', '')}`;
    igBtn.addEventListener('click', () => {
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('lead_instagram_clicked', { listing_id: listing.id, name: listing.name });
      }
    });
  }

  // Viral Sharing (WhatsApp + Copy Link)
  const shareWaBtn = document.getElementById('btn-share-wa');
  if (shareWaBtn) {
    const shareText = encodeURIComponent(`Check out ${listing.name} in ${listing.area}, Lagos on Lagos Updates Directory: ${window.location.href}`);
    shareWaBtn.href = `https://api.whatsapp.com/send?text=${shareText}`;
    shareWaBtn.addEventListener('click', () => {
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('viral_share_whatsapp_clicked', { listing_id: listing.id, name: listing.name });
      }
    });
  }

  const copyBtn = document.getElementById('btn-copy-link');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      if (typeof window.trackEvent === 'function') {
        window.trackEvent('share_link_copied', { listing_id: listing.id });
      }
      navigator.clipboard.writeText(window.location.href).then(() => {
        const orig = copyBtn.textContent;
        copyBtn.textContent = '✓ Copied Link!';
        setTimeout(() => { copyBtn.textContent = orig; }, 2000);
      }).catch(() => {
        prompt('Copy this link:', window.location.href);
      });
    });
  }
}

/* ========================================
   ROUTER & INITIALIZATION
   ======================================== */
function syncVendorNavState() {
  const token = localStorage.getItem('lagos_vendor_token');
  const vendorLinks = document.querySelectorAll('a[href*="vendor.html"], a[href="/vendor"], a[href="vendor"], .nav-vendor-link');
  vendorLinks.forEach(link => {
    if (token) {
      link.innerHTML = '👤 Vendor Dashboard';
      link.href = 'vendor.html';
      link.classList.add('nav-vendor-active');
    } else {
      link.textContent = 'Vendor Login';
      link.href = 'vendor.html';
      link.classList.remove('nav-vendor-active');
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const yr = document.getElementById('footer-year');
  if (yr) yr.textContent = new Date().getFullYear();

  syncVendorNavState();

  const page = document.body.dataset.page;
  if (page === 'home')      initHome();
  if (page === 'directory') initDirectory();
  if (page === 'listing')   initListing();

  initBusinessModal();

  // URL triggers to auto-launch the List Business modal
  function checkUrlModalTrigger() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('action') === 'list_business' || window.location.hash === '#list-modal' || window.location.hash === '#list-business') {
      setTimeout(() => {
        const btn = document.getElementById('btn-open-list-modal');
        if (btn) btn.click();
      }, 150);
    }
  }

  checkUrlModalTrigger();
  window.addEventListener('hashchange', checkUrlModalTrigger);
});
