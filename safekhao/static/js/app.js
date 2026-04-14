// SafeKhao Frontend — talks to Python/Flask backend
const API = '';  // same origin
let allProducts = [], consumed = [], recentScans = [], activeCat = 'All';
let camStream = null, scanInterval = null, scanDone = false;
let imageBase64 = null;

// ── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  setDbStatus('loading');
  try {
    const res = await fetch(`${API}/api/products`);
    allProducts = await res.json();
    setDbStatus('ok', `${allProducts.length} products`);
    renderBrowse(); buildCatChips(); populateCompare();
    await refreshDBStats();
    toast(`Database ready — ${allProducts.length} products loaded`);
  } catch (e) {
    setDbStatus('err', 'Server offline');
    toast('Cannot connect to server. Is server.py running?', 'err');
  }
}

function setDbStatus(state, text) {
  const dots = document.querySelectorAll('.db-dot');
  const texts = [document.getElementById('db-pill-text'), document.getElementById('db-pill-mobile-text')];
  dots.forEach(d => { d.className = 'db-dot'; if (state === 'ok') d.classList.add('on'); if (state === 'err') d.classList.add('err'); });
  const msg = state === 'loading' ? 'Connecting...' : state === 'err' ? 'Server offline' : `Local DB · ${text}`;
  texts.forEach(t => { if (t) t.textContent = msg; });
}

// ── TABS ──────────────────────────────────────────────────────────────────────
function goTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn, .bnav').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll(`[data-tab="${name}"]`).forEach(b => b.classList.add('active'));
  if (name === 'database') refreshDBStats();
  if (name === 'browse') renderBrowse();
}

// ── RISK HELPERS ──────────────────────────────────────────────────────────────
function rC(r) {
  const m = { ok: { bg: '#EEF9F4', txt: '#166534', bar: '#16A571', rp: 'rp-ok' },
              low: { bg: '#EFF6FF', txt: '#1E40AF', bar: '#3B82F6', rp: 'rp-low' },
              medium: { bg: '#FFFBEB', txt: '#92400E', bar: '#F59E0B', rp: 'rp-medium' },
              high: { bg: '#FEF0EF', txt: '#991B1B', bar: '#E8453C', rp: 'rp-high' } };
  return m[r] || m.medium;
}
function rL(r) { return { ok: 'Safe', low: 'Low risk', medium: 'Moderate', high: 'High risk' }[r] || r; }
function ipClass(r) { return { ok: 'ip-ok', low: 'ip-low', medium: 'ip-medium', high: 'ip-high' }[r] || 'ip-medium'; }

// ── PRODUCT CARD ──────────────────────────────────────────────────────────────
function productImg(p) {
  if (p.image_url) return `<img src="${p.image_url}" alt="${p.name}" class="pcard-img" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="pcard-icon-fallback" style="display:none;background:${rC(p.risk).bg}"><span style="font-size:22px">${p.icon||'📦'}</span></div>`;
  return `<div class="pcard-icon" style="background:${rC(p.risk).bg}"><span style="font-size:22px">${p.icon||'📦'}</span></div>`;
}

function makeCard(p) {
  const c = rC(p.risk);
  const ings = p.ingredients || [];
  const hiTags = ings.filter(i => i.r === 'high').slice(0, 2)
    .map(i => `<span class="atag">${i.n.split('(')[0].trim()}</span>`).join('');
  const aiTag = p.ai_generated ? `<span class="atag atag-ai">AI</span>` : '';
  return `<div class="pcard" onclick="openDetail('${p.barcode}')">
    <div class="pcard-row">
      ${productImg(p)}
      <div class="pcard-info">
        <div class="pcard-name">${p.name}</div>
        <div class="pcard-meta">${p.brand} · ${p.category || p.cat || ''}</div>
      </div>
      <div class="pcard-right">
        <div class="score-circle" style="--sc:${c.bar}"><span>${p.score}</span></div>
        <span class="rp ${c.rp}" style="font-size:10px;margin-top:3px">${rL(p.risk)}</span>
      </div>
    </div>
    <div class="score-bar"><div class="score-fill" style="width:${p.score}%;background:${c.bar}"></div></div>
    ${(hiTags || aiTag) ? `<div class="atags">${hiTags}${aiTag}</div>` : ''}
  </div>`;
}

// ── SCAN TAB ──────────────────────────────────────────────────────────────────
async function bcLookup(v, force) {
  const el = document.getElementById('scan-result');
  if (!v) { el.style.display = 'none'; return; }
  try {
    const res = await fetch(`${API}/api/products/${v.trim()}`);
    if (res.ok) {
      const p = await res.json();
      const c = rC(p.risk);
      el.style.display = 'block'; el.style.borderLeftColor = c.bar;
      el.innerHTML = `
        <div class="src-row">
          <div class="src-icon" style="background:${c.bg}"><span style="font-size:24px">${p.icon || '📦'}</span></div>
          <div style="flex:1">
            <div style="font-size:15px;font-weight:600;color:var(--c900)">${p.name}</div>
            <div style="font-size:12px;color:var(--c400)">${p.brand} · ${p.barcode}</div>
          </div>
          <span class="rp ${c.rp}">${rL(p.risk)}</span>
        </div>
        <button class="view-full-btn" onclick="openDetail('${p.barcode}')">View full analysis →</button>`;
      trackProduct(p);
    } else if (force) {
      el.style.display = 'block'; el.style.borderLeftColor = '#9CA3AF';
      el.innerHTML = `<div style="text-align:center;padding:12px 0">
        <div style="font-size:14px;font-weight:600;color:var(--c800);margin-bottom:6px">Barcode: ${v} — not found</div>
        <div style="font-size:12px;color:var(--c500);margin-bottom:12px">Use the AI Analyse tab to identify and save this product</div>
        <button class="btn-primary" onclick="prefillAI('${v}');goTab('ai')">Analyse with AI →</button>
      </div>`;
    }
  } catch (e) { if (force) toast('Server error — is Python server running?', 'err'); }
}

function prefillAI(barcode) {
  document.getElementById('ai-barcode').value = barcode;
}

function trackProduct(p) {
  consumed.push(p);
  if (!recentScans.find(x => x.barcode === p.barcode)) recentScans.unshift(p);
  if (recentScans.length > 8) recentScans = recentScans.slice(0, 8);
  renderRecent(); updateHealth();
  fetch(`${API}/api/scans`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ barcode: p.barcode, product_name: p.name }) }).catch(() => {});
}

function renderRecent() {
  const el = document.getElementById('recent-list');
  if (!recentScans.length) {
    el.innerHTML = `<div class="empty-msg"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg><p>Scan a product to start</p></div>`;
    return;
  }
  el.innerHTML = recentScans.map(p => makeCard(p)).join('');
}

// ── BROWSE TAB ────────────────────────────────────────────────────────────────
function buildCatChips() {
  const cats = ['All', ...new Set(allProducts.map(p => p.category || p.cat || 'Other'))].sort((a, b) => a === 'All' ? -1 : a.localeCompare(b));
  document.getElementById('cat-chips').innerHTML = cats.map(c =>
    `<button class="chip${activeCat === c ? ' on' : ''}" onclick="setCat('${c}')">${c}</button>`).join('');
}
function setCat(c) { activeCat = c; buildCatChips(); renderBrowse(); }

function renderBrowse() {
  const q = (document.getElementById('search-in')?.value || '').toLowerCase();
  const rf = document.getElementById('risk-filter')?.value || '';
  const filtered = allProducts.filter(p => {
    const cat = p.category || p.cat || '';
    return (!q || p.name.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q))
      && (activeCat === 'All' || cat === activeCat)
      && (!rf || p.risk === rf);
  });
  const grid = document.getElementById('browse-grid');
  grid.innerHTML = filtered.length
    ? filtered.map(p => makeCard(p)).join('')
    : `<div class="empty-msg" style="grid-column:1/-1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="m20 20-3-3"/></svg><p>No products match</p></div>`;
  const cnt = document.getElementById('browse-count');
  if (cnt) cnt.textContent = `${filtered.length} of ${allProducts.length} products`;
}

// ── DETAIL MODAL ──────────────────────────────────────────────────────────────
async function openDetail(barcode) {
  try {
    const [prodRes, altRes, imgRes] = await Promise.all([
      fetch(`${API}/api/products/${barcode}`),
      fetch(`${API}/api/products/${barcode}/alternatives`),
      fetch(`${API}/api/products/${barcode}/image`)
    ]);
    const p = await prodRes.json();
    const alts = altRes.ok ? await altRes.json() : [];
    const imgData = imgRes.ok ? await imgRes.json() : {};
    if (imgData.image_url) p.image_url = imgData.image_url;

    const c = rC(p.risk);
    const ings = (p.ingredients || []).map(i =>
      `<div class="ing-item">
        <div class="ing-name-w"><div class="ing-n">${i.n}</div>${i.note ? `<div class="ing-note">${i.note}</div>` : ''}</div>
        <span class="ing-p ${ipClass(i.r)}">${rL(i.r)}</span>
      </div>`).join('');
    const warns = (p.warnings || []).map(w =>
      `<div class="warn-item"><div class="warn-dot"></div><div class="warn-text">${w}</div></div>`).join('');
    const futureHtml = (p.future || []).length
      ? `<div class="future-box"><div class="future-box-title">⚠ Future health risks if consumed regularly</div>${p.future.map(f => `<div class="future-row">${f}</div>`).join('')}</div>` : '';

    // Score circle color
    const scoreColor = p.score <= 25 ? '#16A571' : p.score <= 50 ? '#F59E0B' : p.score <= 75 ? '#F97316' : '#E8453C';

    // Product image header
    const imgHtml = p.image_url
      ? `<img src="${p.image_url}" alt="${p.name}" class="detail-product-img" onerror="this.style.display='none'">`
      : `<div class="detail-icon-fallback" style="background:${c.bg}"><span style="font-size:40px">${p.icon||'📦'}</span></div>`;

    // Alternatives panel
    const altsHtml = alts.length ? `
      <div class="alts-section">
        <div class="alts-title">✓ Healthier alternatives</div>
        <div class="alts-grid">
          <div class="alt-current">
            <div class="alt-x">✕</div>
            ${p.image_url ? `<img src="${p.image_url}" class="alt-img" onerror="this.src=''">` : `<div class="alt-emoji">${p.icon||'📦'}</div>`}
            <div class="alt-name">${p.name.split(' ').slice(0,3).join(' ')}</div>
            <div class="alt-badge alt-bad">${rL(p.risk)}</div>
          </div>
          <div class="alt-arrow">→</div>
          ${alts.slice(0,2).map(a => {
            const ac = rC(a.risk);
            return `<div class="alt-item" onclick="closeDetail();openDetail('${a.barcode}')">
              <div class="alt-check">✓</div>
              ${a.image_url ? `<img src="${a.image_url}" class="alt-img" onerror="this.src=''">` : `<div class="alt-emoji">${a.icon||'📦'}</div>`}
              <div class="alt-name">${a.name.split(' ').slice(0,3).join(' ')}</div>
              <div class="alt-badge alt-good">${rL(a.risk)}</div>
            </div>`;
          }).join('')}
        </div>
      </div>` : '';

    document.getElementById('detail-body').innerHTML = `
      <div class="detail-img-wrap">
        ${imgHtml}
        <div class="detail-score-badge" style="background:${scoreColor}">
          <span class="dsb-num">${p.score}</span>
          <span class="dsb-label">/100</span>
        </div>
      </div>
      <div class="detail-info-row">
        <div>
          <div class="detail-name">${p.name}</div>
          <div class="detail-brand">${p.brand} · ${p.category || p.cat || ''}</div>
          ${p.ai_generated ? `<span class="ai-badge-small">✦ AI Analysed</span>` : ''}
        </div>
        <div class="detail-risk-pill rp ${c.rp}">${rL(p.risk)}</div>
      </div>
      ${warns ? `<div class="warn-list negatives-section"><div class="section-label-sm">⊗ Negatives</div>${warns}</div>` : ''}
      ${futureHtml}
      ${altsHtml}
      <div class="ing-title">Ingredient breakdown</div>
      <div>${ings || '<div style="font-size:13px;color:var(--c400);padding:10px 0">No ingredient data</div>'}</div>
      <button class="close-btn" onclick="closeDetail()">Done</button>`;
    document.getElementById('detail-overlay').classList.add('open');
    trackProduct(p);
  } catch (e) { toast('Could not load product', 'err'); }
}
function closeDetail(e) {
  if (!e || e.target === document.getElementById('detail-overlay'))
    document.getElementById('detail-overlay').classList.remove('open');
}

// ── HEALTH TAB ────────────────────────────────────────────────────────────────
function updateHealth() {
  const total = consumed.length, high = consumed.filter(p => p.risk === 'high').length,
    safe = consumed.filter(p => ['ok', 'low'].includes(p.risk)).length;
  document.getElementById('h-total').textContent = total;
  document.getElementById('h-high').textContent = high;
  document.getElementById('h-safe').textContent = safe;
  const avg = total ? consumed.reduce((a, p) => a + p.score, 0) / total : 0;
  document.getElementById('h-grade').textContent = avg < 15 ? 'A+' : avg < 30 ? 'A' : avg < 45 ? 'B' : avg < 60 ? 'C' : 'D';
  let alertHtml = '';
  if (total >= 3 && high / total >= 0.5)
    alertHtml = `<div class="danger-card"><div class="danger-title"><div class="d-dot"></div>Health Alert</div><div class="danger-body">More than half your recent items are high-risk. Try swapping chips for Too Yumm Multigrain or Lijjat Papad.</div></div>`;
  else if (high > 0 && total >= 2)
    alertHtml = `<div class="alert-card"><div class="alert-title"><div class="a-dot"></div>Watch out</div><div class="alert-body">You have ${high} high-risk item${high > 1 ? 's' : ''} in recent scans. Balance with safer choices.</div></div>`;
  document.getElementById('h-alerts').innerHTML = alertHtml;
  const futures = [...new Set(consumed.filter(p => p.future?.length).flatMap(p => p.future))];
  const fw = document.getElementById('h-future-wrap');
  if (futures.length) {
    fw.style.display = 'block';
    const icons = { Hypertension: '❤️', diabetes: '🩸', Obesity: '⚖️', ADHD: '🧠', Dental: '🦷', Kidney: '🫘', Cardiovascular: '❤️', Osteoporosis: '🦴', Anxiety: '😰', liver: '🫀', Cancer: '🔬' };
    document.getElementById('h-future').innerHTML = futures.map(f => {
      const ic = Object.entries(icons).find(([k]) => f.toLowerCase().includes(k.toLowerCase()));
      return `<div class="fi"><div class="fi-icon">${ic ? ic[1] : '⚠️'}</div><div><div class="fi-name">${f}</div><div class="fi-risk">Risk grows with continued habit</div></div></div>`;
    }).join('');
  } else fw.style.display = 'none';
  const hw = document.getElementById('h-history-wrap');
  if (consumed.length) {
    hw.style.display = 'block';
    document.getElementById('h-history').innerHTML = [...consumed].reverse().slice(0, 10).map(p => {
      const c = rC(p.risk);
      return `<div class="hist-item"><div class="hi-icon" style="background:${c.bg}"><span style="font-size:18px">${p.icon || '📦'}</span></div><div class="hi-info"><div class="hi-name">${p.name}</div><div class="hi-brand">${p.brand}</div></div><span class="rp ${c.rp}" style="font-size:10px">${rL(p.risk)}</span></div>`;
    }).join('');
  } else hw.style.display = 'none';
}

// ── COMPARE TAB ───────────────────────────────────────────────────────────────
function populateCompare() {
  const opts = allProducts.map(p => `<option value="${p.barcode}">${p.name} — ${p.brand}</option>`).join('');
  ['cmp-a', 'cmp-b'].forEach(id => { document.getElementById(id).innerHTML = opts; });
  if (allProducts.length > 1) document.getElementById('cmp-b').selectedIndex = 1;
}

async function doCompare() {
  const [b1, b2] = ['cmp-a', 'cmp-b'].map(id => document.getElementById(id).value);
  const [r1, r2] = await Promise.all([fetch(`${API}/api/products/${b1}`), fetch(`${API}/api/products/${b2}`)]);
  const [p1, p2] = await Promise.all([r1.json(), r2.json()]);
  const c1 = rC(p1.risk), c2 = rC(p2.risk);
  const winner = p1.score <= p2.score ? p1 : p2;
  document.getElementById('cmp-out').innerHTML = `
    <div class="cmp-grid">
      <div class="cmp-card${p1.barcode === winner.barcode ? ' winner' : ''}">
        ${p1.barcode === winner.barcode ? '<div class="cmp-winner-badge">Better Choice</div>' : ''}
        <div style="font-size:30px;margin-bottom:8px">${p1.icon || '📦'}</div>
        <div class="cmp-pname">${p1.name}<br><span style="font-size:11px;font-weight:400;color:var(--c400)">${p1.brand}</span></div>
        <div class="cmp-score" style="color:${c1.txt}">${p1.score}</div>
        <div class="cmp-score-sub">risk score / 100</div>
        <div style="margin-top:10px"><span class="rp ${c1.rp}">${rL(p1.risk)}</span></div>
      </div>
      <div class="cmp-card${p2.barcode === winner.barcode ? ' winner' : ''}">
        ${p2.barcode === winner.barcode ? '<div class="cmp-winner-badge">Better Choice</div>' : ''}
        <div style="font-size:30px;margin-bottom:8px">${p2.icon || '📦'}</div>
        <div class="cmp-pname">${p2.name}<br><span style="font-size:11px;font-weight:400;color:var(--c400)">${p2.brand}</span></div>
        <div class="cmp-score" style="color:${c2.txt}">${p2.score}</div>
        <div class="cmp-score-sub">risk score / 100</div>
        <div style="margin-top:10px"><span class="rp ${c2.rp}">${rL(p2.risk)}</span></div>
      </div>
    </div>
    <div class="cmp-verdict">
      <div class="cmp-verdict-title">Our recommendation</div>
      <div class="cmp-verdict-body">Choose <strong>${winner.name}</strong> — ${Math.abs(p1.score - p2.score)} points lower in risk with fewer harmful additives.</div>
    </div>`;
}

// ── AI ANALYSE TAB ────────────────────────────────────────────────────────────
function handleImageUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    imageBase64 = e.target.result.split(',')[1];
    document.getElementById('upload-label').textContent = `✓ ${file.name}`;
    document.getElementById('upload-box').classList.add('has-image');
  };
  reader.readAsDataURL(file);
}

async function runAIAnalysis() {
  const barcode = document.getElementById('ai-barcode').value.trim();
  if (!barcode) { toast('Please enter a barcode', 'err'); return; }

  const btn = document.getElementById('ai-analyse-btn');
  const statusEl = document.getElementById('ai-status');
  btn.disabled = true;
  statusEl.style.display = 'flex';
  statusEl.className = 'ai-status loading';
  statusEl.innerHTML = `<div class="ai-spinner"></div> Groq AI (Llama 3.3) is analysing the product...`;
  document.getElementById('ai-result-area').innerHTML = `
    <div class="ai-placeholder">
      <div class="ai-spinner" style="width:40px;height:40px;border-width:3px;color:var(--pu);margin-bottom:12px"></div>
      <p>Analysing ingredients for safety...</p>
      <p class="ai-placeholder-sub">This usually takes 5-10 seconds</p>
    </div>`;

  try {
    const payload = {
      barcode,
      name: document.getElementById('ai-name').value.trim(),
      brand: document.getElementById('ai-brand').value.trim(),
      ingredients_text: document.getElementById('ai-ingredients').value.trim(),
    };
    if (imageBase64) payload.image_base64 = imageBase64;

    const res = await fetch(`${API}/api/ai/analyse`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.error || 'Analysis failed');

    // Refresh product list
    const pRes = await fetch(`${API}/api/products`);
    allProducts = await pRes.json();
    setDbStatus('ok', `${allProducts.length} products`);
    buildCatChips(); populateCompare();

    statusEl.className = 'ai-status success';
    statusEl.innerHTML = data.from_cache
      ? '✓ Found in database — no AI call needed'
      : '✓ Analysis complete — saved to your local database';

    renderAIResult(data);
    toast(data.from_cache ? 'Product found in DB' : 'AI analysis saved to database!');
  } catch (e) {
    statusEl.className = 'ai-status error';
    statusEl.textContent = `Error: ${e.message}`;
    document.getElementById('ai-result-area').innerHTML = `<div class="ai-placeholder"><p style="color:var(--r)">${e.message}</p><p class="ai-placeholder-sub">Check that GROQ_API_KEY is set — get your free key at console.groq.com</p></div>`;
    toast(e.message, 'err');
  } finally { btn.disabled = false; }
}

function renderAIResult(p) {
  const c = rC(p.risk);
  const ings = (p.ingredients || []).map(i =>
    `<div class="ing-item"><div class="ing-name-w"><div class="ing-n">${i.n}</div>${i.note ? `<div class="ing-note">${i.note}</div>` : ''}</div><span class="ing-p ${ipClass(i.r)}">${rL(i.r)}</span></div>`
  ).join('');
  const warns = (p.warnings || []).map(w =>
    `<div class="warn-item"><div class="warn-dot"></div><div class="warn-text">${w}</div></div>`).join('');
  const futureHtml = (p.future || []).length
    ? `<div class="future-box"><div class="future-box-title">Future health risks</div>${p.future.map(f => `<div class="future-row">${f}</div>`).join('')}</div>` : '';

  document.getElementById('ai-result-area').innerHTML = `
    <div class="ai-result-card">
      <div class="ai-result-header">
        <div class="ai-result-icon" style="background:${c.bg}"><span style="font-size:26px">${p.icon || '📦'}</span></div>
        <div>
          <div class="ai-result-name">${p.name}</div>
          <div class="ai-result-brand">${p.brand} · ${p.category || 'Unknown'}</div>
          ${p.ai_generated ? `<div class="ai-badge"><span>✦</span> AI Analysed by Groq</div>` : ''}
        </div>
      </div>
      <div class="risk-hero" style="background:${c.bg}">
        <div><div class="rh-score" style="color:${c.txt}">${p.score}<span style="font-size:16px;font-weight:500">/100</span></div><div class="rh-sub" style="color:${c.txt}">Risk score</div></div>
        <div style="flex:1;padding-left:14px;border-left:1px solid ${c.txt}25">
          <div class="rh-label" style="color:${c.txt}">${rL(p.risk)}</div>
          <div class="rh-sub" style="color:${c.txt}">${p.category || ''}</div>
        </div>
      </div>
      ${warns ? `<div class="warn-list">${warns}</div>` : ''}
      ${futureHtml}
      <div class="ing-title">Ingredient breakdown</div>
      <div style="margin-bottom:14px">${ings || '<div style="font-size:13px;color:var(--c400);padding:8px 0">No ingredients available</div>'}</div>
      <div class="ai-saved-badge">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
        Saved to local database
      </div>
      <div class="ai-result-actions">
        <button class="btn-primary" onclick="openDetail('${p.barcode}')">View full detail</button>
        <button class="btn-outline" onclick="clearAIForm()">Analyse another</button>
      </div>
    </div>`;
}

function clearAIForm() {
  ['ai-barcode', 'ai-name', 'ai-brand', 'ai-ingredients'].forEach(id => { document.getElementById(id).value = ''; });
  imageBase64 = null;
  document.getElementById('upload-label').textContent = 'Click to upload image of product/ingredients';
  document.getElementById('upload-box').classList.remove('has-image');
  document.getElementById('ai-status').style.display = 'none';
  document.getElementById('ai-result-area').innerHTML = `<div class="ai-placeholder"><svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="32" cy="32" r="28"/><path d="M32 20v14M32 42h.01"/></svg><p>AI analysis results will appear here</p><p class="ai-placeholder-sub">Enter product details and click Analyse</p></div>`;
}

// ── DATABASE TAB ──────────────────────────────────────────────────────────────
async function refreshDBStats() {
  try {
    const res = await fetch(`${API}/api/stats`);
    const s = await res.json();
    document.getElementById('dbs-total').textContent = s.total_products;
    document.getElementById('dbs-scans').textContent = s.total_scans;
    document.getElementById('dbs-ai').textContent = s.ai_analysed;
    renderDBList();
  } catch (e) {}
}

async function renderDBList() {
  const res = await fetch(`${API}/api/products`);
  const prods = await res.json();
  document.getElementById('db-product-count').textContent = `${prods.length} products`;
  document.getElementById('db-list').innerHTML = prods.map(p => {
    const c = rC(p.risk);
    return `<div class="db-row" onclick="openDetail('${p.barcode}')">
      <div class="db-row-icon">${p.icon || '📦'}</div>
      <div class="db-row-info">
        <div class="db-row-name">${p.name} ${p.ai_generated ? '<span style="font-size:10px;background:#F5F3FF;color:#7C3AED;padding:1px 6px;border-radius:10px;margin-left:4px">AI</span>' : ''}</div>
        <div class="db-row-meta">${p.brand} · ${p.category || p.cat || ''} · ${p.barcode}</div>
      </div>
      <span class="rp ${c.rp}" style="font-size:10px">${rL(p.risk)}</span>
      <button class="db-row-del" onclick="delProduct('${p.barcode}',event)" title="Delete">
        <svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6M9 6V4h6v2"/></svg>
      </button>
    </div>`;
  }).join('');
}

function toggleAddForm() {
  const f = document.getElementById('add-form');
  f.style.display = f.style.display === 'none' ? 'block' : 'none';
  if (f.style.display === 'block') f.scrollIntoView({ behavior: 'smooth' });
}

async function submitAddProduct() {
  const name = document.getElementById('nf-name').value.trim();
  const brand = document.getElementById('nf-brand').value.trim();
  const barcode = document.getElementById('nf-barcode').value.trim();
  if (!name || !brand || !barcode) { toast('Name, brand and barcode are required', 'err'); return; }
  const ingsRaw = document.getElementById('nf-ingredients').value.trim();
  const ingredients = ingsRaw ? ingsRaw.split('\n').filter(l => l.trim()).map(l => {
    const [n, r, note] = l.split('|');
    return { n: n?.trim() || l, r: r?.trim() || 'ok', note: note?.trim() || '' };
  }) : [];
  const warnsRaw = document.getElementById('nf-warnings').value.trim();
  const warnings = warnsRaw ? warnsRaw.split('\n').filter(w => w.trim()) : [];
  const product = {
    barcode, name, brand,
    category: document.getElementById('nf-cat').value,
    icon: '📦',
    risk: document.getElementById('nf-risk').value,
    score: parseInt(document.getElementById('nf-score').value) || 50,
    ingredients, warnings, future: [], ai_generated: 0
  };
  await fetch(`${API}/api/products`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(product) });
  const res = await fetch(`${API}/api/products`);
  allProducts = await res.json();
  setDbStatus('ok', `${allProducts.length} products`);
  buildCatChips(); populateCompare();
  toggleAddForm();
  ['nf-name', 'nf-brand', 'nf-barcode', 'nf-score', 'nf-ingredients', 'nf-warnings'].forEach(id => { document.getElementById(id).value = ''; });
  await refreshDBStats();
  toast(`"${name}" added to database`);
}

async function delProduct(barcode, e) {
  e.stopPropagation();
  if (!confirm('Remove this product from the database?')) return;
  await fetch(`${API}/api/products/${barcode}`, { method: 'DELETE' });
  const res = await fetch(`${API}/api/products`);
  allProducts = await res.json();
  setDbStatus('ok', `${allProducts.length} products`);
  buildCatChips(); populateCompare();
  await refreshDBStats();
  toast('Product removed');
}

async function confirmClearScans() {
  if (!confirm('Clear all scan history? This cannot be undone.')) return;
  await fetch(`${API}/api/scans`, { method: 'DELETE' });
  consumed = []; recentScans = [];
  renderRecent(); updateHealth();
  await refreshDBStats();
  toast('Scan history cleared');
}

async function exportDB() {
  const [pr, sr] = await Promise.all([fetch(`${API}/api/products`), fetch(`${API}/api/scans`)]);
  const [products, scans] = await Promise.all([pr.json(), sr.json()]);
  const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), products, scans }, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `SafeKhao_DB_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  toast('Database exported as JSON');
}

// ── CAMERA ────────────────────────────────────────────────────────────────────
async function openCamera() {
  scanDone = false;
  document.getElementById('cam-status').textContent = 'Requesting camera...';
  document.getElementById('cam-result-overlay').classList.remove('show');
  document.getElementById('cam-modal').classList.add('open');
  try {
    camStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
    });
    const v = document.getElementById('cam-video');
    v.srcObject = camStream; await v.play();
    document.getElementById('cam-status').textContent = 'Scanning — hold barcode in the frame';
    startScan();
  } catch (e) {
    document.getElementById('cam-status').textContent = 'Camera denied — use manual barcode entry';
  }
}

function startScan() {
  const v = document.getElementById('cam-video'), c = document.getElementById('cam-canvas');
  const ctx = c.getContext('2d');
  scanInterval = setInterval(async () => {
    if (scanDone || v.readyState < 2) return;
    c.width = v.videoWidth; c.height = v.videoHeight;
    ctx.drawImage(v, 0, 0);
    try {
      if (typeof ZXingWasm !== 'undefined' && ZXingWasm.readBarcodesFromImageData) {
        const results = await ZXingWasm.readBarcodesFromImageData(
          ctx.getImageData(0, 0, c.width, c.height),
          { tryHarder: true, formats: ['EAN13', 'EAN8', 'UPCA', 'UPCE', 'Code128', 'Code39'] }
        );
        if (results?.length && results[0].text) handleBarcode(results[0].text);
      }
    } catch (_) {}
  }, 400);
}

async function handleBarcode(code) {
  if (scanDone) return;
  scanDone = true; clearInterval(scanInterval);
  const sheet = document.getElementById('cam-result-sheet');

  // Show loading while fetching
  sheet.innerHTML = `<div class="crs-drag"></div><div style="text-align:center;padding:20px 0"><div class="ai-spinner" style="width:24px;height:24px;border-width:2.5px;color:var(--g);margin:0 auto 8px"></div><div style="font-size:13px;color:var(--c500)">Looking up barcode ${code}...</div></div>`;
  document.getElementById('cam-result-overlay').classList.add('show');

  try {
    const res = await fetch(`${API}/api/products/${code}`);
    if (res.ok) {
      const p = await res.json();
      const c = rC(p.risk);
      sheet.innerHTML = `
        <div class="crs-drag"></div>
        <div class="crs-row">
          <div class="crs-icon" style="background:${c.bg}"><span style="font-size:24px">${p.icon || '📦'}</span></div>
          <div><div class="crs-name">${p.name}</div><div class="crs-brand">${p.brand}</div></div>
        </div>
        <div class="crs-risk" style="background:${c.bg}">
          <div><div class="crs-score" style="color:${c.txt}">${p.score}<span style="font-size:13px">/100</span></div><div class="crs-sub" style="color:${c.txt}">Risk</div></div>
          <div style="flex:1;padding-left:12px;border-left:1px solid ${c.txt}20"><div class="crs-label" style="color:${c.txt}">${rL(p.risk)}</div><div class="crs-sub" style="color:${c.txt}">${p.category || ''}</div></div>
        </div>
        ${(p.warnings || []).slice(0, 2).map(w => `<div class="crs-warn"><span>⚠</span><span>${w}</span></div>`).join('')}
        <div class="crs-btns">
          <button class="crs-btn-sec" onclick="resetScan()">Scan again</button>
          <button class="crs-btn-pri" onclick="closeCameraOpen('${p.barcode}')">Full analysis →</button>
        </div>`;
      trackProduct(p);
    } else {
      // Not in DB — offer AI analysis
      sheet.innerHTML = `
        <div class="crs-drag"></div>
        <div style="text-align:center;padding:10px 0 14px">
          <div style="font-size:28px;margin-bottom:8px">🔍</div>
          <div style="font-size:15px;font-weight:700;color:var(--c900);margin-bottom:4px">Barcode: ${code}</div>
          <div style="font-size:13px;color:var(--c400);margin-bottom:16px">Not in database — AI can analyse it</div>
          <div class="crs-btns">
            <button class="crs-btn-sec" onclick="resetScan()">Scan again</button>
            <button class="crs-btn-pri" onclick="closeCameraAI('${code}')">Analyse with AI →</button>
          </div>
        </div>`;
    }
  } catch (e) {
    sheet.innerHTML = `<div class="crs-drag"></div><div style="text-align:center;padding:20px;font-size:13px;color:var(--r)">Server error. Is Python server running?</div><div class="crs-btns"><button class="crs-btn-sec" onclick="resetScan()">Try again</button></div>`;
  }
}

function resetScan() {
  scanDone = false;
  document.getElementById('cam-result-overlay').classList.remove('show');
  document.getElementById('cam-status').textContent = 'Scanning — hold barcode in the frame';
  startScan();
}
function closeCameraOpen(barcode) { closeCamera(); setTimeout(() => openDetail(barcode), 250); }
function closeCameraAI(barcode) { closeCamera(); prefillAI(barcode); goTab('ai'); }
function closeCamera() {
  clearInterval(scanInterval); scanDone = true;
  if (camStream) { camStream.getTracks().forEach(t => t.stop()); camStream = null; }
  document.getElementById('cam-modal').classList.remove('open');
  document.getElementById('cam-result-overlay').classList.remove('show');
}

// ── TOAST ─────────────────────────────────────────────────────────────────────
function toast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = type === 'err' ? 'var(--r)' : 'var(--c900)';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

// ── BOOT ──────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  init();
  // Load ZXing barcode scanner
  const s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/zxing-wasm@1.3.4/dist/iife/zxing_wasm.js';
  document.head.appendChild(s);
});
