import { motion, AnimatePresence } from 'framer-motion';
import { formatLakh, formatPercent } from '../utils/format.js';

export default function ProviderPanel({ providers = [], eligibility = [] }) {
  if (!providers || !providers.length) {
    return (
      <div className="card" style={{ padding: 'var(--space-2xl)', textAlign: 'center', color: 'var(--text-muted)' }}>
        No providers available in the market.
      </div>
    );
  }

  const elList = eligibility || [];
  // Merge the provider data with their eligibility status
  const providerState = providers.map(p => {
    const el = elList.find(e => e.provider_id === p.provider_id);
    return {
      ...p,
      eligible: el?.eligible ?? false,
      max_fundable_lakh: el?.max_fundable_lakh ?? 0,
      exclusion_reason: el?.exclusion_reason ?? null
    };
  });

  // Sort: eligible first, then by name
  providerState.sort((a, b) => {
    if (a.eligible !== b.eligible) return b.eligible ? 1 : -1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="provider-panel" style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--space-md)' }}>
      <AnimatePresence>
        {providerState.map((provider) => (
          <ProviderRow key={provider.provider_id} provider={provider} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function ProviderRow({ provider }) {
  const { name, type, total_portfolio_lakh, available_liquidity_lakh, risk_appetite, eligible, max_fundable_lakh, exclusion_reason } = provider;

  const rowStyle = {
    opacity: eligible ? 1 : 0.6,
    filter: eligible ? 'none' : 'grayscale(80%)',
    border: '1px solid var(--border-light)',
    padding: 'var(--space-md)',
    borderRadius: '8px',
    background: 'var(--bg-elevated)'
  };

  // Scale relative to available liquidity instead of total portfolio to make it visible on a projector
  // Enforce a minimum width of 4% for the fundable notch so it never shrinks to sub-pixel sizes
  const availablePercent = 100;
  const fundablePercent = max_fundable_lakh > 0 ? Math.max((max_fundable_lakh / available_liquidity_lakh) * 100, 4) : 0;

  return (
    <motion.div 
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      style={rowStyle}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-sm)' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 'var(--font-size-md)' }}>{name}</div>
          <span className={`type-badge type-badge--${type}`} style={{ marginTop: 4, display: 'inline-block' }}>{type}</span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Risk Appetite</div>
          <div style={{ fontWeight: 600 }}>Up to {formatPercent(risk_appetite, 2)} PD</div>
        </div>
      </div>

      <div style={{ marginBottom: eligible ? 0 : 'var(--space-md)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)', marginBottom: 4, color: 'var(--text-muted)' }}>
          <span>Liquidity & Limits</span>
          <span>{formatLakh(max_fundable_lakh)} fundable</span>
        </div>
        <div style={{ height: 8, background: 'var(--bg-secondary)', borderRadius: 4, position: 'relative', overflow: 'hidden' }}>
          <div style={{ 
            position: 'absolute', 
            top: 0, left: 0, bottom: 0, 
            width: `${availablePercent}%`, 
            background: 'var(--border-light)',
            borderRadius: 4
          }} title={`Available Liquidity: ${formatLakh(available_liquidity_lakh)}`} />
          <div style={{ 
            position: 'absolute', 
            top: 0, left: 0, bottom: 0, 
            width: `${fundablePercent}%`, 
            background: 'var(--accent-primary)',
            borderRadius: 4
          }} title={`Sector Limit Cap: ${formatLakh(max_fundable_lakh)}`} />
        </div>
        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
          <span>Available: {formatLakh(available_liquidity_lakh)}</span>
          <span>Total Portfolio: {formatLakh(total_portfolio_lakh)}</span>
        </div>
      </div>

      {!eligible && exclusion_reason && (
        <div style={{ marginTop: 'var(--space-md)', padding: 'var(--space-sm)', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-danger)', borderRadius: 6, fontSize: 'var(--font-size-sm)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Excluded</div>
          {exclusion_reason}
        </div>
      )}
    </motion.div>
  );
}
