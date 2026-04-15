import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router';
import { motion } from 'motion/react';
import { Mail, Lock, ArrowRight, AlertCircle, Loader2 } from 'lucide-react';
import { authApi, ApiError } from '@/lib/api';
import { saveTokens, isLoggedIn } from '@/lib/auth';

/* ─── Design tokens (mirrors LandingPage) ──────────────────────────────── */
const F      = "'Plus Jakarta Sans', system-ui, sans-serif";
const BG     = '#EEF2F8';
const SURF   = '#E2ECF5';
const BORDER = '#C0D4E8';
const TEXT   = '#0A1428';
const MUTED  = '#608098';
const ACCENT = '#0EA5E9';

/* ─── Logo mark (shared) ─────────────────────────────────────────────────*/
function LogoMark() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lg-login" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#0369A1" />
        </linearGradient>
      </defs>
      <rect width="36" height="36" rx="9" fill="url(#lg-login)" />
      <line x1="11" y1="9" x2="11" y2="27" stroke="white" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M 11 9 L 20 9 C 28.5 9 28.5 21 20 21 L 11 21" stroke="white" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <line x1="20" y1="21" x2="25" y2="14" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M 24.5 16.5 L 27 12 L 22.5 13.5" stroke="white" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

/* ─── Google client ID (same as backend .env — avoids async fetch gate) ── */
const GOOGLE_CLIENT_ID = '470116902016-oilbnaq779bgh098d3m8027stmj57o3k.apps.googleusercontent.com';

/* ─── Inject Google GSI script once globally ─────────────────────────── */
function ensureGsiScript() {
  if (document.getElementById('google-gsi-script')) return;
  const s = document.createElement('script');
  s.id = 'google-gsi-script';
  s.src = 'https://accounts.google.com/gsi/client';
  s.async = true;
  s.defer = true;
  document.head.appendChild(s);
}

/* ─── Google Sign-In button ───────────────────────────────────────────── */
function GoogleButton({ onClick, loading }: { onClick: () => void; loading: boolean }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={loading}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.98 }}
      className="w-full flex items-center justify-center gap-3 py-3 rounded-xl transition-colors"
      style={{
        border: `1px solid ${BORDER}`,
        background: '#fff',
        color: TEXT,
        fontFamily: F,
        fontWeight: 500,
        fontSize: 14,
        cursor: loading ? 'not-allowed' : 'pointer',
        opacity: loading ? 0.6 : 1,
      }}
    >
      {/* Google "G" SVG */}
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M17.64 9.2a10.1 10.1 0 0 0-.16-1.85H9v3.51h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91A8.78 8.78 0 0 0 17.64 9.2z" fill="#4285F4"/>
        <path d="M9 18a8.6 8.6 0 0 0 5.96-2.18l-2.91-2.26a5.43 5.43 0 0 1-8.09-2.85H.98v2.33A9 9 0 0 0 9 18z" fill="#34A853"/>
        <path d="M3.96 10.71A5.41 5.41 0 0 1 3.96 7.3V4.97H.98a9 9 0 0 0 0 8.07l2.98-2.33z" fill="#FBBC05"/>
        <path d="M9 3.58a4.86 4.86 0 0 1 3.44 1.35l2.58-2.59A8.65 8.65 0 0 0 9 0 9 9 0 0 0 .98 4.97l2.98 2.33A5.36 5.36 0 0 1 9 3.58z" fill="#EA4335"/>
      </svg>
      Continue with Google
    </motion.button>
  );
}

/* ─── Input field ─────────────────────────────────────────────────────── */
function Field({
  label, type = 'text', value, onChange, placeholder, icon: Icon, autoComplete,
}: {
  label: string; type?: string; value: string;
  onChange: (v: string) => void; placeholder?: string;
  icon: React.ElementType; autoComplete?: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label style={{ fontFamily: F, fontSize: 13, fontWeight: 500, color: TEXT, display: 'block', marginBottom: 6 }}>
        {label}
      </label>
      <div
        className="flex items-center gap-3 px-4 rounded-xl transition-all"
        style={{
          border: `1px solid ${focused ? ACCENT : BORDER}`,
          background: '#fff',
          boxShadow: focused ? `0 0 0 3px ${ACCENT}18` : 'none',
        }}
      >
        <Icon size={15} style={{ color: focused ? ACCENT : MUTED, flexShrink: 0 }} />
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          autoComplete={autoComplete || 'off'}
          style={{
            flex: 1, border: 'none', outline: 'none', background: 'transparent',
            fontFamily: F, fontSize: 14, color: TEXT, padding: '12px 0',
          }}
        />
      </div>
    </div>
  );
}

/* ─── LoginPage ─────────────────────────────────────────────────────────── */
export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  // Hidden div that Google GSI renders its button into (needed for credential flow)
  const gsiDivRef = useRef<HTMLDivElement>(null);


  // Inject Google GSI script immediately and initialize when ready
  useEffect(() => {
    ensureGsiScript();

    // Callback invoked by Google after user picks their account
    const handleCredential = async (response: { credential: string }) => {
      setLoading(true);
      setError('');
      try {
        const data = await authApi.googleLogin(response.credential, false);
        saveTokens(data.access_token, data.refresh_token, {
          business_name: data.business_name,
          is_admin: data.is_admin,
        });
        window.location.href = '/dashboard';
      } catch (err: any) {
        if (err instanceof ApiError && err.status === 404) {
          setError('No account found for this Google email. Please register first.');
        } else {
          setError(err instanceof ApiError ? err.detail : 'Google sign-in failed. Please try again.');
        }
      } finally {
        setLoading(false);
      }
    };

    // Store callback globally so GSI can call it from the rendered button
    (window as any).__recoveraiGoogleCallback = handleCredential;

    // Initialize GSI once the script is ready
    const init = () => {
      const g = (window as any).google;
      if (!g?.accounts?.id) return;
      g.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredential,
        auto_select: false,
        cancel_on_tap_outside: true,
      });
      // Render a hidden button so GSI is fully primed
      if (gsiDivRef.current) {
        g.accounts.id.renderButton(gsiDivRef.current, {
          type: 'standard',
          size: 'large',
          theme: 'outline',
        });
      }
    };

    // If script already loaded, init immediately; otherwise wait
    if ((window as any).google?.accounts?.id) {
      init();
    } else {
      const existing = document.getElementById('google-gsi-script');
      if (existing) existing.addEventListener('load', init);
    }

    return () => {
      // Cleanup
      try { (window as any).google?.accounts?.id?.cancel(); } catch {}
    };
  }, [navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError('Please fill in all fields.'); return; }
    setError('');
    setLoading(true);
    try {
      const data = await authApi.login(email, password);
      saveTokens(data.access_token, data.refresh_token, {
        business_name: data.business_name,
        is_admin: data.is_admin,
      });
      window.location.href = '/dashboard';
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = () => {
    const g = (window as any).google;
    if (!g?.accounts?.id) {
      setError('Google Sign-In is loading, please try again in a moment.');
      return;
    }
    setError('');
    // prompt() opens the Google account chooser overlay
    g.accounts.id.prompt((notification: any) => {
      if (notification.isNotDisplayed()) {
        // prompt() was suppressed — fallback: click the hidden rendered button
        const btn = gsiDivRef.current?.querySelector('div[role="button"]') as HTMLElement | null;
        if (btn) {
          btn.click();
        } else {
          setError('Google sign-in popup was blocked. Please allow popups for this site.');
        }
      }
    });
  };

  return (
    <div className="min-h-screen flex" style={{ background: BG, fontFamily: F }}>
      {/* ── Left panel — branding ── */}
      <div
        className="hidden lg:flex flex-col justify-between w-[440px] shrink-0 p-12"
        style={{ background: '#071020', borderRight: `1px solid rgba(14,165,233,0.15)` }}
      >
        {/* Dot grid overlay */}
        <div className="absolute left-0 top-0 w-[440px] h-full pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle, rgba(14,165,233,0.15) 1px, transparent 1px)',
            backgroundSize: '32px 32px',
          }} />

        <div className="relative z-10">
          <div className="flex items-center gap-2.5">
            <LogoMark />
            <span>
              <span style={{ fontWeight: 500, fontSize: 18, color: 'rgba(238,242,248,0.92)' }}>Recover</span>
              <span style={{ fontWeight: 800, fontSize: 18, color: ACCENT }}>AI</span>
            </span>
          </div>
        </div>

        <div className="relative z-10">
          <blockquote style={{ fontStyle: 'italic', fontSize: 20, color: 'rgba(238,242,248,0.82)', lineHeight: 1.6, fontWeight: 300, marginBottom: 24 }}>
            "Recovered ₹4.5 lakh from a single client in 90 days — the MSME notice alone saved us ₹15,000 in lawyer fees."
          </blockquote>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full flex items-center justify-center" style={{ background: `${ACCENT}20` }}>
              <span style={{ color: ACCENT, fontWeight: 700, fontSize: 12 }}>RG</span>
            </div>
            <div>
              <p style={{ color: 'rgba(238,242,248,0.9)', fontWeight: 600, fontSize: 14 }}>Ramesh Gupta</p>
              <p style={{ color: MUTED, fontSize: 12, fontWeight: 300 }}>Nagpur Steel Works</p>
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="relative z-10 flex gap-8">
          {[
            { val: '₹30Cr+', label: 'Recovered' },
            { val: '88%',    label: 'Success rate' },
            { val: '500+',   label: 'Businesses' },
          ].map(s => (
            <div key={s.val}>
              <p style={{ color: ACCENT, fontSize: 22, fontWeight: 400, letterSpacing: '-0.03em' }}>{s.val}</p>
              <p style={{ color: MUTED, fontSize: 12, fontWeight: 300 }}>{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right panel — form ── */}
      <div className="flex-1 flex items-center justify-center px-6 py-16">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-[420px]"
        >
          {/* Mobile logo */}
          <div className="flex items-center gap-2.5 mb-10 lg:hidden">
            <LogoMark />
            <span>
              <span style={{ fontWeight: 500, fontSize: 18, color: TEXT }}>Recover</span>
              <span style={{ fontWeight: 800, fontSize: 18, color: ACCENT }}>AI</span>
            </span>
          </div>

          <h1 style={{ fontSize: 28, fontWeight: 600, color: TEXT, letterSpacing: '-0.025em', marginBottom: 6 }}>
            Welcome back
          </h1>
          <p style={{ color: MUTED, fontSize: 14, fontWeight: 300, marginBottom: 32 }}>
            Log in to your RecoverAI account
          </p>

          {/* Google sign-in — always visible */}
          <div className="mb-6">
            {/* Hidden div where GSI renders its internal button (primes the credential flow) */}
            <div ref={gsiDivRef} style={{ display: 'none' }} aria-hidden="true" />
            <GoogleButton onClick={handleGoogleSignIn} loading={loading} />
            <div className="flex items-center gap-3 my-5">
              <div className="flex-1 h-px" style={{ background: BORDER }} />
              <span style={{ color: MUTED, fontSize: 12 }}>or continue with email</span>
              <div className="flex-1 h-px" style={{ background: BORDER }} />
            </div>
          </div>

          {/* Error */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2 px-4 py-3 rounded-xl mb-5"
              style={{ background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626' }}
            >
              <AlertCircle size={14} />
              <span style={{ fontFamily: F, fontSize: 13 }}>{error}</span>
            </motion.div>
          )}

          <form onSubmit={handleLogin} className="flex flex-col gap-5">
            <Field label="Email address" type="email" value={email} onChange={setEmail}
              placeholder="e.g. example@company.com" icon={Mail} autoComplete="new-email" />
            <Field label="Password" type="password" value={password} onChange={setPassword}
              placeholder="e.g. Password@123" icon={Lock} autoComplete="new-password" />

            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ scale: 1.01, boxShadow: `0 8px 24px ${ACCENT}44` }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center justify-center gap-2 py-3.5 rounded-xl"
              style={{
                background: ACCENT,
                color: '#fff',
                fontFamily: F,
                fontWeight: 600,
                fontSize: 15,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.8 : 1,
              }}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : null}
              {loading ? 'Signing in…' : 'Sign in'}
              {!loading && <ArrowRight size={16} />}
            </motion.button>
          </form>

          <p style={{ textAlign: 'center', marginTop: 24, color: MUTED, fontSize: 14 }}>
            Don't have an account?{' '}
            <Link to="/register" style={{ color: ACCENT, fontWeight: 600, textDecoration: 'none' }}>
              Create one free
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
