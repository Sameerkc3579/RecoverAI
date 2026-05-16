/* ── AdminActionBtn — premium hover-animated action button ── */
function AdminActionBtn({ icon, label, color, bg, border, hoverBg, hoverBorder, hoverColor, onClick }) {
  const [hovered, setHovered] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: '8px 16px', borderRadius: 10, cursor: 'pointer',
        background: hovered ? hoverBg : bg,
        border: `1.5px solid ${hovered ? hoverBorder : border}`,
        color: hovered ? hoverColor : color,
        fontSize: 13, fontWeight: 700, fontFamily: 'inherit',
        whiteSpace: 'nowrap', flexShrink: 0,
        transform: hovered ? 'scale(1.04)' : 'scale(1)',
        boxShadow: hovered
          ? `0 4px 14px rgba(0,0,0,0.10), 0 1px 4px rgba(0,0,0,0.06)`
          : '0 1px 3px rgba(0,0,0,0.05)',
        transition: 'all 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      <span style={{ fontSize: 15, lineHeight: 1 }}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

/* Admin Dashboard — God Mode */
function AdminDashboard() {
  const [tab, setTab] = React.useState('overview');
  const [stats, setStats] = React.useState(null);
  const [users, setUsers] = React.useState([]);
  const [activity, setActivity] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedUser, setSelectedUser] = React.useState(null);
  const [userDetail, setUserDetail] = React.useState(null);
  const [search, setSearch] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [modal, setModal] = React.useState(null);
  const [editForm, setEditForm] = React.useState({});
  const [pwForm, setPwForm] = React.useState('');
  const [planForm, setPlanForm] = React.useState('');
  const [saving, setSaving] = React.useState(false);

  // Force inject responsive CSS to bypass browser CSS caching issues
  React.useEffect(() => {
    if (!document.getElementById('admin-dash-styles')) {
      const style = document.createElement('style');
      style.id = 'admin-dash-styles';
      style.innerHTML = `
        .admin-kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
        .admin-detail-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
        
        .admin-actions-bar {
          background: #fff; border-bottom: 1px solid #E8EFF8; padding: 12px 24px;
          display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
          box-shadow: 0 2px 12px rgba(10,20,40,0.06);
        }
        .admin-actions-label-wrap {
          display: flex; align-items: center; gap: 8px;
          padding-right: 20px; border-right: 1.5px solid #E2E8F0;
        }
        .admin-actions-btn-group {
          display: flex; align-items: center; gap: 8px; flex: 1; flex-wrap: wrap;
        }
        
        @media (max-width: 1100px) {
          .admin-kpi-grid { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 900px) {
          .admin-detail-layout { grid-template-columns: 1fr; }
          .admin-actions-bar { padding: 12px 16px; flex-direction: column; align-items: flex-start; gap: 12px; }
          .admin-actions-label-wrap { padding-right: 0; border-right: none; border-bottom: 1.5px solid #E2E8F0; padding-bottom: 8px; width: 100%; }
          .admin-actions-btn-group { flex-wrap: wrap; width: 100%; }
        }
        @media (max-width: 600px) {
          .admin-kpi-grid { grid-template-columns: 1fr 1fr; }
        }
        
        .admin-back-btn {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 6px 12px; background: #fff; border: 1.5px solid #E2E8F0;
          border-radius: 8px; font-size: 12px; font-weight: 700; color: #475569;
          cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .admin-back-btn:hover {
          background: #F8FAFC; border-color: #CBD5E1; color: #0F172A;
          transform: translateX(-3px); box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  const loadOverview = () => {
    setLoading(true);
    Promise.all([
      authFetch('/api/admin/dashboard-stats').then(r => r.json()),
      authFetch('/api/admin/users').then(r => r.json()),
      authFetch('/api/admin/activity').then(r => r.json()),
    ]).then(([s, u, a]) => {
      setStats(s);
      setUsers(Array.isArray(u) ? u : []);
      setActivity(Array.isArray(a) ? a : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  React.useEffect(() => { loadOverview(); }, []);

  const api = (url, opts = {}) =>
    authFetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts })
      .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d.detail || 'Error'); return d; });

  const loadUser = (id) => {
    authFetch('/api/admin/users/' + id).then(r => r.json()).then(d => {
      setSelectedUser(d.user); setUserDetail(d); setTab('detail');
    });
  };

  const doSave = async (action) => {
    setSaving(true);
    try {
      if (action === 'edit') await api('/api/admin/users/' + selectedUser._id, { method: 'PUT', body: JSON.stringify(editForm) });
      else if (action === 'password') await api('/api/admin/users/' + selectedUser._id + '/reset-password', { method: 'POST', body: JSON.stringify({ new_password: pwForm }) });
      else if (action === 'plan') await api('/api/admin/users/' + selectedUser._id + '/change-plan', { method: 'POST', body: JSON.stringify({ plan: planForm }) });
      else if (action === 'toggle') await api('/api/admin/users/' + selectedUser._id + '/toggle-active', { method: 'POST' });
      else if (action === 'delete') {
        await api('/api/admin/users/' + selectedUser._id, { method: 'DELETE' });
        setTab('users'); setSelectedUser(null); setUserDetail(null); loadOverview(); setModal(null); setSaving(false); return;
      } else if (action === 'deleteInv') {
        await api('/api/admin/invoices/' + modal.invId, { method: 'DELETE' });
        loadUser(selectedUser._id); setModal(null); setSaving(false); return;
      }
      setModal(null); loadUser(selectedUser._id); loadOverview();
    } catch (e) { alert(e.message); }
    setSaving(false);
  };

  const filtered = users.filter(u => {
    const q = search.toLowerCase();
    const ms = !q || (u.business_name||'').toLowerCase().includes(q) || (u.email||'').toLowerCase().includes(q);
    const mf = statusFilter === 'all' || (statusFilter === 'active' ? u.is_active !== false : u.is_active === false);
    return ms && mf;
  });

  const pc = p => p === 'Enterprise' ? 'var(--purple)' : p === 'Professional' ? 'var(--blue)' : 'var(--text3)';
  const badge = (active) => ({
    fontSize: 11, padding: '2px 8px', borderRadius: 10, fontWeight: 600,
    background: active !== false ? 'rgba(52,199,89,0.1)' : 'rgba(255,59,48,0.08)',
    color: active !== false ? 'var(--green)' : 'var(--red)'
  });

  if (loading && tab !== 'detail') return React.createElement('div', {style:{padding:60,textAlign:'center',color:'var(--text3)'}}, 'Loading platform data…');

  const AdminModal = ({title, children, onSave, saveLbl, danger}) => (
    <div className="modal-overlay" onClick={() => setModal(null)}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{maxWidth:440}}>
        <div style={{fontWeight:700,fontSize:17,marginBottom:18}}>{title}</div>
        {children}
        <div style={{display:'flex',gap:8,marginTop:22,justifyContent:'flex-end'}}>
          <button className="btn-secondary" onClick={() => setModal(null)}>Cancel</button>
          <button className="btn-primary" style={danger?{background:'var(--red)',borderColor:'var(--red)'}:{}} onClick={onSave} disabled={saving}>{saving?'Saving…':saveLbl}</button>
        </div>
      </div>
    </div>
  );

  if (tab === 'overview') return (
    <div>
      <div className="topbar" style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div>
          <div className="page-title">Platform Overview</div>
          <div className="page-sub">God Mode — System-wide analytics across all users</div>
        </div>
        <div style={{display:'flex',gap:8}}>
          <button className="btn-secondary" onClick={() => setTab('users')}>Manage Users →</button>
          <button className="btn-primary" onClick={() => {
            authFetch('/api/admin/export/users').then(r=>r.json()).then(data=>{
              const rows = [['Email','Business','Plan','Active','Invoices','Tracked','Recovered','Joined'],
                ...data.map(u=>[u.email,u.business_name||'',u.plan||'Starter',u.is_active!==false,u.invoice_count||0,u.total_tracked_value||0,u.total_recovered_value||0,(u.created_at||'').substring(0,10)])];
              const blob = new Blob([rows.map(r=>r.join(',')).join('\n')],{type:'text/csv'});
              const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='users.csv';a.click();
            });
          }}>⬇ Export CSV</button>
        </div>
      </div>
      <div className="content">
        <div className="admin-metric-grid" style={{gridTemplateColumns:'repeat(4,1fr)'}}>
          {[
            {lbl:'Total Users',val:stats?.total_users||0,sub:(stats?.active_users||0)+' active',c:'var(--blue)'},
            {lbl:'Platform Tracked',val:fmtINR(stats?.total_tracked_value||0),sub:(stats?.total_invoices||0)+' invoices',c:'var(--orange)'},
            {lbl:'Total Recovered',val:fmtINR(stats?.total_recovered_value||0),sub:'System-wide',c:'var(--green)'},
            {lbl:'Legal Queue',val:stats?.legal_queue_count||0,sub:'Overdue ≥45 days',c:'var(--red)'},
          ].map((m,i)=>(
            <div key={i} className="metric-card" style={{borderLeft:'4px solid '+m.c}}>
              <div className="metric-label">{m.lbl}</div>
              <div className="metric-value" style={{color:m.c}}>{m.val}</div>
              <div className="metric-change" style={{color:'var(--text3)'}}>{m.sub}</div>
            </div>
          ))}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:16,marginTop:16}}>
          <div className="card" style={{padding:0}}>
            <div style={{padding:'12px 16px',borderBottom:'1px solid var(--border)',fontWeight:700,fontSize:13}}>User Overview</div>
            <div style={{padding:20}}>
              <div style={{fontSize:38,fontWeight:800,color:'var(--blue)'}}>{stats?.new_users_this_month||0}</div>
              <div style={{fontSize:12,color:'var(--text3)',marginTop:2}}>New registrations this month</div>
              <div style={{display:'flex',gap:10,marginTop:14}}>
                {[['Active',stats?.active_users||0,'var(--green)','rgba(52,199,89,0.08)'],['Inactive',stats?.inactive_users||0,'var(--red)','rgba(255,59,48,0.06)']].map(([lbl,val,c,bg])=>(
                  <div key={lbl} style={{flex:1,background:bg,borderRadius:8,padding:'10px 14px',textAlign:'center'}}>
                    <div style={{fontSize:22,fontWeight:800,color:c}}>{val}</div>
                    <div style={{fontSize:11,color:'var(--text3)',marginTop:2}}>{lbl}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="card" style={{padding:0}}>
            <div style={{padding:'12px 16px',borderBottom:'1px solid var(--border)',fontWeight:700,fontSize:13}}>Recent Activity</div>
            <div style={{maxHeight:160,overflowY:'auto'}}>
              {activity.slice(0,8).map((a,i)=>(
                <div key={i} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 16px',borderBottom:'1px solid var(--border)'}}>
                  <span style={{fontSize:15}}>{a.icon}</span>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{fontSize:12,fontWeight:500,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{a.text}</div>
                    <div style={{fontSize:10,color:'var(--text3)'}}>{(a.time||'').substring(0,10)}</div>
                  </div>
                </div>
              ))}
              {!activity.length&&<div style={{padding:20,textAlign:'center',color:'var(--text3)',fontSize:12}}>No recent activity</div>}
            </div>
          </div>
        </div>
        <div className="card" style={{padding:0,marginTop:16}}>
          <div style={{padding:'12px 16px',borderBottom:'1px solid var(--border)',fontWeight:700,fontSize:13,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <span>Top Users by Value Tracked</span>
            <button className="btn-secondary" style={{fontSize:11,padding:'3px 10px'}} onClick={()=>setTab('users')}>View All →</button>
          </div>
          <div className="table-wrap"><table><thead><tr>
            <th>Business / Email</th><th>Plan</th><th style={{textAlign:'right'}}>Invoices</th>
            <th style={{textAlign:'right'}}>Tracked</th><th style={{textAlign:'right'}}>Recovered</th><th>Status</th>
          </tr></thead><tbody>
            {[...users].sort((a,b)=>(b.total_tracked_value||0)-(a.total_tracked_value||0)).slice(0,5).map(u=>(
              <tr key={u._id} onClick={()=>loadUser(u._id)} style={{cursor:'pointer'}} className="mobile-table-row">
                <td><div style={{fontWeight:600}}>{u.business_name||'N/A'}</div><div style={{fontSize:11,color:'var(--text3)'}}>{u.email}</div></td>
                <td><span style={{fontSize:11,fontWeight:700,color:pc(u.plan)}}>{u.plan||'Starter'}</span></td>
                <td style={{textAlign:'right',fontWeight:600}}>{u.invoice_count||0}</td>
                <td style={{textAlign:'right',fontFamily:'monospace'}}>{fmtINR(u.total_tracked_value||0)}</td>
                <td style={{textAlign:'right',fontFamily:'monospace',color:'var(--green)',fontWeight:600}}>{fmtINR(u.total_recovered_value||0)}</td>
                <td><span style={badge(u.is_active)}>{u.is_active!==false?'Active':'Inactive'}</span></td>
              </tr>
            ))}
          </tbody></table></div>
        </div>
      </div>
    </div>
  );

  if (tab === 'users') return (
    <div>
      <div className="topbar" style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div>
          <div className="page-title" style={{display:'flex',alignItems:'center',gap:8}}>
            <button className="admin-back-btn" onClick={()=>setTab('overview')}><span style={{fontSize:14}}>←</span> Overview</button>
            All Platform Users
          </div>
          <div className="page-sub">{users.length} total registered accounts</div>
        </div>
      </div>
      <div className="content">
        <div style={{display:'flex',gap:10,marginBottom:16,flexWrap:'wrap',alignItems:'center'}}>
          <input className="input-field" placeholder="🔍  Search name or email…" value={search} onChange={e=>setSearch(e.target.value)} style={{flex:1,minWidth:260,maxWidth:500}}/>
          <select className="input-field" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} style={{width:140}}>
            <option value="all">All Status</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>
          <div style={{fontSize:13,color:'var(--text3)',marginLeft:'auto'}}>
            <strong style={{color:'var(--text)'}}>{filtered.length}</strong> / {users.length} users
          </div>
        </div>
        <div className="card" style={{padding:0}}>
          <div className="table-wrap"><table>
            <thead><tr>
              <th>Business / Email</th><th>Plan</th><th>Joined</th>
              <th style={{textAlign:'right'}}>Invoices</th>
              <th style={{textAlign:'right'}}>Tracked</th>
              <th style={{textAlign:'right'}}>Recovered</th>
              <th>Status</th>
            </tr></thead>
            <tbody>
              {filtered.map(u=>(
                <tr key={u._id} onClick={()=>loadUser(u._id)} style={{cursor:'pointer'}} className="mobile-table-row">
                  <td>
                    <div style={{fontWeight:600}}>{u.business_name||'—'}</div>
                    <div style={{fontSize:11,color:'var(--text3)'}}>{u.email}</div>
                  </td>
                  <td><span style={{fontSize:11,fontWeight:700,color:pc(u.plan)}}>{u.plan||'Starter'}</span></td>
                  <td style={{fontSize:12,color:'var(--text2)'}}>{(u.created_at||'').substring(0,10)||'—'}</td>
                  <td style={{textAlign:'right',fontWeight:600}}>{u.invoice_count||0}</td>
                  <td style={{textAlign:'right',fontFamily:'monospace'}}>{fmtINR(u.total_tracked_value||0)}</td>
                  <td style={{textAlign:'right',fontFamily:'monospace',color:'var(--green)',fontWeight:600}}>{fmtINR(u.total_recovered_value||0)}</td>
                  <td><span style={badge(u.is_active)}>{u.is_active!==false?'Active':'Inactive'}</span></td>
                </tr>
              ))}
              {!filtered.length && (
                <tr><td colSpan={7} style={{textAlign:'center',padding:50,color:'var(--text3)'}}>
                  {search || statusFilter!=='all' ? 'No users match your filters.' : 'No users registered yet.'}
                </td></tr>
              )}
            </tbody>
          </table></div>
        </div>
      </div>
    </div>
  );

  if (tab === 'detail' && selectedUser) {
    const u = selectedUser;
    const s = userDetail?.stats || {};
    const invs = userDetail?.invoices || [];
    return (
      <div>
        {modal === 'edit' && (
          <AdminModal title="Edit User Details" onSave={()=>doSave('edit')} saveLbl="Save Changes">
            {[['Business Name','business_name','text'],['Email Address','email','email'],['Phone Number','phone','tel'],['City','city','text']].map(([lbl,k,t])=>(
              <div className="input-group" key={k}>
                <label>{lbl}</label>
                <input type={t} className="input-field" value={editForm[k]||''} onChange={e=>setEditForm({...editForm,[k]:e.target.value})}/>
              </div>
            ))}
          </AdminModal>
        )}
        {modal === 'password' && (
          <AdminModal title="Reset User Password" onSave={()=>doSave('password')} saveLbl="Reset Password">
            <div style={{padding:'10px 12px',background:'rgba(0,122,255,0.06)',borderRadius:8,marginBottom:14,fontSize:13,color:'var(--text2)'}}>
              Setting a new password for <strong>{u.email}</strong>
            </div>
            <div className="input-group">
              <label>New Password</label>
              <input type="password" className="input-field" value={pwForm} onChange={e=>setPwForm(e.target.value)} placeholder="Min 8 chars, 1 uppercase, 1 number"/>
            </div>
          </AdminModal>
        )}
        {modal === 'plan' && (
          <AdminModal title="Change Subscription Plan" onSave={()=>doSave('plan')} saveLbl="Update Plan">
            <div style={{display:'flex',flexDirection:'column',gap:10}}>
              {['Starter','Professional','Enterprise'].map(p=>(
                <button key={p} onClick={()=>setPlanForm(p)} style={{
                  padding:'12px 16px',borderRadius:10,cursor:'pointer',textAlign:'left',
                  border:'2px solid '+(planForm===p?'var(--blue)':'var(--border)'),
                  background:planForm===p?'rgba(0,122,255,0.06)':'var(--card-bg)',
                  color:'var(--text)',fontFamily:'inherit'
                }}>
                  <div style={{fontWeight:700,color:pc(p)}}>{p}</div>
                  <div style={{fontSize:11,color:'var(--text3)',marginTop:2}}>
                    {p==='Starter'?'Basic recovery features':p==='Professional'?'Advanced automation + analytics':'Full suite + priority support'}
                  </div>
                </button>
              ))}
            </div>
          </AdminModal>
        )}
        {modal === 'delete' && (
          <AdminModal title="Delete User Account" onSave={()=>doSave('delete')} saveLbl="Yes, Delete Permanently" danger>
            <div style={{background:'rgba(255,59,48,0.06)',border:'1px solid rgba(255,59,48,0.2)',borderRadius:10,padding:14}}>
              <div style={{fontWeight:700,color:'var(--red)',marginBottom:6}}>⚠️  This action is irreversible</div>
              <div style={{fontSize:13,color:'var(--text2)'}}>Permanently delete <strong>{u.email}</strong> and all their data — {s.total_invoices||0} invoices worth {fmtINR(s.total_value||0)}.</div>
            </div>
          </AdminModal>
        )}
        {modal?.type === 'deleteInv' && (
          <AdminModal title="Delete Invoice" onSave={()=>doSave('deleteInv')} saveLbl="Delete Invoice" danger>
            <div style={{fontSize:13,color:'var(--text2)'}}>
              Permanently delete the invoice from <strong>{modal.company}</strong> ({fmtINR(modal.amount)})? This cannot be undone.
            </div>
          </AdminModal>
        )}
        {modal?.type === 'editInv' && (
          <AdminModal title="Edit Invoice" onSave={async()=>{setSaving(true);try{await api('/api/admin/invoices/'+modal.invId,{method:'PUT',body:JSON.stringify(modal.form)});loadUser(u._id);setModal(null);}catch(e){alert(e.message);}setSaving(false);}} saveLbl="Save Invoice">
            {[['Customer/Company','company','text'],['Amount (INR)','amount','number'],['Days Overdue','daysOverdue','number']].map(([lbl,k,t])=>(
              <div className="input-group" key={k}>
                <label>{lbl}</label>
                <input type={t} className="input-field" value={modal.form[k]||''} onChange={e=>setModal({...modal,form:{...modal.form,[k]:t==='number'?Number(e.target.value):e.target.value}})}/>
              </div>
            ))}
            <div className="input-group">
              <label>Status</label>
              <select className="input-field" value={modal.form.status||''} onChange={e=>setModal({...modal,form:{...modal.form,status:e.target.value}})}>
                {['sent','reminded','escalated','legal','recovered'].map(s=><option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </AdminModal>
        )}
        <div className="topbar">
          <div className="page-title" style={{display:'flex',alignItems:'center',gap:8}}>
            <button className="admin-back-btn" onClick={()=>{setTab('users');setSelectedUser(null);setUserDetail(null);}}><span style={{fontSize:14}}>←</span> Users</button>
            {u.business_name || u.email}
          </div>
          <div className="page-sub">{u.email} &bull; Joined {(u.created_at||'').substring(0,10)||'—'} &bull; <span style={{color:u.is_active!==false?'var(--green)':'var(--red)',fontWeight:600}}>{u.is_active!==false?'Active':'Inactive'}</span></div>
        </div>
        <div className="admin-actions-bar">
          {/* Label */}
          <div className="admin-actions-label-wrap">
            <div style={{
              width: 28, height: 28, borderRadius: 8, flexShrink: 0,
              background: 'linear-gradient(135deg, #1D4ED8, #7C3AED)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13,
            }}>⚡</div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 800, color: '#0F172A', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Admin Actions</div>
              <div style={{ fontSize: 9, color: '#94A3B8', fontWeight: 500 }}>God Mode Controls</div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="admin-actions-btn-group">
            {[
              {
                icon: '✏️', label: 'Edit Details', color: '#1D4ED8', bg: '#EFF6FF', border: '#BFDBFE',
                hoverBg: '#DBEAFE', hoverBorder: '#3B82F6', hoverColor: '#1E40AF',
                onClick: () => { setEditForm({ business_name: u.business_name||'', email: u.email||'', phone: u.phone||'', city: u.city||'' }); setModal('edit'); }
              },
              {
                icon: '🔑', label: 'Reset Password', color: '#7C3AED', bg: '#F5F3FF', border: '#DDD6FE',
                hoverBg: '#EDE9FE', hoverBorder: '#8B5CF6', hoverColor: '#6D28D9',
                onClick: () => { setPwForm(''); setModal('password'); }
              },
              {
                icon: '💎', label: 'Change Plan', color: '#0369A1', bg: '#E0F2FE', border: '#BAE6FD',
                hoverBg: '#BAE6FD', hoverBorder: '#0EA5E9', hoverColor: '#0369A1',
                onClick: () => { setPlanForm(u.plan || 'Starter'); setModal('plan'); }
              },
              u.is_active !== false
                ? {
                  icon: '⏸', label: 'Deactivate', color: '#B45309', bg: '#FFFBEB', border: '#FDE68A',
                  hoverBg: '#FEF3C7', hoverBorder: '#F59E0B', hoverColor: '#92400E',
                  onClick: async () => { setSaving(true); await doSave('toggle'); }
                }
                : {
                  icon: '▶', label: 'Activate', color: '#047857', bg: '#ECFDF5', border: '#A7F3D0',
                  hoverBg: '#D1FAE5', hoverBorder: '#10B981', hoverColor: '#065F46',
                  onClick: async () => { setSaving(true); await doSave('toggle'); }
                },
            ].map((btn, i) => (
              <AdminActionBtn key={i} {...btn} />
            ))}

            {/* Divider */}
            <div style={{ width: 1, height: 32, background: '#E2E8F0', flexShrink: 0, marginLeft: 4 }} />

            {/* Delete — danger */}
            <AdminActionBtn
              icon="🗑️"
              label="Delete User"
              color="#DC2626"
              bg="#FEF2F2"
              border="#FECACA"
              hoverBg="#FEE2E2"
              hoverBorder="#EF4444"
              hoverColor="#B91C1C"
              onClick={() => setModal('delete')}
            />
          </div>
        </div>
        <div className="content">
          <div className="admin-kpi-grid">
            {[
              {lbl:'Total Invoices',val:s.total_invoices||0,c:'var(--blue)'},
              {lbl:'Active',val:s.active_count||0,c:'var(--orange)'},
              {lbl:'Legal Queue',val:s.legal_queue_count||0,c:'var(--red)'},
              {lbl:'₹ Tracked',val:fmtINR(s.total_value||0),c:'var(--text)'},
              {lbl:'₹ Recovered',val:fmtINR(s.recovered_value||0),c:'var(--green)'},
            ].map((m,i)=>(
              <div key={i} className="metric-card" style={{borderLeft:'3px solid '+m.c,padding:'12px 14px'}}>
                <div className="metric-label" style={{fontSize:11}}>{m.lbl}</div>
                <div style={{fontWeight:800,fontSize:17,color:m.c,marginTop:4}}>{m.val}</div>
              </div>
            ))}
          </div>
          <div className="admin-detail-layout">
            <div className="card" style={{padding:0,alignSelf:'start'}}>
              <div style={{padding:'12px 16px',borderBottom:'1px solid var(--border)',fontWeight:700,fontSize:13}}>Profile Details</div>
              <div style={{padding:16}}>
                <div style={{width:60,height:60,borderRadius:'50%',background:'linear-gradient(135deg,#1D4ED8,#7C3AED)',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontSize:22,fontWeight:800,margin:'0 auto 16px'}}>
                  {(u.business_name||u.email||'?')[0].toUpperCase()}
                </div>
                {[['Business',u.business_name||'—'],['Email',u.email||'—'],['Phone',u.phone||'—'],['City',u.city||'—'],['Plan',u.plan||'Starter'],['Recovery Rate',(s.recovery_rate||0)+'%'],['Member Since',(u.created_at||'').substring(0,10)||'—']].map(([k,v])=>(
                  <div key={k} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'7px 0',borderBottom:'1px solid var(--border)',fontSize:12}}>
                    <span style={{color:'var(--text3)',fontWeight:500}}>{k}</span>
                    <span style={{fontWeight:600,color:'var(--text)',maxWidth:160,textAlign:'right',wordBreak:'break-all'}}>{v}</span>
                  </div>
                ))}
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'7px 0',fontSize:12}}>
                  <span style={{color:'var(--text3)',fontWeight:500}}>Status</span>
                  <span style={badge(u.is_active)}>{u.is_active!==false?'Active':'Inactive'}</span>
                </div>
              </div>
            </div>
            <div className="card" style={{padding:0}}>
              <div style={{padding:'12px 16px',borderBottom:'1px solid var(--border)',fontWeight:700,fontSize:13}}>Invoices ({invs.length})</div>
              <div className="table-wrap">
                <table><thead><tr>
                  <th>Invoice No.</th><th>Customer</th><th>Status</th><th style={{textAlign:'right'}}>Days Overdue</th><th style={{textAlign:'right'}}>Amount</th><th>Actions</th>
                </tr></thead>
                <tbody>
                  {invs.map(inv=>{
                    const isRecovered = inv.status==='recovered'||inv.recovered;
                    return (
                      <tr key={inv._id} className="mobile-table-row">
                        <td style={{fontWeight:500,fontSize:12}}>{inv.invoiceNo||inv.invoice_no||'N/A'}</td>
                        <td style={{fontWeight:500}}>{inv.company}</td>
                        <td><span style={{fontSize:11,padding:'2px 8px',borderRadius:10,fontWeight:600,background:isRecovered?'rgba(52,199,89,0.1)':'rgba(255,149,0,0.1)',color:isRecovered?'var(--green)':'var(--orange)'}}>{isRecovered?'Recovered':inv.status||'Active'}</span></td>
                        <td style={{textAlign:'right',fontFamily:'monospace',fontSize:12}}>{inv.daysOverdue||0}d</td>
                        <td style={{textAlign:'right',fontFamily:'monospace',fontWeight:600}}>{fmtINR(inv.amount||0)}</td>
                        <td>
                          <div style={{display:'flex',gap:6}}>
                            <button style={{fontSize:11,padding:'3px 8px',borderRadius:6,border:'1px solid var(--border)',background:'transparent',cursor:'pointer',color:'var(--blue)',fontFamily:'inherit'}} onClick={()=>setModal({type:'editInv',invId:inv._id,company:inv.company,amount:inv.amount,form:{company:inv.company,amount:inv.amount,status:inv.status,daysOverdue:inv.daysOverdue}})}>Edit</button>
                            <button style={{fontSize:11,padding:'3px 8px',borderRadius:6,border:'1px solid var(--red)',background:'transparent',cursor:'pointer',color:'var(--red)',fontFamily:'inherit'}} onClick={()=>setModal({type:'deleteInv',invId:inv._id,company:inv.company,amount:inv.amount})}>Del</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {!invs.length&&<tr><td colSpan={6} style={{textAlign:'center',padding:40,color:'var(--text3)'}}>This user has no invoices.</td></tr>}
                </tbody></table>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return <div style={{padding:60,textAlign:'center',color:'var(--text3)'}}>Select a tab above.</div>;
}

