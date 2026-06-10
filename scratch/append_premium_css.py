import os

css_to_add = """
/* -- PREMIUM HOVER ANIMATIONS -- */
.card, .metric-card, .sidebar-brand, .user-card, .timeline-content, .ai-setting-row, .topbar {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card:hover, .metric-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
  border-color: var(--amber-light);
}

[data-theme="dark"] .card:hover, [data-theme="dark"] .metric-card:hover {
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4);
}

/* -- THEME TOGGLE BUTTON FIXES -- */
.theme-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  background: var(--surface2); /* Uses themed surface */
  border: 1px solid var(--border);
  color: var(--text2);
  transition: all 0.2s;
  min-width: 44px;
}

.theme-toggle-btn:hover {
  background: var(--surface3);
  border-color: var(--amber);
  transform: scale(1.05);
}

/* -- TOGGLE SWITCHES -- */
.toggle, .dm-track { width: 36px; height: 20px; border-radius: 20px; background: var(--surface3); position: relative; cursor: pointer; transition: background 0.3s; flex-shrink: 0; }
.toggle.on, .dm-track.on { background: var(--amber); }
.toggle-thumb, .dm-thumb { width: 14px; height: 14px; border-radius: 50%; background: #fff; position: absolute; top: 3px; left: 3px; transition: transform 0.3s; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.toggle.on .toggle-thumb, .dm-track.on .dm-thumb { transform: translateX(16px); }
"""

with open(r"d:\RecoveryAgent\static\css\app.css", "a", encoding="utf-8") as f:
    f.write(css_to_add)

print("Premium CSS appended successfully.")
