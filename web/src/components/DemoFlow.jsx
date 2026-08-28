import { useState, useEffect } from 'react';
import { getMarket, assessInvoice, getOffers, clearMarket, settleMatch } from '../utils/api.js';
import VerificationPanel from './VerificationPanel.jsx';
import RiskPanel from './RiskPanel.jsx';
import OfferComparison from './OfferComparison.jsx';
import PreferenceSliders from './PreferenceSliders.jsx';
import ProviderPanel from './ProviderPanel.jsx';
import MatchSettlement from './MatchSettlement.jsx';
import LearningDelta from './LearningDelta.jsx';

// Default weights from DEMO_SCENARIO.md
const DEFAULT_WEIGHTS = {
  cost: 0.10,
  advance_rate: 0.05,
  speed: 0.60,
  tenor: 0.15,
  fees: 0.05,
  structure: 0.05
};

export default function DemoFlow({ invoiceId, secondaryInvoiceId }) {
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [debouncedWeights, setDebouncedWeights] = useState(DEFAULT_WEIGHTS);

  const [assessment, setAssessment] = useState(null);
  const [market, setMarket] = useState(null);
  const [offersData, setOffersData] = useState(null);
  const [matchData, setMatchData] = useState(null);
  const [learningData, setLearningData] = useState(null);
  const [viewRole, setViewRole] = useState('Market'); // 'Market', 'Supplier', 'Provider'
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

          // Store market for ProviderPanel
          setMarket(marketRes);
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

  const handleClearMarket = async () => {
    try {
      const scenario = {
        preference_overrides: [{ supplier_id: 'SUP001', weights: debouncedWeights, urgent: true }],
        liquidity_overrides: [],
        settlement_events: [],
        naive_mode: isNaive
      };
      // For demo, we clear using the dynamic primary and secondary invoices
      const res = await clearMarket([invoiceId, secondaryInvoiceId], scenario);
      if (res.matches && res.matches.length > 0) {
        setMatchData(res.matches.find(m => m.invoice_id === invoiceId));
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSettleMatch = async (outcome, daysLate) => {
    if (!matchData) return;
    try {
      const scenario = {
        preference_overrides: [{ supplier_id: 'SUP001', weights: debouncedWeights, urgent: true }],
        liquidity_overrides: [],
        settlement_events: [],
        naive_mode: isNaive
      };
      const res = await settleMatch(matchData.match_id, outcome, daysLate, scenario);
      setMatchData(res.after.match);
      if (res.delta) setLearningData(res.delta);
    } catch (err) {
      setError(err.message);
    }
  };

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

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
          <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 4, display: 'flex', gap: 4 }}>
            {['Market', 'Supplier', 'Provider'].map(role => (
              <button 
                key={role}
                onClick={() => setViewRole(role)}
                style={{ 
                  padding: '4px 12px', border: 'none', borderRadius: 4, cursor: 'pointer',
                  fontWeight: 600, fontSize: 'var(--font-size-sm)',
                  background: viewRole === role ? 'var(--accent-primary)' : 'transparent',
                  color: viewRole === role ? '#fff' : 'var(--text-secondary)'
                }}
              >
                {role}
              </button>
            ))}
          </div>
          <div style={{ width: 1, height: 24, background: 'var(--border-light)' }}></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>Naive Market View</span>
            <label className="toggle-switch">
              <input type="checkbox" checked={isNaive} onChange={e => setIsNaive(e.target.checked)} />
              <span className="toggle-slider"></span>
            </label>
          </div>
        </div>
      </div>

      {viewRole !== 'Provider' && (
        <div className="panels-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
          <VerificationPanel assessment={assessment} />
          <RiskPanel assessment={assessment} />
        </div>
      )}

      {viewRole !== 'Supplier' && (
        <div style={{ marginBottom: 'var(--space-2xl)' }}>
          <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, marginBottom: 'var(--space-md)' }}>
            Provider Market
          </h2>
          <ProviderPanel providers={market?.providers} eligibility={assessment?.eligibility} />
        </div>
      )}

      {viewRole !== 'Provider' && (
        <div style={{ marginBottom: 'var(--space-2xl)' }}>
          <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, marginBottom: 'var(--space-md)' }}>
            Supplier Preferences
          </h2>
          <PreferenceSliders weights={weights} onChange={setWeights} />
        </div>
      )}

      {viewRole !== 'Provider' && (
        <div style={{ marginBottom: 'var(--space-2xl)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
            <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, margin: 0 }}>
              Offer Comparison
            </h2>
            {/* Show run clearing button if there are feasible offers */}
            {offersData && offersData.ranking.some(o => o.feasible) && (
              <button className="btn btn--primary" onClick={handleClearMarket}>Run Market Clearing</button>
            )}
          </div>
          {/* We use isNaive flag to toggle the active ranking list instantly without network calls */}
          <OfferComparison
            offersData={offersData}
            isNaive={isNaive}
          />
        </div>
      )}

      {matchData && (
        <div style={{ marginBottom: 'var(--space-2xl)' }}>
          <MatchSettlement 
            match={matchData} 
            providers={market?.providers} 
            onFund={() => setMatchData({ ...matchData, state: 'funded' })} 
            onSettle={handleSettleMatch} 
          />
        </div>
      )}

      {learningData && viewRole !== 'Supplier' && (
        <div style={{ marginBottom: 'var(--space-2xl)' }}>
          <LearningDelta delta={learningData} providers={market?.providers} />
        </div>
      )}
    </div>
  );
}
