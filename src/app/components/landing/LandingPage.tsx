import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { motion, useInView, AnimatePresence } from 'motion/react';
import {
  ArrowRight, CheckCircle, Scale, Star, Menu, X, Bot,
  Sparkles, TrendingUp, Send, Eye, Globe, Phone, Zap,
  MessageSquare, AreaChart, ArrowUpRight, Hammer, Mail,
  Shield, Clock,
} from 'lucide-react';

/* Product Showcase screenshots */
import dashboardImg   from '@/assets/dashboard-main.png';
import campaignImg    from '@/assets/campaigns-view.png';
import legalImg       from '@/assets/legal-queue.png';
import recoveryHubImg from '@/assets/recovery-hub.png';
import invoicesImg    from '@/assets/invoices-list.png';

/* ─── Tokens ──────────────────────────────────────────────────────────────── */
const F      = "'Plus Jakarta Sans', system-ui, sans-serif";
const BG     = '#EEF2F8';
const SURF   = '#E2ECF5';
const BORDER = '#C0D4E8';
const TEXT   = '#0A1428';
const MUTED  = '#608098';
const ACCENT = '#0EA5E9';
const DARK   = '#071020';

const up = {
  hidden:  { opacity: 0, y: 28 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.65, ease: [0.22, 1, 0.36, 1] } },
};

/* ─── Counter ─────────────────────────────────────────────────────────────── */
function useCounter(target: number, dur: number = 2200) {
  const [val, setVal] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });
  useEffect(() => {
    if (!inView) return;
    const t0 = Date.now();
    const id = setInterval(() => {
      const p = Math.min((Date.now() - t0) / dur, 1);
      setVal(Math.floor((1 - Math.pow(1 - p, 3)) * target));
      if (p >= 1) clearInterval(id);
    }, 16);
    return () => clearInterval(id);
  }, [inView, target, dur]);
  return { val, ref };
}

/* ══════════════════════════════════════════════════════════════════════════
   LOGO — SVG mark + wordmark
══════════════════════════════════════════════════════════════════════════ */
function LogoMark({ uid, size = 36 }: { uid: string; size?: number }) {
  const gid = `rai-g-${uid}`;
  const hi  = `rai-h-${uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#0369A1" />
        </linearGradient>
        <radialGradient id={hi} cx="50%" cy="0%" r="80%" gradientUnits="objectBoundingBox">
          <stop offset="0%"   stopColor="white" stopOpacity="0.18" />
          <stop offset="100%" stopColor="white" stopOpacity="0"    />
        </radialGradient>
      </defs>
      <rect width="36" height="36" rx="9" fill={`url(#${gid})`} />
      <rect width="36" height="36" rx="9" fill={`url(#${hi})`} />
      {/* Vertical stem */}
      <line x1="11" y1="9" x2="11" y2="27"
        stroke="white" strokeWidth="2.8" strokeLinecap="round" />
      {/* Bowl: top bar + right-side D-curve + bottom bar */}
      <path d="M 11 9 L 20 9 C 28.5 9 28.5 21 20 21 L 11 21"
        stroke="white" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
      {/* Recovery leg — goes UP-RIGHT */}
      <line x1="20" y1="21" x2="25" y2="14"
        stroke="white" strokeWidth="2.5" strokeLinecap="round" />
      {/* Arrowhead tip at (27,12), wings spread lower-left */}
      <path d="M 24.5 16.5 L 27 12 L 22.5 13.5"
        stroke="white" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

function Logo({ uid, size = 34, light = false }: { uid: string; size?: number; light?: boolean }) {
  const fs = Math.round(size * 0.47);
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark uid={uid} size={size} />
      <span style={{ fontFamily: F, letterSpacing: '-0.03em', lineHeight: 1 }}>
        <span style={{ fontWeight: 500, fontSize: fs, color: light ? 'rgba(238,242,248,0.92)' : TEXT }}>Recover</span>
        <span style={{ fontWeight: 800, fontSize: fs, color: ACCENT }}>AI</span>
      </span>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   NAVBAR
══════════════════════════════════════════════════════════════════════════ */
function Navbar({ onLogin, onRegister }: { onLogin: () => void; onRegister: () => void }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', h);
    return () => window.removeEventListener('scroll', h);
  }, []);

  return (
    <nav className="fixed top-0 w-full z-50 transition-all duration-500"
      style={{
        background: scrolled ? 'rgba(238,242,248,0.92)' : 'transparent',
        backdropFilter: scrolled ? 'blur(20px)' : 'none',
        borderBottom: scrolled ? `1px solid ${BORDER}` : '1px solid transparent',
        fontFamily: F,
      }}>
      {/* Thin top accent stripe */}
      <div className="absolute top-0 left-0 right-0 h-[2px]"
        style={{ background: `linear-gradient(to right, ${ACCENT}, #38BDF8, #7DD3FC)` }} />

      <div className="max-w-6xl mx-auto px-6 h-[60px] flex items-center justify-between">
        <Logo uid="nav" size={34} />

        <div className="hidden md:flex items-center gap-8">
          {['Features', 'How It Works', 'Pricing'].map(l => (
            <a key={l} href={`#${l.toLowerCase().replace(/ /g, '-')}`}
              style={{ color: MUTED, fontSize: 14, fontWeight: 400 }}
              className="hover:text-sky-500 transition-colors">{l}</a>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          <button 
            onClick={onLogin}
            style={{ color: MUTED, fontSize: 14 }} 
            className="hover:text-sky-500 transition-colors px-3 cursor-pointer border-none bg-transparent"
          >
            Log in
          </button>
          <motion.button 
            onClick={onRegister}
            whileHover={{ scale: 1.03, boxShadow: `0 8px 24px ${ACCENT}44` }} 
            whileTap={{ scale: 0.97 }}
            className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl border-none cursor-pointer"
            style={{ background: ACCENT, color: '#fff', fontWeight: 600, fontSize: 14 }}>
            Get started free
          </motion.button>
        </div>

        <button className="md:hidden border-none cursor-pointer bg-transparent" style={{ color: MUTED }} onClick={() => setOpen(!open)}>
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
            style={{ background: SURF, borderBottom: `1px solid ${BORDER}` }}>
            <div className="px-6 py-5 flex flex-col gap-5">
              {['Features', 'How It Works', 'Pricing'].map(l => (
                <a key={l} href={`#${l.toLowerCase().replace(/ /g, '-')}`}
                  style={{ color: MUTED, fontSize: 15, textDecoration: 'none' }}
                  onClick={() => setOpen(false)}>{l}</a>
              ))}
              <button 
                onClick={() => { setOpen(false); onRegister(); }}
                className="py-3 rounded-xl border-none cursor-pointer text-white" 
                style={{ background: ACCENT, fontWeight: 600, fontSize: 14 }}
              >
                Get started free
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   HERO
══════════════════════════════════════════════════════════════════════════ */
function Hero({ onGetStarted }: { onGetStarted: () => void }) {
  const notifs = [
    { icon: CheckCircle, iconColor: '#22C55E', bg: '#F0FDF4', border: '#BBF7D0', label: '₹1,25,000 recovered', sub: 'BuildRight Constructions', pos: { top: '-28px', right: '-32px' }, delay: 0 },
    { icon: Bot, iconColor: ACCENT, bg: '#F0F9FF', border: '#BAE6FD', label: 'AI Draft Ready', sub: 'WhatsApp message prepared', pos: { bottom: '-24px', left: '-28px' }, delay: 0.6 },
  ];

  return (
    <section className="relative min-h-screen flex items-center pt-20 overflow-hidden" style={{ background: BG }}>

      {/* Dot grid */}
      <div className="absolute inset-0 pointer-events-none opacity-60"
        style={{ backgroundImage: `radial-gradient(circle, ${BORDER} 1px, transparent 1px)`, backgroundSize: '36px 36px' }} />

      {/* Blue radial glow left */}
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: `radial-gradient(ellipse 60% 70% at 5% 50%, rgba(14,165,233,0.07) 0%, transparent 60%)` }} />

      <div className="max-w-6xl mx-auto px-6 pb-20 w-full relative z-10">
        <div className="grid lg:grid-cols-2 gap-16 items-center">

          {/* ── Left ── */}
          <div>
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full mb-10"
              style={{ background: 'rgba(14,165,233,0.07)', border: `1px solid rgba(14,165,233,0.18)` }}>
              <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: ACCENT }} />
              <span style={{ color: ACCENT, fontSize: 12, fontFamily: F, fontWeight: 500 }}>AI-Powered Invoice Recovery for MSMEs</span>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.08, ease: [0.22, 1, 0.36, 1] }} className="mb-7">
              <h1 style={{ fontFamily: F, lineHeight: 1.06, letterSpacing: '-0.02em', color: TEXT }}>
                <span style={{ fontSize: 'clamp(40px,5.2vw,68px)', display: 'block', fontWeight: 500 }}>Recover every</span>
                <span style={{ fontSize: 'clamp(40px,5.2vw,68px)', display: 'block', fontWeight: 500 }}>unpaid invoice,</span>
                <em style={{ fontSize: 'clamp(40px,5.2vw,68px)', display: 'block', fontWeight: 500, fontStyle: 'italic', color: ACCENT }}>automatically.</em>
              </h1>
            </motion.div>

            <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.65, delay: 0.2 }}
              className="mb-10" style={{ color: MUTED, fontFamily: F, fontSize: 17, lineHeight: 1.75, fontWeight: 300, maxWidth: 440 }}>
              RecoverAI sends AI-crafted WhatsApp reminders, generates MSME legal notices with compound interest, and runs bulk campaigns — so you get paid faster.
            </motion.p>

            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.3 }}
              className="flex flex-wrap gap-3 mb-12">
              <motion.button 
                onClick={onGetStarted}
                whileHover={{ scale: 1.04, boxShadow: `0 12px 32px ${ACCENT}44` }} whileTap={{ scale: 0.97 }}
                className="flex items-center cursor-pointer gap-2 px-7 py-3.5 rounded-2xl border-none text-white"
                style={{ background: ACCENT, fontFamily: F, fontWeight: 600, fontSize: 15 }}>
                Start recovering free <ArrowRight size={16} />
              </motion.button>
              <motion.button 
                onClick={() => document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' })}
                whileHover={{ scale: 1.02, background: 'rgba(14,165,233,0.05)' }} whileTap={{ scale: 0.97 }}
                className="flex items-center cursor-pointer gap-2 px-7 py-3.5 rounded-2xl"
                style={{ border: `1px solid ${BORDER}`, color: MUTED, fontFamily: F, fontWeight: 500, fontSize: 15, background: 'transparent' }}
                onMouseEnter={e => (e.currentTarget.style.color = TEXT)}
                onMouseLeave={e => (e.currentTarget.style.color = MUTED)}>
                <Eye size={16} /> Watch demo
              </motion.button>
            </motion.div>

            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
              style={{ color: MUTED, fontFamily: F, fontSize: 13, fontWeight: 300 }}>
              Trusted by{' '}
              {['Pinnacle Manufacturing', 'Nagpur Steel Works', 'Global Exports'].map((n) => (
                <span key={n}><span style={{ opacity: 0.85 }}>{n}</span><span style={{ opacity: 0.3 }}> · </span></span>
              ))}
              <span style={{ opacity: 0.5 }}>and 500+ more</span>
            </motion.p>
          </div>

          {/* ── Right — screenshot + floating cards ── */}
          <motion.div initial={{ opacity: 0, x: 32 }} animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.9, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
            className="relative hidden lg:block">

            {/* Ambient glow */}
            <div className="absolute inset-0 rounded-3xl pointer-events-none -z-10"
              style={{ background: `radial-gradient(ellipse at 50% 50%, rgba(14,165,233,0.12), transparent 70%)`, transform: 'scale(1.15)' }} />

            {/* Floating notification cards */}
            {notifs.map((n, i) => (
              <motion.div key={i} initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1, y: [0, -9, 0] }}
                transition={{ opacity: { duration: 0.4, delay: 0.6 + i * 0.2 }, scale: { duration: 0.4, delay: 0.6 + i * 0.2 }, y: { duration: 3.5 + i * 0.5, repeat: Infinity, ease: 'easeInOut', delay: n.delay } }}
                className="absolute z-20" style={n.pos}>
                <div className="flex items-center gap-3 px-4 py-3 rounded-2xl"
                  style={{ background: n.bg, border: `1px solid ${n.border}`, boxShadow: '0 8px 32px rgba(10,20,40,0.1)', backdropFilter: 'blur(8px)', whiteSpace: 'nowrap' }}>
                  <div className="w-7 h-7 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${n.iconColor}15` }}>
                    <n.icon size={14} style={{ color: n.iconColor }} />
                  </div>
                  <div>
                    <p style={{ color: TEXT, fontFamily: F, fontWeight: 600, fontSize: 13, lineHeight: 1 }}>{n.label}</p>
                    <p style={{ color: MUTED, fontFamily: F, fontSize: 11, marginTop: 3 }}>{n.sub}</p>
                  </div>
                </div>
              </motion.div>
            ))}

            {/* Browser chrome + screenshot */}
            <div className="overflow-hidden rounded-2xl"
              style={{ border: `1px solid ${BORDER}`, boxShadow: `0 40px 100px rgba(10,20,40,0.12), 0 0 0 1px ${BORDER}` }}>
              <div className="flex items-center gap-1.5 px-5 py-3.5" style={{ background: SURF, borderBottom: `1px solid ${BORDER}` }}>
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#FF5F56' }} />
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#FFBD2E' }} />
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#27C93F' }} />
                <div className="ml-4 flex-1 h-5 rounded flex items-center px-3" style={{ background: 'rgba(10,20,40,0.04)' }}>
                  <span style={{ color: MUTED, opacity: 0.5, fontSize: 10, fontFamily: F }}>app.recoverai.in</span>
                </div>
              </div>
              <img src={dashboardImg} alt="RecoverAI Dashboard" className="w-full block" />
            </div>
          </motion.div>
        </div>
      </div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-24 pointer-events-none"
        style={{ background: `linear-gradient(to top, ${BG}, transparent)` }} />
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   STATS — animated counters
══════════════════════════════════════════════════════════════════════════ */
function Stats() {
  const { val: v1, ref: r1 } = useCounter(30);
  const { val: v2, ref: r2 } = useCounter(500);
  const { val: v3, ref: r3 } = useCounter(88);
  const outer = useRef(null);
  const inView = useInView(outer, { once: true, margin: '-60px' });

  const items = [
    { ref: r1, display: `₹${v1}Cr+`, label: 'Recovered for Indian MSMEs', sub: 'and growing every week.', pct: 72, accent: true },
    { ref: r2, display: `${v2}+`, label: 'Active businesses on RecoverAI', sub: 'from 12 industries across India.', pct: 60 },
    { ref: r3, display: `${v3}%`, label: 'Average recovery success rate', sub: 'vs. 12% industry baseline.', pct: 88 },
  ];

  return (
    <section ref={outer} style={{ background: SURF, borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}` }}>
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 md:grid-cols-3">
          {items.map((s, i) => (
            <motion.div key={i} ref={s.ref}
              initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.6, delay: i * 0.1 }}
              className={`py-14 px-10 ${i < 2 ? 'md:border-r' : ''}`} style={{ borderColor: BORDER }}>
              <p style={{ fontFamily: F, fontSize: 'clamp(44px,5vw,60px)', color: s.accent ? ACCENT : TEXT, lineHeight: 1, letterSpacing: '-0.04em', fontWeight: 400, marginBottom: 12 }}>
                {s.display}
              </p>
              <p style={{ color: TEXT, fontFamily: F, fontSize: 15, fontWeight: 500, marginBottom: 4 }}>{s.label}</p>
              <p style={{ color: MUTED, fontFamily: F, fontSize: 13, fontWeight: 300, marginBottom: 16 }}>{s.sub}</p>
              {/* Progress bar */}
              <div className="h-[3px] rounded-full overflow-hidden" style={{ background: BORDER }}>
                <motion.div initial={{ width: 0 }} animate={inView ? { width: `${s.pct}%` } : { width: 0 }}
                  transition={{ duration: 1.4, delay: 0.4 + i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                  className="h-full rounded-full" style={{ background: s.accent ? ACCENT : `${ACCENT}60` }} />
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   FEATURES — editorial rows
══════════════════════════════════════════════════════════════════════════ */
function Features() {
  const [active, setActive] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  const features = [
    {
      n: '01', icon: Bot, color: ACCENT, tag: 'Most Used',
      title: 'AI Recovery Messages',
      desc: 'Generate personalized WhatsApp, email and legal notices in one click. Tone adapts to invoice age, industry, and debtor payment history — every message feels individually written.',
      points: ['Adapts tone to invoice age & debtor history', 'Works in Hindi, Hinglish & English', 'Zero setup — active in under 60 seconds'],
    },
    {
      n: '02', icon: Scale, color: '#818CF8', tag: 'Legal',
      title: 'MSME Legal Queue',
      desc: 'Auto-calculate 19.5% compound interest under MSMED Act 2006. Generate Samadhaan legal notices in one click — no lawyer, no ₹15,000 fees per notice.',
      points: ['Auto 19.5% compound interest calculation', 'Samadhaan portal notice in one click', '₹0 extra — no lawyer fees, ever'],
    },
    {
      n: '03', icon: Send, color: '#34D399', tag: '98% Open Rate',
      title: 'WhatsApp Campaigns',
      desc: 'Rapid-fire bulk mode. Process all your debtors in a single 15-minute session. RecoverAI drafts each message, you review and send.',
      points: ['98% open rate vs 22% for email', 'Bulk mode: all debtors in under 15 min', 'AI drafts every message — you just approve'],
    },
    {
      n: '04', icon: MessageSquare, color: '#60A5FA', tag: 'AI Powered',
      title: 'Smart Debtor Inbox',
      desc: 'All replies unified in one inbox. AI translates Hinglish and classifies payment intent as High, Medium, or Low confidence — instantly.',
      points: ['Hinglish & Hindi translation built-in', 'High / Medium / Low intent scoring', 'Full reply history & tracking'],
    },
    {
      n: '05', icon: Zap, color: '#FB923C', tag: 'Automated',
      title: 'Auto Escalation',
      desc: 'Set your rules once. RecoverAI moves each debtor through the escalation ladder automatically based on days overdue and response behavior.',
      points: ['Gentle → Firm → Legal, fully automated', 'Trigger rules based on days & behavior', 'Never miss a follow-up again'],
    },
    {
      n: '06', icon: AreaChart, color: '#F472B6', tag: 'Live Data',
      title: 'Recovery Analytics',
      desc: 'A live dashboard showing every rupee: outstanding, in-progress, and recovered. Monthly trends and exactly who needs your attention today.',
      points: ['Live outstanding vs recovered view', 'Monthly recovery trend charts', 'Priority escalation list — always current'],
    },
  ];

  const f = features[active];

  return (
    <section id="features" ref={ref} className="py-28" style={{ background: BG }}>
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}}
          className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 mb-14">
          <h2 style={{ fontFamily: F, fontSize: 'clamp(34px,4.5vw,52px)', color: TEXT, letterSpacing: '-0.03em', lineHeight: 1.1, fontWeight: 500 }}>
            Six tools built to get<br />
            <em style={{ fontStyle: 'italic', color: ACCENT }}>every rupee back.</em>
          </h2>
          <p style={{ color: MUTED, fontFamily: F, fontSize: 15, fontWeight: 300, lineHeight: 1.7, maxWidth: 320 }}>
            Integrated, automated, and built for the way Indian MSMEs actually run their businesses.
          </p>
        </motion.div>

        {/* Split explorer */}
        <motion.div initial={{ opacity: 0, y: 24 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ delay: 0.15 }}
          className="grid lg:grid-cols-[272px,1fr] gap-3 items-start">

          {/* ── Left nav ── */}
          <div className="rounded-2xl overflow-hidden" style={{ border: `1px solid ${BORDER}`, background: SURF }}>
            {features.map((feat, i) => (
              <button key={feat.n} onClick={() => setActive(i)}
                className="w-full flex items-center cursor-pointer gap-3.5 px-5 py-[15px] text-left relative transition-colors duration-150 border-none"
                style={{
                  background: active === i ? '#fff' : 'transparent',
                  borderBottom: i < 5 ? `1px solid ${BORDER}` : 'none',
                }}>
                {/* Active left bar */}
                {active === i && (
                  <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full"
                    style={{ background: feat.color }} />
                )}
                {/* Icon */}
                <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: `${feat.color}${active === i ? '14' : '08'}`, border: `1px solid ${feat.color}${active === i ? '25' : '10'}`, transition: 'all 0.15s' }}>
                  <feat.icon size={15} style={{ color: feat.color }} />
                </div>
                {/* Label */}
                <span className="flex-1 min-w-0 truncate"
                  style={{ fontFamily: F, color: active === i ? TEXT : MUTED, fontWeight: active === i ? 600 : 400, fontSize: 13.5, transition: 'all 0.15s' }}>
                  {feat.title}
                </span>
                {active === i && (
                  <ArrowUpRight size={13} style={{ color: feat.color, flexShrink: 0 }} />
                )}
              </button>
            ))}
          </div>

          {/* ── Right detail panel ── */}
          <AnimatePresence mode="wait">
            <motion.div key={active}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="rounded-2xl overflow-hidden"
              style={{ border: `1px solid ${BORDER}`, background: '#fff', boxShadow: '0 4px 48px rgba(10,20,40,0.07)' }}>

              {/* Thin color strip at top */}
              <div style={{ height: 3, background: `linear-gradient(90deg, ${f.color} 0%, ${f.color}40 100%)` }} />

              <div className="p-9 lg:p-10">

                {/* Icon + tag */}
                <div className="flex items-center justify-between mb-7">
                  <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                    style={{ background: `${f.color}0E`, border: `1px solid ${f.color}1A` }}>
                    <f.icon size={28} style={{ color: f.color }} />
                  </div>
                  <span className="px-3 py-1.5 rounded-full"
                    style={{ background: `${f.color}0E`, color: f.color, fontFamily: F, fontSize: 11, fontWeight: 700, letterSpacing: '0.04em' }}>
                    {f.tag}
                  </span>
                </div>

                {/* Feature number label */}
                <p style={{ color: f.color, fontFamily: F, fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', marginBottom: 8 }}>FEATURE {f.n}</p>

                {/* Title */}
                <h3 style={{ fontFamily: F, fontSize: 'clamp(22px,2.8vw,28px)', fontWeight: 600, color: TEXT, letterSpacing: '-0.025em', lineHeight: 1.12, marginBottom: 14 }}>
                  {f.title}
                </h3>

                {/* Description */}
                <p style={{ color: MUTED, fontFamily: F, fontSize: 15, lineHeight: 1.8, fontWeight: 300, marginBottom: 28 }}>
                  {f.desc}
                </p>

                {/* Bullet points */}
                <div className="flex flex-col gap-3 mb-8">
                  {f.points.map((pt, pi) => (
                    <motion.div key={pt}
                      initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: pi * 0.07, duration: 0.26 }}
                      className="flex items-center gap-3">
                      <div className="w-[22px] h-[22px] rounded-full flex items-center justify-center shrink-0"
                        style={{ background: `${f.color}0E` }}>
                        <CheckCircle size={12} style={{ color: f.color }} />
                      </div>
                      <span style={{ color: TEXT, fontFamily: F, fontSize: 14 }}>{pt}</span>
                    </motion.div>
                  ))}
                </div>

                {/* Footer: CTA + dot progress */}
                <div className="flex items-center justify-between pt-6"
                  style={{ borderTop: `1px solid ${BORDER}` }}>
                  <button 
                    onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
                    className="flex items-center gap-1.5 hover:opacity-60 transition-opacity border-none cursor-pointer bg-transparent"
                    style={{ color: f.color, fontFamily: F, fontSize: 14, fontWeight: 600 }}>
                    Learn more <ArrowUpRight size={14} />
                  </button>
                  <div className="flex items-center gap-1.5">
                    {features.map((_, i) => (
                      <button key={i} onClick={() => setActive(i)}
                        className="rounded-full transition-all duration-300 border-none cursor-pointer p-0"
                        style={{ height: 6, width: i === active ? 20 : 6, background: i === active ? f.color : BORDER }} />
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   PRODUCT SHOWCASE
══════════════════════════════════════════════════════════════════════════ */
function ProductShowcase() {
  const [active, setActive] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  const tabs = [
    { label: 'Dashboard', img: dashboardImg },
    { label: 'All Invoices', img: invoicesImg },
    { label: 'Legal Queue', img: legalImg },
    { label: 'Campaigns', img: campaignImg },
    { label: 'Recovery Hub', img: recoveryHubImg },
  ];

  return (
    <section ref={ref} className="py-28" style={{ background: SURF }}>
      <div className="max-w-6xl mx-auto px-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}} className="mb-12">
          <h2 style={{ fontFamily: F, fontSize: 'clamp(34px,4.5vw,52px)', color: TEXT, letterSpacing: '-0.03em', lineHeight: 1.1, fontWeight: 500, marginBottom: 12 }}>
            Built for how MSMEs<br /><em style={{ fontStyle: 'italic' }}>actually work.</em>
          </h2>
          <p style={{ color: MUTED, fontFamily: F, fontSize: 16, fontWeight: 300, lineHeight: 1.7, maxWidth: 420 }}>
            Every screen answers one question: how do we help you recover faster?
          </p>
        </motion.div>

        {/* Pill tabs */}
        <motion.div initial={{ opacity: 0 }} animate={inView ? { opacity: 1 } : {}} transition={{ delay: 0.2 }}
          className="flex gap-1.5 mb-6 overflow-x-auto pb-1">
          {tabs.map((t, i) => (
            <button key={t.label} onClick={() => setActive(i)}
              className="px-4 py-2 rounded-xl cursor-pointer whitespace-nowrap transition-all duration-200 shrink-0"
              style={{
                background: active === i ? ACCENT : 'transparent',
                color: active === i ? '#fff' : MUTED,
                fontFamily: F, fontWeight: 500, fontSize: 13,
                border: `1px solid ${active === i ? ACCENT : BORDER}`,
                boxShadow: active === i ? `0 4px 12px ${ACCENT}30` : 'none',
              }}>
              {t.label}
            </button>
          ))}
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 24 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ delay: 0.3 }}>
          <div className="relative max-w-3xl mx-auto">
            {/* Glow */}
            <div className="absolute -inset-3 rounded-3xl pointer-events-none"
              style={{ background: `radial-gradient(ellipse at 50% 80%, rgba(14,165,233,0.08), transparent 70%)` }} />
            <div className="relative rounded-2xl overflow-hidden"
              style={{ border: `1px solid ${BORDER}`, boxShadow: `0 24px 80px rgba(10,20,40,0.1)` }}>
              <div className="flex items-center gap-1.5 px-5 py-3.5" style={{ background: BG, borderBottom: `1px solid ${BORDER}` }}>
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#FF5F56' }} />
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#FFBD2E' }} />
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#27C93F' }} />
                <div className="ml-4 flex-1 h-5 rounded flex items-center px-3" style={{ background: 'rgba(10,20,40,0.04)' }}>
                  <span style={{ color: MUTED, opacity: 0.5, fontSize: 10, fontFamily: F }}>
                    app.recoverai.in/{tabs[active].label.toLowerCase().replace(/ /g, '-')}
                  </span>
                </div>
              </div>
              <AnimatePresence mode="wait">
                <motion.img 
                  key={active} 
                  src={tabs[active].img} 
                  alt={tabs[active].label}
                  initial={{ opacity: 0, y: 6 }} 
                  animate={{ opacity: 1, y: 0 }} 
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.22 }} 
                  className="w-full object-contain block max-h-[500px] bg-white mx-auto"
                  style={{ imageRendering: '-webkit-optimize-contrast', borderRadius: '0 0 16px 16px' }}
                />
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   HOW IT WORKS
══════════════════════════════════════════════════════════════════════════ */
function HowItWorks() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  const steps = [
    { n: '1', icon: Sparkles, color: ACCENT, title: 'Add your invoices', desc: 'Upload manually or sync from Tally, Zoho Books, or QuickBooks. All outstanding dues in under 60 seconds.' },
    { n: '2', icon: Bot, color: '#818CF8', title: 'AI starts recovering', desc: 'Personalized WhatsApp and email reminders go out automatically at 7, 21, and 45-day intervals.' },
    { n: '3', icon: Hammer, color: '#34D399', title: 'Escalate to legal if needed', desc: 'For stubborn debtors, generate MSME Samadhaan legal notices with compound interest in one click.' },
    { n: '4', icon: TrendingUp, color: '#FB923C', title: 'Watch the money flow', desc: 'Track every recovery in real time. Your pipeline shrinks. Your bank account grows.' },
  ];

  return (
    <section id="how-it-works" ref={ref} className="py-28" style={{ background: BG }}>
      <div className="max-w-6xl mx-auto px-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}} className="mb-20">
          <h2 style={{ fontFamily: F, fontSize: 'clamp(34px,4.5vw,52px)', color: TEXT, letterSpacing: '-0.03em', lineHeight: 1.1, fontWeight: 500, maxWidth: 460 }}>
            From invoice to payment<br /><em style={{ fontStyle: 'italic', color: ACCENT }}>in four steps.</em>
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-x-16 gap-y-12">
          {steps.map((s, i) => (
            <motion.div key={s.n} initial={{ opacity: 0, y: 24 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.6, delay: i * 0.1 }}
              className="flex items-start gap-5 group cursor-default">
              <div className="w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 transition-all duration-200 group-hover:shadow-md"
                style={{ background: `${s.color}10`, border: `1px solid ${s.color}25` }}
                onMouseEnter={e => (e.currentTarget.style.background = `${s.color}18`)}
                onMouseLeave={e => (e.currentTarget.style.background = `${s.color}10`)}>
                <s.icon size={18} style={{ color: s.color }} />
              </div>
              <div>
                <p style={{ color: `${s.color}99`, fontFamily: F, fontWeight: 700, fontSize: 11, marginBottom: 6, letterSpacing: '0.07em' }}>STEP {s.n}</p>
                <h3 style={{ color: TEXT, fontFamily: F, fontWeight: 600, fontSize: 18, letterSpacing: '-0.01em', marginBottom: 8 }}>{s.title}</h3>
                <p style={{ color: MUTED, fontFamily: F, fontSize: 14, lineHeight: 1.75, fontWeight: 300 }}>{s.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   TESTIMONIALS
══════════════════════════════════════════════════════════════════════════ */
function Testimonials() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  return (
    <section ref={ref} style={{ background: SURF, borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}` }}>
      <div className="max-w-6xl mx-auto px-6">

        {/* Large featured quote */}
        <motion.div initial={{ opacity: 0, y: 24 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7 }}
          className="relative py-20" style={{ borderBottom: `1px solid ${BORDER}` }}>

          {/* Decorative quotation mark */}
          <div className="absolute top-12 left-0 select-none pointer-events-none"
            style={{ fontFamily: 'Georgia, serif', fontSize: 180, lineHeight: 1, color: `${ACCENT}08`, fontWeight: 400 }}>"</div>

          <div className="relative z-10">
            <div className="flex gap-1 mb-6">
              {[...Array(5)].map((_, j) => <Star key={j} size={14} fill={ACCENT} style={{ color: ACCENT }} />)}
            </div>
            <blockquote style={{ fontFamily: F, fontStyle: 'italic', fontSize: 'clamp(20px,2.8vw,30px)', lineHeight: 1.55, color: TEXT, maxWidth: 780, marginBottom: 28, fontWeight: 300 }}>
              "RecoverAI recovered ₹4.5 lakh from BuildRight Constructions in under 90 days. The MSME legal notice feature alone saves us ₹15,000 per debtor — lawyers used to charge that just to write one letter."
            </blockquote>
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
                style={{ background: `${ACCENT}12`, border: `1.5px solid ${ACCENT}28` }}>
                <span style={{ color: ACCENT, fontFamily: F, fontWeight: 700, fontSize: 13 }}>RG</span>
              </div>
              <div>
                <p style={{ color: TEXT, fontFamily: F, fontWeight: 600, fontSize: 15 }}>Ramesh Gupta</p>
                <p style={{ color: MUTED, fontFamily: F, fontSize: 13, fontWeight: 300 }}>Nagpur Steel Works</p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Two smaller quotes */}
        <div className="grid md:grid-cols-2" style={{ borderBottom: `1px solid ${BORDER}` }}>
          {[
            { q: '"WhatsApp campaigns reached all 22 debtors in 15 minutes. Recovery rate jumped from 12% to 78% in two months. Nothing else we tried came close."', name: 'Priya Desai', role: 'Global Exports Ltd', init: 'PD', c: '#818CF8', delay: 0.2 },
            { q: '"The AI reads Hinglish replies and tells me who to escalate. \'Kal bhej dunga\' → Low confidence. It\'s almost funny how accurate it is — saved us 40 hours a month."', name: 'Vikas Gupta', role: 'Pinnacle Manufacturing', init: 'VG', c: '#34D399', delay: 0.35 },
          ].map((q, i) => (
            <motion.div key={q.name} initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.6, delay: q.delay }}
              className={`py-12 ${i === 0 ? 'md:border-r md:pr-12' : 'md:pl-12'}`} style={{ borderColor: BORDER }}>
              <div className="flex gap-1 mb-5">
                {[...Array(5)].map((_, j) => <Star key={j} size={12} fill={q.c} style={{ color: q.c }} />)}
              </div>
              <blockquote style={{ fontFamily: F, fontStyle: 'italic', fontSize: 16, lineHeight: 1.7, color: MUTED, marginBottom: 20, fontWeight: 300 }}>{q.q}</blockquote>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{ background: `${q.c}10` }}>
                  <span style={{ color: q.c, fontFamily: F, fontWeight: 700, fontSize: 12 }}>{q.init}</span>
                </div>
                <div>
                  <p style={{ color: TEXT, fontFamily: F, fontWeight: 600, fontSize: 14 }}>{q.name}</p>
                  <p style={{ color: MUTED, fontFamily: F, fontSize: 12, fontWeight: 300 }}>{q.role}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   PRICING
══════════════════════════════════════════════════════════════════════════ */
function Pricing({ onGetStarted }: { onGetStarted: () => void }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });
  const [annual, setAnnual] = useState(false);

  const plans = [
    { name: 'Starter', price: '₹0', sub: 'free forever', desc: 'For businesses just getting started with recovery.', features: ['5 active invoices', 'Email reminders', 'Recovery dashboard', 'Invoice tracking'], cta: 'Start free', highlight: false, action: 'register' },
    { name: 'Growth', price: annual ? '₹1,999' : '₹2,499', sub: annual ? '/mo · billed annually' : '/month', desc: 'For businesses serious about what they\'re owed.', features: ['50 active invoices', 'AI recovery messages', 'WhatsApp campaigns', 'MSME legal notices', 'Smart debtor inbox', 'Recovery analytics', 'Auto-escalation'], cta: 'Start 14-day trial', highlight: true, badge: 'Most popular', action: 'register' },
    { name: 'Enterprise', price: annual ? '₹5,999' : '₹7,499', sub: annual ? '/mo · billed annually' : '/month', desc: 'For large MSMEs with complex recovery needs.', features: ['Unlimited invoices', 'Everything in Growth', 'God Mode analytics', 'Tally / Zoho sync', 'API access', 'Priority support'], cta: 'Talk to sales', highlight: false, action: 'sales' },
  ];

  return (
    <section id="pricing" ref={ref} className="py-28" style={{ background: BG }}>
      <div className="max-w-6xl mx-auto px-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}} className="mb-16">
          <h2 style={{ fontFamily: F, fontSize: 'clamp(34px,4.5vw,52px)', color: TEXT, letterSpacing: '-0.03em', lineHeight: 1.1, fontWeight: 500, marginBottom: 16 }}>
            Simple pricing.<br /><em style={{ fontStyle: 'italic', color: ACCENT }}>Serious results.</em>
          </h2>
          <div className="flex items-center gap-3">
            <span style={{ color: annual ? MUTED : TEXT, fontFamily: F, fontSize: 14, fontWeight: annual ? 300 : 500 }}>Monthly</span>
            <button onClick={() => setAnnual(!annual)} className="relative w-11 h-6 rounded-full transition-colors duration-300 border-none cursor-pointer p-0"
              style={{ background: annual ? ACCENT : BORDER }}>
              <div className="absolute top-[3px] w-[18px] h-[18px] rounded-full bg-white transition-all duration-300"
                style={{ left: annual ? 'calc(100% - 21px)' : 3 }} />
            </button>
            <span style={{ color: annual ? TEXT : MUTED, fontFamily: F, fontSize: 14, fontWeight: annual ? 500 : 300 }}>
              Annual{' '}
              <span className="ml-1 px-2 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.1)', color: '#16A34A', fontSize: 11, fontWeight: 600 }}>Save 20%</span>
            </span>
          </div>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-4">
          {plans.map((p, i) => (
            <motion.div key={p.name} initial={{ opacity: 0, y: 28 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.6, delay: i * 0.08 }}
              className="rounded-2xl p-7 flex flex-col relative"
              style={{
                background: p.highlight ? '#fff' : SURF,
                border: `1px solid ${p.highlight ? ACCENT : BORDER}`,
                boxShadow: p.highlight ? `0 8px 40px rgba(14,165,233,0.15)` : 'none',
              }}>
              {p.badge && (
                <div className="absolute -top-3.5 left-6 px-4 py-1 rounded-full"
                  style={{ background: ACCENT, color: '#fff', fontSize: 11, fontFamily: F, fontWeight: 600 }}>
                  {p.badge}
                </div>
              )}
              <p style={{ color: p.highlight ? ACCENT : TEXT, fontFamily: F, fontWeight: 600, fontSize: 15, marginBottom: 10 }}>{p.name}</p>
              <div className="flex items-baseline gap-1 mb-2">
                <span style={{ fontFamily: F, fontSize: 42, color: TEXT, letterSpacing: '-0.04em', lineHeight: 1, fontWeight: 400 }}>{p.price}</span>
                <span style={{ color: MUTED, fontFamily: F, fontSize: 13, marginLeft: 4, fontWeight: 300 }}>{p.sub}</span>
              </div>
              <p style={{ color: MUTED, fontFamily: F, fontSize: 13, fontWeight: 300, lineHeight: 1.6, marginBottom: 24 }}>{p.desc}</p>
              <div className="flex flex-col gap-2.5 mb-8 flex-grow">
                {p.features.map(f => (
                  <div key={f} className="flex items-center gap-2.5">
                    <CheckCircle size={14} style={{ color: p.highlight ? ACCENT : BORDER }} className="shrink-0" />
                    <span style={{ color: MUTED, fontFamily: F, fontSize: 13, fontWeight: 300 }}>{f}</span>
                  </div>
                ))}
              </div>
              <motion.button 
                onClick={p.action === 'sales' ? () => window.open('mailto:sales@recoverai.in', '_blank') : onGetStarted}
                whileHover={{ scale: 1.02, boxShadow: p.highlight ? `0 8px 20px ${ACCENT}44` : 'none' }} whileTap={{ scale: 0.98 }}
                className="w-full py-3.5 rounded-xl cursor-pointer"
                style={{ background: p.highlight ? ACCENT : 'transparent', color: p.highlight ? '#fff' : MUTED, fontFamily: F, fontWeight: 600, fontSize: 14, border: p.highlight ? 'none' : `1px solid ${BORDER}` }}>
                {p.cta}
              </motion.button>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   CTA — dark navy, the dramatic moment
══════════════════════════════════════════════════════════════════════════ */
function CTA({ onGetStarted }: { onGetStarted: () => void }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  return (
    <section ref={ref} className="relative overflow-hidden py-28"
      style={{ background: DARK }}>

      {/* Radial glow */}
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: `radial-gradient(ellipse 70% 60% at 50% 110%, rgba(14,165,233,0.12) 0%, transparent 60%)` }} />

      {/* Dot grid on dark */}
      <div className="absolute inset-0 pointer-events-none opacity-20"
        style={{ backgroundImage: `radial-gradient(circle, rgba(14,165,233,0.3) 1px, transparent 1px)`, backgroundSize: '40px 40px' }} />

      <div className="max-w-6xl mx-auto px-6 relative z-10">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7 }}>
            <h2 style={{ fontFamily: F, fontSize: 'clamp(36px,5vw,58px)', color: '#EEF2F8', letterSpacing: '-0.03em', lineHeight: 1.08, fontWeight: 500, marginBottom: 18 }}>
              Your unpaid invoices<br /><em style={{ fontStyle: 'italic', color: ACCENT }}>won't recover themselves.</em>
            </h2>
            <p style={{ color: 'rgba(238,242,248,0.5)', fontFamily: F, fontSize: 17, lineHeight: 1.75, fontWeight: 300, maxWidth: 420 }}>
              Join 500+ Indian MSMEs who've taken back what's theirs. Free forever — no credit card, no setup fees.
            </p>

            {/* Trust signals */}
            <div className="flex flex-wrap gap-6 mt-8">
              {[
                { icon: Shield, text: 'MSME Act 2006 compliant' },
                { icon: Clock, text: 'Setup in 5 minutes' },
              ].map(s => (
                <div key={s.text} className="flex items-center gap-2">
                  <s.icon size={14} style={{ color: `${ACCENT}` }} />
                  <span style={{ color: 'rgba(238,242,248,0.4)', fontFamily: F, fontSize: 13, fontWeight: 300 }}>{s.text}</span>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 24 }} animate={inView ? { opacity: 1, x: 0 } : {}} transition={{ duration: 0.7, delay: 0.15 }}
            className="flex flex-col gap-3">
            <motion.button 
              onClick={onGetStarted}
              whileHover={{ scale: 1.03, boxShadow: `0 16px 40px ${ACCENT}50` }} whileTap={{ scale: 0.97 }}
              className="flex items-center justify-center cursor-pointer border-none gap-2 py-4 rounded-2xl text-white"
              style={{ background: ACCENT, fontFamily: F, fontWeight: 600, fontSize: 16 }}>
              Start recovering free <ArrowRight size={18} />
            </motion.button>
            <motion.button 
              onClick={() => window.open('mailto:support@recoverai.in', '_blank')}
              whileHover={{ scale: 1.02, background: 'rgba(255,255,255,0.08)' }} 
              whileTap={{ scale: 0.97 }}
              className="flex items-center justify-center cursor-pointer gap-2 py-4 rounded-2xl"
              style={{ background: 'rgba(255,255,255,0.05)', color: 'rgba(238,242,248,0.6)', fontFamily: F, fontWeight: 500, fontSize: 16, border: '1px solid rgba(255,255,255,0.08)' }}>
              <Phone size={17} /> Schedule a demo
            </motion.button>
            <p style={{ color: 'rgba(238,242,248,0.25)', fontFamily: F, fontSize: 12, textAlign: 'center', fontWeight: 300, marginTop: 4 }}>
              No credit card required · Cancel anytime
            </p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   FOOTER
══════════════════════════════════════════════════════════════════════════ */
function Footer() {
  return (
    <footer className="relative overflow-hidden" style={{ background: SURF, borderTop: `1px solid ${BORDER}`, fontFamily: F }}>

      {/* Ghosted wordmark */}
      <div className="absolute bottom-0 left-0 right-0 flex items-end justify-center overflow-hidden pointer-events-none select-none"
        style={{ height: 120 }}>
        <p style={{ fontFamily: F, fontWeight: 700, fontSize: '13vw', color: `${ACCENT}06`, letterSpacing: '-0.05em', lineHeight: 0.8, whiteSpace: 'nowrap' }}>
          RECOVERAI
        </p>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-16 relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10 mb-14">
          <div className="col-span-2">
            <div className="mb-5">
              <Logo uid="footer" size={32} />
            </div>
            <p style={{ color: MUTED, fontSize: 13, lineHeight: 1.75, maxWidth: 220, fontWeight: 300 }}>
              India's AI-powered invoice recovery platform for MSMEs.
            </p>
            <div className="flex items-center gap-2 mt-5">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span style={{ color: MUTED, opacity: 0.5, fontSize: 12 }}>All systems operational</span>
            </div>
          </div>

          {[
            { title: 'Product', links: ['Dashboard', 'All Invoices', 'Recovery Hub', 'Legal Queue', 'Campaigns'] },
            { title: 'Company', links: ['About', 'Blog', 'Careers', 'Contact'] },
            { title: 'Legal', links: ['Privacy', 'Terms', 'Compliance', 'Cookies'] },
          ].map(col => (
            <div key={col.title}>
              <p style={{ color: TEXT, fontWeight: 600, fontSize: 13, marginBottom: 14 }}>{col.title}</p>
              <div className="flex flex-col gap-3">
                {col.links.map(l => (
                  <a key={l} href="#" style={{ color: MUTED, fontSize: 13, fontWeight: 300, opacity: 0.7, textDecoration: 'none' }}
                    className="hover:opacity-100 hover:text-sky-500 transition-all">{l}</a>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-8"
          style={{ borderTop: `1px solid ${BORDER}` }}>
          <p style={{ color: MUTED, opacity: 0.4, fontSize: 13 }}>© 2026 RecoverAI · Made in India</p>
          <div className="flex items-center gap-5">
            <div className="flex items-center gap-1.5">
              <Mail size={13} style={{ color: MUTED, opacity: 0.4 }} />
              <span style={{ color: MUTED, opacity: 0.4, fontSize: 13 }}>support@recoverai.in</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Globe size={13} style={{ color: MUTED, opacity: 0.4 }} />
              <span style={{ color: MUTED, opacity: 0.4, fontSize: 13 }}>recoverai.in</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   ROOT
══════════════════════════════════════════════════════════════════════════ */
export default function LandingPage() {
  const navigate = useNavigate();
  return (
    <div style={{ background: BG, color: TEXT, overflowX: 'hidden' }}>
      <Navbar onLogin={() => navigate('/login')} onRegister={() => navigate('/register')} />
      <Hero onGetStarted={() => navigate('/register')} />
      <Stats />
      <Features />
      <ProductShowcase />
      <HowItWorks />
      <Testimonials />
      <Pricing onGetStarted={() => navigate('/register')} />
      <CTA onGetStarted={() => navigate('/register')} />
      <Footer />
    </div>
  );
}
