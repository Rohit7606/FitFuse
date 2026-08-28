import { motion, AnimatePresence } from 'framer-motion';
import { formatPercent, formatLakh, formatRupees, formatDays } from '../utils/format.js';

export default function OfferComparison({ offers = [] }) {
  if (!offers.length) {
    return (
      <div style={{ padding: 'var(--space-2xl)', textAlign: 'center', color: 'var(--text-muted)' }}>
        No offers available.
      </div>
    );
  }

  // Find the lowest rate to highlight it subtly
  const feasibleOffers = offers.filter(o => o.feasible);
  const minRate = feasibleOffers.length > 0 ? Math.min(...feasibleOffers.map(o => o.rate_annual)) : null;

  return (
    <div className="offers-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-md)' }}>
      <AnimatePresence>
        {offers.map((offer, index) => {
          const isLowestRate = offer.feasible && offer.rate_annual === minRate;
          return (
            <OfferCard 
              key={offer.offer_id}
              offer={offer}
              rank={index + 1}
              isLowestRate={isLowestRate}
            />
          );
        })}
      </AnimatePresence>
    </div>
  );
}

function OfferCard({ offer, rank, isLowestRate }) {
  const { provider, fit_score, rate_annual, cash_now_lakh, tenor_days, days_to_settle, total_cost_lakh, feasible, reason_text, rejection_reason } = offer;

  const cardStyle = {
    opacity: feasible ? 1 : 0.6,
    filter: feasible ? 'none' : 'grayscale(80%)',
    border: '1px solid var(--border-light)',
    position: 'relative'
  };

  return (
    <motion.div 
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 350, damping: 25 }}
      className="card" 
      style={cardStyle}
    >
      <div style={{ position: 'absolute', top: -12, left: 16, background: 'var(--bg-elevated)', border: '1px solid var(--border-light)', borderRadius: '50%', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 'var(--font-size-sm)', zIndex: 1 }}>
        {rank}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-sm)', paddingTop: 8 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 'var(--font-size-sm)' }}>{provider.name}</div>
          <span className={`type-badge type-badge--${provider.type}`} style={{ marginTop: 4, display: 'inline-block' }}>{provider.type}</span>
        </div>
      </div>

      {feasible ? (
        <>
          <div style={{ marginBottom: 'var(--space-lg)' }}>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Fit Score</div>
            <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: 'var(--accent-primary)' }}>{fit_score.toFixed(2)}</div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--space-sm)', fontSize: 'var(--font-size-sm)', marginBottom: 'var(--space-md)' }}>
            <MetricRow 
              label="Cost (Rate)" 
              value={formatPercent(rate_annual, 2)} 
              highlight={isLowestRate} 
            />
            <MetricRow label="Cash Now" value={formatLakh(cash_now_lakh)} />
            <MetricRow label="Speed" value={formatDays(days_to_settle)} />
            <MetricRow label="All-in Cost" value={formatRupees(total_cost_lakh)} />
            <MetricRow label="Tenor" value={`${tenor_days} days`} />
          </div>

          <div style={{ padding: 'var(--space-sm)', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 'var(--font-size-xs)', color: 'var(--text-secondary)' }}>
            {reason_text}
          </div>
        </>
      ) : (
        <div style={{ marginTop: 'var(--space-md)' }}>
          <div style={{ padding: 'var(--space-sm)', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-danger)', borderRadius: 6, fontSize: 'var(--font-size-sm)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Infeasible</div>
            {rejection_reason}
          </div>
        </div>
      )}
    </motion.div>
  );
}

function MetricRow({ label, value, highlight }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 4 }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontWeight: highlight ? 800 : 600, color: highlight ? 'var(--accent-success)' : 'inherit' }}>
        {highlight && <span style={{ marginRight: 4, fontSize: '0.85em' }}>★</span>}
        {value}
      </span>
    </div>
  );
}
