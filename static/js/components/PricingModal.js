/* ─── Pricing Modal ─── */
function PricingModal({ currentPlan, onClose, onUpgrade }) {
  const [step, setStep] = React.useState('selection'); // selection | processing | success
  const [selected, setSelected] = React.useState(null);

  const plans = [
    {
      name: 'Starter', price: '₹0', priceSub: 'forever free', id: 'Starter',
      features: ['Up to 10 Invoices/mo', 'Email Reminders', 'Basic Dashboard', 'WhatsApp (Manual)'],
    },
    {
      name: 'Professional', price: '₹4,999', priceSub: 'per month', id: 'Professional', featured: true,
      features: ['Unlimited Invoices', 'WhatsApp API Integration', 'Legal Notice Generator', 'Dedicated Recovery Agent', 'Real-time AI Chat'],
    },
    {
      name: 'Enterprise', price: '₹19,999', priceSub: 'per month', id: 'Enterprise',
      features: ['Multiple Businesses', 'API Access', 'Custom Workflow Automation', 'White-labeled Documents', 'Priority Support'],
    },
  ];

  function handlePlanSelect(plan) {
    if (plan.id === currentPlan) return;
    setSelected(plan); setStep('processing');
    setTimeout(() => { setStep('success'); onUpgrade(plan.id); }, 3000);
  }

  return (
    <div className="overlay" onClick={onClose} style={{ zIndex: 2000 }}>
      <div className="modal" style={{ maxWidth: 1000, padding: 32 }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <h2 style={{ fontSize: 28, fontWeight: 800 }}>Choose Your Power Level</h2>
            <p style={{ color: 'var(--text3)', marginTop: 4 }}>Scale your recovery operations with professional tools</p>
          </div>
          <button className="btn btn-sm" onClick={onClose}>✕</button>
        </div>

        {step === 'selection' && (
          <div className="pricing-grid">
            {plans.map(p => (
              <div key={p.id} className={`pricing-card ${p.featured ? 'featured' : ''} ${currentPlan === p.id ? 'active' : ''}`}>
                {p.featured && <div className="plan-badge">MOST POPULAR</div>}
                <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 8 }}>{p.name}</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 4 }}>
                  <span style={{ fontSize: 32, fontWeight: 800 }}>{p.price}</span>
                  <span style={{ color: 'var(--text3)', fontSize: 13 }}>{p.priceSub}</span>
                </div>
                <div style={{ height: 1, background: 'var(--border)', margin: '16px 0' }}></div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text2)' }}>What's included:</div>
                  {p.features.map(f => (
                    <div key={f} style={{ display: 'flex', gap: 8, fontSize: 13, marginBottom: 8, alignItems: 'center' }}>
                      <span style={{ color: 'var(--green)', fontWeight: 800 }}>✓</span>
                      <span>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  className={`btn ${p.featured ? 'btn-primary' : 'btn-outline'} btn-lg`}
                  style={{ width: '100%', marginTop: 24, justifyContent: 'center' }}
                  disabled={currentPlan === p.id}
                  onClick={() => handlePlanSelect(p)}>
                  {currentPlan === p.id ? 'Current Plan' : 'Select Plan'}
                </button>
              </div>
            ))}
          </div>
        )}

        {step === 'processing' && (
          <div className="payment-checking">
            <div className="spinner" style={{ width: 48, height: 48, borderWidth: 4, marginBottom: 24 }}></div>
            <h3 style={{ fontSize: 20, fontWeight: 700 }}>Processing Secure Payment</h3>
            <p style={{ color: 'var(--text3)', marginTop: 8 }}>Talking to Razorpay servers...</p>
            <div style={{ marginTop: 24, padding: '12px 20px', background: 'var(--surface2)', borderRadius: 12, fontSize: 13, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 10px var(--green)' }}></div>
              Secure Transaction: {selected?.price} / month
            </div>
          </div>
        )}

        {step === 'success' && (
          <div className="payment-checking">
            <div className="success-pulse">✓</div>
            <h3 style={{ fontSize: 24, fontWeight: 800, color: 'var(--green)' }}>Welcome to {selected?.name}!</h3>
            <p style={{ color: 'var(--text3)', marginTop: 8, maxWidth: 400 }}>Your workspace has been upgraded. You now have access to all {selected?.name} features.</p>
            <button className="btn btn-primary btn-lg" style={{ marginTop: 32, padding: '14px 40px' }} onClick={onClose}>
              Go to Dashboard →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
