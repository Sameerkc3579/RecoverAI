/* ─── Debtor Inbox Page — with AI Smart Replies (#10) ─── */
function DebtorInbox({ invoices, openDetail, fetchInvoices }) {
  const [showSimModal, setShowSimModal] = React.useState(false);
  const [simInvoiceId, setSimInvoiceId] = React.useState('');
  const [simMessage, setSimMessage] = React.useState('');
  const [simLoading, setSimLoading] = React.useState(false);
  const [simResult, setSimResult] = React.useState(null);
  const [simError, setSimError] = React.useState('');

  // Smart reply state: { msgKey: { loading, reply, error } }
  const [smartReplies, setSmartReplies] = React.useState({});

  const msgs = invoices.flatMap(inv =>
    (inv.communication_log || []).map(log => ({ ...log, inv }))
  ).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  const activeInvoices = invoices.filter(i => !i.recovered);

  async function handleSimSubmit(e) {
    e.preventDefault();
    if (!simInvoiceId || !simMessage.trim()) return;
    setSimLoading(true); setSimResult(null); setSimError('');
    try {
      const res = await authFetch('/api/webhook/debtor-reply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invoice_id: simInvoiceId, message: simMessage.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setSimResult(data);
      fetchInvoices();
    } catch (err) { setSimError(err.message); }
    setSimLoading(false);
  }

  function closeModal() {
    setShowSimModal(false); setSimMessage(''); setSimInvoiceId('');
    setSimResult(null); setSimError('');
  }

  const intentBadge = intent =>
    intent === 'promise_to_pay' ? 'badge-green' :
    intent === 'dispute'        ? 'badge-red' :
    intent === 'stall'          ? 'badge-amber' : 'badge-gray';

  /* ── Feature #10: AI Smart Reply ── */
  async function generateSmartReply(msg, key) {
    setSmartReplies(prev => ({ ...prev, [key]: { loading: true, reply: '', error: '' } }));
    try {
      const context = `
Debtor: ${msg.inv.company} (${msg.inv.contact})
Invoice: ${msg.inv.invoiceNo}, Amount: ₹${Number(msg.inv.amount).toLocaleString('en-IN')}, ${msg.inv.daysOverdue} days overdue
Debtor's message: "${msg.translated_text || msg.raw_message}"
Detected intent: ${msg.intent || 'unknown'}
Suggested action: ${msg.suggested_action || ''}`;

      const reply = await callAI(SYSTEM_PROMPT,
        `You are a professional, empathetic debt recovery agent for an Indian MSME. 
Draft a short, firm but polite WhatsApp reply (3-4 sentences max) to the debtor based on:
${context}

Rules:
- Be professional and respectful, never aggressive
- If intent is "promise_to_pay": acknowledge promise, confirm amount and deadline
- If intent is "dispute": ask for specific details of the dispute, keep door open
- If intent is "stall": acknowledge concern but firmly ask for a specific payment date
- End with your name (Recovery Team) and a next-step call to action
- Keep it brief, suitable for WhatsApp`
      );
      setSmartReplies(prev => ({ ...prev, [key]: { loading: false, reply, error: '' } }));
    } catch (e) {
      setSmartReplies(prev => ({ ...prev, [key]: { loading: false, reply: '', error: e.message } }));
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">Debtor Inbox</div>
          <div className="page-sub">{msgs.length} message{msgs.length !== 1 ? 's' : ''} · AI-classified replies with Smart Reply</div>
        </div>
        <div className="topbar-actions">
          <button id="btn-simulate-reply" className="btn btn-primary"
            onClick={() => setShowSimModal(true)} title="Simulate an incoming debtor reply to test the NLP pipeline">
            ⚡ Simulate Incoming Reply
          </button>
        </div>
      </div>

      <div className="content">
        {msgs.length === 0 ? (
          <div className="empty" style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div className="empty-icon" style={{ fontSize: 40, marginBottom: 16 }}>📥</div>
            <div className="empty-title" style={{ fontSize: 18, fontWeight: 700 }}>Inbox Zero</div>
            <div className="empty-sub" style={{ color: 'var(--text3)', marginBottom: 20 }}>
              No debtor replies yet. Use the ⚡ button above to simulate one!
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {msgs.map((msg, i) => {
              const key = `${i}_${msg.timestamp}`;
              const sr = smartReplies[key] || {};
              return (
                <div key={i} className="card inbox-card" style={{ overflow: 'hidden' }}>
                  {/* Message Header */}
                  <div className="inbox-msg-grid" onClick={() => openDetail(msg.inv)} style={{ cursor: 'pointer' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{msg.inv.company}</div>
                      <div style={{ fontSize: 11, color: 'var(--text3)' }}>{msg.inv.contact}</div>
                      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 8 }}>{new Date(msg.timestamp).toLocaleString('en-IN')}</div>
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Original: "{msg.raw_message}"</div>
                      <div style={{ fontSize: 13, fontWeight: 500, wordBreak: 'break-word' }}>{msg.translated_text}</div>
                    </div>
                    <div>
                      <span className={`badge ${intentBadge(msg.intent)}`}>{(msg.intent || 'unknown').replace(/_/g, ' ').toUpperCase()}</span>
                      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>Conf: {msg.confidence}</div>
                      <div style={{ fontSize: 11, color: 'var(--amber)', marginTop: 4 }}>{msg.suggested_action}</div>
                    </div>
                  </div>

                  {/* Smart Reply Section */}
                  <div style={{ borderTop: '1px solid var(--border)', padding: '10px 14px', background: 'var(--surface2)' }}>
                    {!sr.reply && !sr.loading && (
                      <button className="smart-reply-btn" onClick={() => generateSmartReply(msg, key)}>
                        ✨ AI Draft Reply
                      </button>
                    )}
                    {sr.loading && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text3)' }}>
                        <span className="spinner" style={{ width: 14, height: 14 }} /> Drafting smart reply...
                      </div>
                    )}
                    {sr.error && <div style={{ fontSize: 12, color: 'var(--red)' }}>❌ {sr.error}</div>}
                    {sr.reply && (
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--purple)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>✨ AI Draft Reply</span>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button className="btn btn-sm" onClick={() => { navigator.clipboard.writeText(sr.reply); }}>Copy</button>
                            <button className="btn btn-sm btn-success" onClick={() => window.open(`https://wa.me/${(msg.inv.phone||'').replace(/\D/g,'')}?text=${encodeURIComponent(sr.reply)}`, '_blank')}>
                              💬 Send via WhatsApp
                            </button>
                            <button className="btn btn-sm" onClick={() => generateSmartReply(msg, key)}>↺ Regen</button>
                            <button className="btn btn-sm" onClick={() => setSmartReplies(prev => { const n = {...prev}; delete n[key]; return n; })}>✕</button>
                          </div>
                        </div>
                        <div className="ai-box" style={{ fontSize: 12, padding: '10px 14px', minHeight: 'auto', lineHeight: 1.6 }}>{sr.reply}</div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Simulate Incoming Reply Modal */}
      {showSimModal && (
        <div className="overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <div>
                <div className="modal-title">⚡ Simulate Incoming Reply</div>
                <div className="modal-sub">Test the NLP pipeline — select an invoice and type a debtor message</div>
              </div>
              <button className="close-btn" onClick={closeModal}>×</button>
            </div>

            {!simResult ? (
              <form onSubmit={handleSimSubmit}>
                <div className="form-group">
                  <label className="form-label" htmlFor="sim-invoice-select">Invoice / Debtor</label>
                  <select id="sim-invoice-select" className="form-input" value={simInvoiceId} onChange={e => setSimInvoiceId(e.target.value)} required>
                    <option value="">— Select an invoice —</option>
                    {activeInvoices.map(inv => (
                      <option key={inv.id} value={inv.id}>{inv.company} · {inv.invoiceNo} · ₹{Number(inv.amount).toLocaleString('en-IN')}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="sim-message-input">Debtor Message</label>
                  <textarea id="sim-message-input" className="form-input" rows={4}
                    placeholder='e.g. "Kal payment bhej deta hoon sir" or "Wrong amount hai, dispute karna chahta hoon"'
                    value={simMessage} onChange={e => setSimMessage(e.target.value)}
                    style={{ resize: 'vertical', fontFamily: 'inherit' }} required />
                  <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
                    💡 Try Hindi/Hinglish: "kal bhej dunga", "galat invoice hai", "boss nahi hain abhi"
                  </div>
                </div>
                {simError && <div className="danger-box" style={{ marginBottom: 12 }}>❌ {simError}</div>}
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button type="button" className="btn" onClick={closeModal}>Cancel</button>
                  <button type="submit" id="btn-simulate-submit" className="btn btn-primary" disabled={simLoading || !simInvoiceId || !simMessage.trim()}>
                    {simLoading ? <><span className="spinner" />&nbsp;Processing NLP...</> : '⚡ Send & Analyse'}
                  </button>
                </div>
              </form>
            ) : (
              <div>
                <div className="info-box" style={{ marginBottom: 16 }}>
                  ✅ Reply processed! The Inbox has been refreshed with the new AI analysis.
                </div>
                {simResult.fallback_mode && (
                  <div className="warn-box" style={{ marginBottom: 12 }}>
                    ⚡ <strong>Heuristic Fallback Active</strong> — Gemini API quota reached. Intent classified using keyword matching.
                  </div>
                )}
                <div style={{ background: 'var(--surface2)', borderRadius: 'var(--radius)', padding: 14, marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', color: 'var(--text3)' }}>AI Analysis Result</span>
                    <span className={`badge ${intentBadge(simResult.intent)}`} style={{ fontSize: 12 }}>
                      {(simResult.intent || 'unknown').replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {[['Translation', simResult.translated_text], ['Confidence', simResult.confidence?.toUpperCase()], ['Suggested Action', simResult.suggested_action]].map(([lbl, val]) => (
                      <div key={lbl}>
                        <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 2 }}>{lbl}</div>
                        <div style={{ fontSize: 12, fontWeight: 500 }}>{val}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="btn" onClick={() => { setSimResult(null); setSimMessage(''); setSimInvoiceId(''); setSimError(''); }}>← Send Another</button>
                  <button className="btn btn-primary" onClick={closeModal}>Done</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
