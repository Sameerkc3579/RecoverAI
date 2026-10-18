/* ─── Debtor Inbox — Real WhatsApp Webhook Messages + Simulate ─── */
function DebtorInbox({ invoices, openDetail, fetchInvoices }) {
  const [showSimModal, setShowSimModal] = React.useState(false);
  const [simInvoiceId, setSimInvoiceId]   = React.useState('');
  const [simMessage, setSimMessage]       = React.useState('');
  const [simLoading, setSimLoading]       = React.useState(false);
  const [simResult, setSimResult]         = React.useState(null);
  const [simError, setSimError]           = React.useState('');

  // Live WhatsApp messages from /api/whatsapp/messages
  const [waMsgs, setWaMsgs]           = React.useState([]);
  const [waLoading, setWaLoading]     = React.useState(false);
  const [waStatus, setWaStatus]       = React.useState(null); // webhook config status
  const [activeTab, setActiveTab]     = React.useState('all'); // 'all' | 'whatsapp' | 'simulated'

  // Smart reply state: { msgKey: { loading, reply, error } }
  const [smartReplies, setSmartReplies] = React.useState({});

  // Merge simulated (from communication_log) + real (from WA webhook)
  const simulatedMsgs = invoices.flatMap(inv =>
    (inv.communication_log || []).map(log => ({ ...log, inv, _source: 'simulated' }))
  );

  const liveMsgs = waMsgs.map(m => ({
    ...m,
    _source: 'whatsapp',
    raw_message: m.raw_message,
    translated_text: m.translated_text,
    intent: m.intent,
    confidence: m.confidence,
    suggested_action: m.suggested_action,
    inv: invoices.find(i => i.id === m.invoice_id) || {
      company: m.sender_name || m.from_number,
      contact: m.from_number,
      invoiceNo: '—',
      amount: 0,
      daysOverdue: 0,
      phone: m.from_number,
      id: null,
    },
  }));

  const allMsgs = [...simulatedMsgs, ...liveMsgs]
    .sort((a, b) => new Date(b.timestamp || b.received_at) - new Date(a.timestamp || a.received_at));

  const displayMsgs =
    activeTab === 'whatsapp'  ? allMsgs.filter(m => m._source === 'whatsapp') :
    activeTab === 'simulated' ? allMsgs.filter(m => m._source === 'simulated') :
    allMsgs;

  const activeInvoices = invoices.filter(i => !i.recovered);

  // Fetch live WA messages + status on mount
  React.useEffect(() => {
    fetchWaMessages();
    fetchWaStatus();
  }, []);

  async function fetchWaMessages() {
    setWaLoading(true);
    try {
      const res = await authFetch('/api/whatsapp/messages?limit=100');
      if (res.ok) {
        const data = await res.json();
        setWaMsgs(data);
      }
    } catch (e) { console.error('Failed to load WA messages', e); }
    setWaLoading(false);
  }

  async function fetchWaStatus() {
    try {
      const res = await authFetch('/api/whatsapp/status');
      if (res.ok) setWaStatus(await res.json());
    } catch (e) { /* silent */ }
  }

  async function handleSimSubmit(e) {
    e.preventDefault();
    if (!simInvoiceId || !simMessage.trim()) return;
    setSimLoading(true); setSimResult(null); setSimError('');
    try {
      const res = await authFetch('/api/debtor-reply', {
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

  const intentEmoji = intent =>
    intent === 'promise_to_pay' ? '✅' :
    intent === 'dispute'        ? '⚠️' :
    intent === 'stall'          ? '⏳' : '❓';

  async function generateSmartReply(msg, key) {
    setSmartReplies(prev => ({ ...prev, [key]: { loading: true, reply: '', error: '' } }));
    try {
      const context = `Debtor: ${msg.inv.company} (${msg.inv.contact})
Invoice: ${msg.inv.invoiceNo}, Amount: ₹${Number(msg.inv.amount).toLocaleString('en-IN')}, ${msg.inv.daysOverdue} days overdue
Debtor message: "${msg.translated_text || msg.raw_message}"
Detected intent: ${msg.intent || 'unknown'}`;
      const reply = await callAI(SYSTEM_PROMPT,
        `Draft a short, firm but polite WhatsApp reply (3-4 sentences max) based on:
${context}
Rules: professional, respectful, never aggressive.
If promise_to_pay: confirm amount & deadline.
If dispute: ask for specifics, keep door open.
If stall: acknowledge but ask for a specific payment date.
End: "— RecoverAI Collections"`
      );
      setSmartReplies(prev => ({ ...prev, [key]: { loading: false, reply, error: '' } }));
    } catch (e) {
      setSmartReplies(prev => ({ ...prev, [key]: { loading: false, reply: '', error: e.message } }));
    }
  }

  async function sendManualReply(toNumber, text) {
    try {
      const res = await authFetch('/api/whatsapp/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_number: toNumber, message: text }),
      });
      if (!res.ok) {
        const d = await res.json();
        alert('Send failed: ' + (d.detail || 'Unknown error'));
      } else {
        alert('✅ Message sent via WhatsApp!');
      }
    } catch (e) { alert('Send error: ' + e.message); }
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  const waConfigured = waStatus?.fully_configured;

  return (
    <div>
      {/* ── Topbar ── */}
      <div className="topbar">
        <div>
          <div className="page-title">Debtor Inbox</div>
          <div className="page-sub">
            {allMsgs.length} message{allMsgs.length !== 1 ? 's' : ''} ·&nbsp;
            {liveMsgs.length} live via WhatsApp · {simulatedMsgs.length} simulated
          </div>
        </div>
        <div className="topbar-actions">
          <button className="btn" onClick={() => { fetchWaMessages(); fetchWaStatus(); }}
            title="Refresh live messages from WhatsApp webhook">
            ↻ Refresh
          </button>
          <button id="btn-simulate-reply" className="btn btn-primary"
            onClick={() => setShowSimModal(true)}
            title="Simulate an incoming debtor reply to test the NLP pipeline">
            ⚡ Simulate Incoming Reply
          </button>
        </div>
      </div>

      <div className="content">

        {/* ── Webhook Status Banner ── */}
        {waStatus && (
          <div style={{
            marginBottom: 16, padding: '10px 16px', borderRadius: 10,
            background: waConfigured ? 'var(--green-bg)' : 'var(--amber-bg)',
            border: `1px solid ${waConfigured ? 'var(--green)' : 'var(--amber)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>{waConfigured ? '🟢' : '🟡'}</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13, color: waConfigured ? 'var(--green)' : 'var(--amber-dark)' }}>
                  {waConfigured ? 'WhatsApp Webhook Active' : 'WhatsApp Webhook Not Fully Configured'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                  {waConfigured
                    ? `Webhook URL: /api/webhooks/whatsapp · Auto-reply: ${waStatus.auto_reply_enabled ? 'ON' : 'OFF'}`
                    : 'Set WHATSAPP_VERIFY_TOKEN, WHATSAPP_PHONE_NUMBER_ID, and WHATSAPP_ACCESS_TOKEN in your .env to activate.'}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[
                ['Verify Token', waStatus.verify_token_set],
                ['HMAC Secret', waStatus.webhook_secret_set],
                ['Phone ID', waStatus.phone_number_id_set],
                ['Access Token', waStatus.access_token_set],
              ].map(([label, ok]) => (
                <span key={label} style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 12,
                  background: ok ? 'var(--green)' : '#999', color: '#fff',
                }}>
                  {ok ? '✓' : '✗'} {label}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* ── Tab Filter ── */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {[
            ['all',       `All (${allMsgs.length})`,          'badge-gray'],
            ['whatsapp',  `💬 Live WhatsApp (${liveMsgs.length})`, 'badge-green'],
            ['simulated', `⚡ Simulated (${simulatedMsgs.length})`, 'badge-blue'],
          ].map(([tab, label, cls]) => (
            <div key={tab}
              className={`chip${activeTab === tab ? ' selected' : ''}`}
              onClick={() => setActiveTab(tab)}
              style={{ cursor: 'pointer' }}>
              {label}
            </div>
          ))}
          {waLoading && <span style={{ fontSize: 12, color: 'var(--text3)', alignSelf: 'center' }}>
            <span className="spinner" style={{ width: 12, height: 12, display: 'inline-block', marginRight: 4 }} />
            Loading live messages...
          </span>}
        </div>

        {/* ── Message List ── */}
        {displayMsgs.length === 0 ? (
          <div className="empty" style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div className="empty-icon" style={{ fontSize: 40, marginBottom: 16 }}>📥</div>
            <div className="empty-title" style={{ fontSize: 18, fontWeight: 700 }}>Inbox Zero</div>
            <div className="empty-sub" style={{ color: 'var(--text3)', marginBottom: 20 }}>
              {activeTab === 'whatsapp'
                ? 'No live WhatsApp messages yet. Configure the webhook and messages from debtors will appear here automatically.'
                : 'No messages. Use the ⚡ Simulate button above to test the NLP pipeline!'}
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {displayMsgs.map((msg, i) => {
              const key = `${i}_${msg.timestamp || msg.received_at}`;
              const sr  = smartReplies[key] || {};
              const isLive = msg._source === 'whatsapp';

              return (
                <div key={i} className="card inbox-card" style={{ overflow: 'hidden' }}>

                  {/* Source badge */}
                  <div style={{
                    padding: '4px 14px',
                    background: isLive ? 'var(--green-bg)' : 'var(--blue-bg)',
                    borderBottom: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px',
                      color: isLive ? 'var(--green)' : 'var(--blue)',
                    }}>
                      {isLive ? '💬 Live WhatsApp Message' : '⚡ Simulated Reply'}
                    </span>
                    {isLive && msg.from_number && (
                      <span style={{ fontSize: 10, color: 'var(--text3)' }}>
                        From: {msg.from_number} {msg.sender_name ? `(${msg.sender_name})` : ''}
                        {msg.matched === false && (
                          <span style={{ marginLeft: 8, color: 'var(--amber)', fontWeight: 700 }}>
                            ⚠ Unmatched — no invoice found for this number
                          </span>
                        )}
                      </span>
                    )}
                  </div>

                  {/* Message Body */}
                  <div className="inbox-msg-grid"
                    onClick={() => msg.inv.id && openDetail(msg.inv)}
                    style={{ cursor: msg.inv.id ? 'pointer' : 'default' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{msg.inv.company}</div>
                      <div style={{ fontSize: 11, color: 'var(--text3)' }}>{msg.inv.contact || msg.from_number}</div>
                      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 8 }}>
                        {new Date(msg.timestamp || msg.received_at).toLocaleString('en-IN')}
                      </div>
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        Original: "{msg.raw_message}"
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 500, wordBreak: 'break-word' }}>
                        {msg.translated_text}
                      </div>
                    </div>
                    <div>
                      <span style={{ fontSize: 18, marginRight: 6 }}>{intentEmoji(msg.intent)}</span>
                      <span className={`badge ${intentBadge(msg.intent)}`}>
                        {(msg.intent || 'unknown').replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>Conf: {msg.confidence}</div>
                      <div style={{ fontSize: 11, color: 'var(--amber)', marginTop: 4 }}>{msg.suggested_action}</div>
                      {msg.fallback_mode && (
                        <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4, fontStyle: 'italic' }}>
                          ⚡ Heuristic fallback
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Smart Reply Section */}
                  <div style={{ borderTop: '1px solid var(--border)', padding: '10px 14px', background: 'var(--surface2)' }}>
                    {!sr.reply && !sr.loading && (
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <button className="smart-reply-btn" onClick={() => generateSmartReply(msg, key)}>
                          ✨ AI Draft Reply
                        </button>
                        {isLive && waConfigured && msg.inv.phone && (
                          <button className="btn btn-sm btn-success"
                            onClick={() => {
                              const draft = smartReplies[key]?.reply;
                              const phone = (msg.from_number || msg.inv.phone || '').replace(/\D/g, '');
                              if (draft) sendManualReply(phone, draft);
                              else alert('Generate an AI draft first.');
                            }}>
                            💬 Send via WhatsApp API
                          </button>
                        )}
                      </div>
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
                          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--purple)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                            ✨ AI Draft Reply
                          </span>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button className="btn btn-sm" onClick={() => navigator.clipboard.writeText(sr.reply)}>Copy</button>
                            {isLive && waConfigured ? (
                              <button className="btn btn-sm btn-success"
                                onClick={() => sendManualReply((msg.from_number || msg.inv.phone || '').replace(/\D/g,''), sr.reply)}>
                                💬 Send via WA API ↗
                              </button>
                            ) : (
                              <button className="btn btn-sm btn-success"
                                onClick={() => window.open(`https://wa.me/${toWhatsAppNumber(msg.inv.phone)}?text=${encodeURIComponent(sr.reply)}`, '_blank')}>
                                💬 Send via WA Link ↗
                              </button>
                            )}
                            <button className="btn btn-sm" onClick={() => generateSmartReply(msg, key)}>↺ Regen</button>
                            <button className="btn btn-sm" onClick={() => setSmartReplies(prev => { const n={...prev}; delete n[key]; return n; })}>✕</button>
                          </div>
                        </div>
                        <div className="ai-box" style={{ fontSize: 12, padding: '10px 14px', minHeight: 'auto', lineHeight: 1.6 }}>
                          {sr.reply}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Simulate Incoming Reply Modal ── */}
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
                  <select id="sim-invoice-select" className="form-input"
                    value={simInvoiceId} onChange={e => setSimInvoiceId(e.target.value)} required>
                    <option value="">— Select an invoice —</option>
                    {activeInvoices.map(inv => (
                      <option key={inv.id} value={inv.id}>
                        {inv.company} · {inv.invoiceNo} · ₹{Number(inv.amount).toLocaleString('en-IN')}
                      </option>
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
                  <button type="submit" id="btn-simulate-submit" className="btn btn-primary"
                    disabled={simLoading || !simInvoiceId || !simMessage.trim()}>
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
                    <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', color: 'var(--text3)' }}>
                      AI Analysis Result
                    </span>
                    <span className={`badge ${intentBadge(simResult.intent)}`} style={{ fontSize: 12 }}>
                      {(simResult.intent || 'unknown').replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {[
                      ['Translation', simResult.translated_text],
                      ['Confidence', simResult.confidence?.toUpperCase()],
                      ['Suggested Action', simResult.suggested_action],
                    ].map(([lbl, val]) => (
                      <div key={lbl}>
                        <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 2 }}>{lbl}</div>
                        <div style={{ fontSize: 12, fontWeight: 500 }}>{val}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="btn" onClick={() => { setSimResult(null); setSimMessage(''); setSimInvoiceId(''); setSimError(''); }}>
                    ← Send Another
                  </button>
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
