/**
 * Unit formatting helpers — the ONLY place unit conversion happens.
 *
 * The API sends ₹ lakh (AGENTS.md §3.5). Display conversion to crore,
 * rupee formatting, and percentage display all live here.
 *
 * Owner: Person C
 */

/**
 * Format lakh value as rupees string.
 * 0.17 → "₹16,722" (rough)
 * 10.00 → "₹10.00 lakh"
 */
export function formatLakh(value) {
  if (value === null || value === undefined) return '—';
  if (value >= 100) {
    return `₹${(value / 100).toFixed(2)} cr`;
  }
  return `₹${value.toFixed(2)} lakh`;
}

/**
 * Format lakh as absolute rupees (for costs).
 * 0.17 → "₹17,000"
 */
export function formatRupees(lakhValue) {
  if (lakhValue === null || lakhValue === undefined) return '—';
  const rupees = Math.round(lakhValue * 100000);
  return `₹${rupees.toLocaleString('en-IN')}`;
}

/**
 * Format a decimal fraction as percentage.
 * 0.088 → "8.8%"
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format days to settle.
 * 0 → "Same day"
 * 1 → "1 day"
 * 3 → "3 days"
 */
export function formatDays(days) {
  if (days === 0) return 'Same day';
  if (days === 1) return '1 day';
  return `${days} days`;
}
