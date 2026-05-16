/* ─── RecoverAI — Shared Config, Helpers & API Utilities ─── */

/* ── Token Store ─────────────────────────────────────────── */
function getToken() { return localStorage.getItem('recoverai_token'); }
function setToken(t) { if (t) localStorage.setItem('recoverai_token', t); else localStorage.removeItem('recoverai_token'); }
function getIsAdmin() { return localStorage.getItem('recoverai_is_admin') === 'true'; }
function setIsAdmin(v) { localStorage.setItem('recoverai_is_admin', String(v)); }

/* ── Authenticated Fetch (with auto-refresh) ─────────────── */
async function authFetch(url, opts = {}) {
  const token = getToken();
  const headers = { ...(opts.headers || {}) };
  if (token) headers['Authorization'] = 'Bearer ' + token;
  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(opts.body instanceof FormData) && !headers['Content-Type'] && opts.method && opts.method !== 'GET') {
    // caller sets Content-Type if needed
  }
  let res = await fetch(url, { ...opts, headers });

  // Auto-refresh on 401
  if (res.status === 401) {
    const refresh = localStorage.getItem('recoverai_refresh');
    if (refresh) {
      try {
        const rRes = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (rRes.ok) {
          const rData = await rRes.json();
          setToken(rData.access_token);
          localStorage.setItem('recoverai_refresh', rData.refresh_token);
          headers['Authorization'] = 'Bearer ' + rData.access_token;
          res = await fetch(url, { ...opts, headers });
        } else {
          // Refresh failed — force logout
          setToken(null);
          localStorage.removeItem('recoverai_refresh');
          localStorage.removeItem('recoverai_user_details');
          localStorage.removeItem('recoverai_is_admin');
          window.location.replace('/');
          return res;
        }
      } catch (e) {
        console.error('Token refresh error:', e);
      }
    }
  }
  return res;
}

/* ── Formatting Helpers ──────────────────────────────────── */
function fmtINR(n) { return '₹' + Number(n).toLocaleString('en-IN'); }
function getInitials(n) { return (n || '').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || '??'; }
function daysBadge(d, rec) {
  if (rec) return 'badge-green';
  if (d >= 45) return 'badge-red';
  if (d >= 21) return 'badge-amber';
  return 'badge-blue';
}

/* ── Number to Words (for legal PDFs) ────────────────────── */
function numberToWords(num) {
  const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
  const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];
  function words(n) {
    if (n < 20) return ones[n];
    if (n < 100) return tens[Math.floor(n / 10)] + (n % 10 ? ' ' + ones[n % 10] : '');
    if (n < 1000) return ones[Math.floor(n / 100)] + ' Hundred' + (n % 100 ? ' ' + words(n % 100) : '');
    if (n < 100000) return words(Math.floor(n / 1000)) + ' Thousand' + (n % 1000 ? ' ' + words(n % 1000) : '');
    if (n < 10000000) return words(Math.floor(n / 100000)) + ' Lakh' + (n % 100000 ? ' ' + words(n % 100000) : '');
    return words(Math.floor(n / 10000000)) + ' Crore' + (n % 10000000 ? ' ' + words(n % 10000000) : '');
  }
  const n = Math.round(Number(num));
  return n === 0 ? 'Zero' : words(n);
}

/* ── AI API Call ─────────────────────────────────────────── */
async function callAI(systemPrompt, prompt, invoiceData, tone) {
  const invoice_data = invoiceData ? {
    invoice_no: invoiceData.invoiceNo,
    company: invoiceData.company,
    contact: invoiceData.contact,
    amount: invoiceData.amount,
    days_overdue: invoiceData.daysOverdue,
    due_date: invoiceData.dueDate,
    phone: invoiceData.phone,
    email: invoiceData.email,
    status: invoiceData.status,
  } : {};
  const res = await authFetch('/api/generate-message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, invoice_data, tone: tone || 'Firm Warning' })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'API Error');
  return data.message || '';
}

/* ── WhatsApp Deep Link ──────────────────────────────────── */
function sendViaWhatsApp(phone, messageText) {
  const cleanPhone = (phone || '').replace(/\D/g, '');
  const encoded = encodeURIComponent(messageText || '');
  const url = cleanPhone ? `https://wa.me/${cleanPhone}?text=${encoded}` : `https://wa.me/?text=${encoded}`;
  window.open(url, '_blank');
}

/* ── Legal PDF Generator ─────────────────────────────────── */
async function generateLegalPDF(inv, settings) {
  const id = inv.interest_data || {};
  const penalty = id.interest_accrued || 0;
  const totalClaim = id.total_claim || inv.amount;
  const days = id.days_overdue || inv.daysOverdue || 0;
  const today = new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });

  const el = document.createElement('div');
  el.innerHTML = `
    <div style="font-family: 'Times New Roman', Georgia, serif; padding: 48px 56px; color: #1a1a1a; font-size: 13px; line-height: 1.8; max-width: 210mm;">
      <div style="text-align: center; border-bottom: 3px double #8B0000; padding-bottom: 16px; margin-bottom: 24px;">
        <div style="font-size: 20px; font-weight: bold; color: #8B0000; letter-spacing: 1px; text-transform: uppercase;">${settings?.businessName || 'RecoverAI Legal Services'}</div>
        <div style="font-size: 11px; color: #555; margin-top: 4px;">${settings?.ownerName || ''} &nbsp;|&nbsp; ${settings?.phone || ''} &nbsp;|&nbsp; ${settings?.email || ''}</div>
        ${settings?.gstin ? `<div style="font-size: 10px; color: #777; margin-top: 2px;">GSTIN: ${settings.gstin}</div>` : ''}
      </div>
      <div style="text-align: right; font-size: 12px; color: #555; margin-bottom: 20px;">Date: <strong>${today}</strong></div>
      <div style="text-align: center; font-size: 16px; font-weight: bold; color: #8B0000; margin-bottom: 4px; text-decoration: underline;">LEGAL NOTICE</div>
      <div style="text-align: center; font-size: 11px; color: #555; margin-bottom: 24px;">Under the Micro, Small and Medium Enterprises Development Act, 2006</div>
      <div style="margin-bottom: 20px;">
        <strong>To,</strong><br/>
        <strong>${inv.company}</strong><br/>
        Attn: ${inv.contact || 'The Proprietor / Director'}<br/>
        ${inv.gstin ? 'GSTIN: ' + inv.gstin + '<br/>' : ''}
        ${inv.email ? 'Email: ' + inv.email + '<br/>' : ''}
        ${inv.phone ? 'Phone: ' + inv.phone : ''}
      </div>
      <div style="margin-bottom: 16px;"><strong>Subject: Demand for Payment of Invoice No. ${inv.invoiceNo} and Accrued Interest under MSMED Act, 2006</strong></div>
      <div style="margin-bottom: 14px;">Dear Sir/Madam,</div>
      <div style="margin-bottom: 14px; text-align: justify;">Under instructions from my client, <strong>${settings?.businessName || '[Creditor Business Name]'}</strong>${settings?.gstin ? ' (GSTIN: ' + settings.gstin + ')' : ''}, I hereby serve this Legal Notice upon you as required under the <strong>Micro, Small and Medium Enterprises Development Act, 2006</strong> ("MSMED Act").</div>
      <div style="margin-bottom: 14px; text-align: justify;">My client supplied goods/services to your company as evidenced by <strong>Invoice No. ${inv.invoiceNo}</strong>, dated <strong>${inv.issueDate || 'N/A'}</strong>, for an amount of <strong>₹${Number(inv.amount).toLocaleString('en-IN')}</strong>. The said amount became due and payable on <strong>${inv.dueDate || 'N/A'}</strong>. As of the date of this notice, the payment is overdue by <strong>${days} days</strong>.</div>
      <div style="margin: 20px 0; border: 1.5px solid #8B0000; border-radius: 4px; overflow: hidden;">
        <div style="background: #8B0000; color: white; padding: 8px 16px; font-weight: bold; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Statement of Claim</div>
        <div style="display: flex; justify-content: space-between; padding: 10px 16px; border-bottom: 1px solid #ddd;"><span>Base Invoice Amount</span><strong>₹${Number(inv.amount).toLocaleString('en-IN')}</strong></div>
        <div style="display: flex; justify-content: space-between; padding: 10px 16px; border-bottom: 1px solid #ddd; background: #fff5f5; color: #8B0000;"><span>Interest under MSMED Act §15 (19.5% p.a. compound × ${days} days)</span><strong>+ ₹${Number(penalty).toLocaleString('en-IN')}</strong></div>
        <div style="display: flex; justify-content: space-between; padding: 12px 16px; font-size: 14px; font-weight: bold; background: #fafafa;"><span>Total Amount Payable</span><span style="color: #8B0000; font-size: 15px;">₹${Number(totalClaim).toLocaleString('en-IN')}</span></div>
      </div>
      <div style="margin-bottom: 14px; text-align: justify;">Under <strong>Section 15</strong> of the MSMED Act, 2006, any buyer who fails to make payment to a micro or small enterprise is liable to pay compound interest with monthly rests at three times the bank rate notified by the Reserve Bank of India. The current applicable rate is <strong>19.5% per annum</strong>.</div>
      <div style="margin: 20px 0; padding: 14px 16px; background: #fff5f5; border-left: 4px solid #8B0000; font-weight: bold;">You are hereby called upon to pay the total sum of ₹${Number(totalClaim).toLocaleString('en-IN')} (Rupees ${numberToWords(totalClaim)} Only) within <strong>15 (Fifteen) days</strong> from the date of receipt of this notice.</div>
      <div style="margin-bottom: 14px; padding-left: 20px;">
        1. File a reference before the <strong>Micro and Small Enterprise Facilitation Council</strong> under Section 18 of the MSMED Act, 2006.<br/>
        2. File a case on the <strong>MSME Samadhaan Portal</strong> (Government of India).<br/>
        3. Initiate appropriate <strong>civil and/or criminal proceedings</strong> before the competent court of law.
      </div>
      <div style="margin-bottom: 8px;">Yours faithfully,</div>
      <div style="margin-top: 36px;">
        <strong>${settings?.ownerName || '[Authorised Signatory]'}</strong><br/>
        ${settings?.businessName || '[Business Name]'}<br/>
        ${settings?.phone ? 'Phone: ' + settings.phone + '<br/>' : ''}
        ${settings?.email ? 'Email: ' + settings.email : ''}
      </div>
      <div style="margin-top: 40px; padding-top: 12px; border-top: 1px solid #ccc; font-size: 9px; color: #999; text-align: center;">
        This notice has been issued under the provisions of the MSMED Act, 2006 and is without prejudice to all other rights and remedies available to the creditor under applicable laws.
        <br/>Generated by RecoverAI — MSME Invoice Recovery Platform
      </div>
    </div>
  `;

  const opt = {
    margin: 0,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };
  const filename = `Legal_Notice_${inv.invoiceNo || 'Draft'}.pdf`;
  const blob = await html2pdf().set(opt).from(el).outputPdf('blob');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ── Icon SVG Component ──────────────────────────────────── */
function IconSvg({ path, size = 18 }) {
  if (Array.isArray(path)) {
    return React.createElement('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' },
      ...path.map((d, i) => React.createElement('path', { key: i, d }))
    );
  }
  return React.createElement('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' },
    React.createElement('path', { d: path })
  );
}

/* ── Constants ───────────────────────────────────────────── */
const STATUS_META = {
  sent:      { label: '1st Reminder Sent', color: 'badge-blue',  days: '0–14d overdue' },
  reminded:  { label: 'Follow-up Sent',    color: 'badge-amber', days: '15–34d overdue' },
  escalated: { label: 'Final Notice',      color: 'badge-amber', days: '35–44d overdue' },
  legal:     { label: 'Legal Draft Ready', color: 'badge-red',   days: '45d+ overdue' },
  recovered: { label: 'Recovered',         color: 'badge-green', days: '' },
};

const SYSTEM_PROMPT = `You are RecoverAI's intelligent recovery agent for Indian MSME businesses.
You draft professional, contextually appropriate debt-recovery messages for Indian businesses.
Key rules:
- WhatsApp messages: conversational, warm but firm, 3-5 lines, can use "ji", "sir/madam"
- Emails: professional format with Subject line, opening, body, closing signature
- Legal notices: formal, cite MSMED Act 2006 Sections 15-17, give 15-day ultimatum, formal language
- NEVER be aggressive or threatening; always offer a payment arrangement path
- Include specific invoice number, amount, and due date in every message
- Sign off messages as "[Business Name] Collections Team"`;

const ACTIVITY_LOG = [
  { id: 1, type: 'legal',    text: '<strong>Legal notice generated</strong> for Navi Mumbai Exports (₹1,20,000)',  time: '2 hours ago',      color: '#FEE2E2', iconColor: '#EF4444' },
  { id: 2, type: 'recovery', text: '<strong>Invoice recovered</strong> — Thane IT Solutions paid ₹67,000',          time: 'Yesterday, 3:42 PM', color: '#DCFCE7', iconColor: '#10B981' },
  { id: 3, type: 'reminder', text: '<strong>WhatsApp reminder sent</strong> to Sharma Traders for INV-2024-041',    time: 'Yesterday, 10:00 AM', color: '#FEF3C7', iconColor: '#F59E0B' },
  { id: 4, type: 'new',      text: '<strong>New invoice added</strong> — Bandra Café Co. ₹15,000 (INV-2025-044)',  time: '2 days ago',        color: '#DBEAFE', iconColor: '#3B82F6' },
  { id: 5, type: 'reminder', text: '<strong>Email reminder sent</strong> to Pune Digital Agency for INV-2025-018', time: '3 days ago',        color: '#FFEDD5', iconColor: '#F97316' },
  { id: 6, type: 'recovery', text: '<strong>Invoice recovered</strong> — Nagpur Steel Works paid ₹1,95,000',        time: '5 days ago',        color: '#DCFCE7', iconColor: '#10B981' },
];
