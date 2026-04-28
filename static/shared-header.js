(function () {
  /* ── CSS ── */
  const style = document.createElement('style');
  style.textContent = `
    :root {
      --bg:#f2f2f7;--card:rgba(255,255,255,0.72);--text:#1d1d1f;--text-muted:#86868b;
      --border:rgba(0,0,0,0.1);--accent:#0071e3;--accent-hover:#0068d0;
      --easy:#34c759;--normal:#ff9f0a;--hard:#ff3b30;
      --radius:14px;--radius-sm:10px;--surface2:rgba(0,0,0,0.04);
    }
    body.dark {
      --bg:#1c1c1e;--card:rgba(44,44,46,0.8);--text:#f5f5f7;--text-muted:#98989d;
      --border:rgba(255,255,255,0.1);--surface2:rgba(255,255,255,0.06);
    }
    #app-header {
      background:rgba(255,255,255,0.72);
      backdrop-filter:blur(28px) saturate(200%);
      -webkit-backdrop-filter:blur(28px) saturate(200%);
      color:var(--text);padding:0 16px;height:56px;
      display:flex;align-items:center;justify-content:space-between;
      position:sticky;top:0;z-index:100;
      border-bottom:1px solid rgba(0,0,0,0.08);
      box-shadow:0 1px 0 rgba(0,0,0,0.06),0 4px 16px rgba(0,0,0,0.06);
    }
    body.dark #app-header {
      background:rgba(28,28,30,0.82);border-bottom-color:rgba(255,255,255,0.08);
      box-shadow:0 1px 0 rgba(255,255,255,0.05);
    }
    #header-left{display:flex;align-items:center;gap:4px;flex-shrink:0;}
    #header-title{
      position:absolute;left:50%;transform:translateX(-50%);
      font-size:1rem;font-weight:700;letter-spacing:-0.01em;
      white-space:nowrap;max-width:calc(100% - 200px);text-align:center;color:var(--text);
    }
    #header-right{display:flex;align-items:center;gap:8px;flex-shrink:0;}
    #drawer-toggle{
      background:rgba(0,0,0,0.06);color:var(--text);border:none;
      border-radius:980px;padding:6px 11px;font-size:1.1rem;line-height:1;cursor:pointer;
    }
    body.dark #drawer-toggle{background:rgba(255,255,255,0.1);}
    #sh-buy-btn{
      background:var(--accent);color:#fff;border:none;border-radius:980px;
      padding:6px 14px;font-size:0.82rem;font-weight:600;white-space:nowrap;
      cursor:pointer;box-shadow:0 2px 8px rgba(0,113,227,0.3);text-decoration:none;
    }
    #sh-buy-btn:hover{background:var(--accent-hover);}
    /* Drawer */
    #drawer-overlay{
      position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:200;
      opacity:0;pointer-events:none;transition:opacity 0.25s;
    }
    #drawer-overlay.open{opacity:1;pointer-events:all;}
    #drawer{
      position:fixed;top:0;left:0;height:100%;width:270px;
      background:rgba(242,242,247,0.88);backdrop-filter:blur(32px) saturate(200%);
      -webkit-backdrop-filter:blur(32px) saturate(200%);z-index:201;
      border-right:1px solid rgba(0,0,0,0.08);
      transform:translateX(-100%);transition:transform 0.3s cubic-bezier(.4,0,.2,1);
      display:flex;flex-direction:column;overflow:hidden;
      box-shadow:4px 0 40px rgba(0,0,0,0.12);
    }
    body.dark #drawer{background:rgba(28,28,30,0.9);border-right-color:rgba(255,255,255,0.08);}
    #drawer.open{transform:translateX(0);}
    #drawer-head{
      background:transparent;color:var(--text);padding:0 16px;height:56px;
      display:flex;align-items:center;justify-content:space-between;flex-shrink:0;
      border-bottom:1px solid var(--border);
    }
    #drawer-head span{font-size:1rem;font-weight:700;}
    #drawer-close{
      background:rgba(0,0,0,0.06);border:none;color:var(--text-muted);
      border-radius:980px;padding:4px 10px;font-size:1rem;cursor:pointer;
    }
    body.dark #drawer-close{background:rgba(255,255,255,0.1);}
    #drawer-nav{flex:1;padding:8px 10px;overflow-y:auto;}
    .drawer-nav-item{
      display:flex;align-items:center;gap:12px;width:100%;background:none;border:none;
      text-align:left;padding:11px 12px;font-size:0.9rem;color:var(--text);
      cursor:pointer;transition:background 0.15s;border-radius:10px;
      margin-bottom:2px;text-decoration:none;
    }
    .drawer-nav-item:hover{background:rgba(0,0,0,0.05);}
    body.dark .drawer-nav-item:hover{background:rgba(255,255,255,0.06);}
    .drawer-nav-item.active{color:var(--accent);font-weight:600;background:rgba(0,113,227,0.1);}
    body.dark .drawer-nav-item.active{background:rgba(0,113,227,0.18);}
    .drawer-divider{height:1px;background:var(--border);margin:6px 12px;}
    #drawer-footer{
      padding:12px;border-top:1px solid var(--border);flex-shrink:0;
      display:flex;flex-direction:column;gap:2px;
    }
    #drawer-footer .drawer-footer-btn{
      display:flex;align-items:center;justify-content:center;gap:6px;
      background:var(--surface2);border:1px solid var(--border);color:var(--text-muted);
      font-size:0.82rem;cursor:pointer;padding:8px 10px;text-align:center;width:100%;
      border-radius:980px;transition:background 0.15s,color 0.15s;font-family:inherit;
    }
    #drawer-footer .drawer-footer-btn:hover{color:var(--text);}
    #sh-lang-wrap{display:flex;flex-direction:column;gap:4px;padding:8px 10px;}
    #sh-lang-wrap label{font-size:0.78rem;color:var(--text-muted);}
    #sh-lang-wrap select{
      width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;
      font-size:0.85rem;font-family:inherit;color:var(--text);
      background:var(--card);outline:none;cursor:pointer;
    }
    #sh-font-wrap{padding:8px 10px;}
    #sh-font-wrap label{font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:6px;}
    #sh-font-row{display:flex;align-items:center;gap:8px;}
    #sh-font-row button{
      background:var(--surface2);color:var(--text);width:30px;height:30px;
      padding:0;font-size:1rem;border-radius:6px;border:1px solid var(--border);cursor:pointer;font-family:inherit;
    }
    #sh-font-label{font-size:0.8rem;color:var(--text-muted);flex:1;text-align:center;}
  `;
  document.head.appendChild(style);

  /* ── Detect current page ── */
  const cur = location.pathname;
  function isActive(href) {
    if (href === '/') return cur === '/';
    return cur.startsWith(href);
  }
  function navItem(href, label) {
    const el = document.createElement('a');
    el.className = 'drawer-nav-item' + (isActive(href) ? ' active' : '');
    el.href = href;
    el.textContent = label;
    return el;
  }
  function tabItem(tab, label) {
    const el = document.createElement('a');
    el.className = 'drawer-nav-item';
    el.href = '/?tab=' + tab;
    el.textContent = label;
    return el;
  }
  function divider() {
    const d = document.createElement('div'); d.className = 'drawer-divider'; return d;
  }

  /* ── Header HTML ── */
  const pageTitle = document.title.split('—')[0].trim() || '智能閹雞模型';
  const header = document.createElement('header');
  header.id = 'app-header';
  header.innerHTML = `
    <div id="header-left">
      <button id="drawer-toggle" onclick="shOpenDrawer()" title="選單">☰</button>
    </div>
    <div id="header-title">${pageTitle}</div>
    <div id="header-right">
      <a id="sh-buy-btn" href="/buy">購買模擬器</a>
    </div>
  `;

  /* ── Drawer HTML ── */
  const overlay = document.createElement('div');
  overlay.id = 'drawer-overlay';
  overlay.onclick = () => shCloseDrawer();

  const drawer = document.createElement('div');
  drawer.id = 'drawer';
  drawer.innerHTML = `
    <div id="drawer-head">
      <span>選單</span>
      <button id="drawer-close" onclick="shCloseDrawer()">✕</button>
    </div>
  `;

  const nav = document.createElement('nav');
  nav.id = 'drawer-nav';
  nav.appendChild(navItem('/', '首頁'));
  nav.appendChild(divider());
  nav.appendChild(tabItem('rankings', '排名'));
  nav.appendChild(tabItem('stats', '統計'));
  nav.appendChild(tabItem('simulator', '線上模擬器'));
  nav.appendChild(tabItem('rules', '系統介紹'));
  nav.appendChild(tabItem('manual', '操作說明書'));
  nav.appendChild(divider());
  nav.appendChild(navItem('/about', '關於我們'));
  nav.appendChild(navItem('/faq', '常見問題'));
  nav.appendChild(navItem('/support', '支援服務'));
  nav.appendChild(navItem('/buy', '購買模擬器'));
  nav.appendChild(divider());
  drawer.appendChild(nav);

  /* ── Drawer footer ── */
  const footer = document.createElement('div');
  footer.id = 'drawer-footer';
  footer.innerHTML = `
    <div id="sh-lang-wrap">
      <label>語言 / Language</label>
      <select id="sh-lang-select">
        <option value="zh-tw">🇹🇼 繁體中文</option>
        <option value="en">🇺🇸 English</option>
        <option value="ja">🇯🇵 日本語</option>
        <option value="ko">🇰🇷 한국어</option>
      </select>
    </div>
    <div class="drawer-divider" style="margin:4px 0 0;"></div>
    <div id="sh-font-wrap">
      <label>字體大小</label>
      <div id="sh-font-row">
        <button onclick="shFontSize(-1)">A-</button>
        <span id="sh-font-label">標準</span>
        <button onclick="shFontSize(1)">A+</button>
      </div>
    </div>
    <div class="drawer-divider" style="margin:0;"></div>
    <div style="display:flex;gap:8px;padding:8px 0 4px;">
      <button class="drawer-footer-btn" onclick="shToggleDark()" id="sh-dark-btn" style="flex:1;">深色模式</button>
    </div>
  `;
  drawer.appendChild(footer);

  /* ── Mount ── */
  document.body.insertBefore(overlay, document.body.firstChild);
  document.body.insertBefore(drawer, document.body.firstChild);
  document.body.insertBefore(header, document.body.firstChild);

  /* ── Dark mode ── */
  const isDark = localStorage.getItem('darkMode') === '1';
  if (isDark) document.body.classList.add('dark');
  function shToggleDark() {
    document.body.classList.toggle('dark');
    localStorage.setItem('darkMode', document.body.classList.contains('dark') ? '1' : '0');
    const btn = document.getElementById('sh-dark-btn');
    if (btn) btn.textContent = document.body.classList.contains('dark') ? '淺色模式' : '深色模式';
  }
  window.shToggleDark = shToggleDark;
  const darkBtn = document.getElementById('sh-dark-btn');
  if (darkBtn && isDark) darkBtn.textContent = '淺色模式';

  /* ── Font size ── */
  const FONT_STEPS = [13, 14, 16, 18, 20];
  const FONT_LABELS = ['最小', '小', '標準', '大', '最大'];
  let fontIdx = parseInt(localStorage.getItem('shFontIdx') || '2');
  function applyFont() {
    document.documentElement.style.fontSize = FONT_STEPS[fontIdx] + 'px';
    const lbl = document.getElementById('sh-font-label');
    if (lbl) lbl.textContent = FONT_LABELS[fontIdx];
  }
  applyFont();
  window.shFontSize = function(d) {
    fontIdx = Math.max(0, Math.min(FONT_STEPS.length - 1, fontIdx + d));
    localStorage.setItem('shFontIdx', fontIdx);
    applyFont();
  };

  /* ── Open / Close ── */
  window.shOpenDrawer = function() {
    document.getElementById('drawer').classList.add('open');
    document.getElementById('drawer-overlay').classList.add('open');
  };
  window.shCloseDrawer = function() {
    document.getElementById('drawer').classList.remove('open');
    document.getElementById('drawer-overlay').classList.remove('open');
  };
})();
