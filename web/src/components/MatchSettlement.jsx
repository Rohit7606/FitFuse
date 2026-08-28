import { motion } from 'framer-motion';
import { formatLakh, formatPercent, formatRupees, formatDays } from '../utils/format.js';

export default function MatchSettlement({ match, providers = [], onFund, onSettle }) {
  if (!match) return null;

  const {
    state,
    allocations,
    syndicated,
    total_advance_lakh,
    blended_rate_annual,
    blended_cost_lakh,
    supplier_fit_score,
    days_to_settle,
    reason_text
  } = match;

  const stateColors = {
    matched: 'var(--text-muted)',
    funded: 'var(--accent-primary)',
    settled: 'var(--accent-success)',
    late: 'var(--accent-warning)',
    defaulted: 'var(--accent-danger)',
    cancelled: 'var(--accent-danger)'
  };

  const stateColor = stateColors[state] || stateColors.matched;
  const isFunded = state === 'funded';
  const isSettled = ['settled', 'late', 'defaulted'].includes(state);

  return (
    <div className="card" style={{ border: `2px solid ${stateColor}`, padding: 'var(--space-xl)', background: 'var(--bg-elevated)', marginTop: 'var(--space-2xl)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-lg)' }}>
        <div>
          <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, marginBottom: 'var(--space-xs)' }}>Clearing & Settlement</h2>
          <div style={{ color: 'var(--text-secondary)' }}>Status: <strong style={{ color: stateColor, textTransform: 'uppercase' }}>{state}</strong></div>
        </div>
        
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          {state === 'matched' && onFund && (
            <button onClick={onFund} className="btn btn--primary">Disburse Funds</button>
          )}
          {state === 'funded' && onSettle && (
            <button onClick={() => onSettle('late', 5)} className="btn btn--warning">Buyer Pays Late (5d)</button>
          )}
          {state === 'funded' && onSettle && (
            <button onClick={() => onSettle('settled', 0)} className="btn btn--success">Buyer Pays On Time</button>
          )}
        </div>
      </div>

      <div style={{ padding: 'var(--space-md)', background: 'var(--bg-secondary)', borderRadius: 8, marginBottom: 'var(--space-xl)', fontSize: 'var(--font-size-md)', lineHeight: 1.5 }}>
        {reason_text}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
        <div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Advance</div>
          <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{formatLakh(total_advance_lakh)}</div>
        </div>
        <div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Blended Rate</div>
          <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{formatPercent(blended_rate_annual, 2)}</div>
        </div>
        <div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Blended Cost</div>
          <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{formatRupees(blended_cost_lakh)}</div>
        </div>
        <div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Settlement</div>
          <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{formatDays(days_to_settle)}</div>
        </div>
      </div>

      {syndicated && (
        <div style={{ background: 'var(--bg-secondary)', padding: 'var(--space-md)', borderRadius: 8 }}>
          <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, marginBottom: 'var(--space-md)' }}>Syndication Split</div>
          <div style={{ display: 'flex', height: 24, borderRadius: 12, overflow: 'hidden', marginBottom: 'var(--space-sm)' }}>
            {allocations.map((alloc, i) => {
              const width = `${(alloc.amount_lakh / total_advance_lakh) * 100}%`;
              const colors = ['var(--accent-primary)', 'var(--accent-secondary)', 'var(--accent-success)', 'var(--accent-warning)'];
              const color = colors[i % colors.length];
              const provider = providers.find(p => p.provider_id === alloc.provider_id);
              return (
                <div 
                  key={alloc.provider_id}
                  style={{ width, background: color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 'var(--font-size-xs)', fontWeight: 700, color: '#fff' }}
                  title={`${provider?.name}: ${formatLakh(alloc.amount_lakh)}`}
                >
                  {formatLakh(alloc.amount_lakh)}
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-xl)', fontSize: 'var(--font-size-xs)' }}>
            {allocations.map((alloc, i) => {
              const provider = providers.find(p => p.provider_id === alloc.provider_id);
              const colors = ['var(--accent-primary)', 'var(--accent-secondary)', 'var(--accent-success)', 'var(--accent-warning)'];
              return (
                <div key={alloc.provider_id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: colors[i % colors.length] }} />
                  <span><strong>{provider?.name}</strong> ({formatLakh(alloc.amount_lakh)})</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
