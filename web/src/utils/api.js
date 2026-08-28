/**
 * FitFuse API client — single module consumed by all components.
 *
 * One flag switches between committed mocks and the live API.
 * Every component consumes this client, never fetch() directly.
 *
 * Owner: Person C
 */

const API_BASE = import.meta.env.VITE_API_BASE || '';
const USE_MOCKS = !API_BASE;

/**
 * Fetch from the API or return mock data.
 */
async function apiFetch(endpoint, options = {}) {
  if (USE_MOCKS) {
    // Load mock data from src/mocks/
    const mockMap = {
      '/api/market': () => import('../mocks/market.json'),
      '/api/assess': () => import('../mocks/assess.json'),
      '/api/offers': () => import('../mocks/offers.json'),
      '/api/clear': () => import('../mocks/clear.json'),
      '/api/settle': () => import('../mocks/settle.json'),
    };
    const loader = mockMap[endpoint];
    if (loader) {
      const mod = await loader();
      // Deep clone the mock to prevent cached object mutation bugs across re-renders
      return JSON.parse(JSON.stringify(mod.default));
    }
    throw new Error(`No mock for ${endpoint}`);
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

export function getMarket() {
  return apiFetch('/api/market');
}

export function assessInvoice(invoiceId, scenario = {}) {
  return apiFetch('/api/assess', {
    method: 'POST',
    body: JSON.stringify({ invoice_id: invoiceId, scenario }),
  });
}

export function getOffers(invoiceId, scenario = {}) {
  return apiFetch('/api/offers', {
    method: 'POST',
    body: JSON.stringify({ invoice_id: invoiceId, scenario }),
  });
}

export function clearMarket(invoiceIds, scenario = {}) {
  return apiFetch('/api/clear', {
    method: 'POST',
    body: JSON.stringify({ invoice_ids: invoiceIds, scenario }),
  });
}

export function settleMatch(matchId, outcome, daysLate = 0, scenario = {}) {
  return apiFetch('/api/settle', {
    method: 'POST',
    body: JSON.stringify({ match_id: matchId, outcome, days_late: daysLate, scenario }),
  });
}
