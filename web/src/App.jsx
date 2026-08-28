/**
 * FitFuse — App shell
 * 
 * Loads market data at mount, renders the demo flow.
 * State lives in React state — no localStorage, no sessionStorage.
 *
 * Owner: Person C
 */

import React, { useState, useEffect } from 'react';
import { getMarket } from './utils/api.js';

export default function App() {
  const [market, setMarket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getMarket()
      .then((data) => {
        setMarket(data);
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
        <MarketOverview market={market} />
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

function MarketOverview({ market }) {
  const suppliers = market.suppliers || [];
  const buyers = market.buyers || [];
  const invoices = market.invoices || [];
  const providers = market.providers || [];

  return (
    <div className="animate-fade-in">
      <div className="section-header">
        <div>
          <h1 className="section-header__title">Market Overview</h1>
          <p className="section-header__subtitle">
            {invoices.length} invoices · {providers.length} capital providers · {suppliers.length} suppliers
          </p>
        </div>
        <span className="synthetic-badge">Simulated Data</span>
      </div>

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
        <StatCard label="Invoices" value={invoices.length} icon="📄" />
        <StatCard label="Suppliers" value={suppliers.length} icon="🏭" />
        <StatCard label="Buyers" value={buyers.length} icon="🏢" />
        <StatCard label="Providers" value={providers.length} icon="🏦" />
      </div>

      {/* Providers list */}
      <div style={{ marginBottom: 'var(--space-xl)' }}>
        <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, marginBottom: 'var(--space-md)' }}>
          Capital Providers
        </h2>
        <div className="providers-grid">
          {providers.map((p) => (
            <ProviderCard key={p.provider_id} provider={p} />
          ))}
        </div>
      </div>

      {/* Invoices list */}
      <div>
        <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, marginBottom: 'var(--space-md)' }}>
          Live Invoices
        </h2>
        <div style={{ display: 'grid', gap: 'var(--space-sm)' }}>
          {invoices.map((inv) => (
            <InvoiceRow key={inv.invoice_id} invoice={inv} suppliers={suppliers} buyers={buyers} />
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
      <div style={{ fontSize: '1.5rem', marginBottom: 'var(--space-xs)' }}>{icon}</div>
      <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 800, color: 'var(--text-primary)' }}>
        {value}
      </div>
      <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)', marginTop: 'var(--space-xs)' }}>
        {label}
      </div>
    </div>
  );
}

function ProviderCard({ provider }) {
  const typeClass = `type-badge type-badge--${provider.type}`;
  const liquidityPct = provider.total_portfolio_lakh > 0
    ? ((provider.available_liquidity_lakh / provider.total_portfolio_lakh) * 100).toFixed(0)
    : 0;

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <div style={{ fontWeight: 700, fontSize: 'var(--font-size-base)' }}>{provider.name}</div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 2 }}>
            {provider.provider_id}
          </div>
        </div>
        <span className={typeClass}>{provider.type}</span>
      </div>

      {/* Liquidity bar */}
      <div style={{ marginBottom: 'var(--space-md)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)', color: 'var(--text-secondary)', marginBottom: 4 }}>
          <span>Available Liquidity</span>
          <span>₹{provider.available_liquidity_lakh.toFixed(0)} lakh ({liquidityPct}%)</span>
        </div>
        <div style={{ height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${liquidityPct}%`,
            background: `linear-gradient(90deg, var(--accent-primary), var(--accent-info))`,
            borderRadius: 3,
            transition: 'width var(--transition-slow)',
          }} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-sm)', fontSize: 'var(--font-size-xs)' }}>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Risk appetite</span>
          <div style={{ fontWeight: 600 }}>{(provider.risk_appetite * 100).toFixed(1)}%</div>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Speed</span>
          <div style={{ fontWeight: 600 }}>{provider.speed_capability_days === 0 ? 'Same day' : `${provider.speed_capability_days} days`}</div>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Ticket range</span>
          <div style={{ fontWeight: 600 }}>₹{provider.min_ticket_lakh}–{provider.max_ticket_lakh} L</div>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Target return</span>
          <div style={{ fontWeight: 600 }}>{(provider.target_return * 100).toFixed(1)}%</div>
        </div>
      </div>
    </div>
  );
}

function InvoiceRow({ invoice, suppliers, buyers }) {
  const supplier = suppliers.find((s) => s.supplier_id === invoice.supplier_id);
  const buyer = buyers.find((b) => b.buyer_id === invoice.buyer_id);

  return (
    <div className="card" style={{ padding: 'var(--space-md) var(--space-lg)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-lg)' }}>
        <div>
          <span style={{ fontWeight: 700 }}>{invoice.invoice_id}</span>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
            {invoice.goods_description?.replace(/_/g, ' ')}
          </div>
        </div>
        <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
          {supplier?.name || invoice.supplier_id} → {buyer?.name || invoice.buyer_id}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-lg)' }}>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>₹{invoice.amount_lakh.toFixed(2)} lakh</div>
          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>{invoice.tenor_days} days</div>
        </div>
        <span style={{
          padding: '3px 10px',
          borderRadius: 100,
          fontSize: 'var(--font-size-xs)',
          fontWeight: 600,
          background: invoice.status === 'open' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255,255,255,0.06)',
          color: invoice.status === 'open' ? 'var(--accent-success)' : 'var(--text-muted)',
        }}>
          {invoice.status}
        </span>
      </div>
    </div>
  );
}
