c = open('d:/RecoveryAgent/static/css/app_v2.css', encoding='utf-8').read()

# The sidebar border-right has 2-space indent (after our indent stripping)
c = c.replace(
    '  border-right: 1px solid var(--border)\n.popover-stat:last-child',
    '  box-shadow: inset -1px 0 0 var(--border);\n.popover-stat:last-child'
)

# Verify
lines = [l for l in c.split('\n') if 'border-right' in l or 'box-shadow: inset' in l]
print('\n'.join(lines[:10]))

open('d:/RecoveryAgent/static/css/app_v2.css', 'w', encoding='utf-8', newline='\n').write(c)
print('Done')
