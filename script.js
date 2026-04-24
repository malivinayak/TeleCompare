/**
 * TeleCompare — script.js
 * Vanilla JS · no frameworks · reads data/plans.json
 */

'use strict';

/* ── STATE ───────────────────────────────────────────────── */
const state = {
  allPlans:       [],   // raw plans from JSON
  filteredPlans:  [],   // after filter/sort
  metadata:       {},   // lastUpdated, dataStatus, sourceNote
  comparePlans:   [],   // ids selected for comparison (max 3)
  sortKey:        'price',
  sortAsc:        true,
  activeFilters:  { has5G: false, hasOtt: false, unlimitedCalling: false },
  filterOp:       '',
  filterValidity: '',
  filterBudget:   '',
};

/* ── DOM REFS ────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const finderForm    = $('finder-form');
const recOutput     = $('rec-output');
const plansGrid     = $('plans-grid');
const plansCount    = $('plans-count');
const compareBar    = $('compare-bar');
const compareChips  = $('compare-chips');
const compareHint   = $('compare-hint');
const compareBtn    = $('compare-btn');
const clearCmpBtn   = $('clear-compare-btn');
const modalOverlay  = $('modal-overlay');
const modalBody     = $('modal-body');
const modalClose    = $('modal-close');
const statusDot     = $('status-dot');
const statusText    = $('status-text');

/* ── LOAD ────────────────────────────────────────────────── */
async function loadPlans() {
  try {
    const res = await fetch('data/plans.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    state.allPlans  = (json.plans || []).map(p => calculatePlanMetrics(p));
    state.metadata  = {
      lastUpdated: json.lastUpdated,
      dataStatus:  json.dataStatus  || 'manual',
      sourceNote:  json.sourceNote  || '',
    };
  } catch (err) {
    console.error('Failed to load plans.json:', err);
    state.metadata = { lastUpdated: null, dataStatus: 'fallback', sourceNote: 'Could not load plan data.' };
    showLoadError();
  }
  applyFiltersAndSort();
  updateDataStatus();
  updateHeroStats();
}

/* ── METRIC CALCULATION ──────────────────────────────────── */
function calculatePlanMetrics(plan) {
  const days   = plan.validityDays   || 1;
  const price  = plan.price          || 0;
  const dataGB = plan.totalDataGB    || plan.dataPerDayGB * days || 0;
  return {
    ...plan,
    costPerDay: price / days,
    costPerGB:  dataGB > 0 ? price / dataGB : Infinity,
    hasOtt:     Array.isArray(plan.ottBenefits) && plan.ottBenefits.length > 0,
  };
}

/* ── APPLY FILTERS + SORT ────────────────────────────────── */
function applyFiltersAndSort() {
  let plans = [...state.allPlans];

  if (state.filterOp)       plans = plans.filter(p => p.operator === state.filterOp);
  if (state.filterValidity) {
    const v = parseInt(state.filterValidity);
    plans = plans.filter(p => Math.abs(p.validityDays - v) <= 6);
  }
  if (state.filterBudget)   plans = plans.filter(p => p.price <= parseInt(state.filterBudget));
  if (state.activeFilters.has5G)           plans = plans.filter(p => p.has5G);
  if (state.activeFilters.hasOtt)          plans = plans.filter(p => p.hasOtt);
  if (state.activeFilters.unlimitedCalling)plans = plans.filter(p => p.unlimitedCalling);

  plans = sortPlans(plans);
  state.filteredPlans = plans;
  renderPlans();
  plansCount.textContent = `${plans.length} plan${plans.length !== 1 ? 's' : ''}`;
}

/* ── SORT ────────────────────────────────────────────────── */
function sortPlans(plans) {
  const key = state.sortKey;
  const asc = state.sortAsc;
  return [...plans].sort((a, b) => {
    const va = a[key] ?? Infinity;
    const vb = b[key] ?? Infinity;
    return asc ? va - vb : vb - va;
  });
}

/* ── RENDER PLANS ────────────────────────────────────────── */
function renderPlans() {
  if (!state.filteredPlans.length) {
    plansGrid.innerHTML = `
      <div class="plans-empty" role="listitem">
        <div style="font-size:36px;opacity:.3" aria-hidden="true">🔍</div>
        <p>No plans match your filters. Try broadening your search.</p>
      </div>`;
    return;
  }
  plansGrid.innerHTML = state.filteredPlans.map(renderPlanCard).join('');
  // re-bind compare buttons
  plansGrid.querySelectorAll('.compare-btn').forEach(btn => {
    btn.addEventListener('click', () => toggleComparePlan(btn.dataset.id));
  });
  syncCompareButtons();
}

function renderPlanCard(plan) {
  const selected = state.comparePlans.includes(plan.id);
  const opColor  = operatorColor(plan.operator);
  const tags     = (plan.tags || []).slice(0, 3).map(t => `<span class="tag ${tagClass(t)}">${t}</span>`).join('');
  const ottText  = plan.hasOtt ? `<span>${plan.ottBenefits.slice(0,2).join(', ')}</span>` : '—';
  const note     = plan.notes ? `<div class="plan-card__note">${plan.notes}</div>` : '';

  return `
  <article class="plan-card${selected ? ' compare-selected' : ''}"
    data-op="${plan.operator}" data-id="${plan.id}" role="listitem"
    aria-label="${plan.operator} ₹${plan.price} ${plan.validityDays}-day plan">

    <div class="plan-card__header">
      <div class="plan-card__op">
        <span class="op-dot" data-op="${plan.operator}" aria-hidden="true">${plan.operator.substring(0,2).toUpperCase()}</span>
        <span class="op-name">${plan.operator}</span>
      </div>
      <div class="plan-card__price"><sup>₹</sup>${plan.price}</div>
    </div>

    <div class="plan-card__metrics">
      <div class="plan-metric">
        <div class="plan-metric__val">${plan.validityDays}d</div>
        <div class="plan-metric__label">Validity</div>
      </div>
      <div class="plan-metric">
        <div class="plan-metric__val">${formatData(plan.dataPerDayGB)}</div>
        <div class="plan-metric__label">Data/day</div>
      </div>
      <div class="plan-metric">
        <div class="plan-metric__val">${formatCurrency(plan.costPerDay)}/d</div>
        <div class="plan-metric__label">Cost/day</div>
      </div>
    </div>

    ${tags ? `<div class="plan-card__tags">${tags}</div>` : ''}
    ${note}

    <div class="plan-card__footer">
      <div class="plan-card__benefits">
        OTT: ${ottText}${plan.has5G ? ' · <strong>5G</strong>' : ''}
      </div>
      <button class="compare-btn${selected ? ' selected' : ''}" data-id="${plan.id}"
        aria-pressed="${selected}" aria-label="${selected ? 'Remove from comparison' : 'Add to comparison'}">
        <span class="icon" aria-hidden="true">${selected ? '✓' : '+'}</span>
        ${selected ? 'Added' : 'Compare'}
      </button>
    </div>

  </article>`;
}

/* ── RECOMMENDATION ──────────────────────────────────────── */
function getFinderPrefs() {
  const fd = new FormData(finderForm);
  const ops = fd.getAll('operators');
  return {
    budget:     parseFloat(fd.get('budget')) || Infinity,
    validity:   parseInt(fd.get('validity')) || 0,
    dataNeed:   fd.get('dataNeed')   || '',
    operators:  ops.length ? ops : [],
    need5g:     fd.get('need5g')     || '',
    needOtt:    fd.get('needOtt')    || '',
  };
}

function scorePlan(plan, prefs) {
  let score  = 0;
  const reasons = [];

  // budget fit (high weight)
  if (plan.price <= prefs.budget) {
    score += 30;
    const headroom = prefs.budget - plan.price;
    if (headroom < prefs.budget * 0.2) score += 10; // efficient use of budget
  } else {
    return { score: -Infinity, reasons: [] }; // over budget — disqualify
  }

  // validity preference
  if (prefs.validity) {
    const diff = Math.abs(plan.validityDays - prefs.validity);
    if (diff === 0) { score += 20; reasons.push(`${plan.validityDays}-day validity matches your preference`); }
    else if (diff <= 7) score += 10;
  }

  // data need
  if (prefs.dataNeed === 'low'    && plan.dataPerDayGB <= 1)  { score += 20; reasons.push(`${formatData(plan.dataPerDayGB)}/day suits light data use`); }
  if (prefs.dataNeed === 'medium' && plan.dataPerDayGB >= 1 && plan.dataPerDayGB <= 2) { score += 20; reasons.push(`${formatData(plan.dataPerDayGB)}/day is a solid everyday allowance`); }
  if (prefs.dataNeed === 'high'   && plan.dataPerDayGB >= 2)  { score += 20; reasons.push(`${formatData(plan.dataPerDayGB)}/day handles heavy use`); }
  if (!prefs.dataNeed) score += 5; // neutral

  // cost efficiency (inverted)
  score += Math.max(0, 15 - plan.costPerDay);

  // 5G
  if (prefs.need5g === 'yes'  && plan.has5G)   { score += 15; reasons.push('includes 5G'); }
  if (prefs.need5g === 'yes'  && !plan.has5G)  score -= 20;
  if (prefs.need5g === 'no'   && plan.has5G)   score -= 5;

  // OTT
  if (prefs.needOtt === 'yes' && plan.hasOtt)  { score += 12; reasons.push(`OTT benefits: ${plan.ottBenefits.slice(0,2).join(', ')}`); }
  if (prefs.needOtt === 'yes' && !plan.hasOtt) score -= 15;

  // operator preference
  if (prefs.operators.length && prefs.operators.includes(plan.operator)) {
    score += 10;
    reasons.push(`from your preferred operator ${plan.operator}`);
  }

  // unlimited calling bonus
  if (plan.unlimitedCalling) { score += 5; }

  // cost-per-GB efficiency
  if (plan.costPerGB < 10)  score += 8;
  else if (plan.costPerGB < 20) score += 4;

  return { score, reasons };
}

function renderRecommendation(prefs) {
  const candidates = state.allPlans
    .map(plan => ({ plan, ...scorePlan(plan, prefs) }))
    .filter(r => r.score > -Infinity)
    .sort((a, b) => b.score - a.score);

  if (!candidates.length) {
    recOutput.innerHTML = `
      <div class="rec-empty">
        <div class="rec-empty__icon" aria-hidden="true">😕</div>
        <p>No plans found within your budget of <strong>${formatCurrency(prefs.budget)}</strong>. Try increasing your budget or removing operator filters.</p>
      </div>`;
    return;
  }

  const { plan, reasons } = candidates[0];
  const opColor = operatorColor(plan.operator);
  const tags    = (plan.tags || []).map(t => `<span class="tag ${tagClass(t)}">${t}</span>`).join('');

  // Build explanation sentence
  const budgetPct = prefs.budget < Infinity
    ? ` — that's ${Math.round((1 - plan.price / prefs.budget) * 100)}% under your ₹${prefs.budget} budget`
    : '';
  const whyDefault = `₹${plan.price} for ${plan.validityDays} days${budgetPct}, giving ${formatData(plan.dataPerDayGB)}/day at just ${formatCurrency(plan.costPerDay)}/day`;
  const whyParts   = [whyDefault, ...reasons].filter(Boolean);
  const why        = whyParts.join(' · ');

  recOutput.innerHTML = `
  <div class="rec-card">
    <div class="rec-badge"><span aria-hidden="true">✦</span> Best match</div>
    <div class="rec-header">
      <div class="rec-op-badge" style="background:${opColor}" aria-label="${plan.operator}">
        ${plan.operator.substring(0,2).toUpperCase()}
      </div>
      <div class="rec-title">
        <h3>${plan.operator} Prepaid</h3>
        <div class="rec-price">₹${plan.price}</div>
        <div class="rec-validity">${plan.validityDays} days validity</div>
      </div>
    </div>
    <div class="rec-metrics">
      <div class="rec-metric">
        <div class="rec-metric__val">${formatData(plan.dataPerDayGB)}</div>
        <div class="rec-metric__label">Data / day</div>
      </div>
      <div class="rec-metric">
        <div class="rec-metric__val">${formatData(plan.totalDataGB)}</div>
        <div class="rec-metric__label">Total data</div>
      </div>
      <div class="rec-metric">
        <div class="rec-metric__val">${formatCurrency(plan.costPerDay)}</div>
        <div class="rec-metric__label">Cost / day</div>
      </div>
      <div class="rec-metric">
        <div class="rec-metric__val">${plan.costPerGB < Infinity ? formatCurrency(plan.costPerGB) : '—'}</div>
        <div class="rec-metric__label">Cost / GB</div>
      </div>
      <div class="rec-metric">
        <div class="rec-metric__val">${plan.has5G ? '✓ Yes' : '✗ No'}</div>
        <div class="rec-metric__label">5G</div>
      </div>
      <div class="rec-metric">
        <div class="rec-metric__val">${plan.hasOtt ? '✓ Yes' : '✗ No'}</div>
        <div class="rec-metric__label">OTT</div>
      </div>
    </div>
    <div class="rec-why"><strong>Why this plan?</strong> ${why}.</div>
    <div class="rec-footer">
      <div class="rec-tags">${tags}</div>
      <a href="${plan.sourceUrl}" target="_blank" rel="noopener" class="btn btn-ghost btn-sm">
        Verify on ${plan.operator} ↗
      </a>
    </div>
  </div>`;

  recOutput.scrollIntoView ? null : recOutput.parentElement.scrollTop = recOutput.offsetTop;
  document.getElementById('recommendation').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ── COMPARE ─────────────────────────────────────────────── */
function toggleComparePlan(id) {
  if (state.comparePlans.includes(id)) {
    state.comparePlans = state.comparePlans.filter(x => x !== id);
  } else {
    if (state.comparePlans.length >= 3) {
      // replace oldest
      state.comparePlans.shift();
    }
    state.comparePlans.push(id);
  }
  syncCompareBar();
  syncCompareButtons();
}

function syncCompareButtons() {
  document.querySelectorAll('.compare-btn').forEach(btn => {
    const sel = state.comparePlans.includes(btn.dataset.id);
    btn.classList.toggle('selected', sel);
    btn.setAttribute('aria-pressed', sel);
    btn.innerHTML = `<span class="icon" aria-hidden="true">${sel ? '✓' : '+'}</span>${sel ? 'Added' : 'Compare'}`;
    btn.closest('.plan-card')?.classList.toggle('compare-selected', sel);
  });
}

function syncCompareBar() {
  const count = state.comparePlans.length;
  compareBar.classList.toggle('visible', count > 0);
  compareBtn.disabled = count < 2;

  compareChips.innerHTML = state.comparePlans.map(id => {
    const plan = state.allPlans.find(p => p.id === id);
    if (!plan) return '';
    return `<span class="compare-bar__chip">
      ${plan.operator} ₹${plan.price}
      <button class="remove-btn" data-id="${id}" aria-label="Remove ${plan.operator} ₹${plan.price} from comparison">&times;</button>
    </span>`;
  }).join('');

  compareChips.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', () => toggleComparePlan(btn.dataset.id));
  });

  compareHint.textContent = count < 2 ? `Select ${2 - count} more to compare` : count === 3 ? '3 plans selected (max)' : '';
}

function renderComparison() {
  const plans = state.comparePlans
    .map(id => state.allPlans.find(p => p.id === id))
    .filter(Boolean);

  if (plans.length < 2) return;

  const rows = [
    { label: 'Operator',      key: p => p.operator },
    { label: 'Price',         key: p => `₹${p.price}`,                  cmp: (a,b) => a.price <= b.price },
    { label: 'Validity',      key: p => `${p.validityDays} days`,        cmp: (a,b) => a.validityDays >= b.validityDays },
    { label: 'Data / day',    key: p => formatData(p.dataPerDayGB),      cmp: (a,b) => a.dataPerDayGB >= b.dataPerDayGB },
    { label: 'Total data',    key: p => formatData(p.totalDataGB) },
    { label: 'Cost / day',    key: p => formatCurrency(p.costPerDay),    cmp: (a,b) => a.costPerDay <= b.costPerDay },
    { label: 'Cost / GB',     key: p => p.costPerGB < Infinity ? formatCurrency(p.costPerGB) : '—', cmp: (a,b) => a.costPerGB <= b.costPerGB },
    { label: '5G',            key: p => p.has5G ? '✓ Yes' : '✗ No' },
    { label: 'Unlimited calls',key: p => p.unlimitedCalling ? '✓ Yes' : '✗ No' },
    { label: 'OTT benefits',  key: p => p.hasOtt ? p.ottBenefits.join(', ') : '—' },
    { label: 'SMS / day',     key: p => p.smsPerDay ?? '—' },
  ];

  const headers = plans.map(p => `
    <th class="plan-col-header" scope="col">
      <div class="op-dot" data-op="${p.operator}" aria-hidden="true">${p.operator.substring(0,2).toUpperCase()}</div>
      <div>${p.operator}</div>
      <div class="price">₹${p.price}</div>
    </th>`).join('');

  const bodyRows = rows.map(row => {
    const cells = plans.map((p, i) => {
      const val = row.key(p);
      let best = false;
      if (row.cmp) {
        best = plans.every((other, j) => j === i || row.cmp(p, other));
      }
      return `<td class="${best ? 'best-cell' : ''}">${val}</td>`;
    }).join('');
    return `<tr><th scope="row">${row.label}</th>${cells}</tr>`;
  }).join('');

  modalBody.innerHTML = `
    <p style="font-size:12px;color:var(--ink-3);margin-bottom:var(--sp-4)">
      <span style="color:var(--green);font-weight:700">Green</span> = best value for that metric across selected plans.
    </p>
    <div style="overflow-x:auto">
      <table class="comp-table" aria-label="Plan comparison table">
        <thead><tr><th scope="col"></th>${headers}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>`;

  openModal();
}

/* ── MODAL ───────────────────────────────────────────────── */
function openModal() {
  modalOverlay.classList.add('open');
  document.body.classList.add('modal-open');
  modalClose.focus();
}
function closeModal() {
  modalOverlay.classList.remove('open');
  document.body.classList.remove('modal-open');
}

/* ── STATUS + STATS ──────────────────────────────────────── */
function updateDataStatus() {
  const { dataStatus, lastUpdated, sourceNote } = state.metadata;
  statusDot.className = `status-dot ${dataStatus}`;
  const dateStr = lastUpdated ? formatDate(lastUpdated) : 'unknown date';
  const statusLabel = { fresh: 'Data is fresh', fallback: 'Using cached data (fallback)', manual: 'Manually curated data' }[dataStatus] || dataStatus;
  statusText.textContent = `${statusLabel} · Last updated ${dateStr}`;
}

function updateHeroStats() {
  $('stat-plans').textContent = state.allPlans.length;
  const meta = state.metadata;
  $('stat-updated').textContent = meta.lastUpdated ? formatDate(meta.lastUpdated) : 'N/A';
}

function showLoadError() {
  plansGrid.innerHTML = `
    <div class="plans-empty" role="listitem">
      <div style="font-size:36px;opacity:.3" aria-hidden="true">⚠️</div>
      <p>Could not load plan data. Please check your connection and refresh.</p>
    </div>`;
}

/* ── HELPERS ─────────────────────────────────────────────── */
function formatCurrency(n) {
  if (n == null || !isFinite(n)) return '—';
  return '₹' + n.toFixed(n < 10 ? 1 : 0);
}

function formatData(gb) {
  if (gb == null || gb === 0) return '—';
  if (gb >= 1000) return (gb / 1000).toFixed(1) + ' TB';
  if (gb >= 1)    return gb % 1 === 0 ? gb + ' GB' : gb.toFixed(1) + ' GB';
  return Math.round(gb * 1024) + ' MB';
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return iso; }
}

function operatorColor(op) {
  return { Jio: 'oklch(52% 0.20 25)', Airtel: 'oklch(52% 0.20 30)', Vi: 'oklch(52% 0.20 305)', BSNL: 'oklch(52% 0.18 155)' }[op] || 'var(--accent)';
}

function tagClass(tag) {
  if (tag === '5G') return 'tag-5g';
  if (tag === 'OTT' || tag.includes('OTT')) return 'tag-ott';
  if (tag === 'Budget' || tag === 'Cheapest') return 'tag-budget';
  return '';
}

/* ── EVENT WIRING ────────────────────────────────────────── */
function wireEvents() {
  // Finder form submit
  finderForm.addEventListener('submit', e => {
    e.preventDefault();
    const prefs = getFinderPrefs();
    renderRecommendation(prefs);
    document.getElementById('recommendation').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // Reset finder
  $('reset-btn').addEventListener('click', () => {
    finderForm.reset();
    recOutput.innerHTML = `
      <div class="rec-empty">
        <div class="rec-empty__icon" aria-hidden="true">🎯</div>
        <p>Fill in your needs above and hit <strong>Find my plan</strong> to get a personalised recommendation.</p>
      </div>`;
  });

  // Sort buttons
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (state.sortKey === btn.dataset.sort) {
        state.sortAsc = !state.sortAsc;
      } else {
        state.sortKey = btn.dataset.sort;
        state.sortAsc = true;
      }
      document.querySelectorAll('.sort-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.sort === state.sortKey);
        if (b.dataset.sort === state.sortKey) {
          b.querySelector('.sort-arrow').textContent = state.sortAsc ? '↑' : '↓';
        } else {
          b.querySelector('.sort-arrow') && (b.querySelector('.sort-arrow').textContent = '');
        }
      });
      applyFiltersAndSort();
    });
  });

  // Filter chips
  document.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const key = chip.dataset.filter;
      state.activeFilters[key] = !state.activeFilters[key];
      chip.classList.toggle('active', state.activeFilters[key]);
      chip.setAttribute('aria-pressed', state.activeFilters[key]);
      applyFiltersAndSort();
    });
  });

  // Operator filter
  $('filter-op').addEventListener('change', e => {
    state.filterOp = e.target.value;
    applyFiltersAndSort();
  });

  // Validity filter
  $('filter-validity').addEventListener('change', e => {
    state.filterValidity = e.target.value;
    applyFiltersAndSort();
  });

  // Budget filter
  $('filter-budget').addEventListener('change', e => {
    state.filterBudget = e.target.value;
    applyFiltersAndSort();
  });

  // Compare bar
  compareBtn.addEventListener('click', renderComparison);
  clearCmpBtn.addEventListener('click', () => {
    state.comparePlans = [];
    syncCompareBar();
    syncCompareButtons();
  });

  // Modal close
  modalClose.addEventListener('click', closeModal);
  modalOverlay.addEventListener('click', e => { if (e.target === modalOverlay) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

/* ── INIT ────────────────────────────────────────────────── */
wireEvents();
loadPlans();
