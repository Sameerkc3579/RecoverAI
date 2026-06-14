/* ─── Invoices Page ─── */
function Invoices({ invoices, openDetail, onAdd }) {
  const [search, setSearch] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [sort, setSort] = React.useState('days_desc');
  const [selectedIds, setSelectedIds] = React.useState(new Set());
  const [bulkModal, setBulkModal] = React.useState(false);
  const [bulkLoading, setBulkLoading] = React.useState(false);
  const [bulkResults, setBulkResults] = React.useState([]);

  // Feature #7: Bulk CSV Import
  const [csvModal, setCsvModal] = React.useState(false);
  const [csvRows, setCsvRows] = React.useState([]);
  const [csvDragOver, setCsvDragOver] = React.useState(false);
  const [csvImporting, setCsvImporting] = React.useState(false);
  const [csvImported, setCsvImported] = React.useState(0);
  const [csvError, setCsvError] = React.useState('');

  const filtered = invoices
    .filter(i => {
      const q = search.toLowerCase();
      if (q && !i.company.toLowerCase().includes(q) && !i.invoiceNo.toLowerCase().includes(q) && !(i.contact || '').toLowerCase().includes(q)) return false;
      if (statusFilter !== 'all' && i.status !== statusFilter) return false;
      return true;
    })
    .sort((a, b) => {
      if (sort === 'days_desc')   return b.daysOverdue - a.daysOverdue;
      if (sort === 'days_asc')    return a.daysOverdue - b.daysOverdue;
      if (sort === 'amount_desc') return b.amount - a.amount;
      if (sort === 'amount_asc')  return a.amount - b.amount;
      if (sort === 'company')     return a.company.localeCompare(b.company);
      return 0;
    });

  const totals = {
    outstanding: invoices.filter(i => !i.recovered).reduce((s, i) => s + i.amount, 0),
    recovered:   invoices.filter(i => i.recovered).reduce((s, i) => s + i.amount, 0),
  };

  async function handleBulkGenerate() {
    setBulkModal(true); setBulkLoading(true);
    const selInvs = invoices.filter(i => selectedIds.has(i.id));
    const results = [];
    for (const inv of selInvs) {
      try {
        const msg = await callAI(SYSTEM_PROMPT,
          `WhatsApp message for ${inv.contact} at ${inv.company} for invoice ${inv.invoiceNo} of ${fmtINR(inv.amount)}, ${inv.daysOverdue} days overdue. Polite but firm, 3-4 lines.`
        );
        results.push({ inv, msg });
      } catch (e) {
        results.push({ inv, msg: `Error: ${e.message}` });
      }
    }
    setBulkResults(results);
    setBulkLoading(false);
  }

  // Split a single CSV line into fields. Handles quoted fields, escaped quotes
  // ("") and commas inside quotes. The previous regex approach
  // (/(?:"([^"]*)"|([^,]*))/g) emitted an empty-string match at every comma, so
  // values shifted into the wrong columns and the whole import was corrupted.
  function splitCSVLine(line) {
    const out = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"') {
          if (line[i + 1] === '"') { cur += '"'; i++; }  // escaped quote
          else inQuotes = false;
        } else { cur += ch; }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ',') {
        out.push(cur); cur = '';
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out.map(v => v.trim());
  }

  // Feature #7: Parse CSV file
  function parseCSV(text) {
    const lines = text.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const headers = splitCSVLine(lines[0]).map(h => h.trim().toLowerCase());
    return lines.slice(1).map(line => {
      const vals = splitCSVLine(line);
      const obj = {};
      headers.forEach((h, i) => { obj[h] = (vals[i] || '').trim(); });
      return {
        company:   obj['company'] || obj['debtor'] || obj['company name'] || '',
        contact:   obj['contact'] || obj['contact name'] || obj['person'] || '',
        email:     obj['email'] || '',
        phone:     obj['phone'] || obj['mobile'] || obj['whatsapp'] || '',
        city:      obj['city'] || obj['location'] || '',
        gstin:     obj['gstin'] || obj['gst'] || '',
        invoiceNo: obj['invoice no'] || obj['invoice number'] || obj['invoice_no'] || `INV-${Date.now().toString().slice(-6)}`,
        amount:    parseFloat(obj['amount'] || obj['value'] || obj['total'] || 0) || 0,
        dueDate:   obj['due date'] || obj['due_date'] || obj['duedate'] || new Date().toISOString().split('T')[0],
        issueDate: obj['issue date'] || obj['issue_date'] || obj['date'] || new Date().toISOString().split('T')[0],
        channel:   obj['channel'] || 'WhatsApp',
        status:    obj['status'] || 'sent',
      };
    }).filter(r => r.company && r.amount > 0);
  }

  function handleCSVFile(file) {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { alert('CSV file too large (max 5MB).'); return; }
    if (!file.name.toLowerCase().endsWith('.csv')) { alert('Please upload a CSV file.'); return; }
    const reader = new FileReader();
    reader.onload = e => {
      const rows = parseCSV(e.target.result);
      if (rows.length === 0) { setCsvError('No valid rows found. Check your CSV format.'); return; }
      setCsvRows(rows); setCsvError('');
    };
    reader.readAsText(file);
  }

  async function importCSV() {
    setCsvImporting(true); setCsvImported(0); setCsvError('');
    let count = 0;
    for (const row of csvRows) {
      try {
        const res = await authFetch('/api/invoices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(row),
        });
        if (res.ok) count++;
      } catch {}
    }
    setCsvImported(count);
    setCsvImporting(false);
    if (count > 0 && typeof onAdd === 'function') {
      // Trigger a refresh — onAdd is used as signal to parent
      setTimeout(() => { setCsvModal(false); setCsvRows([]); }, 1800);
    }
  }

  function downloadTemplate() {
    const template = 'Company,Contact,Email,Phone,City,GSTIN,Invoice No,Amount,Due Date,Issue Date,Channel\nAcme Corp,Raj Kumar,raj@acme.com,9876543210,Mumbai,27AAAAA0000A1Z5,INV-001,50000,2025-06-30,2025-05-01,WhatsApp';
    const blob = new Blob([template], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'RecoverAI_Invoice_Template.csv'; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">All Invoices</div>
          <div className="page-sub">{invoices.length} total · {invoices.filter(i => !i.recovered).length} active</div>
        </div>
        <div className="topbar-actions">
          {selectedIds.size > 0 && <button className="btn btn-success" onClick={handleBulkGenerate}>Bulk Generate ({selectedIds.size})</button>}
          <button className="btn" onClick={() => setCsvModal(true)}>⬆ Import CSV</button>
          <button className="btn btn-primary" id="btn-add-invoice" onClick={onAdd}>+ Add Invoice</button>
        </div>
      </div>
      <div className="content">

        {/* AI Integration Banner */}
        <div style={{ background: 'linear-gradient(135deg, #E0F2FE 0%, #EDE9FE 100%)', border: '1px solid #C0D4E8', borderRadius: '12px', padding: '16px 20px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '16px', boxShadow: '0 4px 12px rgba(139,92,246,0.1)' }}>
          <div style={{ fontSize: '28px' }}>✨</div>
          <div>
            <div style={{ fontSize: '14px', fontWeight: '800', color: '#0A1428', marginBottom: '4px' }}>AI Email Ingestion is Active!</div>
            <div style={{ fontSize: '13px', color: '#334155' }}>Forward your PDF invoices to <strong style={{ color: '#0EA5E9' }}>your-configured-inbox@gmail.com</strong> from your registered email account, and our Zero-Trust AI will automatically extract and map them to this dashboard.</div>
          </div>
        </div>

        {/* Status filter chips */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            ['all', 'All', invoices.length, 'badge-gray'],
            ['sent', '1st Reminder', invoices.filter(i => i.status === 'sent').length, 'badge-blue'],
            ['reminded', 'Follow-up', invoices.filter(i => i.status === 'reminded').length, 'badge-amber'],
            ['escalated', 'Final Notice', invoices.filter(i => i.status === 'escalated').length, 'badge-amber'],
            ['legal', 'Legal Ready', invoices.filter(i => i.status === 'legal').length, 'badge-red'],
            ['recovered', 'Recovered', invoices.filter(i => i.recovered).length, 'badge-green'],
          ].map(([val, lbl, cnt, cls]) => (
            <div key={val} className={`chip${statusFilter === val ? ' selected' : ''}`} onClick={() => setStatusFilter(val)}>
              <span className={`badge ${cls}`} style={{ padding: '1px 6px', fontSize: 10 }}>{cnt}</span>
              {lbl}
            </div>
          ))}
        </div>

        <div className="filter-bar">
          <div className="search-wrap">
            <span className="search-icon">⌕</span>
            <input className="search-input" placeholder="Search company, invoice no, contact..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="filter-select" value={sort} onChange={e => setSort(e.target.value)}>
            <option value="days_desc">Most overdue first</option>
            <option value="days_asc">Least overdue first</option>
            <option value="amount_desc">Highest amount first</option>
            <option value="amount_asc">Lowest amount first</option>
            <option value="company">Company A–Z</option>
          </select>
        </div>

        <div className="card" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 40 }}>
                    <input type="checkbox"
                      onChange={e => {
                        if (e.target.checked) setSelectedIds(new Set(filtered.map(i => i.id)));
                        else setSelectedIds(new Set());
                      }}
                      checked={filtered.length > 0 && selectedIds.size === filtered.length}
                    />
                  </th>
                  <th>Company</th>
                  <th>Invoice</th>
                  <th>Amount</th>
                  <th>Due Date</th>
                  <th>Overdue</th>
                  <th>Status</th>
                  <th>Channel</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={9} style={{ padding: 0, border: 'none' }}>
                      <div className="empty" style={{ padding: '60px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
                        <div className="empty-icon" style={{ fontSize: 48, marginBottom: 16, opacity: 0.4 }}>🧾</div>
                        <div className="empty-title" style={{ fontSize: 15, fontWeight: 700 }}>No invoices found</div>
                        <div className="empty-sub" style={{ marginTop: 6, maxWidth: 220, textAlign: 'center', lineHeight: 1.5 }}>Add your first invoice to start tracking payments</div>
                      </div>
                    </td>
                  </tr>
                )}
                {filtered.map(inv => (
                  <tr key={inv.id} className="mobile-table-row" style={{ cursor: 'pointer' }} onClick={() => openDetail(inv)}>
                    <td data-label="Select" className="mobile-td" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selectedIds.has(inv.id)} onChange={e => {
                        const next = new Set(selectedIds);
                        if (e.target.checked) next.add(inv.id); else next.delete(inv.id);
                        setSelectedIds(next);
                      }} />
                    </td>
                    <td data-label="Company" className="mobile-td">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 30, height: 30, borderRadius: 6, background: 'var(--amber-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--amber-dark)', flexShrink: 0 }}>{getInitials(inv.company)}</div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{inv.company}</div>
                          <div style={{ fontSize: 11, color: 'var(--text3)' }}>{inv.contact}</div>
                        </div>
                      </div>
                    </td>
                    <td data-label="Invoice No" className="mobile-td"><span className="tag">{inv.invoiceNo}</span></td>
                    <td data-label="Amount" className="mobile-td"><strong>{fmtINR(inv.amount)}</strong></td>
                    <td data-label="Due Date" className="mobile-td" style={{ fontSize: 12, color: 'var(--text2)' }}>{inv.dueDate}</td>
                    <td data-label="Overdue" className="mobile-td">
                      <span className={`badge ${daysBadge(inv.daysOverdue, inv.recovered)}`}>
                        {inv.recovered ? 'Paid' : inv.daysOverdue + 'd'}
                      </span>
                    </td>
                    <td data-label="Status" className="mobile-td">
                      <span className={`badge ${STATUS_META[inv.status]?.color || 'badge-gray'}`}>
                        {STATUS_META[inv.status]?.label || inv.status}
                      </span>
                    </td>
                    <td data-label="Channel" className="mobile-td" style={{ fontSize: 12 }}>{inv.channel === 'WhatsApp' ? '💬' : '📧'} {inv.channel}</td>
                    <td data-label="Action" className="mobile-td" onClick={e => e.stopPropagation()}>
                      <button className="btn btn-sm" onClick={() => openDetail(inv)}>View →</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', gap: 12, fontSize: 12, color: 'var(--text3)', flexWrap: 'wrap' }}>
            <span>Showing {filtered.length} of {invoices.length}</span>
            <span style={{ marginLeft: 'auto' }}>Outstanding: <strong style={{ color: 'var(--amber)' }}>{fmtINR(totals.outstanding)}</strong></span>
            <span>Recovered: <strong style={{ color: 'var(--green)' }}>{fmtINR(totals.recovered)}</strong></span>
          </div>
        </div>
      </div>

      {/* Bulk Generate Modal */}
      {bulkModal && (
        <div className="overlay" onClick={() => setBulkModal(false)}>
          <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="modal-title">Bulk Generate WhatsApp Messages</div>
                <div className="modal-sub">AI drafting unique, personalized messages for {selectedIds.size} debtors</div>
              </div>
              <button className="close-btn" onClick={() => setBulkModal(false)}>×</button>
            </div>
            {bulkLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '40px 0' }}>
                <div className="spinner" style={{ width: 24, height: 24, borderTopColor: 'var(--amber)' }}></div>
                <div style={{ fontSize: 13, color: 'var(--text3)' }}>Drafting messages...</div>
              </div>
            ) : (
              <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                {bulkResults.map(({ inv, msg }, idx) => (
                  <div key={idx} style={{ padding: '12px', border: '1px solid var(--border)', borderRadius: 'var(--radius)', marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{inv.company}</div>
                      <button className="btn btn-sm btn-success"
                        onClick={() => window.open(`https://wa.me/${(inv.phone || '').replace(/\D/g, '')}?text=${encodeURIComponent(msg)}`, '_blank')}>
                        Send to {inv.contact} ↗
                      </button>
                    </div>
                    <div className="ai-box" style={{ padding: 8, fontSize: 11, minHeight: 'auto' }}>{msg || 'Error generating message.'}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Feature #7: Bulk CSV Import Modal */}
      {csvModal && (
        <div className="overlay" onClick={() => { setCsvModal(false); setCsvRows([]); setCsvError(''); }}>
          <div className="modal modal-lg" onClick={e => e.stopPropagation()} style={{ maxWidth: 680 }}>
            <div className="modal-header">
              <div>
                <div className="modal-title">⬆ Bulk Import Invoices via CSV</div>
                <div className="modal-sub">Drag & drop a CSV file or click to upload. Supports up to 500 rows.</div>
              </div>
              <button className="close-btn" onClick={() => { setCsvModal(false); setCsvRows([]); setCsvError(''); }}>×</button>
            </div>

            {csvImported > 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--green)', marginBottom: 6 }}>{csvImported} Invoices Imported!</div>
                <div style={{ fontSize: 13, color: 'var(--text3)' }}>Your invoice list will refresh automatically.</div>
              </div>
            ) : csvRows.length > 0 ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--green)' }}>✅ {csvRows.length} rows parsed successfully</span>
                  <button className="btn btn-sm" onClick={() => setCsvRows([])}>← Re-upload</button>
                </div>
                <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8, marginBottom: 16 }}>
                  <table style={{ fontSize: 11 }}>
                    <thead>
                      <tr>
                        <th>Company</th><th>Invoice No</th><th>Amount</th><th>Due Date</th><th>Channel</th>
                      </tr>
                    </thead>
                    <tbody>
                      {csvRows.map((r, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{r.company}</td>
                          <td>{r.invoiceNo}</td>
                          <td style={{ color: 'var(--amber-dark)', fontWeight: 700 }}>{fmtINR(r.amount)}</td>
                          <td style={{ color: 'var(--text3)' }}>{r.dueDate}</td>
                          <td>{r.channel}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {csvError && <div className="danger-box" style={{ marginBottom: 12 }}>❌ {csvError}</div>}
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="btn" onClick={() => setCsvRows([])}>Cancel</button>
                  <button className="btn btn-primary" onClick={importCSV} disabled={csvImporting}>
                    {csvImporting ? <><span className="spinner" /> Importing...</> : `⬆ Import ${csvRows.length} Invoices`}
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div
                  className={`csv-drop-zone${csvDragOver ? ' dragover' : ''}`}
                  onDragOver={e => { e.preventDefault(); setCsvDragOver(true); }}
                  onDragLeave={() => setCsvDragOver(false)}
                  onDrop={e => { e.preventDefault(); setCsvDragOver(false); handleCSVFile(e.dataTransfer.files[0]); }}
                  style={{ marginBottom: 16 }}
                >
                  <div className="csv-drop-zone-icon">📂</div>
                  <div className="csv-drop-zone-title">Drop your CSV file here</div>
                  <div className="csv-drop-zone-sub">or click to browse — supports .csv files up to 500 rows</div>
                  <input type="file" accept=".csv,text/csv" onChange={e => handleCSVFile(e.target.files[0])} />
                </div>
                {csvError && <div className="danger-box" style={{ marginBottom: 12 }}>❌ {csvError}</div>}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: 12, color: 'var(--text3)' }}>Required columns: Company, Amount, Due Date</div>
                  <button className="btn btn-sm" onClick={downloadTemplate}>↓ Download Template</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
