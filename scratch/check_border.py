c = open('d:/RecoveryAgent/static/css/app_v2.css', encoding='utf-8').read()
lines = [l for l in c.split('\n') if 'border-right' in l]
print('\n'.join(lines[:10]))
