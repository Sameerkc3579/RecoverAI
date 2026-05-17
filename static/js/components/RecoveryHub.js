/* ─── Recovery Hub Page ─── */
function RecoveryHub({ invoices, openDetail, settings }) {
  const [selected, setSelected] = React.useState(null);
  const [msgType, setMsgType] = React.useState('whatsapp');
  const [aiMsg, setAiMsg] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const active = invoices.filter(i => !i.recovered).sort((a, b) => b.daysOverdue - a.daysOverdue);
  const sel = selected ? (invoices.find(i => i.id === selected) || null) : null;

  async function generate() {
    if (!sel) return;
    setLoading(true); setAiMsg(''); setCopied(false);
    const idata = sel.interest_data || {};
    const penalty = idata.interest_accrued || 0;
    const totalClaim = idata.total_claim || sel.amount;
    const prompts = {
      whatsapp: sel.daysOverdue >= 45
        ? `Draft a WhatsApp recovery message for:\nDebtor: ${sel.contact}, ${sel.company}\nPhone: ${sel.phone}\nInvoice: ${sel.invoiceNo}\nBase Amount: ${fmtINR(sel.amount)}\nMSMED Act Penalty (19.5% p.a. compound): ${fmtINR(penalty)}\nTotal Legal Claim: ${fmtINR(totalClaim)}\nDays Overdue: ${sel.daysOverdue}\nSender: ${settings.businessName} (${settings.ownerName})\nTone: firm, cite MSMED Act 2006. Max 5 lines. State exact penalty and total claim. Mention MSME Samadhaan filing as next step.`
        : `Draft a WhatsApp recovery message for:\nDebtor: ${sel.contact}, ${sel.company}\nPhone: ${sel.phone}\nInvoice: ${sel.invoiceNo} for ${fmtINR(sel.amount)}\nDue: ${sel.dueDate} (${sel.daysOverdue} days overdue)\nSender: ${settings.businessName} (${settings.ownerName})\nTone: polite but firm. Max 5 lines. Include payment UPI request mention.`,
      email: sel.daysOverdue >= 45
        ? `Draft a professional recovery email:\nTo: ${sel.contact} <${sel.email}>\nCompany: ${sel.company}\nInvoice: ${sel.invoiceNo}\nBase Amount: ${fmtINR(sel.amount)}\nMSMED Act Penalty (19.5% p.a. compound): ${fmtINR(penalty)}\nTotal Legal Claim: ${fmtINR(totalClaim)}\nDays Overdue: ${sel.daysOverdue}\nSender: ${settings.businessName}\nInclude Subject line. Cite MSMED Act 2006 §15-17. State exact interest and total claim. Demand immediate payment to avoid MSME Samadhaan filing.`
        : `Draft a professional recovery email:\nTo: ${sel.contact} <${sel.email}>\nCompany: ${sel.company}\nInvoice: ${sel.invoiceNo} for ${fmtINR(sel.amount)}\nDue: ${sel.dueDate} (${sel.daysOverdue} days overdue)\nSender: ${settings.businessName}\nInclude Subject line. Professional tone. Offer payment arrangement.`,
      legal: `Draft a formal MSME Legal Notice:\nDebtor: ${sel.company}, Contact: ${sel.contact}\nInvoice: ${sel.invoiceNo}\nBase Amount: ${fmtINR(sel.amount)}\nMSMED Act Penalty (19.5% p.a. compound interest with monthly rests): ${fmtINR(penalty)}\nTotal Legal Claim: ${fmtINR(totalClaim)}\nOriginal due: ${sel.dueDate} (now ${sel.daysOverdue} days overdue)\nSender: ${settings.businessName}, ${settings.gstin}\nRequirements: Cite MSMED Act 2006 Sections 15-17, give 15-day ultimatum, state EXACT interest of ${fmtINR(penalty)} at 3x RBI bank rate (19.5% p.a.), demand total of ${fmtINR(totalClaim)}, mention MSME Samadhaan portal filing.`,
    };
    try {
      const msg = await callAI(SYSTEM_PROMPT, prompts[msgType]);
      setAiMsg(msg);
    } catch (e) { setAiMsg(`Error: ${e.message}`); }
    setLoading(false);
  }

  function copy() {
    navigator.clipboard.writeText(aiMsg).catch(() => {});
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  }

  const getTimeline = (inv) => [
    { label: 'Invoice Issued', desc: `${inv.invoiceNo} sent for ${fmtINR(inv.amount)}`, done: true, dot: 'done' },
    { label: '1st Reminder (Day 7)', desc: 'Polite WhatsApp/Email reminder', done: inv.reminders >= 1, dot: inv.reminders >= 1 ? 'done' : inv.daysOverdue >= 7 ? 'active' : 'pending' },
    { label: 'Follow-up (Day 21)', desc: 'Second reminder with payment link', done: inv.reminders >= 2, dot: inv.reminders >= 2 ? 'done' : inv.daysOverdue >= 21 ? 'active' : 'pending' },
    { label: 'Final Notice (Day 35)', desc: 'Strongly worded escalation message', done: inv.reminders >= 3, dot: inv.reminders >= 3 ? 'done' : inv.daysOverdue >= 35 ? 'active' : 'pending' },
    { label: 'Legal Draft (Day 45+)', desc: 'MSME Samadhaan / Letter Before Action', done: inv.daysOverdue >= 45, dot: inv.daysOverdue >= 45 ? 'legal' : 'pending' },
    { label: 'Payment Recovered', desc: 'Invoice closed and marked recovered', done: inv.recovered, dot: inv.recovered ? 'done' : 'pending' },
  ];

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">Recovery Hub</div>
          <div className="page-sub">Generate AI-powered recovery messages for each invoice</div>
        </div>
      </div>
      <div className="content">
        <div className="recovery-grid">

          {/* Invoice list */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Active Invoices ({active.length})
            </div>
            {active.map(inv => (
              <div key={inv.id} className="recovery-item" onClick={() => { setSelected(inv.id); setAiMsg(''); setCopied(false); }}
                style={{ padding: '10px 12px', border: `1.5px solid ${selected === inv.id ? 'var(--amber)' : 'var(--border)'}`, borderRadius: 'var(--radius-lg)', marginBottom: 8, cursor: 'pointer', background: selected === inv.id ? '#FAEEDA' : 'var(--surface)', transition: 'all 0.15s' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{inv.company}</div>
                  <span className={`badge ${daysBadge(inv.daysOverdue, false)}`} style={{ fontSize: 10 }}>{inv.daysOverdue}d</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{inv.invoiceNo}</div>
                <div style={{ fontSize: 13, fontWeight: 700, marginTop: 4, color: 'var(--amber)' }}>{fmtINR(inv.amount)}</div>
              </div>
            ))}
            {active.length === 0 && (
              <div className="empty" style={{ padding: 24 }}>
                <div className="empty-icon">🎉</div>
                <div className="empty-title">All clear!</div>
                <div className="empty-sub">No active invoices</div>
              </div>
            )}
          </div>

          {/* Right panel */}
          {sel ? (
            <div>
              {/* Invoice header */}
              <div className="card" style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700 }}>{sel.company}</div>
                    <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{sel.contact} · {sel.phone} · {sel.email}</div>
                  </div>
                  <span className={`badge ${daysBadge(sel.daysOverdue, false)}`}>{STATUS_META[sel.status]?.label}</span>
                </div>
                <div className="detail-grid">
                  {[['Invoice', sel.invoiceNo], ['Amount', fmtINR(sel.amount)], ['Due Date', sel.dueDate], ['Days Overdue', sel.daysOverdue + 'd overdue'], ['Channel', sel.channel], ['Industry', sel.industry]].map(([l, v]) => (
                    <div key={l} className="detail-item"><div className="detail-label">{l}</div><div className="detail-value">{v}</div></div>
                  ))}
                </div>
                {sel.notes && <div className="info-box" style={{ marginBottom: 0 }}>📝 <strong>Notes:</strong> {sel.notes}</div>}
              </div>

              {/* Timeline */}
              <div className="card" style={{ marginBottom: 12 }}>
                <div className="card-header"><div className="card-title">Recovery Timeline</div></div>
                <div className="timeline">
                  {getTimeline(sel).map((t, i, arr) => (
                    <div key={i} className="timeline-item">
                      <div className="timeline-left">
                        <div className={`timeline-dot ${t.dot}`}></div>
                        {i < arr.length - 1 && <div className="timeline-line"></div>}
                      </div>
                      <div className="timeline-content">
                        <div className="timeline-title" style={{ color: t.done ? 'var(--text)' : 'var(--text3)' }}>{t.label}</div>
                        <div className="timeline-desc">{t.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* AI Generator */}
              <div className="card">
                <div className="card-header">
                  <div className="card-title">AI Message Generator</div>
                  <span className="badge badge-purple">Gemini AI</span>
                </div>
                <div className="tabs" style={{ marginBottom: 12 }}>
                  {[['whatsapp', '💬 WhatsApp'], ['email', '📧 Email'], ['legal', '⚖ Legal Notice']].map(([v, l]) => (
                    <button key={v} className={`tab-btn${msgType === v ? ' active' : ''}`}
                      onClick={() => { setMsgType(v); setAiMsg(''); setCopied(false); }}
                      style={{ color: v === 'legal' && msgType === v ? 'var(--red)' : undefined }}>
                      {l}
                    </button>
                  ))}
                </div>
                {msgType === 'legal' && sel.daysOverdue < 45 && (
                  <div className="warn-box">⚠ Legal notices are most effective after 45 days. This invoice is only {sel.daysOverdue} days overdue.</div>
                )}
                {msgType === 'legal' && sel.daysOverdue >= 45 && (
                  <div className="danger-box">📋 This invoice qualifies for MSME Samadhaan filing (45+ days overdue).</div>
                )}
                <button className="btn btn-primary btn-lg" style={{ width: '100%', justifyContent: 'center', marginBottom: 12 }} onClick={generate} disabled={loading}>
                  {loading ? <><span className="spinner"></span>Generating...</> : `Generate ${msgType === 'whatsapp' ? 'WhatsApp Message' : msgType === 'email' ? 'Email Draft' : 'Legal Notice'}`}
                </button>
                {loading && <div className="ai-loading"><span className="spinner"></span>AI is drafting your message...</div>}
                {aiMsg && !loading && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>Generated Message</span>
                      <button className={`btn btn-sm${copied ? ' copy-flash' : ''}`} onClick={copy}>{copied ? '✓ Copied' : 'Copy'}</button>
                    </div>
                    <div className="ai-box">{aiMsg}</div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      <button className="btn btn-sm" onClick={() => setAiMsg('')}>Clear</button>
                      <button className="btn btn-sm" onClick={generate}>Regenerate</button>
                      {msgType === 'whatsapp' && <button className="btn btn-sm btn-success" onClick={() => sendViaWhatsApp(sel.phone, aiMsg)}>Send via WhatsApp ↗</button>}
                      {msgType === 'legal' && <button className="btn btn-sm btn-danger" onClick={() => generateLegalPDF(sel, settings)}>📄 Download PDF Notice</button>}
                    </div>
                  </div>
                )}
                {!aiMsg && !loading && (
                  <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text3)', fontSize: 12 }}>
                    Click the button above to generate a contextual AI message for {sel.company}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, textAlign: 'center' }}>
              <div style={{ fontSize: 36, marginBottom: 12 }}>←</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Select an invoice to begin</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', maxWidth: 240 }}>Pick any overdue invoice from the left panel to generate AI-powered recovery messages</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
