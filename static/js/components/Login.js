/* ─── Login Screen Component ─── */
function LoginScreen({ onLogin }) {
  const [tab, setTab] = React.useState('login');
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [bizName, setBizName] = React.useState('');
  const [err, setErr] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    window.handleGoogleCredentialResponse = async (response) => {
      setErr(''); setLoading(true);
      try {
        const res = await fetch('/api/auth/google', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credential: response.credential })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Google Login failed');
        setToken(data.access_token);
        if (data.refresh_token) localStorage.setItem('recoverai_refresh', data.refresh_token);
        setIsAdmin(data.is_admin);
        onLogin(data.access_token, data.is_admin, data.business_name, data.email);
      } catch (e) {
        setErr(e.message || 'Google Login failed');
      } finally { setLoading(false); }
    };

    const renderGoogleBtn = async () => {
      const container = document.getElementById('google-signin-btn-container');
      if (!window.google || !container) { setTimeout(renderGoogleBtn, 300); return; }
      try {
        const configRes = await fetch('/api/auth/config');
        const config = await configRes.json();
        const clientId = config.google_client_id;
        container.innerHTML = '';
        if (clientId) {
          window.google.accounts.id.initialize({ client_id: clientId, callback: window.handleGoogleCredentialResponse });
          window.google.accounts.id.renderButton(container, { theme: 'outline', size: 'large', width: '100%', text: 'signin_with' });
        } else {
          container.innerHTML = `<button type="button" class="btn btn-outline btn-lg" style="width:100%;justify-content:center" onclick="alert('Google Sign-In not configured.')">Sign in with Google</button>`;
        }
      } catch (e) { console.error('Failed to load auth config', e); }
    };
    if (tab === 'login') renderGoogleBtn();
  }, [tab]);

  async function handleLogin(e) {
    e.preventDefault(); setErr(''); setLoading(true);
    try {
      const fd = new FormData();
      fd.append('username', email); fd.append('password', password);
      const res = await fetch('/api/auth/login', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');
      localStorage.setItem('recoverai_login_time', Date.now().toString());
      onLogin(data.access_token, data.is_admin, data.business_name, data.email);
    } catch (e) { setErr(e.message); }
    setLoading(false);
  }

  async function handleRegister(e) {
    e.preventDefault(); setErr(''); setLoading(true);
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ business_name: bizName, email, password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');
      localStorage.setItem('recoverai_login_time', Date.now().toString());
      onLogin(data.access_token, data.is_admin, data.business_name, data.email);
    } catch (e) { setErr(e.message); }
    setLoading(false);
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 420 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ width: 52, height: 52, background: 'var(--amber)', borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, fontWeight: 700, color: 'var(--amber-bg)', margin: '0 auto 14px' }}>R</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)' }}>RecoverAI</div>
          <div style={{ fontSize: 13, color: 'var(--text3)', marginTop: 4 }}>MSME Invoice Recovery Platform</div>
        </div>
        <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius-xl)', border: '1px solid var(--border)', padding: 28, boxShadow: 'var(--shadow-md)' }}>
          <div className="tabs" style={{ marginBottom: 22 }}>
            {[['login', 'Sign In'], ['register', 'Create Account']].map(([v, l]) => (
              <button key={v} className={`tab-btn${tab === v ? ' active' : ''}`} onClick={() => { setTab(v); setErr(''); }}>{l}</button>
            ))}
          </div>
          {tab === 'login' ? (
            <form onSubmit={handleLogin}>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input className="form-input" type="email" placeholder="you@business.in" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" />
              </div>
              <div className="form-group">
                <label className="form-label">Password</label>
                <input className="form-input" type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password" />
              </div>
              {err && <div className="danger-box" style={{ marginBottom: 14 }}>{err}</div>}
              <button type="submit" className="btn btn-primary btn-lg" style={{ width: '100%', justifyContent: 'center', marginTop: 4 }} disabled={loading}>
                {loading ? <><span className="spinner"></span> Signing in...</> : 'Sign In →'}
              </button>
              <div style={{ display: 'flex', alignItems: 'center', margin: '24px 0', color: 'var(--text3)', fontSize: 12 }}>
                <div style={{ flex: 1, height: 1, background: 'var(--border)' }}></div>
                <span style={{ padding: '0 12px' }}>OR</span>
                <div style={{ flex: 1, height: 1, background: 'var(--border)' }}></div>
              </div>
              <div id="google-signin-btn-container" style={{ display: 'flex', justifyContent: 'center' }}>
                <button type="button" className="btn btn-outline btn-lg" style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => alert('Google Sign-In not configured. Add GOOGLE_CLIENT_ID to your .env')}>
                  <svg style={{ width: 18, height: 18, marginRight: 8 }} viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  Sign in with Google
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleRegister}>
              <div className="form-group">
                <label className="form-label">Business Name</label>
                <input className="form-input" placeholder="Krishna Enterprises" value={bizName} onChange={e => setBizName(e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input className="form-input" type="email" placeholder="you@business.in" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" />
              </div>
              <div className="form-group">
                <label className="form-label">Password</label>
                <input className="form-input" type="password" placeholder="Min. 8 characters" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" />
              </div>
              {err && <div className="danger-box" style={{ marginBottom: 14 }}>{err}</div>}
              <button type="submit" className="btn btn-primary btn-lg" style={{ width: '100%', justifyContent: 'center', marginTop: 4 }} disabled={loading}>
                {loading ? <><span className="spinner"></span> Creating account...</> : 'Create Account →'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
