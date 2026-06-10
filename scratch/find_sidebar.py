c = open('d:/RecoveryAgent/static/css/app_v2.css', encoding='utf-8').read()

# Print lines around sidebar block for context
idx = c.find('.sidebar {')
print(repr(c[idx:idx+300]))
