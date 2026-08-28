export default function PreferenceSliders({ weights, onChange }) {
  const DIMENSIONS = [
    { key: 'cost', label: 'Cost (Interest Rate)' },
    { key: 'advance', label: 'Advance Rate' },
    { key: 'speed', label: 'Speed to Cash' },
    { key: 'tenor', label: 'Tenor' },
    { key: 'fees', label: 'Fees' },
    { key: 'structure', label: 'Structure' }
  ];

  const handleSliderChange = (changedKey, newValue) => {
    // newValue is a string from range input, between 0 and 100
    const newValPct = parseInt(newValue, 10) / 100;
    
    // We must ensure the sum remains 1.0.
    const oldValPct = weights[changedKey];
    const diff = newValPct - oldValPct;
    
    const otherKeys = DIMENSIONS.map(d => d.key).filter(k => k !== changedKey);
    let remainderToDistribute = -diff;

    // Calculate sum of others to distribute proportionally
    let sumOthers = 0;
    for (const k of otherKeys) {
      sumOthers += weights[k];
    }

    const newWeights = { ...weights, [changedKey]: newValPct };
    
    if (sumOthers === 0) {
      // If others are all 0, distribute evenly
      for (const k of otherKeys) {
        newWeights[k] = (remainderToDistribute / otherKeys.length);
      }
    } else {
      // Distribute proportionally
      for (const k of otherKeys) {
        const proportion = weights[k] / sumOthers;
        newWeights[k] = weights[k] + (remainderToDistribute * proportion);
      }
    }

    // Fix floating point math drift
    let finalSum = 0;
    for (const k of DIMENSIONS) {
      // clamp to [0, 1] just in case
      newWeights[k.key] = Math.max(0, Math.min(1, newWeights[k.key]));
      finalSum += newWeights[k.key];
    }
    
    // Adjust the first 'other' key by the error to ensure exact 1.0 sum
    if (Math.abs(finalSum - 1.0) > 0.0001) {
      newWeights[otherKeys[0]] -= (finalSum - 1.0);
    }

    onChange(newWeights);
  };

  const setPreset = (presetWeights) => {
    onChange(presetWeights);
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-lg)' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-sm)' }}>
          Adjust sliders to re-rank the market based on the supplier&apos;s actual needs. Weights must sum to 100%.
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <button className="btn btn--outline" onClick={() => setPreset({ cost: 0.8, advance: 0.05, speed: 0.05, tenor: 0.05, fees: 0.025, structure: 0.025 })}>
            Cost Sensitive
          </button>
          <button className="btn btn--outline" onClick={() => setPreset({ cost: 0.10, advance: 0.05, speed: 0.60, tenor: 0.15, fees: 0.05, structure: 0.05 })}>
            Need Cash Fast
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl) var(--space-2xl)' }}>
        {DIMENSIONS.map((dim) => (
          <div key={dim.key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-xs)' }}>
              <label style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>{dim.label}</label>
              <span style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                {(weights[dim.key] * 100).toFixed(0)}%
              </span>
            </div>
            <input 
              type="range" 
              min="0" 
              max="100" 
              value={(weights[dim.key] * 100).toFixed(0)}
              onChange={(e) => handleSliderChange(dim.key, e.target.value)}
              className="slider"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
