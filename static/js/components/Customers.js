/* ─── Customers Page — MNC-Grade Profile View ─── */
function Customers({ token, invoices, openDetail }) {
  const [customersData, setCustomersData] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedCustomer, setSelectedCustomer] = React.useState(null);
  const [search, setSearch] = React.useState('');
  const [sortBy, setSortBy] = React.useState('outstanding');
  const [filterStatus, setFilterStatus] = React.useState('all');

  React.useEffect(() => {
    fetch('/api/customers', {
      headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(res => res.json())
    .then(data => {
      setCustomersData(data);
      setLoading(false);
    })
    .catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, [token]);

  // Enrich customers with their invoices for the detail view
  let customers = customersData.map(c => {
    return {
      ...c,
      invoices: invoices.filter(inv => inv.customerId === c.id || inv.company === c.company)
    };
  });

  /* Filter */
  if (search.trim()) {
    const q = search.toLowerCase();
    customers = customers.filter(c =>
      c.company.toLowerCase().includes(q) ||
      (c.contact || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q)
    );
  }
  if (filterStatus === 'risk') {
    customers = customers.filter(c => c.invoices.some(i => !i.recovered && i.daysOverdue >= 45));
  } else if (filterStatus === 'active') {
    customers = customers.filter(c => c.totalOutstanding > 0);
  } else if (filterStatus === 'clear') {
    customers = customers.filter(c => c.totalOutstanding === 0);
  }

  /* Sort */
  customers.sort((a, b) => {
    if (sortBy === 'outstanding') return b.totalOutstanding - a.totalOutstanding;
    if (sortBy === 'recovered') return b.totalRecovered - a.totalRecovered;
    if (sortBy === 'invoices') return b.invoices.length - a.invoices.length;
    if (sortBy === 'name') return a.company.localeCompare(b.company);
    return 0;
  });

  /* Risk helpers */
  function getRisk(c) {
    const hasLegal = c.invoices.some(i => !i.recovered && i.daysOverdue >= 45);
    if (hasLegal) return { label: 'High Risk', cls: 'badge-red', color: 'var(--red)' };
    if (c.totalOutstanding > 0) return { label: 'Active', cls: 'badge-amber', color: 'var(--amber)' };
    return { label: 'Clear', cls: 'badge-green', color: 'var(--green)' };
  }

  /* ── Feature #8: Predictive Risk Score (0-100) ── */
  function getRiskScore(c) {
    let score = 0;
    const total = c.invoices.length;
    if (total === 0) return { score: 0, level: 'low' };

    // Factor 1: % overdue invoices (max 30pts)
    const overdueRatio = c.invoices.filter(i => !i.recovered && i.daysOverdue > 0).length / total;
    score += Math.round(overdueRatio * 30);

    // Factor 2: max days overdue severity (max 30pts)
    const maxDays = Math.max(...c.invoices.map(i => i.daysOverdue || 0));
    if (maxDays >= 90) score += 30;
    else if (maxDays >= 45) score += 20;
    else if (maxDays >= 21) score += 10;

    // Factor 3: recovery rate (max 20pts — lower recovery = higher risk)
    const rate = c.totalAmount > 0 ? c.totalRecovered / c.totalAmount : 0;
    score += Math.round((1 - rate) * 20);

    // Factor 4: dispute signals from communication log (max 20pts)
    const disputes = c.invoices.reduce((n, i) =>
      n + ((i.communication_log || []).filter(l => l.intent === 'dispute').length), 0);
    score += Math.min(20, disputes * 10);

    score = Math.min(100, Math.max(0, score));
    const level = score >= 65 ? 'high' : score >= 35 ? 'medium' : 'low';
    return { score, level };
  }

  /* ── Feature #3: Build Activity Timeline for a customer ── */
  function buildTimeline(c) {
    const events = [];
    c.invoices.forEach(inv => {
      // Invoice created
      events.push({ ts: new Date(inv.issueDate || inv.dueDate || Date.now()), icon: '📄', color: 'var(--blue)', bg: 'var(--blue-bg)', title: `Invoice ${inv.invoiceNo} created`, sub: `${fmtINR(inv.amount)} · Due: ${inv.dueDate || '—'}` });
      // Recovery
      if (inv.recovered) events.push({ ts: new Date(inv.dueDate || Date.now()), icon: '✅', color: 'var(--green)', bg: 'var(--green-bg)', title: `Payment received`, sub: `${fmtINR(inv.amount)} recovered for ${inv.invoiceNo}` });
      // Legal escalation
      if (!inv.recovered && (inv.daysOverdue || 0) >= 45) events.push({ ts: new Date(Date.now() - (inv.daysOverdue - 44) * 86400000), icon: '⚖️', color: 'var(--red)', bg: 'var(--red-bg)', title: `Escalated to Legal Queue`, sub: `${inv.daysOverdue}d overdue — MSMED Act notice eligible` });
      // Communication log entries
      (inv.communication_log || []).forEach(log => {
        const intent = (log.intent || 'unknown').replace(/_/g, ' ');
        const icons = { promise_to_pay: '🤝', dispute: '⚠️', stall: '⏳' };
        events.push({ ts: new Date(log.timestamp || Date.now()), icon: icons[log.intent] || '💬', color: 'var(--purple)', bg: 'var(--purple-bg)', title: `Debtor replied — ${intent}`, sub: log.translated_text || log.raw_message || '' });
      });
    });
    return events.sort((a, b) => b.ts - a.ts);
  }

  function getInitialsColor(name) {
    const colors = [
      ['#1D4ED8','#DBEAFE'],['#7C3AED','#EDE9FE'],['#0369A1','#E0F2FE'],
      ['#065F46','#D1FAE5'],['#9D174D','#FCE7F3'],['#92400E','#FEF3C7']
    ];
    const idx = (name || '').charCodeAt(0) % colors.length;
    return colors[idx];
  }

  function recoveryRate(c) {
    if (!c.totalAmount) return 0;
    return Math.round((c.totalRecovered / c.totalAmount) * 100);
  }

  /* ── Customer Detail Panel ── */
  if (selectedCustomer) {
    const c = selectedCustomer;
    const risk = getRisk(c);
    const [fg, bg] = getInitialsColor(c.company);
    const rate = recoveryRate(c);
    const maxDaysOverdue = Math.max(...c.invoices.map(i => i.daysOverdue || 0));
    const activeInvs = c.invoices.filter(i => !i.recovered);
    const recoveredInvs = c.invoices.filter(i => i.recovered);

    return (
      <div>
        <div className="topbar" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            className="btn"
            style={{ gap: 6, padding: '6px 12px', fontSize: 12 }}
            onClick={() => setSelectedCustomer(null)}
          >
            ← Back to Customers
          </button>
          <div>
            <div className="page-title">{c.company}</div>
            <div className="page-sub">Customer Profile · {c.invoices.length} invoices</div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            {c.phone && (
              <a href={`tel:${c.phone}`} className="btn" style={{ fontSize: 12, gap: 6 }}>
                📞 Call
              </a>
            )}
            {c.email && (
              <a href={`mailto:${c.email}`} className="btn" style={{ fontSize: 12, gap: 6 }}>
                ✉ Email
              </a>
            )}
          </div>
        </div>

        <div className="content">
          {/* Hero Card */}
          <div style={{
            background: 'linear-gradient(135deg, #0F172A 0%, #1E3A5F 60%, #1D4ED8 100%)',
            borderRadius: 20, padding: '28px 32px', marginBottom: 20,
            display: 'flex', alignItems: 'center', gap: 28, position: 'relative', overflow: 'hidden',
          }} className="customer-hero">
            {/* decorative circles */}
            <div style={{ position:'absolute', right:-40, top:-40, width:200, height:200, borderRadius:'50%', background:'rgba(255,255,255,0.03)' }} />
            <div style={{ position:'absolute', right:60, bottom:-60, width:150, height:150, borderRadius:'50%', background:'rgba(255,255,255,0.04)' }} />

            <div style={{
              width: 80, height: 80, borderRadius: 20,
              background: bg, color: fg,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 30, fontWeight: 800, flexShrink: 0,
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
            }}>
              {getInitials(c.company)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#fff', lineHeight: 1.1, marginBottom: 6 }}>
                {c.company}
              </div>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {c.contact && <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.75)' }}>👤 {c.contact}</span>}
                {c.email && <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.75)' }}>✉ {c.email}</span>}
                {c.phone && <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.75)' }}>📞 {c.phone}</span>}
                {c.city && <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.75)' }}>📍 {c.city}</span>}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, flexShrink: 0 }}>
              <span style={{
                padding: '6px 16px', borderRadius: 30, fontSize: 12, fontWeight: 700,
                background: risk.label === 'High Risk' ? 'rgba(239,68,68,0.2)' : risk.label === 'Active' ? 'rgba(14,165,233,0.2)' : 'rgba(16,185,129,0.2)',
                color: risk.label === 'High Risk' ? '#FCA5A5' : risk.label === 'Active' ? '#7DD3FC' : '#6EE7B7',
                border: '1px solid ' + (risk.label === 'High Risk' ? 'rgba(239,68,68,0.4)' : risk.label === 'Active' ? 'rgba(14,165,233,0.4)' : 'rgba(16,185,129,0.4)'),
              }}>{risk.label}</span>
            </div>
          </div>

          {/* KPI Stats */}
          <div className="customer-kpi-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
            {[
              { label: 'Total Invoices', val: c.invoices.length, color: 'var(--blue)', icon: '📄' },
              { label: 'Outstanding', val: fmtINR(c.totalOutstanding), color: 'var(--amber)', icon: '⏳' },
              { label: 'Recovered', val: fmtINR(c.totalRecovered), color: 'var(--green)', icon: '✅' },
              { label: 'Recovery Rate', val: rate + '%', color: rate >= 70 ? 'var(--green)' : rate >= 40 ? 'var(--amber)' : 'var(--red)', icon: '📈' },
            ].map((m, i) => (
              <div key={i} style={{
                background: 'var(--surface)', borderRadius: 14, border: '1px solid var(--border)',
                padding: '18px 20px', position: 'relative', overflow: 'hidden',
              }}>
                <div style={{ fontSize: 22, marginBottom: 8 }}>{m.icon}</div>
                <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>{m.label}</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: m.color }}>{m.val}</div>
                <div style={{ position:'absolute', right:12, top:12, width:40, height:40, borderRadius:'50%', background: m.color + '12' }} />
              </div>
            ))}
          </div>

          {/* Feature #8: AI Risk Score Card */}
          {(() => {
            const rs = getRiskScore(c);
            const rsColor = rs.level === 'high' ? 'var(--red)' : rs.level === 'medium' ? 'var(--amber-dark)' : 'var(--green)';
            const rsBg    = rs.level === 'high' ? 'var(--red-bg)' : rs.level === 'medium' ? 'var(--amber-bg)' : 'var(--green-bg)';
            const rsLabel = rs.level === 'high' ? 'High Risk' : rs.level === 'medium' ? 'Medium Risk' : 'Low Risk';
            return (
              <div style={{ background: 'var(--surface)', borderRadius: 14, border: '1px solid var(--border)', padding: '16px 24px', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 24 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>🤖 AI Default Risk Score</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 10 }}>Computed from payment history, days overdue &amp; dispute signals</div>
                  <div style={{ height: 10, background: 'var(--surface2)', borderRadius: 8, overflow: 'hidden', marginBottom: 6 }}>
                    <div style={{ width: rs.score + '%', height: '100%', borderRadius: 8, background: `linear-gradient(90deg, ${rsBg}, ${rsColor})`, transition: 'width 1s ease' }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text3)' }}>
                    <span>🟢 Low Risk</span><span>🟡 Medium</span><span>🔴 High Risk</span>
                  </div>
                </div>
                <div style={{ textAlign: 'center', flexShrink: 0 }}>
                  <span className={`risk-score risk-${rs.level}`}>{rsLabel}</span>
                  <div style={{ fontSize: 32, fontWeight: 800, color: rsColor, marginTop: 6 }}>{rs.score}<span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text3)' }}>/100</span></div>
                </div>
              </div>
            );
          })()}

          {/* Recovery Progress Bar */}
          <div style={{ background: 'var(--surface)', borderRadius: 14, border: '1px solid var(--border)', padding: '18px 24px', marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontSize: 13, fontWeight: 700 }}>Recovery Progress</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: rate >= 70 ? 'var(--green)' : rate >= 40 ? 'var(--amber)' : 'var(--red)' }}>{rate}%</div>
            </div>
            <div style={{ height: 10, background: 'var(--surface2)', borderRadius: 10, overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 10, width: rate + '%',
                background: rate >= 70 ? 'linear-gradient(90deg, var(--green-light), var(--green))' : rate >= 40 ? 'linear-gradient(90deg, #FCD34D, var(--amber))' : 'linear-gradient(90deg, #FCA5A5, var(--red))',
                transition: 'width 1s ease'
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: 'var(--text3)' }}>
              <span>{recoveredInvs.length} invoices recovered</span>
              <span>{activeInvs.length} still outstanding</span>
            </div>
          </div>

          {/* Two-column: profile + invoices */}
          <div className="customer-detail-grid" style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
            {/* Left: Contact Card */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', fontWeight: 700, fontSize: 13 }}>Contact Details</div>
                <div style={{ padding: '14px 18px' }}>
                  {[
                    ['Contact', c.contact || '—'],
                    ['Email', c.email || '—'],
                    ['Phone', c.phone || '—'],
                    ['City', c.city || '—'],
                    ['GSTIN', c.gstin || '—'],
                  ].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)', fontSize: 12, gap: 8 }}>
                      <span style={{ color: 'var(--text3)', fontWeight: 500, flexShrink: 0 }}>{k}</span>
                      <span style={{ fontWeight: 600, color: 'var(--text)', textAlign: 'right', wordBreak: 'break-all' }}>{v}</span>
                    </div>
                  ))}
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', fontSize: 12 }}>
                    <span style={{ color: 'var(--text3)', fontWeight: 500 }}>Risk Status</span>
                    <span className={`badge ${risk.cls}`}>{risk.label}</span>
                  </div>
                </div>
              </div>

              {/* Quick Stats */}
              <div className="card" style={{ padding: 0 }}>
                <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', fontWeight: 700, fontSize: 13 }}>Payment Summary</div>
                <div style={{ padding: '14px 18px' }}>
                  {[
                    ['Max Days Overdue', maxDaysOverdue + 'd', maxDaysOverdue >= 45 ? 'var(--red)' : maxDaysOverdue >= 21 ? 'var(--amber)' : 'var(--green)'],
                    ['Active Invoices', activeInvs.length, 'var(--blue)'],
                    ['Recovered', recoveredInvs.length, 'var(--green)'],
                    ['Total Business', fmtINR(c.totalAmount), 'var(--text)'],
                  ].map(([k, v, col]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
                      <span style={{ color: 'var(--text3)', fontWeight: 500 }}>{k}</span>
                      <span style={{ fontWeight: 700, color: col }}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right: Invoice List */}
            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', fontWeight: 700, fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Invoice History ({c.invoices.length})</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <span style={{ padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: 'var(--green-bg)', color: 'var(--green)' }}>{recoveredInvs.length} Recovered</span>
                  <span style={{ padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: 'var(--amber-bg)', color: 'var(--amber-dark)' }}>{activeInvs.length} Active</span>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Invoice No.</th>
                      <th>Due Date</th>
                      <th>Days Overdue</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Amount</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {c.invoices.map((inv, i) => {
                      const isRec = inv.recovered || inv.status === 'recovered';
                      const dClass = inv.daysOverdue >= 45 ? 'badge-red' : inv.daysOverdue >= 21 ? 'badge-amber' : 'badge-blue';
                      return (
                        <tr key={i} className="mobile-table-row" style={{ cursor: 'pointer' }} onClick={() => openDetail(inv)}>
                          <td style={{ fontWeight: 600, fontSize: 12 }}>{inv.invoiceNo || '—'}</td>
                          <td style={{ fontSize: 12, color: 'var(--text2)' }}>{inv.dueDate || '—'}</td>
                          <td>
                            {isRec
                              ? <span className="badge badge-green">Paid</span>
                              : <span className={`badge ${dClass}`}>{inv.daysOverdue || 0}d</span>
                            }
                          </td>
                          <td>
                            <span style={{
                              fontSize: 11, padding: '3px 8px', borderRadius: 20, fontWeight: 600,
                              background: isRec ? 'var(--green-bg)' : inv.status === 'legal' ? 'var(--red-bg)' : 'var(--amber-bg)',
                              color: isRec ? 'var(--green)' : inv.status === 'legal' ? 'var(--red)' : 'var(--amber-dark)',
                            }}>{isRec ? 'Recovered' : inv.status || 'Active'}</span>
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 700, fontFamily: 'monospace' }}>{fmtINR(inv.amount)}</td>
                          <td>
                            <button
                              className="btn btn-sm"
                              style={{ fontSize: 11, padding: '3px 10px' }}
                              onClick={e => { e.stopPropagation(); openDetail(inv); }}
                            >View →</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Feature #3: Activity Timeline */}
          <div className="card" style={{ marginTop: 0 }}>
            <div className="card-header" style={{ marginBottom: 12 }}>
              <div className="card-title" style={{ fontWeight: 700, fontSize: 14 }}>📅 Activity Timeline</div>
              <span style={{ fontSize: 11, color: 'var(--text3)' }}>Full history of all interactions</span>
            </div>
            {(() => {
              const events = buildTimeline(c);
              if (events.length === 0) return <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text3)', fontSize: 12 }}>No activity recorded yet.</div>;
              return (
                <div className="timeline">
                  {events.map((ev, i) => (
                    <div key={i} className="timeline-item">
                      <div className="timeline-dot" style={{ background: ev.bg, boxShadow: `0 0 0 2px ${ev.bg}` }}>
                        <span style={{ fontSize: 7 }}>{ev.icon}</span>
                      </div>
                      <div className="timeline-content">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div className="timeline-title">{ev.title}</div>
                          <div className="timeline-meta">{ev.ts.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</div>
                        </div>
                        {ev.sub && <div className="timeline-sub">{ev.sub}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>

        </div>
      </div>
    );
  }

  /* ── Customer List View ── */
  const totalOutstanding = customers.reduce((s, c) => s + c.totalOutstanding, 0);
  const highRiskCount = customers.filter(c => c.invoices.some(i => !i.recovered && i.daysOverdue >= 45)).length;
  const clearCount = customers.filter(c => c.totalOutstanding === 0).length;

  return (
    <div>
      <div className="topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="page-title">Customers</div>
          <div className="page-sub">{customers.length} debtor accounts · {fmtINR(totalOutstanding)} total outstanding</div>
        </div>
      </div>

      <div className="content">
        {loading && <div style={{textAlign: 'center', padding: '40px', color: 'var(--text3)'}}>Loading customers...</div>}
        {!loading && <>
        {/* Summary KPIs */}
        <div className="customer-kpi-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 20 }}>
          {[
            { label: 'Total Customers', val: customers.length, color: 'var(--blue)', icon: '🏢' },
            { label: 'High Risk Accounts', val: highRiskCount, color: 'var(--red)', icon: '⚠️' },
            { label: 'Fully Cleared', val: clearCount, color: 'var(--green)', icon: '✅' },
          ].map((m, i) => (
            <div key={i} style={{
              background: 'var(--surface)', borderRadius: 14, border: '1px solid var(--border)',
              padding: '18px 22px', display: 'flex', alignItems: 'center', gap: 16,
              transition: 'transform 0.2s, box-shadow 0.2s', cursor: 'pointer'
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 12px 24px rgba(10,20,40,0.08)'; e.currentTarget.style.borderColor = 'var(--border2)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = ''; e.currentTarget.style.borderColor = 'var(--border)'; }}
            >
              <div style={{ fontSize: 28 }}>{m.icon}</div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{m.label}</div>
                <div style={{ fontSize: 26, fontWeight: 800, color: m.color, marginTop: 2 }}>{m.val}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="customer-filter-row" style={{ display: 'flex', gap: 14, marginBottom: 24, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="input-field"
            placeholder="🔍  Search company, contact, email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ flex: '1 1 250px', padding: '12px 18px', fontSize: 14, borderRadius: 10, border: '1px solid var(--border2)', background: 'var(--surface)' }}
          />
          <select className="input-field" value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{ flex: '1 1 150px', padding: '12px 18px', fontSize: 14, borderRadius: 10, border: '1px solid var(--border2)', background: 'var(--surface)', cursor: 'pointer' }}>
            <option value="all">All Status</option>
            <option value="risk">High Risk</option>
            <option value="active">Active</option>
            <option value="clear">Cleared</option>
          </select>
          <select className="input-field" value={sortBy} onChange={e => setSortBy(e.target.value)} style={{ flex: '1 1 150px', padding: '12px 18px', fontSize: 14, borderRadius: 10, border: '1px solid var(--border2)', background: 'var(--surface)', cursor: 'pointer' }}>
            <option value="outstanding">Sort: Outstanding</option>
            <option value="recovered">Sort: Recovered</option>
            <option value="invoices">Sort: Invoices</option>
            <option value="name">Sort: Name</option>
          </select>
          <div className="account-count" style={{ fontSize: 14, color: 'var(--text3)', marginLeft: 'auto', flex: '1 1 100px', textAlign: 'right', whiteSpace: 'nowrap' }}>
            <strong style={{ color: 'var(--text)' }}>{customers.length}</strong> accounts
          </div>
        </div>

        {/* Customer Cards Grid */}
        {customers.length === 0 && (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--text3)' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🏢</div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>No customers found</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>Try adjusting your search or filters</div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {customers.map((c, i) => {
            const risk = getRisk(c);
            const rate = recoveryRate(c);
            const [fg, bg] = getInitialsColor(c.company);

            return (
              <div
                key={i}
                onClick={() => setSelectedCustomer(c)}
                style={{
                  background: 'var(--surface)', borderRadius: 16, border: '1px solid var(--border)',
                  padding: 0, cursor: 'pointer', transition: 'all 0.2s',
                  boxShadow: '0 1px 4px rgba(10,20,40,0.06)',
                  overflow: 'hidden',
                }}
                onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 8px 24px rgba(10,20,40,0.12)'; e.currentTarget.style.borderColor = 'var(--border2)'; }}
                onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '0 1px 4px rgba(10,20,40,0.06)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
              >
                {/* Card Header */}
                <div style={{
                  padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 14,
                  borderBottom: '1px solid var(--border)',
                }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12, background: bg, color: fg,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 18, fontWeight: 800, flexShrink: 0,
                  }}>
                    {getInitials(c.company)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.company}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {c.contact}{c.city ? ` · ${c.city}` : ''}
                    </div>
                  </div>
                  <span className={`badge ${risk.cls}`}>{risk.label}</span>
                </div>

                {/* Card Body — KPIs */}
                <div style={{ padding: '14px 20px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Outstanding</div>
                      <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--amber)', marginTop: 2 }}>{fmtINR(c.totalOutstanding)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Recovered</div>
                      <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--green)', marginTop: 2 }}>{fmtINR(c.totalRecovered)}</div>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text3)', marginBottom: 4 }}>
                      <span>Recovery Progress</span>
                      <span style={{ fontWeight: 700, color: rate >= 70 ? 'var(--green)' : rate >= 40 ? 'var(--amber)' : 'var(--red)' }}>{rate}%</span>
                    </div>
                    <div style={{ height: 6, background: 'var(--surface2)', borderRadius: 6, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', borderRadius: 6, width: rate + '%',
                        background: rate >= 70 ? 'var(--green)' : rate >= 40 ? 'var(--amber)' : 'var(--red)',
                        transition: 'width 0.8s ease'
                      }} />
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: 'var(--text3)' }}>
                      {c.invoices.length} invoice{c.invoices.length !== 1 ? 's' : ''}
                    </span>
                    <span style={{
                      fontSize: 11, fontWeight: 600, color: 'var(--blue)',
                      display: 'flex', alignItems: 'center', gap: 3,
                    }}>View Profile →</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        </>}
      </div>
    </div>
  );
}
