/* ─── Root App — Routing, Sidebar, State Management ─── */
const { useState, useEffect, useRef, useCallback } = React;

function App() {
  const [token, setTokenState] = useState(() => getToken());
  const [isAdmin, setIsAdminState] = useState(() => getIsAdmin());
  const [userDetails, setUserDetails] = useState(() => {
    const s = localStorage.getItem('recoverai_user_details');
    return s ? JSON.parse(s) : null;
  });
  // page = current route/section
  const getInitialPage = () => {
    const path = window.location.pathname.substring(1);
    const validPages = ['dashboard', 'inbox', 'invoices', 'recovery', 'legal', 'campaigns', 'customers', 'reports', 'reminders', 'admin', 'settings', 'whatsapp', 'whitelabel', 'accounting', 'login', 'register'];
    return validPages.includes(path) ? path : 'dashboard';
  };
  const [page, setPage] = useState(getInitialPage);

  useEffect(() => {
    window.history.pushState(null, '', `/${page}`);
  }, [page]);

  useEffect(() => {
    if (token && (page === 'login' || page === 'register')) {
      setPage('dashboard');
    }
  }, [token, page]);

  useEffect(() => {
    const onPopState = () => setPage(getInitialPage());
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);
  const [invoices, setInvoices] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedInv, setSelectedInv] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [showPlans, setShowPlans] = useState(false);

  const [settings, setSettings] = useState(() => {
    const local = localStorage.getItem('recoverai_settings');
    return local ? JSON.parse(local) : {
      businessName: '', ownerName: '', phone: '', email: '', gstin: '', city: '',
      autoReminder: true, whatsappEnabled: true, emailEnabled: true,
      legalAtDays: 45, reminderDays: [7, 21, 35], commissionRate: 2, plan: 'Starter',
      aiAllowInstallments: false, aiMaxInstallments: 3, aiMinFirstPct: 30,
      aiTone: 'firm', aiAutoEscalate: false, aiMultilingual: true,
    };
  });

  // Feature #2: Dark Mode
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('recoverai_dark') === 'true');
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : '');
    localStorage.setItem('recoverai_dark', darkMode ? 'true' : 'false');
  }, [darkMode]);

  // Decode email securely from JWT to prevent local storage staleness
  const getEmailFromToken = (t) => {
    try { return t ? JSON.parse(atob(t.split('.')[1])).sub : null; } 
    catch(e) { return null; }
  };
  const tokenEmail = getEmailFromToken(token);

  // Sidebar user info — reactive state, updated immediately on login
  const sidebarUserName = userDetails?.business_name || userDetails?.name || settings.businessName || 'My Account';
  const sidebarUserRole = tokenEmail || userDetails?.email || settings.email || 'Logged in';
  const sidebarInitials = sidebarUserName.split(' ').filter(Boolean).map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'ME';

  // onLogin is called with (isAdmin, bizName, email)
  function handleLogin(adminStatus, bizName, email) {
    setIsAdmin(adminStatus); setIsAdminState(adminStatus);
    
    // Set a frontend session flag so React knows we are logged in. 
    // The actual secure JWT is in the HttpOnly cookie.
    localStorage.setItem('recoverai_token', 'active');
    setTokenState('active');
    
    const userObj = { name: bizName, business_name: bizName, email: email };
    localStorage.setItem('recoverai_user_details', JSON.stringify(userObj));
    setUserDetails(userObj); // reactive update so sidebar shows immediately
    
    // Only pre-fill business name if settings are blank
    if (bizName) setSettings(prev => ({
      ...prev,
      businessName: prev.businessName || bizName,
      ownerName: prev.ownerName || bizName,
    }));
    
    if (page === 'login' || page === 'register') {
      setPage('dashboard');
    }
  }

  async function handleLogout() {
    try {
      // Tell the server to revoke the token and clear cookies
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (e) { /* ignore network errors on logout */ }
    // Clear non-sensitive user metadata from localStorage
    localStorage.removeItem('recoverai_user_details');
    localStorage.removeItem('recoverai_is_admin');
    localStorage.removeItem('recoverai_settings');
    localStorage.removeItem('recoverai_login_time');
    localStorage.removeItem('recoverai_token');
    setUserDetails(null);
    setTokenState(null);
    // Redirect to landing page
    window.location.replace('/');
  }

  // Enforce strict 15-minute login limit
  useEffect(() => {
    const checkTimeout = () => {
      const loginTimeStr = localStorage.getItem('recoverai_login_time');
      if (loginTimeStr && getToken()) {
        const loginTime = parseInt(loginTimeStr, 10);
        // 15 minutes = 15 * 60 * 1000 = 900000 ms
        if (Date.now() - loginTime > 900000) {
          handleLogout();
        }
      }
    };

    // Check periodically every minute
    const interval = setInterval(checkTimeout, 60000);
    
    // Check immediately when visibility changes (switching back to tab) or window gains focus
    document.addEventListener('visibilitychange', checkTimeout);
    window.addEventListener('focus', checkTimeout);
    
    // Check on initial load
    checkTimeout();

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', checkTimeout);
      window.removeEventListener('focus', checkTimeout);
    };
  }, []);

  // Persist settings to localStorage
  useEffect(() => {
    localStorage.setItem('recoverai_settings', JSON.stringify(settings));
  }, [settings]);

  const fetchInvoices = useCallback(() => {
    if (!getToken()) return;
    authFetch('/api/invoices')
      .then(r => r.json())
      .then(data => { 
        if (Array.isArray(data)) {
          // Dynamically recalculate daysOverdue and status based on TODAY'S date
          // This ensures that even if you open the app weeks later, the numbers are perfectly accurate
          const dynamicData = data.map(inv => {
            if (inv.recovered) return inv; // Skip dynamic logic for fully recovered invoices
            const due = new Date(inv.dueDate);
            const days = Math.max(0, Math.floor((Date.now() - due.getTime()) / 86400000));
            let currentStatus = 'sent';
            if (days >= 45) currentStatus = 'legal';
            else if (days >= 35) currentStatus = 'escalated';
            else if (days >= 15) currentStatus = 'reminded';
            return { ...inv, daysOverdue: days, status: currentStatus };
          });
          setInvoices(dynamicData);
        }
      })
      .catch(e => console.error('Error loading invoices:', e));
  }, []);

  useEffect(() => { if (token) fetchInvoices(); }, [token, fetchInvoices]);

  if (!token) {
    if (page !== 'login' && page !== 'register') {
      window.location.replace('/login');
      return null;
    }
    // Fallback if already on /login but somehow inside dashboard.html
    return <LoginScreen onLogin={handleLogin} />;
  }

  /* ── Computed values ── */
  const outstanding = invoices.filter(i => !i.recovered).reduce((s, i) => s + i.amount, 0);
  const recovered = invoices.filter(i => i.recovered).reduce((s, i) => s + i.amount, 0);
  const legalQueue = invoices.filter(i => !i.recovered && i.daysOverdue >= 45);
  const activeCount = invoices.filter(i => !i.recovered).length;
  const recoveryRate = Math.round((recovered / (outstanding + recovered)) * 100) || 0;

  /* ── Invoice CRUD ── */
  async function addInvoice(inv) {
    const due = new Date(inv.dueDate);
    const days = Math.max(0, Math.floor((Date.now() - due.getTime()) / 86400000));
    let status = 'sent';
    if (days >= 45) status = 'legal';
    else if (days >= 35) status = 'escalated';
    else if (days >= 15) status = 'reminded';
    const payload = { ...inv, daysOverdue: days, status, reminders: 0, recovered: false };
    try {
      const res = await authFetch('/api/invoices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const created = await res.json();
      if (res.ok) setInvoices(p => [created, ...p]);
    } catch (e) { console.error('Error adding invoice:', e); }
  }

  async function markRecovered(id) {
    try {
      const res = await authFetch(`/api/invoices/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recovered: true, status: 'recovered' })
      });
      if (res.ok) setInvoices(p => p.map(i => i.id === id ? { ...i, recovered: true, status: 'recovered' } : i));
    } catch (e) { console.error('Error marking recovered:', e); }
    setShowDetailModal(false);
  }

  async function deleteInvoice(id) {
    try {
      await authFetch(`/api/invoices/${id}`, { method: 'DELETE' });
      setInvoices(p => p.filter(i => i.id !== id));
    } catch (e) { console.error('Error deleting invoice:', e); }
    setShowDetailModal(false);
  }

  function openDetail(inv) { setSelectedInv(inv); setShowDetailModal(true); }
  function navTo(id) { setPage(id); setDrawerOpen(false); setProfileOpen(false); }

  /* ── Nav items ── */
  const navItems = [
    { id: 'dashboard',  label: 'Dashboard',       icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z' },
    { id: 'invoices',   label: 'All Invoices',     icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', badge: activeCount > 0 ? activeCount : null, badgeType: 'blue' },
    { id: 'inbox',      label: 'Debtor Invoices',  icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', badge: invoices.filter(i => i.communication_log?.length).length || null, badgeType: 'red' },
    { id: 'recovery',   label: 'Recovery Hub',     icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
    { id: 'legal',      label: 'Legal Queue',      icon: 'M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3', badge: legalQueue.length > 0 ? legalQueue.length : null, badgeType: 'red' },
    { id: 'campaigns',  label: 'Campaigns',        icon: 'M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z' },
    { id: 'customers',  label: 'Customers',        icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
    { id: 'reports',    label: 'Reports',          icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
    { id: 'reminders',  label: 'Reminders',        icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
  ];
  if (isAdmin) navItems.push({ id: 'admin', label: 'God Mode', icon: ['M15 12a3 3 0 11-6 0 3 3 0 016 0z', 'M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z'], badge: 'Admin', badgeType: 'red' });
  navItems.push({ id: 'whatsapp',   label: 'WhatsApp',        icon: 'M20.52 3.449A11.963 11.963 0 0012.002 0C5.373 0 .002 5.373.002 12c0 2.117.554 4.102 1.521 5.83L0 24l6.335-1.663A11.954 11.954 0 0012.002 24c6.628 0 12-5.372 12-12 0-3.205-1.248-6.219-3.482-8.551zm-8.518 18.451a9.946 9.946 0 01-5.073-1.385l-.364-.216-3.76.986 1.004-3.659-.237-.375A9.945 9.945 0 012.003 12c0-5.514 4.486-10 10-10 2.671 0 5.181 1.04 7.071 2.929A9.944 9.944 0 0122.001 12c0 5.514-4.487 10-9.999 10z' });
  navItems.push({ id: 'accounting', label: 'Tally / Zoho',    icon: 'M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z' });
  navItems.push({ id: 'whitelabel', label: 'White-Label',     icon: 'M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01' });

  /* ── Pages map ── */
  const pages = {
    dashboard: <Dashboard invoices={invoices} outstanding={outstanding} recovered={recovered} legalQueue={legalQueue} activeCount={activeCount} recoveryRate={recoveryRate} openDetail={openDetail} setPage={setPage} darkMode={darkMode} setDarkMode={setDarkMode} />,
    inbox:     <DebtorInbox invoices={invoices} openDetail={openDetail} fetchInvoices={fetchInvoices} />,
    invoices:  <Invoices invoices={invoices} openDetail={openDetail} onAdd={() => setShowAddModal(true)} />,
    recovery:  <RecoveryHub invoices={invoices} openDetail={openDetail} settings={settings} />,
    legal:     <LegalQueue invoices={legalQueue} openDetail={openDetail} settings={settings} />,
    campaigns: <Campaigns invoices={invoices} settings={settings} />,
    customers: <Customers token={token} invoices={invoices} openDetail={openDetail} />,
    reports:   <Reports invoices={invoices} outstanding={outstanding} recovered={recovered} recoveryRate={recoveryRate} />,
    reminders: <Reminders invoices={invoices} openDetail={openDetail} />,
    admin:     <AdminDashboard />,
    settings:  <Settings settings={settings} setSettings={setSettings} darkMode={darkMode} setDarkMode={setDarkMode} />,
    whatsapp:  <WhatsAppIntegration token={token} invoices={invoices} settings={settings} />,
    whitelabel:<WhiteLabel settings={settings} setSettings={setSettings} />,
    accounting:<AccountingExport invoices={invoices} settings={settings} />,
  };

  /* ── Profile Popover ── */
  function UserProfileCard() {
    // Use the securely decoded tokenEmail first, then REACTIVE userDetails, then fallback
    const profileEmail = tokenEmail || userDetails?.email || settings.email || 'No email set';
    const profileName = userDetails?.business_name || userDetails?.name || settings.businessName || 'My Account';
    const totalActive = invoices.filter(i => !i.recovered).length;
    const totalRecovered = invoices.filter(i => i.recovered).length;
    const recoveredVal = invoices.filter(i => i.recovered).reduce((s,i) => s + i.amount, 0);
    const outstandingVal = invoices.filter(i => !i.recovered).reduce((s,i) => s + i.amount, 0);
    const initials = getInitials(profileName);
    const recoveryEfficiency = Math.round((totalRecovered / (invoices.length || 1)) * 100);
    return (
      <div className="profile-popover" onClick={e => e.stopPropagation()}>
        <div className="popover-header">
          <div className="popover-avatar">{initials}</div>
          <div className="popover-header-content">
            <div className="popover-name">{profileName}</div>
            <div className="popover-email">{profileEmail}</div>
          </div>
          {isAdmin && <span className="popover-badge">Admin</span>}
        </div>
        <div className="popover-stats">
          <div className="popover-stat"><div className="popover-stat-val">{invoices.length}</div><div className="popover-stat-lbl">Total</div></div>
          <div className="popover-stat"><div className="popover-stat-val" style={{color:'var(--amber)'}}>{totalActive}</div><div className="popover-stat-lbl">Pending</div></div>
          <div className="popover-stat"><div className="popover-stat-val" style={{color:'var(--green)'}}>{totalRecovered}</div><div className="popover-stat-lbl">Recovered</div></div>
        </div>
        <div className="popover-info">
          <div className="popover-info-row"><span className="popover-info-icon">📈</span><span style={{ fontWeight: 600 }}>{recoveryEfficiency}% Recovery Efficiency</span></div>
          <div className="popover-info-row"><span className="popover-info-icon">💎</span><span>{fmtINR(outstandingVal)} still outstanding</span></div>
          {settings.ownerName && (<div className="popover-info-row"><span className="popover-info-icon">👤</span><span>{settings.ownerName}</span></div>)}
          {settings.phone && (<div className="popover-info-row"><span className="popover-info-icon">📞</span><span>{settings.phone}</span></div>)}
          <div className="popover-info-row"><span className="popover-info-icon">💰</span><span style={{color:'var(--green)', fontWeight:700}}>{fmtINR(recoveredVal)} recovered</span></div>
          <div className="popover-info-row popover-plan-row" onClick={() => { setShowPlans(true); setProfileOpen(false); }}>
            <span className="popover-info-icon">🎯</span>
            <span style={{ fontWeight: 600 }}>{settings.plan || 'Starter'} Plan</span>
            <span style={{ marginLeft:'auto', background: settings.plan === 'Professional' ? 'var(--blue-bg)' : settings.plan === 'Enterprise' ? 'var(--purple-bg)' : 'var(--amber-bg)', color: settings.plan === 'Professional' ? 'var(--blue)' : settings.plan === 'Enterprise' ? 'var(--purple)' : 'var(--amber-dark)', fontSize:9, fontWeight:700, padding:'2px 8px', borderRadius:6, textTransform:'uppercase' }}>
              {settings.plan === 'Starter' ? 'UPGRADE' : 'MANAGE'}
            </span>
          </div>
        </div>
        <div className="popover-actions">
          <button className="popover-btn" onClick={() => { setPage('settings'); setProfileOpen(false); setDrawerOpen(false); }}>⚙ Settings</button>
          <button className="popover-btn popover-btn-danger" onClick={handleLogout}>⏻ Sign Out</button>
        </div>
      </div>
    );
  }

  /* ── Nav list renderer ── */
  function renderNavList(onNav) {
    return (
      <>
        {navItems.map(n => (
          <button key={n.id} className={`nav-item${page === n.id ? ' active' : ''}`} onClick={() => onNav(n.id)}>
            <span style={{ width: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: page === n.id ? 1 : 0.75 }}>
              <IconSvg path={n.icon} />
            </span>
            {n.label}
            {n.badge && <span className={`nav-badge${n.badgeType === 'blue' ? ' bg-blue-600' : ''}`}>{n.badge}</span>}
          </button>
        ))}
        <button className={`nav-item${page === 'settings' ? ' active' : ''}`} onClick={() => onNav('settings')}>
          <span style={{ width: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: page === 'settings' ? 1 : 0.75 }}>
            <IconSvg path={['M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z', 'M15 12a3 3 0 11-6 0 3 3 0 016 0z']} />
          </span>
          Settings
        </button>
      </>
    );
  }

  const currentLabel = navItems.find(n => n.id === page)?.label || (page === 'settings' ? 'Settings' : 'RecoverAI');
  const bottomTabs = [
    { id: 'dashboard', icon: '▦', label: 'Home' },
    { id: 'invoices',  icon: '≡', label: 'Invoices' },
    { id: 'recovery',  icon: '↺', label: 'Recovery' },
    { id: 'legal',     icon: '⚖', label: 'Legal' },
    { id: 'menu',      icon: '☰', label: 'Menu' },
  ];

  return (
    <div className="layout" onClick={() => setProfileOpen(false)}>
      {showPlans && <PricingModal currentPlan={settings.plan || 'Starter'} onClose={() => setShowPlans(false)} onUpgrade={newPlan => { setSettings(prev => ({ ...prev, plan: newPlan })); setShowPlans(false); }} />}

      {/* Mobile top bar */}
      <div className="mobile-topbar">
        <button className={`hamburger-btn${drawerOpen ? ' open' : ''}`} onClick={() => setDrawerOpen(o => !o)} aria-label="Menu">
          <span></span><span></span><span></span>
        </button>
        <div className="mobile-topbar-center">
          <div className="brand-icon" style={{ width: 22, height: 22, borderRadius: 5, fontSize: 12 }}>₹</div>
          <span>{currentLabel}</span>
        </div>
        <div style={{ width: 40 }} />
      </div>

      {/* Mobile drawer overlay */}
      <div className={`mobile-drawer-overlay${drawerOpen ? ' open' : ''}`} onClick={() => setDrawerOpen(false)}></div>
      <div className={`mobile-drawer${drawerOpen ? ' open' : ''}`}>
        <div className="sidebar-brand" style={{ paddingLeft: 16 }}>
          <button onClick={() => setDrawerOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '4.5px', marginRight: '6px', padding: '4px' }}>
            <span style={{ width: 18, height: '2px', background: 'currentColor', borderRadius: 2 }}></span>
            <span style={{ width: 18, height: '2px', background: 'currentColor', borderRadius: 2 }}></span>
            <span style={{ width: 18, height: '2px', background: 'currentColor', borderRadius: 2 }}></span>
          </button>
          <div className="brand-icon" style={{ background: '#1D4ED8', color: '#fff', borderRadius: 8, fontSize: 16 }}>₹</div>
          <div className="brand-content">
            <div className="brand-name" style={{ fontSize:15, fontWeight:800, color:'var(--text)' }}>RecoverPro</div>
            <div className="brand-tagline">MSME Invoice Recovery</div>
          </div>
        </div>
        <nav className="nav">{renderNavList(navTo)}</nav>
        <div className="sidebar-bottom">
          <button onClick={() => setDarkMode(!darkMode)} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '10px 14px', marginBottom: 10, borderRadius: 10, cursor: 'pointer', background: darkMode ? '#1E293B' : '#F1F5F9', border: darkMode ? '1px solid #1E3A5F' : '1px solid #C0D4E8', color: darkMode ? '#CBD5E1' : '#334155', fontWeight: 600, fontSize: 13, transition: 'all 0.2s' }}>
            <span style={{ fontSize: 16 }}>{darkMode ? '🌙' : '☀️'}</span>
            <span>{darkMode ? 'Light Mode' : 'Dark Mode'}</span>
          </button>
          {profileOpen && <UserProfileCard />}
          <button className="user-card" onClick={e => { e.stopPropagation(); setProfileOpen(o => !o); }}>
            <div className="user-avatar" style={{ background: '#1D4ED8', color: '#fff' }}>
              {sidebarInitials}<div className="user-avatar-online"></div>
            </div>
            <div style={{minWidth:0, textAlign: 'left'}}>
              <div className="user-name" style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{sidebarUserName}</div>
              <div style={{ fontSize:10, color:'var(--text3)', marginTop:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{sidebarUserRole}</div>
            </div>
            <span className={`user-card-chevron${profileOpen ? ' open' : ''}`}>▾</span>
          </button>
        </div>
      </div>

      {/* Desktop sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon" style={{ background: '#1D4ED8', color: '#fff', borderRadius: 8, fontSize: 16 }}>₹</div>
          <div className="brand-content">
            <div className="brand-name" style={{ fontSize:15, fontWeight:800, color:'var(--text)' }}>RecoverPro</div>
            <div className="brand-tagline">MSME Invoice Recovery</div>
          </div>
        </div>
        <nav className="nav">{renderNavList(setPage)}</nav>
        <div className="sidebar-bottom">
          <div style={{ margin:'0 0 10px', padding:'14px', background:'linear-gradient(135deg,#EFF6FF,#EDE9FE)', borderRadius:12, border:'1px solid #C7D2FE' }}>
            <div style={{ fontSize:24, marginBottom:6 }}>🤖</div>
            <div style={{ fontSize:12, fontWeight:800, color:'#1E40AF', lineHeight:1.2, marginBottom:4 }}>Automate. Accelerate. Recover.</div>
            <div style={{ fontSize:10, color:'#4B5563', lineHeight:1.5, marginBottom:10 }}>Use smart workflows and AI-powered reminders to recover faster.</div>
            <button className="btn btn-primary btn-sm" style={{ width:'100%', justifyContent:'center', fontSize:11, padding:'6px 10px', borderRadius:8 }} onClick={() => setPage('invoices')}>Explore Automation →</button>
          </div>
          <button onClick={() => setDarkMode(!darkMode)} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '10px 14px', marginBottom: 10, borderRadius: 10, cursor: 'pointer', background: darkMode ? '#1E293B' : '#F1F5F9', border: darkMode ? '1px solid #1E3A5F' : '1px solid #C0D4E8', color: darkMode ? '#CBD5E1' : '#334155', fontWeight: 600, fontSize: 13, transition: 'all 0.2s' }}>
            <span style={{ fontSize: 16 }}>{darkMode ? '🌙' : '☀️'}</span>
            <span>{darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}</span>
          </button>
          {profileOpen && <UserProfileCard />}
          <button className="user-card" onClick={e => { e.stopPropagation(); setProfileOpen(o => !o); }}>
            <div className="user-avatar" style={{ background: '#1D4ED8', color: '#fff' }}>
              {sidebarInitials}<div className="user-avatar-online"></div>
            </div>
            <div style={{minWidth:0, textAlign: 'left'}}>
              <div className="user-name" style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{sidebarUserName}</div>
              <div style={{ fontSize:10, color:'var(--text3)', marginTop:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{sidebarUserRole}</div>
            </div>
            <span className={`user-card-chevron${profileOpen ? ' open' : ''}`}>▾</span>
          </button>
        </div>
      </aside>

      {/* Main content — routed by page state */}
      <main className="main">{pages[page] || pages.dashboard}</main>

      {/* Mobile bottom nav removed per user request */}

      {/* Add Invoice Modal */}
      {showAddModal && <AddInvoiceModal onClose={() => setShowAddModal(false)} onAdd={inv => { addInvoice(inv); setShowAddModal(false); }} />}

      {/* Invoice Detail Modal */}
      {showDetailModal && selectedInv && (
        <InvoiceDetailModal
          inv={invoices.find(i => i.id === selectedInv.id) || selectedInv}
          settings={settings}
          onClose={() => setShowDetailModal(false)}
          onRecover={() => markRecovered(selectedInv.id)}
          onDelete={() => deleteInvoice(selectedInv.id)}
        />
      )}
    </div>
  );
}

/* ── Mount ── */
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
