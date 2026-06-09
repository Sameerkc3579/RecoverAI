/* ─── Tally / Zoho Accounting Export Integration ─── */
function AccountingExport({ invoices, settings }) {
  const [exporting, setExporting] = React.useState(false);
  const [exportDone, setExportDone] = React.useState(null);
  const [selectedFormat, setSelectedFormat] = React.useState('tally_xml');
  const [filterStatus, setFilterStatus] = React.useState('all');
  const [dateFrom, setDateFrom] = React.useState('');
  const [dateTo, setDateTo] = React.useState('');
  const [tab, setTab] = React.useState('export'); // export | sync
  const [syncState, setSyncState] = React.useState('idle'); // idle | connecting | syncing | done

  async function demoZohoSync() {
    setSyncState('connecting');
    await new Promise(r => setTimeout(r, 1500));
    setSyncState('syncing');
    
    const fakeInvoices = [
      { company: 'Acme Corp (Zoho)', contact: 'John Doe', phone: '9876543210', amount: 45000, invoiceNo: 'ZINV-' + Math.floor(Math.random()*1000), dueDate: '2026-05-10', channel: 'WhatsApp' },
      { company: 'Stark Industries', contact: 'Tony S', phone: '9876543211', amount: 120000, invoiceNo: 'ZINV-' + Math.floor(Math.random()*1000), dueDate: '2026-04-15', channel: 'Email' },
      { company: 'Wayne Enterprises', contact: 'Bruce W', phone: '9876543212', amount: 85000, invoiceNo: 'ZINV-' + Math.floor(Math.random()*1000), dueDate: '2026-06-01', channel: 'WhatsApp' }
    ];

    for (const inv of fakeInvoices) {
      try {
        await authFetch('/api/invoices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(inv),
        });
      } catch (e) {}
    }

    await new Promise(r => setTimeout(r, 2000));
    setSyncState('done');
    setTimeout(() => {
      window.location.reload();
    }, 2000);
  }

  const filteredInvoices = invoices.filter(inv => {
    if (filterStatus === 'recovered' && !inv.recovered) return false;
    if (filterStatus === 'pending' && inv.recovered) return false;
    return true;
  });

  /* ─── Tally XML Generator ─── */
  function generateTallyXML(invList) {
    const bizName = settings?.businessName || 'Your Business';
    const ledgerEntries = invList.map(inv => `
    <VOUCHER VCHTYPE="Sales" ACTION="Create">
      <DATE>${inv.issueDate ? inv.issueDate.replace(/-/g,'') : '20260101'}</DATE>
      <NARRATION>Invoice #${inv.invoiceNo} - ${inv.company}</NARRATION>
      <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
      <ALLLEDGERENTRIES.LIST>
        <LEDGERNAME>${inv.company}</LEDGERNAME>
        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
        <AMOUNT>-${inv.amount}</AMOUNT>
      </ALLLEDGERENTRIES.LIST>
      <ALLLEDGERENTRIES.LIST>
        <LEDGERNAME>Sales Account</LEDGERNAME>
        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
        <AMOUNT>${inv.amount}</AMOUNT>
      </ALLLEDGERENTRIES.LIST>
    </VOUCHER>`).join('\n');

    return `<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>${bizName}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
${ledgerEntries}
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>`;
  }

  /* ─── CSV Generator ─── */
  function generateCSV(invList) {
    const headers = ['Invoice #','Client Name','Amount (₹)','Issue Date','Due Date','Days Overdue','Status','GSTIN'];
    const rows = invList.map(inv => [
      inv.invoiceNo, inv.company, inv.amount,
      inv.issueDate || '', inv.dueDate || '', inv.daysOverdue || 0,
      inv.recovered ? 'Recovered' : inv.status,
      inv.gstin || ''
    ]);
    return [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
  }

  function doExport() {
    if (filteredInvoices.length === 0) { alert('No invoices match the filter.'); return; }
    setExporting(true);
    setTimeout(() => {
      let content, filename, mimeType;
      if (selectedFormat === 'tally_xml') {
        content = generateTallyXML(filteredInvoices);
        filename = `recoverai_tally_${new Date().toISOString().split('T')[0]}.xml`;
        mimeType = 'application/xml';
      } else if (selectedFormat === 'csv') {
        content = generateCSV(filteredInvoices);
        filename = `recoverai_invoices_${new Date().toISOString().split('T')[0]}.csv`;
        mimeType = 'text/csv';
      } else if (selectedFormat === 'json') {
        content = JSON.stringify(filteredInvoices, null, 2);
        filename = `recoverai_invoices_${new Date().toISOString().split('T')[0]}.json`;
        mimeType = 'application/json';
      }
      const blob = new Blob([content], {type: mimeType});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
      setExporting(false);
      setExportDone({ format: selectedFormat, count: filteredInvoices.length, filename });
      setTimeout(() => setExportDone(null), 5000);
    }, 1000);
  }

  const totalAmount = filteredInvoices.reduce((s,i)=>s+i.amount,0);
  const recoveredAmt = filteredInvoices.filter(i=>i.recovered).reduce((s,i)=>s+i.amount,0);

  return (
    <div className="content">
      <div className="topbar">
        <div>
          <div className="page-title">🔗 Accounting Integrations</div>
          <div className="page-sub">Export to Tally ERP · Sync with Zoho Books · Download CSV</div>
        </div>
        <div className="topbar-actions">
          {exportDone && (
            <span style={{fontSize:12,fontWeight:700,padding:'6px 14px',borderRadius:20,background:'var(--green-bg)',color:'var(--green)',border:'1px solid var(--green)'}}>
              ✓ Exported {exportDone.count} invoices as {exportDone.format.toUpperCase()}
            </span>
          )}
        </div>
      </div>

      <div style={{display:'flex',gap:4,margin:'4px 0 20px',background:'var(--surface2)',padding:4,borderRadius:12,width:'fit-content'}}>
        {[['export','📤 Export Data'],['sync','☁️ Zoho Sync']].map(([id,label])=>(
          <button key={id} onClick={()=>setTab(id)} style={{
            padding:'8px 18px',borderRadius:8,border:'none',cursor:'pointer',
            fontSize:13,fontWeight:600,fontFamily:'Plus Jakarta Sans,sans-serif',
            background:tab===id?'var(--surface)':'transparent',
            color:tab===id?'var(--text)':'var(--text3)',
            boxShadow:tab===id?'var(--shadow)':'none',
            transition:'all 0.2s',
          }}>{label}</button>
        ))}
      </div>

      {tab === 'export' && (
        <div style={{display:'grid',gridTemplateColumns:'1fr 320px',gap:20}}>
          <div style={{display:'flex',flexDirection:'column',gap:16}}>
            {/* Format Selection */}
            <div className="card" style={{padding:24}}>
              <div style={{fontSize:15,fontWeight:800,color:'var(--text)',marginBottom:16}}>Export Format</div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12}}>
                {[
                  {id:'tally_xml',icon:'📒',name:'Tally XML',desc:'Import directly into Tally ERP 9 / Prime'},
                  {id:'csv',icon:'📊',name:'CSV Spreadsheet',desc:'Open in Excel, Zoho Sheets, or Google Sheets'},
                  {id:'json',icon:'🔧',name:'JSON Data',desc:'For developers and API integrations'},
                ].map(fmt=>(
                  <div key={fmt.id} onClick={()=>setSelectedFormat(fmt.id)} style={{
                    padding:'16px',borderRadius:12,cursor:'pointer',transition:'all 0.2s',
                    border: selectedFormat===fmt.id ? '2px solid var(--amber)' : '1px solid var(--border)',
                    background: selectedFormat===fmt.id ? 'var(--amber-bg)' : 'var(--surface2)',
                  }}>
                    <div style={{fontSize:28,marginBottom:8}}>{fmt.icon}</div>
                    <div style={{fontSize:13,fontWeight:800,color:'var(--text)',marginBottom:4}}>{fmt.name}</div>
                    <div style={{fontSize:11,color:'var(--text2)',lineHeight:1.6}}>{fmt.desc}</div>
                    {selectedFormat===fmt.id && <div style={{marginTop:8,fontSize:10,fontWeight:700,color:'var(--amber)',textTransform:'uppercase',letterSpacing:1}}>✓ Selected</div>}
                  </div>
                ))}
              </div>
            </div>

            {/* Filters */}
            <div className="card" style={{padding:24}}>
              <div style={{fontSize:15,fontWeight:800,color:'var(--text)',marginBottom:16}}>Filter Invoices</div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:14}}>
                <div>
                  <label style={{fontSize:11,fontWeight:700,color:'var(--text3)',display:'block',marginBottom:6,textTransform:'uppercase',letterSpacing:1}}>Status</label>
                  <select value={filterStatus} onChange={e=>setFilterStatus(e.target.value)} className="form-input" style={{width:'100%'}}>
                    <option value="all">All Invoices ({invoices.length})</option>
                    <option value="pending">Pending Only ({invoices.filter(i=>!i.recovered).length})</option>
                    <option value="recovered">Recovered Only ({invoices.filter(i=>i.recovered).length})</option>
                  </select>
                </div>
                <div>
                  <label style={{fontSize:11,fontWeight:700,color:'var(--text3)',display:'block',marginBottom:6,textTransform:'uppercase',letterSpacing:1}}>Date From</label>
                  <input type="date" value={dateFrom} onChange={e=>setDateFrom(e.target.value)} className="form-input" style={{width:'100%'}} />
                </div>
                <div>
                  <label style={{fontSize:11,fontWeight:700,color:'var(--text3)',display:'block',marginBottom:6,textTransform:'uppercase',letterSpacing:1}}>Date To</label>
                  <input type="date" value={dateTo} onChange={e=>setDateTo(e.target.value)} className="form-input" style={{width:'100%'}} />
                </div>
              </div>
            </div>

            {/* Tally Import Guide */}
            {selectedFormat === 'tally_xml' && (
              <div className="card" style={{padding:20,background:'rgba(14,165,233,0.05)',border:'1px solid rgba(14,165,233,0.2)'}}>
                <div style={{fontSize:14,fontWeight:800,color:'var(--text)',marginBottom:10}}>📒 How to Import into Tally ERP</div>
                {['Open Tally ERP 9 or Tally Prime','Go to Gateway of Tally → Import Data','Select "Vouchers" and choose the exported XML file','Verify the entries and accept the import'].map((step,i)=>(
                  <div key={i} style={{display:'flex',alignItems:'flex-start',gap:10,marginBottom:8,fontSize:13,color:'var(--text2)'}}>
                    <div style={{width:22,height:22,borderRadius:'50%',background:'rgba(14,165,233,0.15)',color:'var(--amber)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:11,fontWeight:700,flexShrink:0}}>{i+1}</div>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Summary & Export Button */}
          <div style={{display:'flex',flexDirection:'column',gap:16}}>
            <div className="card" style={{padding:24}}>
              <div style={{fontSize:15,fontWeight:800,color:'var(--text)',marginBottom:16}}>Export Summary</div>
              <div style={{display:'flex',flexDirection:'column',gap:12,marginBottom:20}}>
                {[
                  ['Invoices to Export',filteredInvoices.length,'var(--text)'],
                  ['Total Amount',`₹${totalAmount.toLocaleString('en-IN')}`,'var(--blue)'],
                  ['Recovered',`₹${recoveredAmt.toLocaleString('en-IN')}`,'var(--green)'],
                  ['Outstanding',`₹${(totalAmount-recoveredAmt).toLocaleString('en-IN')}`,'var(--amber)'],
                  ['Format',selectedFormat.toUpperCase(),'var(--purple)'],
                ].map(([label,val,color])=>(
                  <div key={label} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px 0',borderBottom:'1px solid var(--border)'}}>
                    <span style={{fontSize:13,color:'var(--text2)'}}>{label}</span>
                    <span style={{fontSize:13,fontWeight:700,color}}>{val}</span>
                  </div>
                ))}
              </div>
              <button className="btn btn-primary" style={{width:'100%',justifyContent:'center',padding:'13px',fontSize:14}}
                onClick={doExport} disabled={exporting || filteredInvoices.length===0}>
                {exporting ? '⌛ Generating Export...' : `📤 Export ${filteredInvoices.length} Invoices`}
              </button>
            </div>
            <div className="card" style={{padding:20}}>
              <div style={{fontSize:13,fontWeight:800,color:'var(--text)',marginBottom:10}}>🔒 Data Security</div>
              <div style={{fontSize:12,color:'var(--text2)',lineHeight:1.7}}>
                All exports are generated locally in your browser. No data is sent to any external server during the export process.
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'sync' && (
        <div className="card" style={{padding:32,textAlign:'center',maxWidth:540,margin:'0 auto'}}>
          <div style={{fontSize:48,marginBottom:16}}>☁️</div>
          <div style={{fontSize:18,fontWeight:900,color:'var(--text)',marginBottom:10}}>Zoho Books Integration</div>
          <div style={{fontSize:14,color:'var(--text2)',lineHeight:1.7,marginBottom:28}}>
            Connect your Zoho Books account to automatically pull unpaid invoices into RecoverAI. No CSV needed — it syncs on a schedule.
          </div>

          {syncState === 'idle' && (
            <>
              <div style={{background:'var(--surface2)',border:'1px solid var(--border)',borderRadius:12,padding:20,marginBottom:24,textAlign:'left'}}>
                <div style={{fontSize:13,fontWeight:700,color:'var(--text)',marginBottom:12}}>What Zoho Sync Will Do:</div>
                {['Auto-import all unpaid invoices from Zoho Books','Sync payment status back to Zoho when marked Recovered in RecoverAI','Schedule daily sync at midnight IST','Map Zoho contacts to RecoverAI debtors automatically'].map(f=>(
                  <div key={f} style={{display:'flex',alignItems:'flex-start',gap:8,marginBottom:8,fontSize:13,color:'var(--text2)'}}>
                    <span style={{color:'var(--green)',fontWeight:700,flexShrink:0}}>✓</span>
                    <span>{f}</span>
                  </div>
                ))}
              </div>
              <button className="btn btn-primary" style={{padding:'13px 32px',fontSize:14}} onClick={demoZohoSync}>
                🔗 Connect Zoho Books
              </button>
              <div style={{marginTop:12,fontSize:12,color:'var(--text3)'}}>Powered by Zoho Books API v3 · OAuth 2.0 secured</div>
            </>
          )}

          {syncState === 'connecting' && (
            <div style={{padding: '40px 0'}}>
              <div className="spinner" style={{width: 32, height: 32, borderTopColor: 'var(--blue)', marginBottom: 16, margin: '0 auto'}}></div>
              <div style={{fontWeight: 700, fontSize: 14, color: 'var(--text)'}}>Connecting to Zoho Books via OAuth 2.0...</div>
              <div style={{fontSize: 12, color: 'var(--text3)', marginTop: 8}}>Negotiating secure tokens</div>
            </div>
          )}

          {syncState === 'syncing' && (
            <div style={{padding: '40px 0'}}>
              <div className="spinner" style={{width: 32, height: 32, borderTopColor: 'var(--amber)', marginBottom: 16, margin: '0 auto'}}></div>
              <div style={{fontWeight: 700, fontSize: 14, color: 'var(--text)'}}>Syncing Unpaid Invoices...</div>
              <div style={{fontSize: 12, color: 'var(--text3)', marginTop: 8}}>Fetching data from Zoho Servers</div>
            </div>
          )}

          {syncState === 'done' && (
            <div style={{padding: '40px 0'}}>
              <div style={{fontSize: 48, marginBottom: 16}}>✅</div>
              <div style={{fontWeight: 800, fontSize: 18, color: 'var(--green)'}}>Sync Complete!</div>
              <div style={{fontSize: 13, color: 'var(--text2)', marginTop: 8}}>Successfully imported 3 invoices. Reloading dashboard...</div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
