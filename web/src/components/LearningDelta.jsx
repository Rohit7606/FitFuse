import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { formatPercent } from '../utils/format.js';

export default function LearningDelta({ delta, providers = [] }) {
  // We use local state to trigger the animation of the repricing after a short delay
  const [showAfter, setShowAfter] = useState(false);

  useEffect(() => {
    if (!delta) return;
    const timer = setTimeout(() => setShowAfter(true), 1500);
    return () => clearTimeout(timer);
  }, [delta]);

  if (!delta) return null;

  const { trigger, repriced_invoices, provider_bid_adjustments, summary_text } = delta;

  const bandColors = {
    prime: 'var(--accent-success)',
    standard: 'var(--accent-primary)',
    watch: 'var(--accent-warning)',
    decline: 'var(--accent-danger)'
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="card" 
      style={{ border: '2px solid var(--accent-primary)', padding: 'var(--space-xl)', background: 'var(--bg-elevated)', marginTop: 'var(--space-2xl)' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
        <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, margin: 0 }}>Market Learning</h2>
        <span className="type-badge type-badge--fintech" style={{ background: 'var(--accent-warning)', color: '#fff' }}>Trigger: {trigger.days_late} Days Late</span>
      </div>

      <div style={{ padding: 'var(--space-md)', background: 'var(--bg-secondary)', borderRadius: 8, marginBottom: 'var(--space-xl)', fontSize: 'var(--font-size-md)', lineHeight: 1.5 }}>
        {summary_text}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl)' }}>
        
        {/* Repriced Invoices */}
        <div>
          <h3 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 'var(--space-md)' }}>Repriced Open Invoices</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {repriced_invoices.map((inv) => (
              <div key={inv.invoice_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-sm)', background: 'var(--bg-secondary)', borderRadius: 6 }}>
                <span style={{ fontWeight: 600 }}>{inv.invoice_id}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                  {/* Before state */}
                  <span style={{ 
                    padding: '2px 8px', borderRadius: 4, fontSize: 'var(--font-size-xs)', fontWeight: 700,
                    background: `${bandColors[inv.band_before]}20`, color: bandColors[inv.band_before]
                  }}>
                    {inv.band_before.toUpperCase()} ({formatPercent(inv.pd_before, 2)})
                  </span>
                  
                  {/* Animated Arrow & After State */}
                  <AnimatePresence>
                    {showAfter && (
                      <motion.div 
                        initial={{ opacity: 0, x: -10 }} 
                        animate={{ opacity: 1, x: 0 }}
                        style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}
                      >
                        <span style={{ color: 'var(--text-muted)' }}>→</span>
                        <span style={{ 
                          padding: '2px 8px', borderRadius: 4, fontSize: 'var(--font-size-xs)', fontWeight: 700,
                          background: `${bandColors[inv.band_after]}20`, color: bandColors[inv.band_after],
                          border: `1px solid ${bandColors[inv.band_after]}`
                        }}>
                          {inv.band_after.toUpperCase()} ({formatPercent(inv.pd_after, 2)})
                        </span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            ))}
            {repriced_invoices.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No other invoices affected.</div>
            )}
          </div>
        </div>

        {/* Provider Adjustments */}
        <div>
          <h3 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 'var(--space-md)' }}>Provider Bid Adjustments</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {provider_bid_adjustments.map((adj, i) => {
              const provider = providers.find(p => p.provider_id === adj.provider_id);
              return (
                <div key={i} style={{ padding: 'var(--space-sm)', background: 'var(--bg-secondary)', borderRadius: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600 }}>{provider?.name || adj.provider_id}</span>
                    <AnimatePresence>
                      {showAfter && (
                        <motion.span 
                          initial={{ opacity: 0, scale: 0.5 }} 
                          animate={{ opacity: 1, scale: 1 }}
                          style={{ color: adj.rate_adjustment > 0 ? 'var(--accent-danger)' : 'var(--accent-success)', fontWeight: 700 }}
                        >
                          {adj.rate_adjustment > 0 ? '+' : ''}{(adj.rate_adjustment * 10000).toFixed(0)} bps
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </div>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>Segment: {adj.segment}</div>
                </div>
              );
            })}
            {provider_bid_adjustments.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No rate adjustments.</div>
            )}
          </div>
        </div>

      </div>
    </motion.div>
  );
}
