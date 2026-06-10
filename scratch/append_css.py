import os

css_to_add = """
/* -- TOGGLE SWITCHES -- */
.toggle, .dm-track { width: 36px; height: 20px; border-radius: 20px; background: var(--surface3); position: relative; cursor: pointer; transition: background 0.3s; flex-shrink: 0; }
.toggle.on, .dm-track.on { background: var(--amber); }
.toggle-thumb, .dm-thumb { width: 14px; height: 14px; border-radius: 50%; background: #fff; position: absolute; top: 3px; left: 3px; transition: transform 0.3s; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.toggle.on .toggle-thumb, .dm-track.on .dm-thumb { transform: translateX(16px); }

/* Sidebar theme toggle */
.theme-toggle-btn { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-radius: var(--radius); cursor: pointer; color: var(--text2); background: transparent; border: 1px solid transparent; width: 100%; transition: all 0.2s; font-size: 12px; font-weight: 600; font-family: 'Plus Jakarta Sans', sans-serif; margin-bottom: 8px; }
.theme-toggle-btn:hover { background: var(--surface2); color: var(--text); }
"""

with open(r"d:\RecoveryAgent\static\css\app.css", "a", encoding="utf-8") as f:
    f.write(css_to_add)

print("CSS appended successfully.")
