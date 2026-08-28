export default function RiskPanel({ assessment }) {
  if (!assessment) return null;

  const { pd, pd_lower_bound, pd_upper_bound, risk_band, reason_factors } = assessment;

  // Render the horizontal risk band
  const renderRiskBar = () => {
    // We assume max PD is around 10% for the visual scale
    const MAX_PD = 0.10;
    const toPct = (val) => Math.min((val / MAX_PD) * 100, 100);

    const lowerPct = toPct(pd_lower_bound);
    const upperPct = toPct(pd_upper_bound);
    const pointPct = toPct(pd);

    return (
      <div style={{ position: 'relative', height: 24, background: 'var(--bg-secondary)', borderRadius: 12, marginTop: 'var(--space-md)', overflow: 'hidden' }}>
        {/* Uncertainty band */}
        <div style={{ 
          position: 'absolute', 
          left: `${lowerPct}%`, 
          width: `${upperPct - lowerPct}%`, 
          height: '100%', 
          background: 'rgba(234, 179, 8, 0.2)' // Warning/yellowish tint
        }} />
        
        {/* Point estimate marker */}
        <div style={{
          position: 'absolute',
          left: `${pointPct}%`,
          width: 4,
          height: '100%',
          background: 'var(--accent-warning)',
          borderRadius: 2,
          transform: 'translateX(-50%)'
        }} />
      </div>
    );
  };

  return (
    <div className="card">
      <div className="card__header" style={{ marginBottom: 'var(--space-md)' }}>
        <h3 style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>Risk Assessment</h3>
        <span className={`badge`} style={{ background: 'var(--accent-primary)', color: 'white' }}>
          {risk_band}
        </span>
      </div>

      <div style={{ marginBottom: 'var(--space-xl)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Probability of Default</div>
            <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 800, color: 'var(--text-primary)' }}>
              {(pd * 100).toFixed(1)}%
            </div>
          </div>
          <div style={{ textAlign: 'right', color: 'var(--text-secondary)', fontSize: 'var(--font-size-sm)' }}>
            Range: {(pd_lower_bound * 100).toFixed(1)}% – {(pd_upper_bound * 100).toFixed(1)}%
          </div>
        </div>
        
        {renderRiskBar()}
      </div>

      <div>
        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginBottom: 'var(--space-sm)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Key Risk Factors</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          {reason_factors?.map((factor, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-sm)', padding: 'var(--space-xs) 0', borderBottom: i < reason_factors.length - 1 ? '1px solid var(--border-light)' : 'none' }}>
              <span style={{ color: 'var(--text-secondary)' }}>{factor.factor}</span>
              <span style={{ fontWeight: 600, color: factor.weight > 0 ? 'var(--accent-danger)' : 'var(--accent-success)' }}>
                {factor.weight > 0 ? '+' : ''}{(factor.weight * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
