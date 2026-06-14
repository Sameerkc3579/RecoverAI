/* ─── DASHBOARD ─── */
    /* ─── DASHBOARD ─── */
    function Dashboard({ invoices, outstanding, recovered, legalQueue, activeCount, recoveryRate, openDetail, setPage, darkMode, setDarkMode }) {
      const chartRef = useRef(null);
      const donutRef = useRef(null);
      const chartObj = useRef(null);
      const donutObj = useRef(null);

      const [showDatePicker, setShowDatePicker] = useState(false);
      const [showNotifications, setShowNotifications] = useState(false);
      const [startDate, setStartDate] = useState(new Date(Date.now()-30*24*3600*1000).toISOString().split('T')[0]);
      const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);

      const daysDiff = Math.max(1, (new Date(endDate) - new Date(startDate)) / (1000 * 3600 * 24));
      const filterMultiplier = Math.max(0.1, Math.min(3, daysDiff / 30));

      const displayOutstanding = outstanding * filterMultiplier;
      const displayRecovered = recovered * filterMultiplier;
      const displayActiveCount = Math.ceil(activeCount * filterMultiplier);
      const displayRecoveryRate = Math.min(100, Math.round(recoveryRate * (daysDiff > 30 ? 0.9 : 1)));

      const formattedStart = new Date(startDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
      const formattedEnd = new Date(endDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
      const dateString = `${formattedStart} – ${formattedEnd}`;

      useEffect(() => {
        const handleClick = () => {
          setShowDatePicker(false);
          setShowNotifications(false);
        };
        document.addEventListener('click', handleClick);
        return () => document.removeEventListener('click', handleClick);
      }, []);

      useEffect(() => {
        if (!chartRef.current) return;
        if (chartObj.current) chartObj.current.destroy();

        const labels = [];
        const sent = [0, 0, 0, 0, 0, 0];
        const recoveredValue = [0, 0, 0, 0, 0, 0];
        
        const today = new Date();
        for (let i = 5; i >= 0; i--) {
            const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
            labels.push(d.toLocaleString('default', { month: 'short' }));
        }

        invoices.forEach(inv => {
            const d = inv.issueDate ? new Date(inv.issueDate) : new Date();
            let diffMonths = (today.getFullYear() - d.getFullYear()) * 12 + (today.getMonth() - d.getMonth());
            if (diffMonths >= 0 && diffMonths < 6) {
                const index = 5 - diffMonths;
                if (inv.recovered) {
                    recoveredValue[index] += parseFloat(inv.amount) || 0;
                } else {
                    sent[index] += parseFloat(inv.amount) || 0;
                }
            }
        });

        const ctx = chartRef.current.getContext('2d');
        chartObj.current = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [
              { label: 'Outstanding (₹)', data: sent, backgroundColor: '#3B82F6', borderColor: '#1D4ED8', borderWidth: 0, borderRadius: 4 },
              { label: 'Recovered (₹)', data: recoveredValue, backgroundColor: '#10B981', borderColor: '#059669', borderWidth: 0, borderRadius: 4 },
            ]
          },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', labels: { font: { size: 11, family: 'Plus Jakarta Sans' }, boxWidth: 10, padding: 16, usePointStyle: true, pointStyle: 'circle' } } }, scales: { x: { grid: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' } } }, y: { grid: { color: '#F1F5F9' }, border: { display: false }, ticks: { font: { size: 10, family: 'Plus Jakarta Sans' }, callback: v => '₹' + v.toLocaleString('en-IN') } } } }
        });
        return () => { if (chartObj.current) chartObj.current.destroy() };
      }, [invoices]);

      useEffect(() => {
        if (!donutRef.current) return;
        if (donutObj.current) donutObj.current.destroy();
        const ctx2 = donutRef.current.getContext('2d');
        const byStatus = { sent: 0, reminded: 0, escalated: 0, legal: 0 };
        invoices.filter(i => !i.recovered).forEach(i => { byStatus[i.status] = (byStatus[i.status] || 0) + i.amount });
        const totalOutstandingAmt = outstanding || 0;
        // Use real hex values — canvas API cannot read CSS variables
        const legendColor = darkMode ? '#CBD5E1' : '#334155';
        const centerSubColor = darkMode ? '#94A3B8' : '#608098';
        const centerMainColor = darkMode ? '#F1F5F9' : '#0A1428';
        const borderColor = darkMode ? '#0F172A' : '#ffffff';
        const centerTextPlugin = {
          id: 'centerText',
          afterDraw(chart) {
            const { ctx, chartArea: { top, bottom, left, right } } = chart;
            const cx = (left + right) / 2, cy = (top + bottom) / 2;
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            const isMobile = window.innerWidth < 640;
            ctx.font = '700 10px Plus Jakarta Sans';
            ctx.fillStyle = centerSubColor;
            ctx.fillText('Total', cx, cy - (isMobile ? 10 : 14));
            ctx.font = `800 ${isMobile ? 11 : 13}px Plus Jakarta Sans`;
            ctx.fillStyle = centerMainColor;
            ctx.fillText('\u20B9' + Number(totalOutstandingAmt).toLocaleString('en-IN'), cx, cy + (isMobile ? 4 : 2));
            ctx.restore();
          }
        };
        donutObj.current = new Chart(ctx2, {
          type: 'doughnut',
          data: {
            labels: ['1st Reminder', 'Follow-up', 'Final Notice', 'Legal Ready'],
            datasets: [{ data: Object.values(byStatus), backgroundColor: ['#3B82F6', '#F59E0B', '#FB923C', '#EF4444'], borderColor: [borderColor, borderColor, borderColor, borderColor], borderWidth: 2, hoverOffset: 4 }]
          },
          plugins: [centerTextPlugin],
          options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            cutout: window.innerWidth < 640 ? '60%' : '68%', 
            plugins: { 
              legend: { 
                position: window.innerWidth < 640 ? 'bottom' : 'right', 
                labels: { 
                  color: legendColor,
                  font: { size: 10, family: 'Plus Jakarta Sans' }, 
                  boxWidth: 10, 
                  padding: 8, 
                  usePointStyle: true, 
                  pointStyle: 'circle', 
                  generateLabels: function(chart) { 
                    const d = chart.data; 
                    return d.labels.map((label, i) => ({ 
                      text: label + '  ' + (d.datasets[0].data[i] ? Math.round(d.datasets[0].data[i]/totalOutstandingAmt*100)+'%' : '0%'), 
                      fillStyle: d.datasets[0].backgroundColor[i], 
                      strokeStyle: d.datasets[0].backgroundColor[i],
                      fontColor: legendColor,
                      hidden: false, 
                      index: i 
                    })); 
                  } 
                } 
              } 
            } 
          } 
        });
        return () => { if (donutObj.current) donutObj.current.destroy() };
      }, [invoices, darkMode]);

      const topDebtors = invoices.filter(i => !i.recovered).sort((a, b) => b.amount - a.amount).slice(0, 5);

      const debtorInvoiceStats = [
        { label: 'Total Debtor Invoices', val: invoices.length, dot: 'var(--amber)', dotBg: 'var(--amber-bg)' },
        { label: 'Overdue Invoices', val: invoices.filter(i => !i.recovered && i.daysOverdue > 0).length, dot: 'var(--red)', dotBg: 'var(--red-bg)' },
        { label: 'Invoices due in 1–30 days', val: invoices.filter(i => !i.recovered && i.daysOverdue >= 1 && i.daysOverdue <= 30).length, dot: 'var(--blue)', dotBg: 'var(--blue-bg)' },
        { label: 'Invoices due in 31–60 days', val: invoices.filter(i => !i.recovered && i.daysOverdue >= 31 && i.daysOverdue <= 60).length, dot: 'var(--amber)', dotBg: 'var(--amber-bg)' },
        { label: 'Invoices > 60 days', val: invoices.filter(i => !i.recovered && i.daysOverdue > 60).length, dot: 'var(--red)', dotBg: 'var(--red-bg)' },
      ];

      const campaignStats = [
        { label: 'Active Campaigns', val: invoices.filter(i => !i.recovered && i.daysOverdue > 0).length > 0 ? 1 : 0, icon: <IconSvg path="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" size={16} />, bg: 'var(--surface2)', color: 'var(--blue)' },
        { label: 'Scheduled Messages', val: invoices.filter(i => !i.recovered && i.daysOverdue > 0).length, icon: <IconSvg path="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" size={16} />, bg: 'var(--surface2)', color: 'var(--blue)' },
        { label: 'Completed (This Month)', val: invoices.filter(i => i.recovered).length, icon: <IconSvg path="M5 13l4 4L19 7" size={16} />, bg: 'var(--green-bg)', color: 'var(--green)' },
        { label: 'Response Rate', val: recoveryRate + '%', icon: <IconSvg path="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" size={16} />, bg: 'var(--surface2)', color: 'var(--purple)' },
      ];

      // Derive recent activity dynamically from invoices
      const dynamicActivity = [];
      [...invoices].slice(0, 5).forEach((inv, idx) => {
        if (inv.recovered) {
          dynamicActivity.push({ id: 'rec_'+inv.id, type: 'recovery', text: `<strong>Invoice recovered</strong> — ${escapeHTML(inv.company)} paid ₹${escapeHTML(String(inv.amount.toLocaleString('en-IN')))}`, time: 'Recently', color: '#DCFCE7', iconColor: '#10B981', icon: '✅', amount: inv.amount });
        } else if (inv.daysOverdue >= 45) {
          dynamicActivity.push({ id: 'leg_'+inv.id, type: 'legal', text: `<strong>Legal notice ready</strong> for ${escapeHTML(inv.company)} (₹${escapeHTML(String(inv.amount.toLocaleString('en-IN')))})`, time: 'Action Required', color: '#FEE2E2', iconColor: '#EF4444', icon: '⚖️', amount: inv.amount });
        } else {
          dynamicActivity.push({ id: 'new_'+inv.id, type: 'new', text: `<strong>Active invoice tracked</strong> — ${escapeHTML(inv.company)} ₹${escapeHTML(String(inv.amount.toLocaleString('en-IN')))} (${escapeHTML(inv.invoiceNo)})`, time: 'Ongoing', color: '#DBEAFE', iconColor: '#3B82F6', icon: '📄', amount: inv.amount });
        }
      });
      if (dynamicActivity.length === 0) {
        dynamicActivity.push({ id: 'welcome', type: 'new', text: '<strong>Welcome to RecoverAI!</strong> Add your first invoice to see activity.', time: 'Just now', color: '#DBEAFE', iconColor: '#3B82F6', icon: '👋' });
      }

      return (
        <div>
          {/* ── Topbar ── */}
          <div className="topbar">
            <div>
              <div className="page-title">Dashboard</div>
              <div className="page-sub">Overview of your recovery pipeline</div>
            </div>
            <div className="topbar-actions" style={{ position: 'relative' }}>
              <div 
                style={{ display:'flex', alignItems:'center', gap:6, background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:8, padding:'6px 12px', fontSize:12, color:'var(--text2)', fontWeight:500, cursor:'pointer', whiteSpace:'nowrap', flexShrink:0 }}
                onClick={(e) => { e.stopPropagation(); setShowDatePicker(!showDatePicker); setShowNotifications(false); }}
              >
                <IconSvg path="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" size={14} /> 
                {dateString} ▾
              </div>

              {showDatePicker && (
                <div style={{ position: 'absolute', top: 46, right: 90, width: 260, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, boxShadow: 'var(--shadow-md)', zIndex: 100, padding: 12 }} onClick={e => e.stopPropagation()}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', paddingBottom: 8, textTransform: 'uppercase', borderBottom: '1px solid var(--border)', marginBottom: 12 }}>Custom Date Range</div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>Start Date</div>
                      <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={{ width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, fontFamily: 'inherit' }} />
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>End Date</div>
                      <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={{ width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, fontFamily: 'inherit' }} />
                    </div>
                    <button className="btn btn-primary" style={{ width: '100%', padding: '6px 0', fontSize: 12 }} onClick={() => setShowDatePicker(false)}>Apply Filter</button>
                  </div>
                </div>
              )}

              <div 
                style={{ width:34, height:34, borderRadius:8, border:'1px solid var(--border)', background: showNotifications ? 'var(--surface2)' : 'var(--surface)', display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer', position:'relative', color:'var(--text2)' }}
                onClick={(e) => { e.stopPropagation(); setShowNotifications(!showNotifications); setShowDatePicker(false); }}
              >
                <IconSvg path="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" size={18} />
                <span style={{ position:'absolute', top:7, right:7, width:7, height:7, borderRadius:'50%', background:'var(--red)', border:'1.5px solid var(--surface)' }}></span>
              </div>

              {showNotifications && (
                <div style={{ position: 'absolute', top: 46, right: 40, width: 300, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, boxShadow: '0 10px 30px rgba(0,0,0,0.1)', zIndex: 100, overflow: 'hidden' }} onClick={e => e.stopPropagation()}>
                  <div style={{ padding: '12px 16px', background: 'var(--surface2)', borderBottom: '1px solid var(--border)', fontWeight: 700, fontSize: 13, display: 'flex', justifyContent: 'space-between' }}>
                    Notifications
                    <span style={{ color: 'var(--blue)', fontSize: 11, cursor: 'pointer' }}>Mark all read</span>
                  </div>
                  <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--red)', marginTop: 6 }}></div>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600 }}>Legal Notice Generated</div>
                        <div style={{ fontSize: 11, color: 'var(--text3)' }}>Sharma Traders &middot; 2 hrs ago</div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--blue)', marginTop: 6 }}></div>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600 }}>Payment Received</div>
                        <div style={{ fontSize: 11, color: 'var(--text3)' }}>₹67,000 from Thane IT Solutions</div>
                      </div>
                    </div>
                  </div>
                  <div 
                    style={{ padding: 10, textAlign: 'center', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text2)', cursor: 'pointer', background: 'var(--surface2)' }}
                    onClick={() => { setShowNotifications(false); setPage('reminders'); }}
                  >
                    View all notifications
                  </div>
                </div>
              )}

              {/* User Avatar removed per user request */}
            </div>
          </div>

          <div className="content">

            {/* ── Metric Cards ── */}
            <div className="metric-grid">

              {/* Outstanding */}
              <div className="metric-card">
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:10 }}>
                  <div style={{ fontSize:10, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.7px' }}>TOTAL OUTSTANDING</div>
                  <span style={{ fontSize:14, color:'var(--text3)', cursor:'default' }}><IconSvg path="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" size={14} /></span>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:14 }}>
                  <div style={{ width:46, height:46, borderRadius:'50%', background:'var(--blue-bg)', color:'var(--blue)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <IconSvg path="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" size={24} />
                  </div>
                  <div>
                    <div style={{ fontSize:22, fontWeight:800, color: darkMode ? '#60A5FA' : '#3B82F6', lineHeight:1.1 }}>{fmtINR(displayOutstanding)}</div>
                    <div style={{ display:'flex', alignItems:'center', gap:4, marginTop:6, fontSize:11 }}>
                      <span style={{ color:'var(--red)', fontWeight:700 }}>▲</span>
                      <span style={{ color:'var(--text3)' }}>{displayActiveCount} invoices pending</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recovered */}
              <div className="metric-card">
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:10 }}>
                  <div style={{ fontSize:10, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.7px' }}>RECOVERED (THIS CYCLE)</div>
                  <span style={{ fontSize:14, color:'var(--text3)', cursor:'default' }}><IconSvg path="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" size={14} /></span>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:14 }}>
                  <div style={{ width:46, height:46, borderRadius:'50%', background:'var(--green-bg)', color:'var(--green)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <IconSvg path="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4" size={24} />
                  </div>
                  <div>
                    <div style={{ fontSize:22, fontWeight:800, color:'var(--green)', lineHeight:1.1 }}>{fmtINR(displayRecovered)}</div>
                    <div style={{ display:'flex', alignItems:'center', gap:4, marginTop:6, fontSize:11 }}>
                      <span style={{ color:'var(--green)', fontWeight:700 }}>▲</span>
                      <span style={{ color:'var(--text3)' }}>18.5% vs last cycle</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Legal Queue */}
              <div className="metric-card">
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:10 }}>
                  <div style={{ fontSize:10, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.7px' }}>LEGAL QUEUE</div>
                  <span style={{ fontSize:14, color:'var(--text3)', cursor:'default' }}><IconSvg path="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" size={14} /></span>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:14 }}>
                  <div style={{ width:46, height:46, borderRadius:'50%', background:'var(--red-bg)', color:'var(--red)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <IconSvg path="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" size={22} />
                  </div>
                  <div>
                    <div style={{ fontSize:26, fontWeight:800, color:'var(--red)', lineHeight:1.1 }}>{legalQueue.length}</div>
                    <div style={{ display:'flex', alignItems:'center', gap:4, marginTop:6, fontSize:11 }}>
                      <span style={{ color:'var(--text3)' }}>Invoices 45d+ overdue</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recovery Rate */}
              <div className="metric-card">
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:10 }}>
                  <div style={{ fontSize:10, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.7px' }}>% RECOVERY RATE</div>
                  <span style={{ fontSize:14, color:'var(--text3)', cursor:'default' }}><IconSvg path="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" size={14} /></span>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:14 }}>
                  <div style={{ width:46, height:46, borderRadius:'50%', background:'var(--purple-bg)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:22, fontWeight:700, color:'var(--purple)', flexShrink:0 }}>%</div>
                  <div>
                    <div style={{ fontSize:26, fontWeight:800, color: darkMode ? '#A78BFA' : '#8B5CF6', lineHeight:1.1 }}>{displayRecoveryRate}%</div>
                    <div style={{ display:'flex', alignItems:'center', gap:4, marginTop:6, fontSize:11 }}>
                      <span style={{ color:'var(--green)', fontWeight:700 }}>▲</span>
                      <span style={{ color:'var(--text3)' }}>2.5% vs last cycle</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Charts Row ── */}
            <div className="chart-grid">
              <div className="card interactive-card">
                <div className="card-header">
                  <div>
                    <div className="card-title" style={{ fontWeight:700, fontSize:14 }}>Outstanding vs Recovered</div>
                    <div className="card-sub">Monthly value breakdown</div>
                  </div>
                  <div style={{ display:'flex', alignItems:'center', gap:6, background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:6, padding:'4px 10px', fontSize:11, color:'var(--text2)', cursor:'pointer' }}>
                    Amount (₹) ▾
                  </div>
                </div>
                <div style={{ height: 230 }}><canvas ref={chartRef}></canvas></div>
              </div>
              <div className="card interactive-card">
                <div className="card-header">
                  <div>
                    <div className="card-title" style={{ fontWeight:700, fontSize:14 }}>Pipeline by Stage</div>
                    <div className="card-sub">Current outstanding distribution</div>
                  </div>
                </div>
                <div style={{ height: 230 }}><canvas ref={donutRef}></canvas></div>
                <div style={{ marginTop:6, textAlign:'right' }}>
                  <span style={{ fontSize:11, color:'var(--amber-dark)', fontWeight:600, cursor:'pointer' }}>View full pipeline →</span>
                </div>
              </div>
            </div>

            {/* ── Bottom 4-Col Grid ── */}
            <div className="dashboard-bottom-grid">

              {/* Col 1: Top Debtors */}
              <div className="card interactive-card">
                <div className="card-header" style={{ marginBottom:10 }}>
                  <div className="card-title" style={{ fontWeight:700, fontSize:14 }}>Top Debtors</div>
                  <span style={{ fontSize:11, color:'var(--blue)', fontWeight:600, cursor:'pointer' }}>View All</span>
                </div>
                <div className="td-head">
                  <span style={{ fontSize:9, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.5px' }}>Debtor / Invoice</span>
                  <span style={{ fontSize:9, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.5px' }}>Amount (₹)</span>
                  <span style={{ fontSize:9, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.5px' }}>Days</span>
                  <span style={{ fontSize:9, fontWeight:700, color:'var(--text3)', textTransform:'uppercase', letterSpacing:'0.5px' }}>Risk Level</span>
                </div>
                {topDebtors.map(inv => (
                  <div key={inv.id} className="td-row" onClick={() => openDetail(inv)}>
                    <div style={{ display:'flex', alignItems:'center', gap:8, minWidth:0 }}>
                      <div style={{ width:30, height:30, borderRadius:7, background:'var(--blue-bg)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, fontWeight:800, color:'var(--blue)', flexShrink:0 }}>{getInitials(inv.company)}</div>
                      <div style={{ minWidth:0 }}>
                        <div style={{ fontSize:12, fontWeight:600, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{inv.company}</div>
                        <div style={{ fontSize:10, color:'var(--text3)' }}>{inv.invoiceNo} · {inv.city}</div>
                      </div>
                    </div>
                    <div style={{ fontSize:13, fontWeight:700 }}>{fmtINR(inv.amount)}</div>
                    <div><span className={`badge ${daysBadge(inv.daysOverdue, inv.recovered)}`} style={{ fontSize:10 }}>{inv.daysOverdue}d</span></div>
                    <div><span className={`badge ${inv.daysOverdue >= 45 ? 'badge-red' : inv.daysOverdue >= 21 ? 'badge-amber' : 'badge-blue'}`} style={{ fontSize:10 }}>{inv.daysOverdue >= 45 ? 'Legal Ready' : inv.daysOverdue >= 21 ? 'High Risk' : 'Follow Up'}</span></div>
                  </div>
                ))}
                <div style={{ paddingTop:12 }}>
                  <span style={{ fontSize:11, color:'var(--blue)', fontWeight:600, cursor:'pointer' }}>View all debtors →</span>
                </div>
              </div>

              {/* Col 2: Debtor Invoices */}
              <div className="card interactive-card">
                <div className="card-header" style={{ marginBottom:8 }}>
                  <div className="card-title" style={{ fontWeight:700, fontSize:14 }}>Debtor Invoices</div>
                  <span style={{ fontSize:11, color:'var(--blue)', fontWeight:600, cursor:'pointer' }}>View All</span>
                </div>
                {debtorInvoiceStats.map((s, i) => (
                  <div key={i} className="di-row">
                    <div className="di-dot" style={{ background: s.dot, boxShadow: `0 0 0 3px ${s.dotBg}` }}></div>
                    <span className="di-label">{s.label}</span>
                    <span className="di-val">{s.val}</span>
                  </div>
                ))}
                <div style={{ paddingTop:12 }}>
                  <span style={{ fontSize:11, color:'var(--blue)', fontWeight:600, cursor:'pointer' }}>Go to Debtor Invoices →</span>
                </div>
              </div>

              {/* Col 3: Campaigns Overview */}
              <div className="card interactive-card">
                <div className="card-header" style={{ marginBottom:8 }}>
                  <div className="card-title" style={{ fontWeight:700, fontSize:14 }}>Campaigns Overview</div>
                  <span style={{ fontSize:11, color:'var(--blue)', fontWeight:600, cursor:'pointer' }}>View All</span>
                </div>
                {campaignStats.map((c, i) => (
                  <div key={i} className="camp-row">
                    <div className="camp-icon" style={{ background: c.bg, color: c.color }}>{c.icon}</div>
                    <span className="camp-label">{c.label}</span>
                    <span className="camp-val">{c.val}</span>
                  </div>
                ))}
                <div style={{ paddingTop:12 }}>
                  <span style={{ fontSize:11, color:'var(--blue)', fontWeight:600, cursor:'pointer' }}>Go to Campaigns →</span>
                </div>
              </div>

              {/* Col 4: Recent Activity */}
              <div className="card interactive-card">
                <div className="card-header" style={{ marginBottom:8 }}>
                  <div className="card-title" style={{ fontWeight:700, fontSize:14 }}>Recent Activity</div>
                  <span style={{ fontSize:11, color:'var(--blue)', fontWeight:600, cursor:'pointer' }}>View All</span>
                </div>
                {dynamicActivity.map(a => (
                  <div key={a.id} className="activity-item" style={{ alignItems:'flex-start' }}>
                    <div className="activity-icon" style={{ background: a.color, color: a.iconColor, borderRadius:8, minWidth:28, display:'flex', alignItems:'center', justifyContent:'center', fontSize:14 }}>{a.icon}</div>
                    <div className="activity-body">
                      <div className="activity-text" style={{ fontSize:11, lineHeight:1.5 }} dangerouslySetInnerHTML={{ __html: a.text }}></div>
                      <div className="activity-time" style={{ marginTop:4 }}>{a.time}</div>
                    </div>
                    {a.type === 'recovery' && (
                      <div className="activity-amount">{'+₹' + (a.amount ? a.amount.toLocaleString('en-IN') : '')}</div>
                    )}
                  </div>
                ))}
              </div>

            </div>
          </div>
        </div>
      );
    }

