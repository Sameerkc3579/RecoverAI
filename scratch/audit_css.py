c = open('d:/RecoveryAgent/static/css/app_v2.css', encoding='utf-8').read()
print('html font-size present:', 'html {' in c[:200])
print('sidebar box-shadow present:', 'inset -1px 0 0' in c)
print('sidebar border-right present:', 'border-right: 1px solid var(--border)\n' in c)
# Remove any lingering sidebar border-right - could be duplicate from old block
# Find every occurrence
import re
matches = [(m.start(), c[max(0,m.start()-50):m.start()+100]) for m in re.finditer(r'border-right: 1px solid var\(--border\)', c)]
for pos, ctx in matches:
    print(f'\n--- pos {pos} ---')
    print(repr(ctx))
