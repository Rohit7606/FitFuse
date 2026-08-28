import { useState, useEffect } from 'react';
import { getMarket, assessInvoice, getOffers } from '../utils/api.js';
import VerificationPanel from './VerificationPanel.jsx';
import RiskPanel from './RiskPanel.jsx';
import OfferComparison from './OfferComparison.jsx';
import PreferenceSliders from './PreferenceSliders.jsx';

// Default weights from DEMO_SCENARIO.md.
// These six keys are the contract (SCHEMA.md 3.3) — cost, advance, speed,
// tenor, fees, structure. The API rejects anything else with a 422, because a
// weight vector that sums to 1.0 over the wrong keys used to return a
// confident, wrong ranking instead of an error.
const DEFAULT_WEIGHTS = {
  cost: 0.10,
  advance: 0.05,
  speed: 0.60,
  tenor: 0.15,
  fees: 0.05,
  structure: 0.05
};

export default function DemoFlow({ invoiceId = 'INV001' }) {
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [debouncedWeights, setDebouncedWeights] = useState(DEFAULT_WEIGHTS);
  
  const [assessment, setAssessment] = useState(null);
  const [offersData, setOffersData] = useState(null);
  const [isNaive, setIsNaive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Debounce slider changes
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedWeights(weights);
    }, 250);
    return () => clearTimeout(handler);
  }, [weights]);

  // Fetch data
  useEffect(() => {
    let active = true;
    
    async function fetchData() {
      try {
        const scenario = {
          preference_overrides: [
            {
              supplier_id: 'SUP001',
              weights: debouncedWeights,
              urgent: true
            }
          ],
          liquidity_overrides: [],
          settlement_events: [],
          naive_mode: false
        };
        // Parallel fetch for speed
        const [marketRes, assessRes, offersRes] = await Promise.all([
          getMarket(),
          assessInvoice(invoiceId, scenario),
          getOffers(invoiceId, scenario)
        ]);
        
        if (active) {
          // Merge provider info into offers
          const providerMap = {};
          marketRes.providers.forEach(p => { providerMap[p.provider_id] = p; });
          
          offersRes.offers = offersRes.offers.map(o => ({
            ...o,
            provider: providerMap[o.provider_id]
          }));

          // Rebuild the ranked arrays mapping offer IDs to actual offer objects
          offersRes.ranking = offersRes.ranking.map(id => offersRes.offers.find(o => o.offer_id === id));
          offersRes.naive_ranking = offersRes.naive_ranking.map(id => offersRes.offers.find(o => o.offer_id === id));

          // Note: we don't need to store market in state since we just map it
          setAssessment(assessRes.assessment);
          setOffersData(offersRes);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          setError(err.message);
          setLoading(false);
        }
      }
    }
    
    fetchData();
    
    return () => { active = false; };
  }, [invoiceId, debouncedWeights]);

  if (loading && !assessment) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
        <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700 }}>Loading Invoice {invoiceId}…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ maxWidth: 600, margin: '0 auto', textAlign: 'center', border: '1px solid var(--accent-danger)' }}>
        <div style={{ color: 'var(--accent-danger)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>Error loading data</div>
        <div>{error}</div>
      </div>
    );
  }

  return (
    <div className="demo-flow animate-fade-in">
      <div className="demo-flow__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-xl)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
            <h1 className="section-header__title">Invoice Assessment</h1>
            <span className="synthetic-badge">Synthetic Data</span>
          </div>
          <p className="section-header__subtitle">Reviewing {invoiceId}</p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>Naive Market View</span>
          <label className="toggle-switch">
            <input type="checkbox" checked={isNaive} onChange={e => setIsNaive(e.target.checked)} />
            <span className="toggle-slider"></span>
          </label>
        </div>
      </div>

      <div className="panels-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
        <VerificationPanel assessment={assessment} />
        <RiskPanel assessment={assessment} />
      </div>

      <div style={{ marginBottom: 'var(--space-2xl)' }}>
        <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, marginBottom: 'var(--space-md)' }}>
          Supplier Preferences
        </h2>
        <PreferenceSliders weights={weights} onChange={setWeights} />
      </div>

      <div>
        <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, marginBottom: 'var(--space-md)' }}>
          Offer Comparison
        </h2>
        {/* We use isNaive flag to toggle the active ranking list instantly without network calls */}
        <OfferComparison 
          offers={isNaive ? offersData.naive_ranking : offersData.ranking} 
          isNaive={isNaive}
          fitBeatsRate={offersData.fit_beats_rate}
        />
      </div>
    </div>
  );
}
