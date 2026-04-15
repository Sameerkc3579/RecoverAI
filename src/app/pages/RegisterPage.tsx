import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router';
import { motion } from 'motion/react';
import { Building2, Mail, Lock, ArrowRight, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { authApi, ApiError } from '@/lib/api';
import { isLoggedIn, saveTokens } from '@/lib/auth';

/* ─── Google client ID ───────────────────────────────────────────────────── */
const GOOGLE_CLIENT_ID = '470116902016-oilbnaq779bgh098d3m8027stmj57o3k.apps.googleusercontent.com';

function ensureGsiScript() {
  if (document.getElementById('google-gsi-script')) return;
  const s = document.createElement('script');
  s.id = 'google-gsi-script';
  s.src = 'https://accounts.google.com/gsi/client';
  s.async = true;
  s.defer = true;
  document.head.appendChild(s);
}

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
        border: `1px solid #C0D4E8`,
        background: '#fff',
        color: '#0A1428',
        fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        fontWeight: 500,
        fontSize: 14,
        cursor: loading ? 'not-allowed' : 'pointer',
        opacity: loading ? 0.6 : 1,
      }}
    >
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

/* ─── Design tokens ──────────────────────────────────────────────────── */
const F      = "'Plus Jakarta Sans', system-ui, sans-serif";
const BG     = '#EEF2F8';
const BORDER = '#C0D4E8';
const TEXT   = '#0A1428';
const MUTED  = '#608098';
const ACCENT = '#0EA5E9';

/* ─── Logo mark ───────────────────────────────────────────────────────── */
function LogoMark() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
      <defs>
        <linearGradient id="lg-reg" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#0369A1" />
        </linearGradient>
      </defs>
      <rect width="36" height="36" rx="9" fill="url(#lg-reg)" />
      <line x1="11" y1="9" x2="11" y2="27" stroke="white" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M 11 9 L 20 9 C 28.5 9 28.5 21 20 21 L 11 21" stroke="white" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <line x1="20" y1="21" x2="25" y2="14" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M 24.5 16.5 L 27 12 L 22.5 13.5" stroke="white" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

/* ─── Password strength ───────────────────────────────────────────────── */
function strengthOf(pw: string) {
  let score = 0;
  if (pw.length >= 8)          score++;
  if (/[A-Z]/.test(pw))        score++;
  if (/[a-z]/.test(pw))        score++;
  if (/\d/.test(pw))           score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return score;
}
const STRENGTH_COLORS = ['#EF4444', '#F97316', '#EAB308', '#22C55E', '#16A34A'];
const STRENGTH_LABELS = ['Very weak', 'Weak', 'Fair', 'Strong', 'Very strong'];

/* ─── Input field ─────────────────────────────────────────────────────── */
function Field({
  label, type = 'text', value, onChange, placeholder, icon: Icon, hint, autoComplete,
}: {
  label: string; type?: string; value: string;
  onChange: (v: string) => void; placeholder?: string;
  icon: React.ElementType; hint?: React.ReactNode; autoComplete?: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label style={{ fontFamily: F, fontSize: 13, fontWeight: 500, color: TEXT, display: 'block', marginBottom: 6 }}>
        {label}
      </label>
      <div className="flex items-center gap-3 px-4 rounded-xl transition-all"
        style={{
          border: `1px solid ${focused ? ACCENT : BORDER}`,
          background: '#fff',
          boxShadow: focused ? `0 0 0 3px ${ACCENT}18` : 'none',
        }}>
        <Icon size={15} style={{ color: focused ? ACCENT : MUTED, flexShrink: 0 }} />
        <input
          type={type} value={value}
          onChange={e => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          autoComplete={autoComplete || 'off'}
          style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontFamily: F, fontSize: 14, color: TEXT, padding: '12px 0' }}
        />
      </div>
      {hint}
    </div>
  );
}

/* ─── RegisterPage ────────────────────────────────────────────────────── */
export default function RegisterPage() {
  const navigate = useNavigate();
  const [businessName, setBusinessName] = useState('');
  const [email, setEmail]               = useState('');
  const [password, setPassword]         = useState('');
  const [error, setError]               = useState('');
  const [success, setSuccess]           = useState('');
  const [loading, setLoading]           = useState(false);
  const gsiDivRef = useRef<HTMLDivElement>(null);

  // Load GSI script and initialize Google Sign-In
  useEffect(() => {
    ensureGsiScript();

    const handleCredential = async (response: { credential: string }) => {
      setLoading(true);
      setError('');
      try {
        const data = await authApi.googleLogin(response.credential, true);
        saveTokens(data.access_token, data.refresh_token, {
          business_name: data.business_name,
          is_admin: data.is_admin,
        });
        window.location.href = '/dashboard';
      } catch (err: any) {
        setError(err instanceof ApiError ? err.detail : 'Google sign-in failed. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    const init = () => {
      const g = (window as any).google;
      if (!g?.accounts?.id) return;
      g.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredential,
        auto_select: false,
        cancel_on_tap_outside: true,
      });
      if (gsiDivRef.current) {
        g.accounts.id.renderButton(gsiDivRef.current, { type: 'standard', size: 'large', theme: 'outline' });
      }
    };

    if ((window as any).google?.accounts?.id) {
      init();
    } else {
      const existing = document.getElementById('google-gsi-script');
      if (existing) existing.addEventListener('load', init);
    }

    return () => {
      try { (window as any).google?.accounts?.id?.cancel(); } catch {}
    };
  }, [navigate]);

  const handleGoogleSignIn = () => {
    const g = (window as any).google;
    if (!g?.accounts?.id) {
      setError('Google Sign-In is loading, please try again in a moment.');
      return;
    }
    setError('');
    g.accounts.id.prompt((notification: any) => {
      if (notification.isNotDisplayed()) {
        const btn = gsiDivRef.current?.querySelector('div[role="button"]') as HTMLElement | null;
        if (btn) {
          btn.click();
        } else {
          setError('Google sign-in popup was blocked. Please allow popups for this site.');
        }
      }
    });
  };

  const strength = strengthOf(password);
  const strengthColor = password ? STRENGTH_COLORS[strength - 1] ?? '#EF4444' : BORDER;
  const strengthLabel = password ? STRENGTH_LABELS[strength - 1] ?? 'Very weak' : '';

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!businessName || !email || !password) {
      setError('Please fill in all fields.');
      return;
    }
    if (strength < 3) {
      setError('Password is too weak. Add uppercase, numbers, or symbols.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await authApi.register(businessName, email, password);
      setSuccess('Account created! Redirecting to login…');
      setTimeout(() => navigate('/login'), 1800);
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-16" style={{ background: BG, fontFamily: F }}>
      {/* Dot grid */}
      <div className="fixed inset-0 pointer-events-none opacity-50"
        style={{ backgroundImage: `radial-gradient(circle, ${BORDER} 1px, transparent 1px)`, backgroundSize: '36px 36px' }} />

      {/* Blue glow */}
      <div className="fixed inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(14,165,233,0.06), transparent)' }} />

      <motion.div
        initial={{ opacity: 0, y: 28 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55 }}
        className="w-full max-w-[460px] relative z-10"
      >
        {/* Card */}
        <div className="rounded-2xl p-10" style={{ background: '#fff', border: `1px solid ${BORDER}`, boxShadow: '0 24px 80px rgba(10,20,40,0.08)' }}>
          {/* Logo */}
          <div className="flex items-center gap-2.5 mb-8">
            <LogoMark />
            <span>
              <span style={{ fontWeight: 500, fontSize: 18, color: TEXT }}>Recover</span>
              <span style={{ fontWeight: 800, fontSize: 18, color: ACCENT }}>AI</span>
            </span>
          </div>

          <h1 style={{ fontSize: 26, fontWeight: 600, color: TEXT, letterSpacing: '-0.025em', marginBottom: 6 }}>
            Create your account
          </h1>
          <p style={{ color: MUTED, fontSize: 14, fontWeight: 300, marginBottom: 30 }}>
            Start recovering unpaid invoices in minutes.
          </p>

          {/* Success */}
          {success && (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="flex items-center gap-2 px-4 py-3 rounded-xl mb-5"
              style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', color: '#16A34A' }}
            >
              <CheckCircle size={14} />
              <span style={{ fontFamily: F, fontSize: 13 }}>{success}</span>
            </motion.div>
          )}

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
          {/* Google sign-in */}
          <div style={{ marginBottom: 20 }}>
            <div ref={gsiDivRef} style={{ display: 'none' }} aria-hidden="true" />
            <GoogleButton onClick={handleGoogleSignIn} loading={loading} />
            <div className="flex items-center gap-3 my-5">
              <div className="flex-1 h-px" style={{ background: '#C0D4E8' }} />
              <span style={{ color: '#608098', fontSize: 12 }}>or sign up with email</span>
              <div className="flex-1 h-px" style={{ background: '#C0D4E8' }} />
            </div>
          </div>

          <form onSubmit={handleRegister} className="flex flex-col gap-5">
            <Field label="Business / Company name" value={businessName} onChange={setBusinessName}
              placeholder="e.g. Pinnacle Manufacturing Co." icon={Building2} autoComplete="off" />
            <Field label="Work email" type="email" value={email} onChange={setEmail}
              placeholder="e.g. example@company.com" icon={Mail} autoComplete="new-email" />
            <Field
              label="Password" type="password" value={password} onChange={setPassword}
              placeholder="e.g. Password@123 (Min 8 chars, upper+number+symbol)" icon={Lock} autoComplete="new-password"
              hint={
                password ? (
                  <div className="mt-2">
                    {/* Strength bar */}
                    <div className="flex gap-1 mb-1">
                      {[1, 2, 3, 4, 5].map(i => (
                        <div key={i} className="flex-1 h-1 rounded-full transition-all duration-300"
                          style={{ background: i <= strength ? strengthColor : BORDER }} />
                      ))}
                    </div>
                    <p style={{ color: strengthColor, fontSize: 11, fontFamily: F }}>{strengthLabel}</p>
                  </div>
                ) : null
              }
            />

            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ scale: 1.01, boxShadow: `0 8px 24px ${ACCENT}44` }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center justify-center gap-2 py-3.5 rounded-xl mt-1"
              style={{
                background: ACCENT, color: '#fff',
                fontFamily: F, fontWeight: 600, fontSize: 15,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.8 : 1,
              }}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : null}
              {loading ? 'Creating account…' : 'Create free account'}
              {!loading && <ArrowRight size={16} />}
            </motion.button>
          </form>

          <p style={{ textAlign: 'center', marginTop: 20, color: MUTED, fontSize: 14 }}>
            Already have an account?{' '}
            <Link to="/login" style={{ color: ACCENT, fontWeight: 600, textDecoration: 'none' }}>
              Sign in
            </Link>
          </p>
        </div>

        <p style={{ textAlign: 'center', marginTop: 16, color: MUTED, fontSize: 12, opacity: 0.7 }}>
          By signing up you agree to our Terms of Service and Privacy Policy.
        </p>
      </motion.div>
    </div>
  );
}
