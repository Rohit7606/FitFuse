/**
 * FitFuse — App shell
 * 
 * Loads market data at mount, renders the demo flow.
 * State lives in React state — no localStorage, no sessionStorage.
 *
 * Owner: Person C
 */

import { useState, useEffect } from 'react';
import { getMarket } from './utils/api.js';
import DemoFlow from './components/DemoFlow.jsx';

export default function App() {
  // We'll keep market fetch just to make sure backend is up, but DemoFlow drives the demo
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getMarket()
      .then(() => {
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="app-layout">
        <Header />
        <main className="app-main" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>
              Loading market…
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>
              Fetching simulated market data
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-layout">
        <Header />
        <main className="app-main" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card" style={{ textAlign: 'center', maxWidth: 480 }}>
            <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, color: 'var(--accent-danger)', marginBottom: 'var(--space-sm)' }}>
              Failed to load market
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-sm)' }}>
              {error}
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app-layout">
      <Header />
      <main className="app-main">
        <DemoFlow invoiceId="INV001" />
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className="app-header">
      <div className="app-header__logo">
        <span className="app-header__title">FitFuse</span>
        <span className="app-header__subtitle">Invoice Financing Clearinghouse</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
        <span className="synthetic-badge">Simulated Data</span>
      </div>
    </header>
  );
}
