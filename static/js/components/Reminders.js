/* ─── Reminders Page ─── */
function Reminders({ invoices, openDetail }) {
  const active = invoices.filter(i => !i.recovered && i.daysOverdue > 0).sort((a, b) => b.daysOverdue - a.daysOverdue);

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="page-title">Reminders Schedule</div>
          <div className="page-sub">Upcoming and past automated follow-ups</div>
        </div>
      </div>
      <div className="content">
        <div className="card">
          <div className="card-header" style={{ marginBottom: 16 }}>
            <div className="card-title">Pending Reminders Queue</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {active.length === 0 && (
              <div className="empty" style={{ padding: 40, textAlign: 'center', color: 'var(--text3)' }}>No pending reminders.</div>
            )}
            {active.map(inv => {
              let nextAction = '', badge = '';
              if (inv.daysOverdue >= 45) { nextAction = 'File MSME Samadhaan Case'; badge = 'badge-red'; }
              else if (inv.daysOverdue >= 35) { nextAction = 'Send Final Legal Notice'; badge = 'badge-red'; }
              else if (inv.daysOverdue >= 21) { nextAction = 'Send Warning Email & WhatsApp'; badge = 'badge-amber'; }
              else { nextAction = 'Send Gentle Follow-up'; badge = 'badge-blue'; }

              return (
                <div key={inv.id} className="reminder-item" style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{inv.company} <span style={{ color: 'var(--text3)', fontWeight: 400 }}>({inv.invoiceNo})</span></div>
                    <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 4 }}>Due {inv.dueDate} — <strong style={{ color: 'var(--red)' }}>{inv.daysOverdue} days overdue</strong></div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className={`badge ${badge}`}>{nextAction}</span>
                    <button className="btn btn-sm btn-primary" onClick={() => openDetail(inv)}>Review →</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
