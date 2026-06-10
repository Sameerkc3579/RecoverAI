content = open('d:/RecoveryAgent/static/css/app_v2.css', 'r', encoding='utf-8').read()

# Normalise to \n so replacements are reliable
content = content.replace('\r\n', '\n')

# ── 1. Add transition to .card base ──────────────────────────────────────────
old_card = "    .card {\n      background: var(--surface);\n      border-radius: var(--radius-lg);\n      border: 1px solid var(--border);\n      padding: 16px\n    }"
new_card = "    .card {\n      background: var(--surface);\n      border-radius: var(--radius-lg);\n      border: 1px solid var(--border);\n      padding: 16px;\n      transition: transform 0.25s cubic-bezier(0.4,0,0.2,1), box-shadow 0.25s cubic-bezier(0.4,0,0.2,1), border-color 0.25s ease;\n    }"
if old_card in content:
    content = content.replace(old_card, new_card, 1)
    print('Patched .card')
else:
    print('ERROR: .card block not found')

# ── 2. Add transition to .metric-card base ───────────────────────────────────
old_metric = "    .metric-card {\n      background: var(--surface);\n      border-radius: var(--radius-lg);\n      border: 1px solid var(--border);\n      padding: 16px 18px\n    }"
new_metric = "    .metric-card {\n      background: var(--surface);\n      border-radius: var(--radius-lg);\n      border: 1px solid var(--border);\n      padding: 16px 18px;\n      transition: transform 0.25s cubic-bezier(0.4,0,0.2,1), box-shadow 0.25s cubic-bezier(0.4,0,0.2,1), border-color 0.25s ease;\n    }"
if old_metric in content:
    content = content.replace(old_metric, new_metric, 1)
    print('Patched .metric-card')
else:
    print('ERROR: .metric-card block not found')

# ── 3. Remove any old/weak hover blocks previously appended ──────────────────
markers = ['/* -- PREMIUM HOVER ANIMATIONS -- */', '/* ══']
for marker in markers:
    idx = content.find(marker)
    while idx != -1:
        content = content[:idx]
        idx = content.find(marker)
print('Stripped old hover blocks')

# ── 4. Append definitive, high-specificity hover rules ───────────────────────
hover_css = '''
/* ══════════════════════════════════════════════════════════════════
   PREMIUM LIFT HOVER — ALL PAGES
   Covers every card / box variant used across Dashboard, Reports,
   Invoices, Settings, Customers, RecoveryHub, LegalQueue, etc.
   ══════════════════════════════════════════════════════════════════ */

/* Base transition already on .card and .metric-card above */

.card:hover,
.metric-card:hover,
.pricing-card:hover,
.portal-share-card:hover,
.ai-box:hover,
.info-box:hover,
.warn-box:hover,
.danger-box:hover {
  transform: translateY(-4px) !important;
  box-shadow: 0 10px 28px rgba(10, 20, 40, 0.10), 0 2px 8px rgba(10, 20, 40, 0.06) !important;
  border-color: var(--amber-light) !important;
}

[data-theme="dark"] .card:hover,
[data-theme="dark"] .metric-card:hover,
[data-theme="dark"] .pricing-card:hover,
[data-theme="dark"] .portal-share-card:hover,
[data-theme="dark"] .ai-box:hover,
[data-theme="dark"] .info-box:hover,
[data-theme="dark"] .warn-box:hover,
[data-theme="dark"] .danger-box:hover {
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.40), 0 2px 8px rgba(0, 0, 0, 0.20) !important;
  border-color: var(--amber) !important;
}

/* ── Theme Toggle Button (inline-styled in Dashboard_v2.js) ──────── */
/* Handled via React inline styles; no additional CSS needed */
'''

content = content.rstrip() + '\n' + hover_css

open('d:/RecoveryAgent/static/css/app_v2.css', 'w', encoding='utf-8', newline='\n').write(content)
print('Done — app_v2.css written with definitive hover rules.')

# Verify
check = open('d:/RecoveryAgent/static/css/app_v2.css', 'r', encoding='utf-8').read()
print('transition in .card:', 'transition' in check[check.find('.card {'):check.find('.card {')+400])
print('PREMIUM LIFT HOVER count:', check.count('PREMIUM LIFT HOVER'))
