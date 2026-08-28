export default function VerificationPanel({ assessment }) {
  if (!assessment) return null;

  const { irn_valid, irn_rejection_reason, duplicate_hash_detected, duplicate_of_invoice_id, confidence } = assessment;

  return (
    <div className="card">
      <div className="card__header" style={{ marginBottom: 'var(--space-md)' }}>
        <h3 style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>Verification</h3>
        <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
          {irn_valid ? (
            <span className="badge badge--success">IRN Valid</span>
          ) : (
            <span className="badge badge--danger" title={irn_rejection_reason}>IRN Rejected</span>
          )}
        </div>
      </div>

      {duplicate_hash_detected && (
        <div className="alert alert--danger" style={{ marginBottom: 'var(--space-md)', padding: 'var(--space-sm)', borderRadius: 6, background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-danger)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
          <div style={{ fontWeight: 700, marginBottom: 2 }}>Duplicate Detected</div>
          <div style={{ fontSize: 'var(--font-size-sm)' }}>This invoice matches the hash of {duplicate_of_invoice_id}. Blocked.</div>
        </div>
      )}

      <div>
        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginBottom: 'var(--space-sm)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Field Confidence</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-sm)' }}>
          <ConfidenceBadge label="Amount" level={confidence?.amount_lakh} />
          <ConfidenceBadge label="Buyer" level={confidence?.buyer_id} />
          <ConfidenceBadge label="Delivery" level={confidence?.delivery_confirmed} />
          <ConfidenceBadge label="Description" level={confidence?.goods_description} />
        </div>
      </div>
    </div>
  );
}

function ConfidenceBadge({ label, level }) {
  // level is 'verified', 'inferred', or 'unknown'
  const styles = {
    verified: { color: 'var(--accent-success)', icon: '✓' },
    inferred: { color: 'var(--accent-warning)', icon: '≈' },
    unknown:  { color: 'var(--text-muted)', icon: '?' }
  };
  
  const style = styles[level] || styles.unknown;

  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 'var(--font-size-sm)', padding: 'var(--space-xs) 0', borderBottom: '1px solid var(--border-light)' }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: style.color, fontWeight: 600 }}>
        <span style={{ fontSize: 'var(--font-size-xs)' }}>{style.icon}</span>
        <span style={{ textTransform: 'capitalize' }}>{level || 'Unknown'}</span>
      </div>
    </div>
  );
}
