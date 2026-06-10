/* ─── Reports Page — Advanced Visualizations ─── */
function Reports({ invoices, outstanding, recovered, recoveryRate }) {
  const lineRef     = React.useRef(null);
  const barRef      = React.useRef(null);
  const forecastRef = React.useRef(null);
  const rateRef     = React.useRef(null);
  const lineObj     = React.useRef(null);
  const barObj      = React.useRef(null);
  const forecastObj = React.useRef(null);
  const rateObj     = React.useRef(null);

  const active = invoices.filter(i => !i.recovered);
  const aging = {
    '0-30':  active.filter(i => i.daysOverdue >= 0  && i.daysOverdue <= 30).reduce((s, i) => s + i.amount, 0),
    '31-60': active.filter(i => i.daysOverdue > 30  && i.daysOverdue <= 60).reduce((s, i) => s + i.amount, 0),
    '60-90': active.filter(i => i.daysOverdue > 60  && i.daysOverdue <= 90).reduce((s, i) => s + i.amount, 0),
    '90+':   active.filter(i => i.daysOverdue > 90).reduce((s, i) => s + i.amount, 0),
  };

  // Build last-6-month trend data
  const today = new Date();
  const months = [];
  const monthOutstanding = [];
  const monthRecovered   = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
    months.push(d.toLocaleString('default', { month: 'short' }));
    const mo = d.getMonth(), yr = d.getFullYear();
    const inMonth = invoices.filter(inv => {
      const dd = new Date(inv.issueDate || inv.dueDate || '');
      return dd.getMonth() === mo && dd.getFullYear() === yr;
    });
    monthOutstanding.push(inMonth.filter(inv => !inv.recovered).reduce((s, inv) => s + inv.amount, 0));
    monthRecovered.push(inMonth.filter(inv => inv.recovered).reduce((s, inv) => s + inv.amount, 0));
  }

  // Cashflow Forecast Data
  const forecastWeeks = ['This Week', 'Next Week', 'Week 3', 'Week 4+'];
  const forecastData = [0, 0, 0, 0];
  active.forEach(i => {
    const dd = new Date(i.dueDate || Date.now());
    const diffDays = (dd - today) / 86400000;
    if (diffDays <= 7) forecastData[0] += i.amount;
    else if (diffDays <= 14) forecastData[1] += i.amount;
    else if (diffDays <= 21) forecastData[2] += i.amount;
    else forecastData[3] += i.amount;
  });

  // Recovery Rate Data
  const monthRate = monthOutstanding.map((outst, i) => {
    const recov = monthRecovered[i];
    const total = outst + recov;
    return total > 0 ? Math.round((recov / total) * 100) : 0;
  });

  // Avg days to recover
  const recoveredInvs = invoices.filter(i => i.recovered);
  const avgDays = recoveredInvs.length
    ? Math.round(recoveredInvs.reduce((s, i) => s + (i.daysOverdue || 0), 0) / recoveredInvs.length)
    : 0;

  // Build line chart — cumulative recovery trend
  React.useEffect(() => {
    if (!lineRef.current) return;
    if (lineObj.current) lineObj.current.destroy();
    const ctx = lineRef.current.getContext('2d');
    lineObj.current = new Chart(ctx, {
      type: 'line',
      data: {
        labels: months,
        datasets: [
          { label: 'Outstanding (₹)', data: monthOutstanding, borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,0.08)', fill: true, tension: 0.4, borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#3B82F6' },
          { label: 'Recovered (₹)',   data: monthRecovered,   borderColor: '#10B981', backgroundColor: 'rgba(16,185,129,0.08)', fill: true, tension: 0.4, borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#10B981' },
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { 
          legend: { position: 'top', labels: { font: { size: 11, family: 'Plus Jakarta Sans' }, boxWidth: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: {
            callbacks: {
              label: function(context) {
                let label = context.dataset.label || '';
                if (label) {
                  label = label.split(' (')[0] + ': ';
                }
                if (context.parsed.y !== null) {
                  label += fmtINR(context.parsed.y);
                }
                return label;
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' } } },
          y: { grid: { color: 'rgba(0,0,0,0.05)' }, border: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' }, callback: v => '₹' + (v/1000).toFixed(0) + 'K' } }
        }
      }
    });
    return () => { if (lineObj.current) lineObj.current.destroy(); };
  }, [invoices]);

  // Build line chart — Cashflow Forecast
  React.useEffect(() => {
    if (!forecastRef.current) return;
    if (forecastObj.current) forecastObj.current.destroy();
    forecastObj.current = new Chart(forecastRef.current.getContext('2d'), {
      type: 'line',
      data: {
        labels: forecastWeeks,
        datasets: [{ label: 'Expected Cashflow (₹)', data: forecastData, borderColor: '#8B5CF6', backgroundColor: 'rgba(139,92,246,0.1)', fill: true, tension: 0.4, borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#8B5CF6' }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { 
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                return 'Expected Cashflow: ' + fmtINR(context.parsed.y);
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' } } },
          y: { grid: { color: 'rgba(0,0,0,0.05)' }, border: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' }, callback: v => '₹' + (v/1000).toFixed(0) + 'K' } }
        }
      }
    });
    return () => { if (forecastObj.current) forecastObj.current.destroy(); };
  }, [invoices]);

  // Build bar chart — Month-over-Month Recovery Rate
  React.useEffect(() => {
    if (!rateRef.current) return;
    if (rateObj.current) rateObj.current.destroy();
    rateObj.current = new Chart(rateRef.current.getContext('2d'), {
      type: 'bar',
      data: {
        labels: months,
        datasets: [{ label: 'Recovery Rate (%)', data: monthRate, backgroundColor: '#10B981', borderRadius: 4 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' } } },
          y: { grid: { color: 'rgba(0,0,0,0.05)' }, border: { display: false }, max: 100, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' }, callback: v => v + '%' } }
        }
      }
    });
    return () => { if (rateObj.current) rateObj.current.destroy(); };
  }, [invoices]);

  // Build horizontal bar chart — aging
  React.useEffect(() => {
    if (!barRef.current) return;
    if (barObj.current) barObj.current.destroy();
    const ctx = barRef.current.getContext('2d');
    barObj.current = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['0–30 Days', '31–60 Days', '60–90 Days', '90+ Days'],
        datasets: [{
          data: Object.values(aging),
          backgroundColor: ['#3B82F6','#F59E0B','#FB923C','#EF4444'],
          borderRadius: 6, borderSkipped: false,
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: { 
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                return 'Outstanding: ' + fmtINR(context.parsed.x);
              }
            }
          }
        },
        scales: {
          x: { grid: { color: 'rgba(0,0,0,0.05)' }, border: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' }, callback: v => '₹' + (v/1000).toFixed(0) + 'K' } },
          y: { grid: { display: false }, ticks: { font: { size: 11, family: 'Plus Jakarta Sans' } } }
        }
      }
    });
    return () => { if (barObj.current) barObj.current.destroy(); };
  }, [invoices]);

  function exportCSV() {
    const rows = [['Company', 'Invoice No', 'Amount', 'Due Date', 'Days Overdue', 'Status', 'Recovered']];
    invoices.forEach(i => rows.push([i.company, i.invoiceNo, i.amount, i.dueDate, i.daysOverdue, i.status, i.recovered ? 'Yes' : 'No']));
    const csv = rows.map(r => r.map(v => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'RecoverAI_Report.csv'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const totalAgingAmt = Object.values(aging).reduce((a, b) => a + b, 0);

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">Financial Reports</div>
          <div className="page-sub">Advanced analytics, aging summaries &amp; trend visualizations</div>
        </div>
        <div className="topbar-actions">
          <button className="btn" onClick={exportCSV}>↓ Export CSV</button>
          <button className="btn btn-primary" onClick={() => alert('PDF export — open DevTools → Print → Save as PDF for now.')}>↓ Export PDF</button>
        </div>
      </div>
      <div className="content">



        {/* Top Charts Row: Cashflow Forecast & Recovery Rate */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div className="card interactive-card">
            <div className="card-header">
              <div>
                <div className="card-title" style={{ fontWeight: 700, fontSize: 14 }}>Cashflow Forecast</div>
                <div className="card-sub">Expected incoming payments next 4 weeks</div>
              </div>
              <span className="badge badge-purple" style={{ fontSize: 10 }}>Predictive AI</span>
            </div>
            <div className="reports-chart-wrap" style={{ height: 200 }}><canvas ref={forecastRef}></canvas></div>
          </div>
          <div className="card interactive-card">
            <div className="card-header">
              <div>
                <div className="card-title" style={{ fontWeight: 700, fontSize: 14 }}>Month-over-Month Recovery Rate</div>
                <div className="card-sub">Percentage of invoice value recovered</div>
              </div>
            </div>
            <div className="reports-chart-wrap" style={{ height: 200 }}><canvas ref={rateRef}></canvas></div>
          </div>
        </div>

        {/* Charts Row */}
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 16, marginBottom: 20 }}>
          <div className="card interactive-card">
            <div className="card-header">
              <div>
                <div className="card-title" style={{ fontWeight: 700, fontSize: 14 }}>Monthly Recovery Trend</div>
                <div className="card-sub">Outstanding vs Recovered — last 6 months</div>
              </div>
            </div>
            <div className="reports-chart-wrap"><canvas ref={lineRef}></canvas></div>
          </div>
          <div className="card interactive-card">
            <div className="card-header">
              <div>
                <div className="card-title" style={{ fontWeight: 700, fontSize: 14 }}>Aging Analysis</div>
                <div className="card-sub">Outstanding by overdue bracket</div>
              </div>
            </div>
            <div className="reports-chart-wrap"><canvas ref={barRef}></canvas></div>
          </div>
        </div>

        {/* Bottom 2-col: Executive Summary + Aging Table */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div className="card interactive-card">
            <div className="card-header" style={{ marginBottom: 16 }}>
              <div className="card-title">Executive Summary</div>
              <span style={{ fontSize: 11, color: 'var(--text3)' }}>Current period</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                ['Total Outstanding',       fmtINR(outstanding),       'var(--amber)'],
                ['Total Recovered',         fmtINR(recovered),         'var(--green)'],
                ['Recovery Rate',           recoveryRate + '%',        'var(--purple)'],
                ['High Risk (90d+)',        fmtINR(aging['90+']),      'var(--red)'],
                ['Active Invoices',         active.length + ' invoices','var(--blue)'],
                ['Avg Days to Recover',     avgDays + ' days',         'var(--text)'],
              ].map(([label, value, color]) => (
                <div key={label} className="report-item" style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>
                  <span style={{ color: 'var(--text2)', fontSize: 13 }}>{label}:</span>
                  <strong style={{ fontSize: 15, color }}>{value}</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="card interactive-card">
            <div className="card-header" style={{ marginBottom: 16 }}>
              <div className="card-title">Aging Summary</div>
              <span style={{ fontSize: 11, color: 'var(--text3)' }}>{fmtINR(totalAgingAmt)} total</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                ['0 – 30 Days',       aging['0-30'],  'var(--blue)',       '#3B82F6'],
                ['31 – 60 Days',      aging['31-60'], 'var(--amber-dark)', '#F59E0B'],
                ['60 – 90 Days',      aging['60-90'], 'var(--amber)',      '#FB923C'],
                ['90+ Days (Severe)', aging['90+'],   'var(--red)',        '#EF4444'],
              ].map(([label, value, color, fill]) => {
                const pct = totalAgingAmt > 0 ? Math.round(value / totalAgingAmt * 100) : 0;
                return (
                  <div key={label} className="report-item">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 500 }}>{label}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <strong style={{ color, fontSize: 13 }}>{fmtINR(value)}</strong>
                        <span style={{ fontSize: 11, color: 'var(--text3)' }}>{pct}%</span>
                      </div>
                    </div>
                    <div title={fmtINR(value)} style={{ height: 8, background: 'var(--surface2)', borderRadius: 4, overflow: 'hidden', cursor: 'pointer' }}>
                      <div style={{ width: pct + '%', height: '100%', background: fill, borderRadius: 4, transition: 'width 0.8s ease' }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

