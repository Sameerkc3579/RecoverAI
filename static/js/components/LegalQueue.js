/* ─── Legal Queue Page ─── */
function LegalQueue({ invoices, openDetail, settings }) {
  const [selected, setSelected] = React.useState(null);
  const [aiNotice, setAiNotice] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const sel = selected ? invoices.find(i => i.id === selected) : null;

  const totalPrincipal = invoices.reduce((s, i) => s + i.amount, 0);
  const totalClaim = invoices.reduce((s, i) => s + (i.interest_data?.total_claim || i.amount), 0);
  const totalInterest = invoices.reduce((s, i) => s + (i.interest_data?.interest_accrued || 0), 0);

  function idata(inv) {
    const d = inv.interest_data || {};
    return {
      interest: d.interest_accrued || 0,
      claim: d.total_claim || inv.amount,
      days: d.days_overdue || inv.daysOverdue || 0,
      rate: d.annual_rate_pct || 19.5,
      basis: d.legal_basis || 'MSMED Act 2006, §15–17',
    };
  }

  async function generateNotice() {
    if (!sel) return;
    setLoading(true); setAiNotice(''); setCopied(false);
    const id = idata(sel);
    try {
      const msg = await callAI(SYSTEM_PROMPT,
        `Draft a complete formal MSME Legal Notice / Letter Before Action for:\n\nSENDER:\nBusiness: ${settings.businessName}\nOwner: ${settings.ownerName}\nPhone: ${settings.phone}\nEmail: ${settings.email}\nGSTIN: ${settings.gstin}\n\nDEBTOR:\nCompany: ${sel.company}\nContact: ${sel.contact}\nPhone: ${sel.phone}\nGSTIN: ${sel.gstin || 'N/A'}\n\nINVOICE DETAILS:\nInvoice No: ${sel.invoiceNo}\nIssue Date: ${sel.issueDate}\nDue Date: ${sel.dueDate}\nBase Amount: ${fmtINR(sel.amount)}\nDays Overdue: ${id.days}\nMSMED Act Penalty (19.5% p.a. compound with monthly rests): ${fmtINR(id.interest)}\nTotal Legal Claim: ${fmtINR(id.claim)}\n\nRequirements:\n1. Formal legal notice header with date\n2. Cite MSMED Act 2006, Sections 15, 16, 17\n3. State EXACT interest of ${fmtINR(id.interest)} accrued at 3x Reserve Bank rate (19.5% p.a.)\n4. Demand TOTAL payment of ${fmtINR(id.claim)} within 15 days of this notice\n5. Mention filing with MSME Samadhaan portal as next step\n6. Professional legal closing\n7. Signature block for ${settings.ownerName}, ${settings.businessName}`
      );
      setAiNotice(msg);
    } catch (e) { setAiNotice(`Error: ${e.message}`); }
    setLoading(false);
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">Legal Queue</div>
          <div className="page-sub">{invoices.length} invoices qualify for legal action (45+ days overdue)</div>
        </div>
        <div className="topbar-actions" style={{ display: 'flex', gap: 8 }}>
          <span className="badge badge-amber" style={{ fontSize: 11 }}>Principal: {fmtINR(totalPrincipal)}</span>
          <span className="badge badge-red" style={{ fontSize: 12 }}>Total Claim: {fmtINR(totalClaim)}</span>
        </div>
      </div>
      <div className="content">
        {invoices.length === 0 && (
          <div className="empty">
            <div className="empty-icon">⚖</div>
            <div className="empty-title">No invoices in legal queue</div>
            <div className="empty-sub">Invoices 45+ days overdue will appear here</div>
          </div>
        )}

        <div className="legal-grid">
          <div>
            <div className="danger-box">
              <strong>⚠ Action Required</strong><br />
              These invoices are eligible for MSME Samadhaan filing under the MSMED Act 2006. Compound interest at 3× RBI bank rate (19.5% p.a.) has accrued <strong>{fmtINR(totalInterest)}</strong> in penalties.
            </div>
            {invoices.map(inv => {
              const id = idata(inv);
              return (
                <div key={inv.id} onClick={() => { setSelected(inv.id); setAiNotice(''); setCopied(false); }}
                  style={{ padding: '12px', border: `1.5px solid ${selected === inv.id ? 'var(--red)' : 'var(--border)'}`, borderRadius: 'var(--radius-lg)', marginBottom: 8, cursor: 'pointer', background: selected === inv.id ? 'var(--red-bg)' : 'var(--surface)', transition: 'all 0.15s' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ fontWeight: 700, fontSize: 13 }}>{inv.company}</div>
                    <span className="badge badge-red">{id.days}d overdue</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{inv.contact} · {inv.invoiceNo}</div>
                  <div style={{ marginTop: 8, background: 'var(--red-bg)', borderRadius: 'var(--radius)', padding: '8px 10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>
                      <span>Base: {fmtINR(inv.amount)}</span>
                      <span style={{ color: 'var(--red)', fontWeight: 600 }}>+{fmtINR(id.interest)} penalty</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--red)' }}>{fmtINR(id.claim)}</div>
                      <span className="badge badge-red" style={{ fontSize: 9 }}>Total Claim</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {sel ? (
            <div>
              {/* Legal Claim Breakdown */}
              <div className="card" style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700 }}>{sel.company}</div>
                    <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{sel.contact} · {sel.phone}</div>
                  </div>
                  <button className="btn btn-sm" onClick={() => openDetail(sel)}>Full Details →</button>
                </div>
                {(() => {
                  const id = idata(sel);
                  return (
                    <div style={{ marginBottom: 14 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>⚖ Legal Claim Breakdown</div>
                      <div style={{ background: 'var(--surface2)', borderRadius: 'var(--radius)', overflow: 'hidden', border: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
                          <span style={{ fontSize: 12, color: 'var(--text2)' }}>Base Invoice Amount</span>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>{fmtINR(sel.amount)}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid var(--border)', background: 'var(--red-bg)' }}>
                          <span style={{ fontSize: 12, color: 'var(--red)' }}>MSMED Penalty ({id.rate}% p.a. × {id.days}d)</span>
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--red)' }}>+{fmtINR(id.interest)}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 14px' }}>
                          <span style={{ fontSize: 13, fontWeight: 700 }}>Total Legal Claim</span>
                          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--red)' }}>{fmtINR(id.claim)}</span>
                        </div>
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 6, textAlign: 'right' }}>{id.basis}</div>
                    </div>
                  );
                })()}
                <div className="info-box" style={{ marginBottom: 0 }}>
                  <strong>MSME Samadhaan Eligibility:</strong> This invoice has been overdue for {idata(sel).days} days. Under MSMED Act Section 15, payment was due within 45 days. You are entitled to compound interest at 3× the RBI notified rate (19.5% p.a.).
                </div>
              </div>

              {/* Notice Generator */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Legal Notice Generator</div>
                    <div className="card-sub">AI-drafted formal Letter Before Action</div>
                  </div>
                  <span className="badge badge-red">MSMED Act 2006</span>
                </div>
                <button className="btn btn-danger btn-lg" style={{ width: '100%', justifyContent: 'center', marginBottom: 12 }} onClick={generateNotice} disabled={loading}>
                  {loading ? <><span className="spinner"></span>Drafting Legal Notice...</> : '⚖ Generate Legal Notice'}
                </button>
                {loading && <div className="ai-loading"><span className="spinner"></span>Drafting formal legal notice with MSME Act references...</div>}
                {aiNotice && !loading && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Legal Notice Draft</span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className={`btn btn-sm${copied ? ' copy-flash' : ''}`}
                          onClick={() => { navigator.clipboard.writeText(aiNotice).catch(() => {}); setCopied(true); setTimeout(() => setCopied(false), 2000); }}>
                          {copied ? '✓ Copied' : 'Copy'}
                        </button>
                      </div>
                    </div>
                    <div className="ai-box" style={{ fontFamily: 'Georgia, serif', fontSize: 11, lineHeight: 1.9 }}>{aiNotice}</div>
                    <div style={{ marginTop: 10, display: 'flex', gap: 6, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      <button className="btn btn-sm" onClick={generateNotice}>Regenerate</button>
                      <button className="btn btn-sm btn-success" onClick={() => sendViaWhatsApp(sel.phone, aiNotice)}>💬 Send via WhatsApp</button>
                      <button className="btn btn-sm btn-danger" onClick={() => generateLegalPDF(sel, settings)}>📄 Download PDF Notice</button>
                      <button className="btn btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red-light)' }}
                        onClick={() => window.open('https://samadhaan.msme.gov.in', '_blank')}>File MSME Samadhaan →</button>
                    </div>
                  </div>
                )}
                {!aiNotice && !loading && (
                  <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text3)', fontSize: 12 }}>
                    Click above to generate a court-ready legal notice for {sel.company}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 350, textAlign: 'center' }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>⚖</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Select a debtor</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', maxWidth: 220 }}>Choose an invoice from the left to generate a formal MSME legal notice</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
