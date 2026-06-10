"""
Fix two Vercel vs localhost visual differences:
1. "Zoomed in" on Vercel - caused by no html{font-size} rule, Tailwind CDN sets 16px
2. Vertical line after sidebar - sidebar border-right is too visually prominent

Also strips the unnecessary 4-space indentation from the CSS file (was copy-pasted 
from inside a <style> tag) so it's clean standalone CSS.
"""

with open('d:/RecoveryAgent/static/css/app_v2.css', 'r', encoding='utf-8') as f:
    content = f.read()

# Normalize line endings
content = content.replace('\r\n', '\n')

# ── 1. Strip the 4-space indentation that exists throughout the file ──────────
# Every rule was indented 4 spaces from being inside a <style> tag
lines = content.split('\n')
cleaned = []
for line in lines:
    if line.startswith('    '):
        cleaned.append(line[4:])
    else:
        cleaned.append(line)
content = '\n'.join(cleaned)

# ── 2. Add html font-size fix at the very top (before * {}) ──────────────────
html_fix = """/* ── BASE RESET — prevents Tailwind CDN from zooming the page ── */
html {
  font-size: 14px;
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
}

"""
content = html_fix + content

# ── 3. Fix sidebar border-right → use box-shadow (invisible as a hard line) ──
content = content.replace(
    '  border-right: 1px solid var(--border);',
    '  box-shadow: inset -1px 0 0 var(--border);'
)

print('border-right fixed:', 'border-right: 1px solid var(--border)' not in content)
print('html font-size added:', 'html {' in content)

with open('d:/RecoveryAgent/static/css/app_v2.css', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print(f'Done. File size: {len(content)} bytes')
