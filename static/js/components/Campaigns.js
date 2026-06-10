/* ─── Campaigns Page + Campaign Runner Modal ─── */
function Campaigns({ invoices, settings }) {
  const [showRunner, setShowRunner] = React.useState(false);
  const [sort, setSort] = React.useState('days_desc');

  const targets = invoices
    .filter(i => !i.recovered && i.daysOverdue > 0)
    .sort((a, b) => {
      if (sort === 'days_desc')   return b.daysOverdue - a.daysOverdue;
      if (sort === 'days_asc')    return a.daysOverdue - b.daysOverdue;
      if (sort === 'amount_desc') return (b.interest_data?.total_claim || b.amount) - (a.interest_data?.total_claim || a.amount);
      if (sort === 'amount_asc')  return (a.interest_data?.total_claim || a.amount) - (b.interest_data?.total_claim || b.amount);
      return 0;
    });

  const totalClaim = targets.reduce((s, i) => s + (i.interest_data?.total_claim || i.amount), 0);
  const avgDays = targets.length ? Math.round(targets.reduce((s, i) => s + i.daysOverdue, 0) / targets.length) : 0;

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">Campaigns</div>
          <div className="page-sub">{targets.length} active overdue invoices ready for bulk recovery</div>
        </div>
        <div className="topbar-actions">
          <span className="badge badge-amber" style={{ fontSize: 11 }}>Total Claim: {fmtINR(totalClaim)}</span>
        </div>
      </div>
      <div className="content">

        {/* Hero */}
        <div style={{ background: 'linear-gradient(135deg, var(--amber-bg) 0%, var(--surface) 100%)', border: '2px solid var(--amber-light)', borderRadius: 'var(--radius-xl)', padding: '28px 32px', marginBottom: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--amber-dark)', marginBottom: 4 }}>🚀 Rapid Fire WhatsApp Campaign</div>
            <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.6 }}>
              Process <strong>{targets.length} debtors</strong> one‑by‑one without triggering popup blockers.<br />
              AI drafts each message → you review → click Send & Next → repeat.
            </div>
          </div>
          <button id="btn-start-whatsapp-campaign" className="btn btn-primary btn-lg"
            style={{ padding: '14px 32px', fontSize: 16, fontWeight: 700, borderRadius: 'var(--radius-lg)', boxShadow: '0 4px 16px rgba(186,117,23,0.3)' }}
            onClick={() => setShowRunner(true)} disabled={targets.length === 0}>
            💬 Start WhatsApp Campaign
          </button>
        </div>

        {/* Summary Metrics */}
        <div className="admin-metric-grid">
          <div className="metric-card"><div className="metric-label">🎯 Campaign Targets</div><div className="metric-value" style={{ color: 'var(--amber)' }}>{targets.length}</div><div className="metric-change"><span style={{ fontSize: 11, color: 'var(--text3)' }}>Active overdue invoices</span></div></div>
          <div className="metric-card"><div className="metric-label">💰 Total Claim Value</div><div className="metric-value" style={{ color: 'var(--red)' }}>{fmtINR(totalClaim)}</div><div className="metric-change"><span style={{ fontSize: 11, color: 'var(--text3)' }}>Including MSMED penalties</span></div></div>
          <div className="metric-card"><div className="metric-label">📅 Avg Days Overdue</div><div className="metric-value">{avgDays}d</div><div className="metric-change"><span style={{ fontSize: 11, color: 'var(--text3)' }}>Across all targets</span></div></div>
        </div>

        {/* Target List */}
        <div className="card" style={{ padding: 0, marginTop: 16 }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>Campaign Target List</div>
              <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>Overdue invoices eligible for WhatsApp recovery blitz</div>
            </div>
            <select className="filter-select" value={sort} onChange={e => setSort(e.target.value)}>
              <option value="days_desc">Most overdue first</option>
              <option value="days_asc">Least overdue first</option>
              <option value="amount_desc">Highest claim first</option>
              <option value="amount_asc">Lowest claim first</option>
            </select>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 40, textAlign: 'center' }}>#</th>
                  <th>Company</th>
                  <th>Contact</th>
                  <th>Invoice</th>
                  <th>Days Overdue</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Total Claim</th>
                </tr>
              </thead>
              <tbody>
                {targets.length === 0 && (
                  <tr className="mobile-table-row"><td colSpan={7} className="mobile-td" style={{ justifyContent: 'center' }}>
                    <div className="empty"><div className="empty-icon">🎉</div><div className="empty-title">No overdue invoices</div><div className="empty-sub">All invoices are recovered or current!</div></div>
                  </td></tr>
                )}
                {targets.map((inv, idx) => {
                  const claim = inv.interest_data?.total_claim || inv.amount;
                  return (
                    <tr key={inv.id} className="mobile-table-row">
                      <td data-label="#" className="mobile-td" style={{ textAlign: 'center', fontWeight: 600, color: 'var(--text3)', fontSize: 12 }}>{idx + 1}</td>
                      <td data-label="Company" className="mobile-td">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--amber-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--amber-dark)', flexShrink: 0 }}>{getInitials(inv.company)}</div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{inv.company}</div>
                        </div>
                      </td>
                      <td data-label="Contact" className="mobile-td" style={{ fontSize: 12, color: 'var(--text2)' }}>{inv.contact}</td>
                      <td data-label="Invoice" className="mobile-td"><span className="tag">{inv.invoiceNo}</span></td>
                      <td data-label="Days Overdue" className="mobile-td"><span className={`badge ${daysBadge(inv.daysOverdue, false)}`}>{inv.daysOverdue}d</span></td>
                      <td data-label="Status" className="mobile-td"><span className={`badge ${STATUS_META[inv.status]?.color || 'badge-gray'}`}>{STATUS_META[inv.status]?.label || inv.status}</span></td>
                      <td data-label="Total Claim" className="mobile-td" style={{ textAlign: 'right' }}>
                        <div style={{ fontWeight: 700, fontSize: 13 }}>{fmtINR(claim)}</div>
                        {inv.interest_data?.interest_accrued > 0 && (
                          <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 2 }}>+{fmtINR(inv.interest_data.interest_accrued)} penalty</div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {targets.length > 0 && (
            <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text3)' }}>
              <span>{targets.length} invoice{targets.length !== 1 ? 's' : ''} in campaign queue</span>
              <span>Total: <strong style={{ color: 'var(--amber)' }}>{fmtINR(totalClaim)}</strong></span>
            </div>
          )}
        </div>
      </div>

      {showRunner && <CampaignRunnerModal targets={targets} settings={settings} onClose={() => setShowRunner(false)} />}
    </div>
  );
}

/* ─── Campaign Runner Modal (Rapid Fire WhatsApp Engine) ─── */
function CampaignRunnerModal({ targets, settings, onClose }) {
  const [currentIdx, setCurrentIdx] = React.useState(0);
  const [aiMsg, setAiMsg] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [sentCount, setSentCount] = React.useState(0);
  const [finished, setFinished] = React.useState(false);
  const [skippedIds, setSkippedIds] = React.useState(new Set());

  const inv = targets[currentIdx] || null;
  const total = targets.length;
  const progressPct = total > 0 ? Math.round(((sentCount + skippedIds.size) / total) * 100) : 0;

  React.useEffect(() => {
    if (!inv || finished) return;
    let cancelled = false;
    async function generate() {
      setLoading(true); setAiMsg('');
      const idata = inv.interest_data || {};
      const penalty = idata.interest_accrued || 0;
      const totalClaim = idata.total_claim || inv.amount;
      const prompt = inv.daysOverdue >= 45
        ? `Draft a WhatsApp recovery message for:\nDebtor: ${inv.contact}, ${inv.company}\nPhone: ${inv.phone}\nInvoice: ${inv.invoiceNo}\nBase Amount: ${fmtINR(inv.amount)}\nMSMED Act Penalty: ${fmtINR(penalty)}\nTotal Legal Claim: ${fmtINR(totalClaim)}\nDays Overdue: ${inv.daysOverdue}\nSender: ${settings.businessName} (${settings.ownerName})\nTone: firm, cite MSMED Act 2006. Max 5 lines. State exact penalty and total claim.`
        : `Draft a WhatsApp recovery message for:\nDebtor: ${inv.contact}, ${inv.company}\nPhone: ${inv.phone}\nInvoice: ${inv.invoiceNo} for ${fmtINR(inv.amount)}\nDue: ${inv.dueDate} (${inv.daysOverdue} days overdue)\nSender: ${settings.businessName} (${settings.ownerName})\nTone: polite but firm. Max 5 lines. Include payment UPI request mention.`;
      try {
        const msg = await callAI(SYSTEM_PROMPT, prompt);
        if (!cancelled) setAiMsg(msg);
      } catch (e) {
        if (!cancelled) setAiMsg(`Error generating message: ${e.message}`);
      }
      if (!cancelled) setLoading(false);
    }
    generate();
    return () => { cancelled = true; };
  }, [currentIdx, finished]);

  function sendAndNext() {
    if (!inv || !aiMsg) return;
    sendViaWhatsApp(inv.phone, aiMsg);
    setSentCount(c => c + 1); advanceToNext();
  }
  function skipAndNext() {
    if (!inv) return;
    setSkippedIds(prev => { const s = new Set(prev); s.add(inv.id); return s; });
    advanceToNext();
  }
  function advanceToNext() {
    if (currentIdx + 1 >= total) setFinished(true);
    else setCurrentIdx(i => i + 1);
  }

  if (finished) return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🎉</div>
        <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 8, color: 'var(--green)' }}>Campaign Complete!</div>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 20, lineHeight: 1.6 }}>
          You processed <strong>{total}</strong> debtor{total !== 1 ? 's' : ''}.<br />
          <span style={{ color: 'var(--green)' }}><strong>{sentCount}</strong> sent via WhatsApp</span>
          {skippedIds.size > 0 && <span> · <span style={{ color: 'var(--text3)' }}>{skippedIds.size} skipped</span></span>}
        </div>
        <div className="progress" style={{ height: 8, marginBottom: 20 }}>
          <div className="progress-fill progress-green" style={{ width: '100%' }}></div>
        </div>
        <button className="btn btn-primary btn-lg" onClick={onClose} style={{ padding: '12px 40px' }}>Done</button>
      </div>
    </div>
  );

  if (!inv) return null;
  const claim = inv.interest_data?.total_claim || inv.amount;

  return (
    <div className="overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()} style={{ maxWidth: 640 }}>
        <div className="modal-header">
          <div>
            <div className="modal-title">💬 WhatsApp Campaign Runner</div>
            <div className="modal-sub">Process each debtor one at a time — no popup blockers!</div>
          </div>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--amber-dark)' }}>Sending {currentIdx + 1} of {total}</span>
            <span style={{ fontSize: 12, color: 'var(--text3)' }}>{sentCount} sent · {skippedIds.size} skipped</span>
          </div>
          <div className="progress" style={{ height: 8 }}>
            <div className="progress-fill progress-amber" style={{ width: progressPct + '%', transition: 'width 0.4s ease' }}></div>
          </div>
        </div>
        <div style={{ background: 'var(--surface2)', borderRadius: 'var(--radius-lg)', padding: '16px 18px', marginBottom: 16, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--amber-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700, color: 'var(--amber-dark)' }}>{getInitials(inv.company)}</div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700 }}>{inv.company}</div>
                <div style={{ fontSize: 12, color: 'var(--text3)' }}>{inv.contact} · {inv.phone}</div>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className={`badge ${daysBadge(inv.daysOverdue, false)}`}>{inv.daysOverdue}d overdue</span>
              <div style={{ fontSize: 15, fontWeight: 800, marginTop: 4, color: 'var(--amber)' }}>{fmtINR(claim)}</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span className="tag">{inv.invoiceNo}</span>
            <span className={`badge ${STATUS_META[inv.status]?.color || 'badge-gray'}`} style={{ fontSize: 10 }}>{STATUS_META[inv.status]?.label}</span>
            {inv.interest_data?.interest_accrued > 0 && <span className="badge badge-red" style={{ fontSize: 10 }}>+{fmtINR(inv.interest_data.interest_accrued)} penalty</span>}
          </div>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 6 }}>Drafted WhatsApp Message</div>
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '32px 0' }}>
              <div className="spinner" style={{ width: 20, height: 20 }}></div>
              <div style={{ fontSize: 12, color: 'var(--text3)' }}>AI is drafting message for {inv.company}...</div>
            </div>
          ) : (
            <div className="ai-box" style={{ minHeight: 90, maxHeight: 200 }}>{aiMsg}</div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn" onClick={skipAndNext} disabled={loading}>Skip →</button>
          <button id="btn-send-and-next" className="btn btn-primary btn-lg"
            onClick={sendAndNext} disabled={loading || !aiMsg}
            style={{ flex: 1, justifyContent: 'center', padding: '14px 24px', fontSize: 16, fontWeight: 700, borderRadius: 'var(--radius-lg)', boxShadow: '0 4px 16px rgba(186,117,23,0.25)' }}>
            💬 Send & Next
          </button>
          <button className="btn" onClick={onClose} style={{ color: 'var(--text3)' }}>Stop</button>
        </div>
      </div>
    </div>
  );
}
