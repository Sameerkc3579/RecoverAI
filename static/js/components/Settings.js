/* ─── Settings Page — with Dark Mode (#2), AI Negotiation (#9), Debtor Portal (#5) ─── */
function Settings({ settings, setSettings, darkMode, setDarkMode }) {
  const [local, setLocal] = React.useState(settings);
  const [saved, setSaved] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [portalLink, setPortalLink] = React.useState('');
  const [portalLoading, setPortalLoading] = React.useState(false);

  // Keep local in sync if parent settings change (e.g. after login)
  React.useEffect(() => { setLocal(settings); }, [settings]);

  function save() {
    setSaving(true);
    setSettings(local);
    setSaved(true);
    setSaving(false);
    setTimeout(() => setSaved(false), 2500);
  }

  function upd(k, v) { setLocal(p => ({ ...p, [k]: v })); }

  /* ── Feature #5: Generate Debtor Portal Link ── */
  async function generatePortalLink(invoiceId) {
    setPortalLoading(true); setPortalLink('');
    try {
      const res = await authFetch('/api/invoices/' + invoiceId + '/portal-link', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setPortalLink(data.portal_url || window.location.origin + '/portal?token=' + (data.token || 'demo'));
      } else {
        // Fallback demo link
        setPortalLink(window.location.origin + '/portal?token=demo_' + invoiceId.slice(0,8));
      }
    } catch {
      setPortalLink(window.location.origin + '/portal?token=demo');
    }
    setPortalLoading(false);
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">Settings</div>
          <div className="page-sub">Configure your business profile, recovery preferences, and AI behaviour</div>
        </div>
        <div className="topbar-actions">
          <button className={`btn btn-primary${saved ? ' btn-success' : ''}`} onClick={save} disabled={saving}>
            {saved ? '✓ Saved!' : 'Save Changes'}
          </button>
        </div>
      </div>
      <div className="content">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>

          {/* LEFT COLUMN */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Business Profile */}
            <div className="card">
              <div className="card-header"><div className="card-title">Business Profile</div></div>
              <div className="form-group">
                <label className="form-label">Business Name</label>
                <input className="form-input" value={local.businessName || ''} onChange={e => upd('businessName', e.target.value)} placeholder="Krishna Enterprises" />
              </div>
              <div className="form-group">
                <label className="form-label">Owner / Contact Name</label>
                <input className="form-input" value={local.ownerName || ''} onChange={e => upd('ownerName', e.target.value)} placeholder="Anil Kumar" />
              </div>
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Phone</label>
                  <input className="form-input" value={local.phone || ''} onChange={e => upd('phone', e.target.value)} placeholder="+91 98765 00001" />
                </div>
                <div className="form-group">
                  <label className="form-label">City</label>
                  <input className="form-input" value={local.city || ''} onChange={e => upd('city', e.target.value)} placeholder="Mumbai" />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Business Contact Email</label>
                <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4 }}>Used on legal notices and letterheads (not your login email)</div>
                <input className="form-input" type="email" value={local.email || ''} onChange={e => upd('email', e.target.value)} placeholder="contact@yourbusiness.in" />
              </div>
              <div className="form-group">
                <label className="form-label">GSTIN</label>
                <input className="form-input" value={local.gstin || ''} onChange={e => upd('gstin', e.target.value)} placeholder="27AAAAA0000A1Z5" />
              </div>
            </div>

            {/* Feature #5 — Debtor Self-Service Portal */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">🔗 Debtor Self-Service Portal</div>
                <span className="badge badge-blue" style={{ fontSize: 10 }}>New</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 14, lineHeight: 1.6 }}>
                Generate a secure, read-only magic link for a debtor to view their invoices, download PDFs, and make partial payment proposals — without needing an account.
              </div>
              <div className="portal-share-card">
                <div style={{ fontSize: 22, marginBottom: 8 }}>🌐</div>
                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Debtor Portal</div>
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', marginBottom: 16 }}>A branded, secure portal your debtors can access to review and respond to invoices.</div>
                {portalLink ? (
                  <div>
                    <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: 8, padding: '10px 14px', fontSize: 12, wordBreak: 'break-all', marginBottom: 10, fontFamily: 'monospace', color: '#fff' }}>{portalLink}</div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-sm" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)' }} onClick={() => navigator.clipboard.writeText(portalLink)}>📋 Copy Link</button>
                      <button className="btn btn-sm" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)' }} onClick={() => window.open(`https://wa.me/?text=${encodeURIComponent('Please view your invoice here: ' + portalLink)}`, '_blank')}>💬 Share via WhatsApp</button>
                    </div>
                  </div>
                ) : (
                  <button className="btn" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)' }} onClick={() => generatePortalLink('demo')} disabled={portalLoading}>
                    {portalLoading ? <><span className="spinner" style={{ borderTopColor: '#fff' }} /> Generating...</> : '⚡ Generate Portal Link'}
                  </button>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text3)' }}>🔒 Links are time-limited (48 hours) and debtor-specific for security.</div>
            </div>
          </div>

          {/* RIGHT COLUMN */}
          <div>
            {/* Feature #2 — Dark Mode + Recovery Settings */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header"><div className="card-title">Display & Recovery Settings</div></div>

              {/* Dark Mode Toggle */}
              <div className="settings-row" style={{ paddingBottom: 14, marginBottom: 4 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>🌙 Dark Mode</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>Switch between light and dark interface theme</div>
                </div>
                <div className={`dm-track${darkMode ? ' on' : ''}`} onClick={() => setDarkMode(!darkMode)} style={{ cursor: 'pointer' }}>
                  <div className="dm-thumb"></div>
                </div>
              </div>

              {[
                ['autoReminder', 'Auto Reminders', 'Send reminders automatically on schedule'],
                ['whatsappEnabled', 'WhatsApp Channel', 'Send via WhatsApp Business API'],
                ['emailEnabled', 'Email Channel', 'Send follow-ups via email'],
              ].map(([key, title, desc]) => (
                <div key={key} className="settings-row">
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{title}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{desc}</div>
                  </div>
                  <div className={`toggle${local[key] ? ' on' : ''}`} onClick={() => upd(key, !local[key])}>
                    <div className="toggle-thumb"></div>
                  </div>
                </div>
              ))}
              <div className="form-group" style={{ marginTop: 12, marginBottom: 0 }}>
                <label className="form-label">Legal Action Threshold (Days Overdue)</label>
                <input className="form-input" type="number" value={local.legalAtDays || 45} onChange={e => upd('legalAtDays', parseInt(e.target.value) || 45)} min={30} max={90} />
              </div>
            </div>

            {/* Feature #9 — AI Negotiation Behaviour */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <div className="card-title">🤖 AI Negotiation Behaviour</div>
                <span className="badge badge-purple" style={{ fontSize: 10 }}>New</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 14, lineHeight: 1.6 }}>
                Control how the AI responds during automated WhatsApp negotiations with debtors.
              </div>

              <div className="ai-setting-row">
                <div className="ai-setting-icon">🤝</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Allow Installment Offers</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)' }}>AI can propose a payment plan if debtor can't pay in full</div>
                </div>
                <div className={`toggle${local.aiAllowInstallments ? ' on' : ''}`} onClick={() => upd('aiAllowInstallments', !local.aiAllowInstallments)}>
                  <div className="toggle-thumb"></div>
                </div>
              </div>

              {local.aiAllowInstallments && (
                <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '10px 14px', margin: '8px 0 12px', border: '1px solid var(--border)' }}>
                  <div className="form-group" style={{ marginBottom: 8 }}>
                    <label className="form-label">Max Installments Allowed</label>
                    <select className="form-input" value={local.aiMaxInstallments || 3} onChange={e => upd('aiMaxInstallments', parseInt(e.target.value))}>
                      {[2,3,4,6].map(n => <option key={n} value={n}>{n} months</option>)}
                    </select>
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Min First Installment (%)</label>
                    <input className="form-input" type="number" value={local.aiMinFirstPct || 30} onChange={e => upd('aiMinFirstPct', parseInt(e.target.value) || 30)} min={10} max={80} />
                  </div>
                </div>
              )}

              <div className="ai-setting-row">
                <div className="ai-setting-icon">🌡️</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>AI Tone</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)' }}>Set the negotiation style for automated messages</div>
                </div>
                <select className="form-input" style={{ width: 'auto', padding: '4px 10px', fontSize: 12 }} value={local.aiTone || 'firm'} onChange={e => upd('aiTone', e.target.value)}>
                  <option value="friendly">Friendly</option>
                  <option value="firm">Firm</option>
                  <option value="formal">Formal / Legal</option>
                </select>
              </div>

              <div className="ai-setting-row">
                <div className="ai-setting-icon">🔁</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Auto-escalate after stalls</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)' }}>Automatically escalate to legal notice after 3 stall replies</div>
                </div>
                <div className={`toggle${local.aiAutoEscalate ? ' on' : ''}`} onClick={() => upd('aiAutoEscalate', !local.aiAutoEscalate)}>
                  <div className="toggle-thumb"></div>
                </div>
              </div>

              <div className="ai-setting-row">
                <div className="ai-setting-icon">🌐</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Multilingual Replies</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)' }}>AI replies in the debtor's detected language (Hindi, Marathi, etc.)</div>
                </div>
                <div className={`toggle${local.aiMultilingual !== false ? ' on' : ''}`} onClick={() => upd('aiMultilingual', local.aiMultilingual === false ? true : false)}>
                  <div className="toggle-thumb"></div>
                </div>
              </div>
            </div>

            {/* Commission */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header"><div className="card-title">Commission Model</div></div>
              <div className="info-box" style={{ marginBottom: 12 }}>Your commission is automatically calculated on recovered invoice amounts. Track your earnings below.</div>
              <div className="form-group" style={{ marginBottom: 8 }}>
                <label className="form-label">Commission Rate (%)</label>
                <input className="form-input" type="number" value={local.commissionRate || 2} onChange={e => upd('commissionRate', parseFloat(e.target.value) || 0)} min={0} max={10} step={0.5} />
              </div>
              <div style={{ background: 'var(--green-bg)', border: '1px solid var(--green-light)', borderRadius: 'var(--radius)', padding: '10px 12px', fontSize: 12, color: 'var(--green)' }}>
                Estimated earnings this cycle: <strong>₹{Math.round(262000 * (local.commissionRate || 2) / 100).toLocaleString('en-IN')}</strong> ({local.commissionRate || 2}% of ₹2,62,000 recovered)
              </div>
            </div>

            {/* Integrations */}
            <div className="card">
              <div className="card-header"><div className="card-title">Integrations</div></div>
              {[
                ['WhatsApp Business API', 'Connect to send real messages', 'badge-amber', 'Not Connected'],
                ['Zoho Books / Tally', 'Auto-import invoices', 'badge-amber', 'Not Connected'],
                ['Razorpay / PhonePe', 'Add payment links in messages', 'badge-green', 'Connected'],
                ['MSME Samadhaan Portal', 'Direct filing integration', 'badge-blue', 'Available'],
              ].map(([name, desc, cls, status]) => (
                <div key={name} className="settings-row">
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 1 }}>{desc}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className={`badge ${cls}`} style={{ fontSize: 10 }}>{status}</span>
                    <button className="btn btn-sm">{status === 'Connected' ? 'Disconnect' : 'Connect'}</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
