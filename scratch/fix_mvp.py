import re

with open('d:/RecoveryAgent/RecoverAI_MVP.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Total Outstanding color
content = re.sub(r"color:'var\(--text\)'(.*?)fmtINR\(displayOutstanding\)\}\}\<\/div\>",
                 r"color:'var(--blue)'\g<1>fmtINR(displayOutstanding)}</div>", content)

# Replace Recovery Rate color
content = re.sub(r"color:'var\(--text\)'(.*?)displayRecoveryRate\}\%\<\/div\>",
                 r"color:'var(--purple)'\g<1>displayRecoveryRate}%</div>", content)

# Replace Center Text Plugin color
content = content.replace("ctx.fillStyle = darkMode ? '#94A3B8' : '#608098';",
                          "ctx.fillStyle = darkMode ? 'var(--text2)' : 'var(--text3)';")
content = content.replace("ctx.fillStyle = darkMode ? '#F1F5F9' : '#0A1428';",
                          "ctx.fillStyle = darkMode ? 'var(--text)' : 'var(--text)';")

# Replace Pie Chart Legend color
content = re.sub(r"legend: \{\s*position: window\.innerWidth < 640 \? 'bottom' : 'right',\s*labels: \{\s*font:",
                 "legend: { position: window.innerWidth < 640 ? 'bottom' : 'right', labels: { color: 'var(--text2)', font:", content)

with open('d:/RecoveryAgent/RecoverAI_MVP.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Replaced values in RecoverAI_MVP.html')
