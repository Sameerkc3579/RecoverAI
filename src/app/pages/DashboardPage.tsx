import { useNavigate } from 'react-router';
import { motion } from 'motion/react';
import {
  LayoutDashboard, Inbox, FileText, RotateCcw, Scale,
  Megaphone, ShieldAlert, Settings, LogOut, Check
} from 'lucide-react';
import { clearTokens } from '@/lib/auth';

const F      = "'Plus Jakarta Sans', system-ui, sans-serif";
const BG     = '#F4F7FB';
const SURF   = '#FFFFFF';
const BORDER = '#E2E8F0';
const TEXT   = '#0F172A';
const MUTED  = '#64748B';
const ACCENT = '#0EA5E9';

function SidebarItem({ icon: Icon, label, badge, active = false, badgeColor = '#EF4444' }: any) {
  return (
    <div className={`flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${active ? 'bg-sky-100 text-sky-700 font-semibold' : 'text-slate-600 hover:bg-slate-50 font-medium'}`} style={{ fontFamily: F, fontSize: 14 }}>
      <div className="flex items-center gap-3">
        <Icon size={18} className={active ? 'text-sky-600' : 'text-slate-500'} />
        {label}
      </div>
      {badge && (
        <span className="text-[11px] font-bold text-white px-2 py-0.5 rounded-full" style={{ backgroundColor: badgeColor }}>
          {badge}
        </span>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearTokens();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex" style={{ background: BG, fontFamily: F }}>
      {/* Sidebar */}
      <aside className="w-[260px] bg-white flex flex-col shrink-0" style={{ borderRight: `1px solid ${BORDER}` }}>
        <div className="p-6 pb-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-lg" style={{ background: ACCENT }}>
              R
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight" style={{ color: TEXT }}>RecoverAI</h1>
              <p className="text-[11px] text-slate-500 font-medium">MSME Invoice Recovery</p>
            </div>
          </div>
        </div>

        <div className="px-3 py-4 flex-1 flex flex-col gap-6">
          <div>
            <div className="px-3 mb-2 text-[11px] font-bold tracking-wider text-slate-400">MAIN</div>
            <div className="flex flex-col gap-1">
              <SidebarItem icon={LayoutDashboard} label="Dashboard" active />
              <SidebarItem icon={Inbox} label="Debtor Inbox" badge="1" />
              <SidebarItem icon={FileText} label="All Invoices" badge="22" badgeColor="#F59E0B" />
              <SidebarItem icon={RotateCcw} label="Recovery Hub" />
              <SidebarItem icon={Scale} label="Legal Queue" badge="12" />
              <SidebarItem icon={Megaphone} label="Campaigns" />
              <SidebarItem icon={ShieldAlert} label="God Mode" badge="Admin" />
            </div>
          </div>

          <div>
            <div className="px-3 mb-2 text-[11px] font-bold tracking-wider text-slate-400">ACCOUNT</div>
            <div className="flex flex-col gap-1">
              <SidebarItem icon={Settings} label="Settings" />
              <div onClick={handleLogout}>
                <SidebarItem icon={LogOut} label="Sign Out" />
              </div>
            </div>
          </div>
        </div>

        <div className="p-4" style={{ borderTop: `1px solid ${BORDER}` }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm">
              S
            </div>
            <div>
              <p className="font-bold text-sm leading-tight" style={{ color: TEXT }}>sam</p>
              <p className="text-[11px] text-slate-500 font-medium">Starter Plan · Mumbai</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: TEXT }}>Dashboard</h1>
            <p className="text-sm font-medium text-slate-500 mt-1">Overview of your recovery pipeline</p>
          </div>
          <div className="flex items-center gap-4">
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span> Live
            </span>
            <span className="text-sm font-medium text-slate-500">14 April 2026</span>
          </div>
        </header>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-6 mb-6">
          {/* Box 1 */}
          <div className="bg-white p-5 rounded-2xl" style={{ border: `1px solid ${BORDER}` }}>
            <div className="text-xs font-bold text-slate-400 mb-3 flex items-center gap-1.5 uppercase tracking-wider">
              <span>💰</span> OUTSTANDING
            </div>
            <div className="text-[28px] font-extrabold text-amber-500 mb-2 leading-none">₹22,40,500</div>
            <div className="text-xs font-semibold text-slate-500 flex items-center gap-1">
              <span className="text-amber-500">▲</span> 22 invoices pending
            </div>
          </div>
          {/* Box 2 */}
          <div className="bg-white p-5 rounded-2xl" style={{ border: `1px solid ${BORDER}` }}>
            <div className="text-xs font-bold text-slate-400 mb-3 flex items-center gap-1.5 uppercase tracking-wider">
              <span>✓</span> RECOVERED
            </div>
            <div className="text-[28px] font-extrabold text-emerald-600 mb-2 leading-none">₹3,00,000</div>
            <div className="text-xs font-semibold text-slate-500 flex items-center gap-1">
              <span className="text-emerald-600">▲</span> This cycle
            </div>
          </div>
          {/* Box 3 */}
          <div className="bg-white p-5 rounded-2xl" style={{ border: `1px solid ${BORDER}` }}>
            <div className="text-xs font-bold text-slate-400 mb-3 flex items-center gap-1.5 uppercase tracking-wider">
              <span className="text-slate-400">⚖️</span> LEGAL QUEUE
            </div>
            <div className="text-[28px] font-extrabold text-red-500 mb-2 leading-none">12</div>
            <div className="text-xs font-semibold text-slate-500 flex items-center gap-1">
              Invoices 45d+ overdue
            </div>
          </div>
          {/* Box 4 */}
          <div className="bg-white p-5 rounded-2xl" style={{ border: `1px solid ${BORDER}` }}>
            <div className="text-xs font-bold text-slate-400 mb-3 flex items-center gap-1.5 uppercase tracking-wider">
              % RECOVERY RATE
            </div>
            <div className="text-[28px] font-extrabold text-slate-800 mb-4 leading-none">12%</div>
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
              <div className="bg-emerald-400 h-full rounded-full" style={{ width: '12%' }}></div>
            </div>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-[5fr_3fr] gap-6 mb-6">
          {/* Chart 1: Bar Chart */}
          <div className="bg-white p-6 rounded-2xl" style={{ border: `1px solid ${BORDER}` }}>
            <h2 className="font-bold text-slate-800 mb-1">Outstanding vs Recovered</h2>
            <p className="text-xs font-medium text-slate-500 mb-8">Monthly ₹ value breakdown</p>
            
            <div className="flex items-center justify-center gap-6 mb-8 text-xs font-semibold text-slate-500">
              <div className="flex items-center gap-2"><div className="w-3 h-3 border-2 border-amber-500 rounded-sm"></div> Outstanding</div>
              <div className="flex items-center gap-2"><div className="w-3 h-3 border-2 border-emerald-500 bg-emerald-200 rounded-sm"></div> Recovered</div>
            </div>

            {/* Fake Chart Area */}
            <div className="relative h-56 flex">
              {/* Y Axis text */}
              <div className="flex flex-col justify-between h-full text-[10px] text-slate-400 font-medium pr-4 text-right transform translate-y-2">
                <span>₹2,00,000</span>
                <span>₹1,60,000</span>
                <span>₹1,20,000</span>
                <span>₹80,000</span>
                <span>₹40,000</span>
                <span>₹0</span>
              </div>
              {/* Grid lines */}
              <div className="flex-1 relative border-b border-slate-200">
                 {/* render 5 lines */}
                 {[0,1,2,3,4].map(i => (
                    <div key={i} className="absolute w-full border-t border-slate-100" style={{ top: `${i * 20}%`}}></div>
                 ))}
                 
                 {/* Fake Bars */}
                 <div className="absolute inset-0 flex items-end justify-around px-8">
                    {/* Oct */}
                    <div className="w-16 flex items-end justify-center h-full pb-0 relative z-10">
                    </div>
                    {/* Nov */}
                    <div className="w-16 flex items-end justify-center gap-1 h-full pb-0 relative z-10">
                        <div className="w-9 h-[10%] bg-orange-100 border-2 border-amber-500 rounded-t-sm"></div>
                    </div>
                    {/* Dec */}
                    <div className="w-16 flex items-end justify-center gap-1 h-full pb-0 relative z-10">
                        <div className="w-9 h-[40%] bg-orange-100 border-2 border-amber-500 rounded-t-sm"></div>
                        <div className="w-9 h-[30%] bg-emerald-200 border-2 border-emerald-600 rounded-t-sm"></div>
                    </div>
                    {/* Jan */}
                    <div className="w-16 flex items-end justify-center gap-1 h-full pb-0 relative z-10">
                        <div className="w-9 h-[20%] bg-orange-100 border-2 border-amber-500 rounded-t-sm"></div>
                    </div>
                    {/* Feb */}
                    <div className="w-16 flex items-end justify-center gap-1 h-full pb-0 relative z-10">
                        <div className="w-9 h-[25%] bg-orange-100 border-2 border-amber-500 rounded-t-sm"></div>
                        <div className="w-9 h-[85%] bg-emerald-200 border-2 border-emerald-600 rounded-t-sm"></div>
                    </div>
                    {/* Mar */}
                    <div className="w-16 flex items-end justify-center gap-1 h-full pb-0 relative z-10">
                        <div className="w-9 h-[15%] bg-orange-100 border-2 border-amber-500 rounded-t-sm"></div>
                    </div>
                 </div>
              </div>
            </div>
            {/* X Axis */}
            <div className="flex ml-[4.5rem] px-8 mt-3">
              {['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'].map((m, i) => (
                 <div key={m} className={`flex-1 text-center text-[11px] font-medium text-slate-400 ${i === 0 ? '-ml-2' : ''}`}>{m}</div>
              ))}
            </div>
          </div>

          {/* Chart 2: Donut Chart */}
          <div className="bg-white p-6 rounded-2xl flex flex-col" style={{ border: `1px solid ${BORDER}` }}>
            <h2 className="font-bold text-slate-800 mb-1">Pipeline by Stage</h2>
            <p className="text-xs font-medium text-slate-500 mb-8">Current outstanding distribution</p>
            
            <div className="flex-1 flex items-center justify-center relative min-h-[220px]">
               {/* Pure CSS Donut Background */}
               <div className="w-[200px] h-[200px] rounded-full border-[20px] border-slate-50 relative"></div>
               
               {/* Overlaid Rings to match style EXACTLY */}
               <svg className="absolute w-[200px] h-[200px] -rotate-90 pointer-events-none">
                 {/* Circle circumference = 2 * pi * 80 = 502.6 */}
                 {/* Blue: 10%. Dasharray: 50.2, gaps: 502.6. Offset: 0 */}
                 <circle cx="100" cy="100" r="80" fill="transparent" stroke="#93C5FD" strokeWidth="20" strokeDasharray="50.2 502.6" strokeDashoffset="0"></circle>
                 {/* Yellow: 15%. Dasharray: 75.4. Length up to here: 25% (125.6). Offset: -50.2 */}
                 <circle cx="100" cy="100" r="80" fill="transparent" stroke="#FCD34D" strokeWidth="20" strokeDasharray="75.4 502.6" strokeDashoffset="-50.2"></circle>
                 {/* Orange: 35%. Dasharray: 175.9. Length up to here: 60% (301.5). Offset: -125.6 */}
                 <circle cx="100" cy="100" r="80" fill="transparent" stroke="#F59E0B" strokeWidth="20" strokeDasharray="175.9 502.6" strokeDashoffset="-125.6"></circle>
                 {/* Pink: 40%. Dasharray: 201. Length up to here: 100% (502.6). Offset: -301.5 */}
                 <circle cx="100" cy="100" r="80" fill="transparent" stroke="#FECDD3" strokeWidth="20" strokeDasharray="201 502.6" strokeDashoffset="-301.5"></circle>
               </svg>
            </div>

            <div className="flex items-center justify-center gap-4 mt-8 text-[11px] font-semibold text-slate-500">
               <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-[#93C5FD] rounded-sm"></div> 1st Reminder</div>
               <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-[#FCD34D] rounded-sm"></div> Follow-up</div>
               <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-[#F59E0B] rounded-sm"></div> Final Notice</div>
               <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-[#FECDD3] rounded-sm"></div> Legal Ready</div>
            </div>
          </div>
        </div>

        {/* Bottom Lists Grid */}
        <div className="grid grid-cols-[2fr_2fr] gap-6 min-h-0 pb-8">
          
          {/* Top Debtors */}
          <div className="bg-white rounded-2xl flex flex-col" style={{ border: `1px solid ${BORDER}` }}>
            <div className="p-6 pb-4 flex items-center justify-between border-b border-slate-100">
               <h2 className="font-bold text-slate-800">Top Debtors</h2>
               <span className="px-3 py-1 bg-rose-100 text-rose-500 rounded-full text-[11px] font-bold">12 legal ready</span>
            </div>
            <div className="flex-1 w-full max-h-[360px] overflow-y-auto">
               {/* Item 1 */}
               <div className="flex flex-row items-center justify-between p-5 border-b border-slate-100">
                 <div className="flex items-center gap-4">
                   <div className="w-11 h-11 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-[13px] shrink-0">BC</div>
                   <div>
                     <p className="font-bold text-[14px] text-slate-800 leading-tight">BuildRight Constructions</p>
                     <p className="text-[12px] text-slate-500 font-medium mt-0.5">INV-2025-112 · Noida</p>
                   </div>
                 </div>
                 <div className="text-right">
                   <p className="font-bold text-[15px] text-slate-800 leading-tight">₹4,50,000</p>
                   <p className="text-[10px] font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded inline-block mt-1">191d overdue</p>
                 </div>
               </div>
               {/* Item 2 */}
               <div className="flex flex-row items-center justify-between p-5 border-b border-slate-100">
                 <div className="flex items-center gap-4">
                   <div className="w-11 h-11 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-[13px] shrink-0">PM</div>
                   <div>
                     <p className="font-bold text-[14px] text-slate-800 leading-tight">Pinnacle Manufacturing</p>
                     <p className="text-[12px] text-slate-500 font-medium mt-0.5">INV-2025-055 · Chennai</p>
                   </div>
                 </div>
                 <div className="text-right">
                   <p className="font-bold text-[15px] text-slate-800 leading-tight">₹3,20,000</p>
                   <p className="text-[10px] font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded inline-block mt-1">145d overdue</p>
                 </div>
               </div>
               {/* Item 3 */}
               <div className="flex flex-row items-center justify-between p-5 border-b border-slate-100">
                 <div className="flex items-center gap-4">
                   <div className="w-11 h-11 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-[13px] shrink-0">IS</div>
                   <div>
                     <p className="font-bold text-[14px] text-slate-800 leading-tight">Indore Steel Solutions</p>
                     <p className="text-[12px] text-slate-500 font-medium mt-0.5">INV-2024-098 · Indore</p>
                   </div>
                 </div>
                 <div className="text-right">
                   <p className="font-bold text-[15px] text-slate-800 leading-tight">₹2,45,000</p>
                   <p className="text-[10px] font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded inline-block mt-1">190d overdue</p>
                 </div>
               </div>
               {/* Item 4 */}
               <div className="flex flex-row items-center justify-between p-5">
                 <div className="flex items-center gap-4">
                   <div className="w-11 h-11 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-[13px] shrink-0">GE</div>
                   <div>
                     <p className="font-bold text-[14px] text-slate-800 leading-tight">Global Exports Ltd</p>
                     <p className="text-[12px] text-slate-500 font-medium mt-0.5">INV-2025-090 · Ahmedabad</p>
                   </div>
                 </div>
                 <div className="text-right">
                   <p className="font-bold text-[15px] text-slate-800 leading-tight">₹2,15,000</p>
                   <p className="text-[10px] font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded inline-block mt-1">120d overdue</p>
                 </div>
               </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-white rounded-2xl flex flex-col" style={{ border: `1px solid ${BORDER}` }}>
            <div className="p-6 pb-4 border-b border-slate-100">
               <h2 className="font-bold text-slate-800">Recent Activity</h2>
            </div>
            <div className="flex-1 w-full max-h-[360px] overflow-y-auto">
               <div className="flex items-start gap-4 p-5 border-b border-slate-100">
                  <div className="w-9 h-9 rounded-full bg-rose-50 flex items-center justify-center shrink-0 mt-0.5">
                     <Scale size={16} className="text-rose-500" />
                  </div>
                  <div>
                    <p className="text-[13px] text-slate-800 leading-relaxed"><span className="font-bold">Legal notice generated</span> for Navi Mumbai Exports (₹1,20,000)</p>
                    <p className="text-[11px] text-slate-400 mt-1">2 hours ago</p>
                  </div>
               </div>
               <div className="flex items-start gap-4 p-5 border-b border-slate-100">
                  <div className="w-9 h-9 rounded-full bg-emerald-50 flex items-center justify-center shrink-0 mt-0.5">
                     <Check size={16} className="text-emerald-500" />
                  </div>
                  <div>
                    <p className="text-[13px] text-slate-800 leading-relaxed"><span className="font-bold">Invoice recovered</span> — Thane IT Solutions paid ₹67,000</p>
                    <p className="text-[11px] text-slate-400 mt-1">Yesterday, 3:42 PM</p>
                  </div>
               </div>
               <div className="flex items-start gap-4 p-5 border-b border-slate-100">
                  <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center shrink-0 mt-0.5">
                     <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-500"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                  </div>
                  <div>
                    <p className="text-[13px] text-slate-800 leading-relaxed"><span className="font-bold">WhatsApp reminder sent</span> to Sharma Traders for INV-2024-041</p>
                    <p className="text-[11px] text-slate-400 mt-1">Yesterday, 10:00 AM</p>
                  </div>
               </div>
               <div className="flex items-start gap-4 p-5 border-b border-slate-100">
                  <div className="w-9 h-9 rounded-full bg-blue-50 flex items-center justify-center shrink-0 mt-0.5">
                     <LayoutDashboard size={16} className="text-blue-500" />
                  </div>
                  <div>
                    <p className="text-[13px] text-slate-800 leading-relaxed"><span className="font-bold">New invoice added</span> — Bandra Café Co. ₹15,000 (INV-2025-044)</p>
                    <p className="text-[11px] text-slate-400 mt-1">2 days ago</p>
                  </div>
               </div>
               <div className="flex items-start gap-4 p-5">
                  <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center shrink-0 mt-0.5">
                     <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-500"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                  </div>
                  <div>
                    <p className="text-[13px] text-slate-800 leading-relaxed"><span className="font-bold">Email reminder sent</span> to Pune Digital Agency for INV-2025-018</p>
                    <p className="text-[11px] text-slate-400 mt-1">3 days ago</p>
                  </div>
               </div>
            </div>
          </div>
          
        </div>
      </main>
    </div>
  );
}
