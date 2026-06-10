/* ─── White-Label Branding Settings Component ─── */
function WhiteLabel({ settings, setSettings }) {
  const [logoPreview, setLogoPreview] = React.useState(
    localStorage.getItem('recoverai_logo') || null
  );
  const [primaryColor, setPrimaryColor] = React.useState(
    localStorage.getItem('recoverai_brand_color') || '#0EA5E9'
  );
  const [brandName, setBrandName] = React.useState(
    localStorage.getItem('recoverai_brand_name') || 'RecoverAI'
  );
  const [tagline, setTagline] = React.useState(
    localStorage.getItem('recoverai_brand_tagline') || 'MSME Invoice Recovery'
  );
  const [saved, setSaved] = React.useState(false);
  const fileRef = React.useRef();

  function handleLogoUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      const dataUrl = ev.target.result;
      setLogoPreview(dataUrl);
      localStorage.setItem('recoverai_logo', dataUrl);
    };
    reader.readAsDataURL(file);
  }

  function handleSave() {
    localStorage.setItem('recoverai_brand_color', primaryColor);
    localStorage.setItem('recoverai_brand_name', brandName);
    localStorage.setItem('recoverai_brand_tagline', tagline);
    // Apply CSS variable instantly
    document.documentElement.style.setProperty('--amber', primaryColor);
    document.documentElement.style.setProperty('--amber-dark', primaryColor);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  function handleReset() {
    localStorage.removeItem('recoverai_logo');
    localStorage.removeItem('recoverai_brand_color');
    localStorage.removeItem('recoverai_brand_name');
    localStorage.removeItem('recoverai_brand_tagline');
    setLogoPreview(null);
    setPrimaryColor('#0EA5E9');
    setBrandName('RecoverAI');
    setTagline('MSME Invoice Recovery');
    document.documentElement.style.removeProperty('--amber');
    document.documentElement.style.removeProperty('--amber-dark');
  }

  const colorPresets = [
    { color: '#0EA5E9', name: 'Sky Blue' },
    { color: '#8B5CF6', name: 'Purple' },
    { color: '#10B981', name: 'Emerald' },
    { color: '#F59E0B', name: 'Amber' },
    { color: '#EF4444', name: 'Red' },
    { color: '#EC4899', name: 'Pink' },
    { color: '#06B6D4', name: 'Cyan' },
    { color: '#6366F1', name: 'Indigo' },
  ];

  return (
    <div className="content">
      <div className="topbar">
        <div>
          <div className="page-title">🎨 White-Label Branding</div>
          <div className="page-sub">Customise the platform with your own logo, name, and brand colors</div>
        </div>
        <div className="topbar-actions">
          {saved && (
            <span style={{
              display:'flex',alignItems:'center',gap:6,fontSize:12,fontWeight:700,
              padding:'6px 14px',borderRadius:20,background:'var(--green-bg)',color:'var(--green)',
              border:'1px solid var(--green)',animation:'fade-in 0.3s ease'
            }}>✓ Saved & Applied!</span>
          )}
          <button className="btn" onClick={handleReset}>↺ Reset to Default</button>
          <button className="btn btn-primary" onClick={handleSave}>💾 Save Branding</button>
        </div>
      </div>

      <div style={{display:'flex',flexWrap:'wrap',gap:20,marginTop:4}}>
        {/* FORM */}
        <div style={{display:'flex',flexDirection:'column',gap:16,flex:'1 1 400px'}}>

          {/* Logo Upload */}
          <div className="card" style={{padding:24}}>
            <div style={{fontSize:15,fontWeight:800,color:'var(--text)',marginBottom:4}}>Company Logo</div>
            <div style={{fontSize:13,color:'var(--text2)',marginBottom:20}}>Uploaded logo appears in the sidebar, legal notices, and PDF reports.</div>
            <div style={{display:'flex',alignItems:'center',gap:20,flexWrap:'wrap'}}>
              <div style={{
                width:100,height:100,borderRadius:16,border:'2px dashed var(--border)',
                background:'var(--surface2)',display:'flex',alignItems:'center',justifyContent:'center',
                overflow:'hidden',cursor:'pointer',flexShrink:0,
              }} onClick={()=>fileRef.current?.click()}>
                {logoPreview
                  ? <img src={logoPreview} alt="Logo" style={{width:'100%',height:'100%',objectFit:'contain',padding:8}} />
                  : <div style={{textAlign:'center',color:'var(--text3)'}}>
                      <div style={{fontSize:28,marginBottom:6}}>🖼️</div>
                      <div style={{fontSize:11,fontWeight:600}}>Upload Logo</div>
                    </div>
                }
              </div>
              <div>
                <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp" style={{display:'none'}} onChange={handleLogoUpload} />
                <button className="btn" onClick={()=>fileRef.current?.click()} style={{marginBottom:8,display:'flex',alignItems:'center',gap:6}}>
                  📤 Upload Logo
                </button>
                <div style={{fontSize:11,color:'var(--text3)',lineHeight:1.7}}>
                  PNG, JPG, SVG, WebP<br/>Recommended: 200×200px · Max 2MB
                </div>
                {logoPreview && (
                  <button onClick={()=>{setLogoPreview(null);localStorage.removeItem('recoverai_logo');}} style={{
                    background:'none',border:'none',color:'var(--red)',cursor:'pointer',
                    fontSize:11,fontWeight:600,marginTop:6,padding:0,
                  }}>✕ Remove Logo</button>
                )}
              </div>
            </div>
          </div>

          {/* Brand Name & Tagline */}
          <div className="card" style={{padding:24}}>
            <div style={{fontSize:15,fontWeight:800,color:'var(--text)',marginBottom:16}}>Brand Identity</div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))',gap:14}}>
              <div>
                <label style={{fontSize:11,fontWeight:700,color:'var(--text3)',display:'block',marginBottom:6,textTransform:'uppercase',letterSpacing:1}}>Platform Name</label>
                <input value={brandName} onChange={e=>setBrandName(e.target.value)} className="form-input" style={{width:'100%'}} placeholder="RecoverAI" maxLength={30} />
                <div style={{fontSize:10,color:'var(--text3)',marginTop:4}}>Shows in sidebar & browser tab</div>
              </div>
              <div>
                <label style={{fontSize:11,fontWeight:700,color:'var(--text3)',display:'block',marginBottom:6,textTransform:'uppercase',letterSpacing:1}}>Tagline</label>
                <input value={tagline} onChange={e=>setTagline(e.target.value)} className="form-input" style={{width:'100%'}} placeholder="MSME Invoice Recovery" maxLength={50} />
                <div style={{fontSize:10,color:'var(--text3)',marginTop:4}}>Shown below the platform name</div>
              </div>
            </div>
          </div>

          {/* Primary Color */}
          <div className="card" style={{padding:24}}>
            <div style={{fontSize:15,fontWeight:800,color:'var(--text)',marginBottom:4}}>Primary Brand Color</div>
            <div style={{fontSize:13,color:'var(--text2)',marginBottom:20}}>Applied to buttons, active nav items, badges, and accents across the entire platform.</div>
            <div style={{display:'flex',flexWrap:'wrap',gap:10,marginBottom:20}}>
              {colorPresets.map(({color,name})=>(
                <button key={color} onClick={()=>setPrimaryColor(color)} title={name} style={{
                  width:36,height:36,borderRadius:10,background:color,border:'none',cursor:'pointer',
                  outline: primaryColor===color ? `3px solid #fff` : '3px solid transparent',
                  outlineOffset:2,boxShadow: primaryColor===color ? `0 0 0 5px ${color}40` : 'none',
                  transition:'all 0.2s',
                }} />
              ))}
              <label style={{
                width:36,height:36,borderRadius:10,border:'2px dashed var(--border)',
                display:'flex',alignItems:'center',justifyContent:'center',
                cursor:'pointer',overflow:'hidden',position:'relative',
              }} title="Custom color">
                <input type="color" value={primaryColor} onChange={e=>setPrimaryColor(e.target.value)}
                  style={{position:'absolute',opacity:0,width:'100%',height:'100%',cursor:'pointer'}} />
                <span style={{fontSize:16}}>🎨</span>
              </label>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:12}}>
              <div style={{width:44,height:44,borderRadius:10,background:primaryColor,flexShrink:0}}></div>
              <div>
                <div style={{fontSize:13,fontWeight:700,color:'var(--text)'}}>Selected: {primaryColor.toUpperCase()}</div>
                <div style={{fontSize:11,color:'var(--text3)'}}>Changes apply instantly across the platform</div>
              </div>
            </div>
          </div>

          {/* Legal Notice Letterhead */}
          <div className="card" style={{padding:24}}>
            <div style={{fontSize:15,fontWeight:800,color:'var(--text)',marginBottom:4}}>Legal Notice Letterhead</div>
            <div style={{fontSize:13,color:'var(--text2)',marginBottom:16}}>
              Your logo and brand name will automatically appear on all generated MSMED Act legal notice PDFs.
            </div>
            <div style={{
              background:'var(--surface2)',border:'1px solid var(--border)',borderRadius:10,
              padding:'16px 20px',display:'flex',alignItems:'center',gap:14,
            }}>
              {logoPreview
                ? <img src={logoPreview} alt="Logo" style={{width:44,height:44,objectFit:'contain',borderRadius:6}} />
                : <div style={{width:44,height:44,borderRadius:6,background:primaryColor,display:'flex',alignItems:'center',justifyContent:'center',color:'#fff',fontWeight:900,fontSize:18}}>₹</div>
              }
              <div>
                <div style={{fontSize:15,fontWeight:900,color:'var(--text)'}}>{brandName}</div>
                <div style={{fontSize:11,color:'var(--text3)'}}>{tagline}</div>
              </div>
              <div style={{marginLeft:'auto',fontSize:11,color:'var(--text3)',textAlign:'right'}}>
                Legal Notice<br/>Under MSMED Act 2006
              </div>
            </div>
          </div>
        </div>

        {/* LIVE PREVIEW */}
        <div style={{position:'sticky',top:80,flex:'1 1 320px'}}>
          <div className="card" style={{padding:20}}>
            <div style={{fontSize:13,fontWeight:800,color:'var(--text)',marginBottom:14,textTransform:'uppercase',letterSpacing:1}}>🖥️ Live Sidebar Preview</div>
            <div style={{
              background:'var(--surface)',border:'1px solid var(--border)',borderRadius:12,
              overflow:'hidden',boxShadow:'var(--shadow-md)',
            }}>
              {/* Sidebar Brand */}
              <div style={{padding:'14px 16px',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',gap:10}}>
                <div style={{
                  width:30,height:30,borderRadius:7,background:primaryColor,
                  display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0,
                  overflow:'hidden',
                }}>
                  {logoPreview
                    ? <img src={logoPreview} alt="Logo" style={{width:'100%',height:'100%',objectFit:'contain'}} />
                    : <span style={{color:'#fff',fontWeight:900,fontSize:14}}>₹</span>
                  }
                </div>
                <div>
                  <div style={{fontSize:13,fontWeight:800,color:'var(--text)'}}>{brandName}</div>
                  <div style={{fontSize:9,color:'var(--text3)'}}>{tagline}</div>
                </div>
              </div>
              {/* Fake nav items */}
              {[['▦ Dashboard',true],['≡ Invoices',false],['💬 WhatsApp',false],['⚖ Legal Queue',false],['📊 Reports',false]].map(([label,active])=>(
                <div key={label} style={{
                  margin:'4px 8px',padding:'9px 10px',borderRadius:7,fontSize:12,fontWeight:500,
                  background: active ? primaryColor : 'transparent',
                  color: active ? '#fff' : 'var(--text2)',
                }}>{label}</div>
              ))}
              <div style={{padding:'12px 8px',borderTop:'1px solid var(--border)',margin:'6px 0 0'}}>
                <div style={{
                  display:'flex',alignItems:'center',gap:10,padding:'8px 10px',
                  borderRadius:8,background:'var(--surface2)',
                }}>
                  <div style={{width:30,height:30,borderRadius:'50%',background:primaryColor,display:'flex',alignItems:'center',justifyContent:'center',color:'#fff',fontSize:12,fontWeight:700}}>YB</div>
                  <div>
                    <div style={{fontSize:12,fontWeight:700,color:'var(--text)'}}>Your Business</div>
                    <div style={{fontSize:9,color:'var(--text3)'}}>admin@business.com</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
