'use strict';

const $ = (id) => document.getElementById(id);

function showToast(message, kind = 'info') {
  const toast = $('toast');
  const alert = $('toast-alert');
  alert.className = `alert alert-${kind}`;
  $('toast-msg').textContent = message;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 5000);
}

function collectFlags(scope) {
  const flags = {};
  scope.querySelectorAll('input[data-flag]').forEach((el) => {
    flags[el.dataset.flag] = el.checked;
  });
  return flags;
}

function selectedLanguages() {
  return Array.from($('prefer-lang').selectedOptions).map((o) => o.value);
}

function addCardToGallery(card) {
  const gallery = $('gallery');
  const wrapper = document.createElement('div');
  wrapper.className = 'relative group';

  const src = card.front
    ? `/api/image/front/${encodeURIComponent(card.front)}`
    : null;

  if (src) {
    const img = document.createElement('img');
    img.src = src;
    img.alt = card.name;
    img.loading = 'lazy';
    img.className = 'rounded-lg w-full aspect-[5/7] object-cover shadow cursor-zoom-in';
    wrapper.appendChild(img);

    const backSrc = card.back ? `/api/image/back/${encodeURIComponent(card.back)}` : null;
    wrapper.addEventListener('click', () => openLightbox(card.name, src, backSrc));
  } else {
    const placeholder = document.createElement('div');
    placeholder.className =
      'rounded-lg w-full aspect-[5/7] bg-base-300 flex items-center justify-center text-xs text-center text-error p-1';
    placeholder.textContent = `No art: ${card.name}`;
    wrapper.appendChild(placeholder);
  }

  if (card.quantity > 1) {
    const qty = document.createElement('span');
    qty.className = 'badge badge-sm badge-neutral absolute top-1 right-1';
    qty.textContent = `x${card.quantity}`;
    wrapper.appendChild(qty);
  }

  if (card.back) {
    const back = document.createElement('span');
    back.className = 'badge badge-sm badge-accent absolute bottom-1 left-1';
    back.textContent = '2-sided';
    wrapper.appendChild(back);
  }

  const tip = document.createElement('div');
  tip.className =
    'absolute inset-x-0 bottom-0 bg-base-300/90 text-[10px] leading-tight p-1 rounded-b-lg opacity-0 group-hover:opacity-100 transition truncate';
  tip.textContent = card.name;
  wrapper.appendChild(tip);

  gallery.appendChild(wrapper);
}

function startFetch() {
  const url = $('deck-url').value.trim();
  if (!url) {
    showToast('Please enter a deck URL.', 'warning');
    return;
  }

  const body = {
    url,
    prefer_set: $('prefer-set').value,
    ignore_set: $('ignore-set').value,
    prefer_lang: selectedLanguages(),
    ...collectFlags(document),
  };

  const fetchBtn = $('fetch-btn');
  const status = $('fetch-status');
  fetchBtn.disabled = true;
  fetchBtn.classList.add('btn-disabled');
  status.innerHTML = '<span class="loading loading-spinner loading-sm"></span> Parsing deck…';

  $('gallery').innerHTML = '';
  $('gallery-section').classList.remove('hidden');
  $('card-count').textContent = '0';

  fetch('/api/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.error) throw new Error(data.error);
      streamEvents(data.job_id);
    })
    .catch((err) => {
      status.textContent = '';
      resetFetchButton();
      showToast(err.message, 'error');
    });
}

function resetFetchButton() {
  const fetchBtn = $('fetch-btn');
  fetchBtn.disabled = false;
  fetchBtn.classList.remove('btn-disabled');
}

function streamEvents(jobId) {
  const status = $('fetch-status');
  const source = new EventSource(`/api/fetch/${jobId}/events`);
  let unique = 0; // distinct deck entries (one thumbnail each)
  let total = 0; // total copies (sum of quantities)

  const countLabel = () =>
    total === unique ? `${total}` : `${total} total · ${unique} unique`;

  source.addEventListener('log', (e) => {
    const data = JSON.parse(e.data);
    status.innerHTML = `<span class="loading loading-spinner loading-sm"></span> ${data.message}`;
  });

  source.addEventListener('card', (e) => {
    const card = JSON.parse(e.data);
    addCardToGallery(card);
    unique += 1;
    total += Number(card.quantity) || 1;
    $('card-count').textContent = countLabel();
    status.innerHTML = `<span class="loading loading-spinner loading-sm"></span> Fetched ${total} card${total === 1 ? '' : 's'}…`;
  });

  source.addEventListener('error', (e) => {
    // Distinguish a server-sent "error" event (has data) from a connection drop.
    if (e.data) {
      const data = JSON.parse(e.data);
      showToast(data.message, 'error');
    }
  });

  source.addEventListener('done', () => {
    const summary = total === unique ? `${total} cards` : `${total} cards (${unique} unique)`;
    status.textContent = `Done — ${summary} ready for PDF.`;
    source.close();
    resetFetchButton();
  });

  source.onerror = () => {
    // Stream closed (either after 'done' or a network issue).
    source.close();
    resetFetchButton();
  };
}

function generatePdf() {
  const body = {
    card_size: $('card_size').value,
    paper_size: $('paper_size').value,
    registration: $('registration').value,
    specialty: $('specialty').value,
    fit: $('fit').value,
    extend_corners: $('extend_corners').value,
    crop: $('crop').value,
    crop_backs: $('crop_backs').value,
    ppi: $('ppi').value,
    quality: $('quality').value,
    skip: $('skip').value,
    label: $('label').value,
    ...collectFlags(document),
  };

  const pdfBtn = $('pdf-btn');
  const status = $('pdf-status');
  pdfBtn.disabled = true;
  pdfBtn.classList.add('btn-disabled');
  status.innerHTML = '<span class="loading loading-spinner loading-sm"></span> Generating PDF…';

  fetch('/api/generate-pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.error) throw new Error(data.error);
      status.textContent = 'PDF downloaded. Adjust options and generate again, or fetch a new deck.';
      window.location = data.download_url;
      showToast('PDF generated successfully.', 'success');
    })
    .catch((err) => {
      status.textContent = '';
      showToast(err.message, 'error');
    })
    .finally(() => {
      pdfBtn.disabled = false;
      pdfBtn.classList.remove('btn-disabled');
    });
}

// --- Lightbox -------------------------------------------------------------

function makeLightboxImage(src, alt) {
  const img = document.createElement('img');
  img.src = src;
  img.alt = alt;
  img.className = 'max-h-[85vh] max-w-full rounded-lg shadow-2xl object-contain';
  return img;
}

function openLightbox(name, frontSrc, backSrc) {
  const content = $('lightbox-content');
  content.innerHTML = '';
  content.appendChild(makeLightboxImage(frontSrc, name));
  if (backSrc) {
    content.appendChild(makeLightboxImage(backSrc, `${name} (back)`));
  }
  $('lightbox').classList.remove('hidden');
}

function closeLightbox() {
  $('lightbox').classList.add('hidden');
  $('lightbox-content').innerHTML = '';
}

$('lightbox').addEventListener('click', closeLightbox);
$('lightbox-content').addEventListener('click', (e) => e.stopPropagation());
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeLightbox();
});

// --- Persisted options (localStorage) -------------------------------------

const STORAGE_KEY = 'cardMakerOptions';

function storageKeyFor(el) {
  if (el.id === 'deck-url') return null; // deck URL is per-deck, not a preference
  if (el.id) return el.id;
  if (el.dataset.flag) return el.dataset.flag;
  return null; // skip elements like the collapse toggles
}

function persistableElements() {
  return Array.from(document.querySelectorAll('input, select')).filter(storageKeyFor);
}

function saveOptions() {
  const data = {};
  for (const el of persistableElements()) {
    const key = storageKeyFor(el);
    if (el.type === 'checkbox') {
      data[key] = el.checked;
    } else if (el.multiple) {
      data[key] = Array.from(el.selectedOptions).map((o) => o.value);
    } else {
      data[key] = el.value;
    }
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    /* storage unavailable (e.g. private mode) — ignore */
  }
}

function restoreOptions() {
  let data;
  try {
    data = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
  } catch (e) {
    data = null;
  }
  if (!data) return;
  for (const el of persistableElements()) {
    const key = storageKeyFor(el);
    if (!(key in data)) continue;
    const value = data[key];
    if (el.type === 'checkbox') {
      el.checked = Boolean(value);
    } else if (el.multiple && Array.isArray(value)) {
      const chosen = new Set(value);
      Array.from(el.options).forEach((o) => {
        o.selected = chosen.has(o.value);
      });
    } else {
      el.value = value;
    }
  }
}

document.addEventListener('change', saveOptions);

$('fetch-btn').addEventListener('click', startFetch);
$('pdf-btn').addEventListener('click', generatePdf);
$('lightbox-close').addEventListener('click', closeLightbox);

restoreOptions();
