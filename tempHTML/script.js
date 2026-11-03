(function () {
  'use strict';

  /* ---------- SAMPLE DATA (synthetic, not Cosmic Mart figures) ----------
     Prior-quarter history for Quarterly Reports. Replace when real data exists. */
  const SAMPLE_HISTORY = [
    { quarter: 'Q4 2025', money: 18200, carbon: 2600, waste: 410 },
    { quarter: 'Q1 2026', money: 21400, carbon: 3050, waste: 372 },
    { quarter: 'Q2 2026', money: 24900, carbon: 3500, waste: 340 },
    { quarter: 'Q3 2026', money: 27300, carbon: 3900, waste: 301 }
  ];

  const PAGE = 10;
  const DEST_ORDER = ['restock', 'refurbish', 'resell', 'donate', 'recycle'];
  const URGENT_FLAGS = ['swollen_battery', 'hazmat_handling'];
  const SORTS = {
    returned_at: { label: 'Date received', get: r => Date.parse(r.returned_at) },
    return_id: { label: 'Return ID', get: r => r.return_id },
    product: { label: 'Product', get: r => r.product.toLowerCase() },
    expected_recovery_usd: { label: 'Expected recovery', get: r => r.expected_recovery_usd },
    estimated_carbon_emission_avoided_kg: { label: 'Carbon impact', get: r => r.estimated_carbon_emission_avoided_kg },
    confidence: { label: 'Confidence', get: r => r.confidence },
    value_at_stake_usd: { label: 'Value at stake', get: r => r.value_at_stake_usd }
  };

  const blank = () => ({ search: '', dest: '', cat: '', cond: '', flag: '', sort: 'returned_at', dir: 'desc', shown: PAGE, key: '' });
  const state = {
    returns: [], destinations: [], categories: [], conditions: [], flags: [],
    tab: 'queue',
    sel: { queue: null, approved: null },
    lists: { queue: blank(), approved: blank() }
  };

  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = v => String(v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const label = s => String(s).replace(/_/g, ' ');
  const unique = arr => Array.from(new Set(arr)).sort();
  const money = n => '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const moneyWhole = n => '$' + Math.round(n).toLocaleString('en-US');
  const num1 = n => Number(n).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const pct = c => Math.round(c * 100) + '%';
  const fmtDate = iso => new Date(iso).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC' }) + ' UTC';
  const quarterOf = iso => { const d = new Date(iso); return 'Q' + (Math.floor(d.getUTCMonth() / 3) + 1) + ' ' + d.getUTCFullYear(); };
  const byId = id => state.returns.find(r => r.return_id === id);
  const isList = () => state.tab !== 'reports';

  /* ---------- Load ---------- */
  fetch('queue.json')
    .then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
    .then(data => {
      state.returns = data.map(r => ({ ...r, status: r.status === 'approved' ? 'approved' : 'queue', original_destination: r.recommended_destination }));
      const dests = unique(state.returns.map(r => r.recommended_destination));
      state.destinations = DEST_ORDER.filter(d => dests.includes(d)).concat(dests.filter(d => !DEST_ORDER.includes(d)));
      state.categories = unique(state.returns.map(r => r.category));
      state.conditions = unique(state.returns.map(r => r.condition));
      state.flags = unique(state.returns.flatMap(r => r.flags));
      init();
    })
    .catch(() => {
      const box = $('#load-error');
      box.hidden = false;
      box.innerHTML = '<strong>Could not load queue.json.</strong> Browsers block reading local files when this page is opened directly. ' +
        'Start a local server in this folder, for example <code>python -m http.server 8000</code>, then open <code>http://localhost:8000</code>.';
      $('#side-list').hidden = true;
    });

  /* ---------- Init ---------- */
  function init() {
    setupTabs();
    setupControls();
    render();
  }

  function setupTabs() {
    const tabs = $$('.tab');
    const show = name => {
      state.tab = name;
      tabs.forEach(t => {
        const on = t.dataset.tab === name;
        t.classList.toggle('is-active', on);
        t.setAttribute('aria-selected', on);
        t.tabIndex = on ? 0 : -1;
      });
      syncControls();
      render();
    };
    tabs.forEach((t, i) => {
      t.addEventListener('click', () => show(t.dataset.tab));
      t.addEventListener('keydown', e => {
        let j = null;
        if (e.key === 'ArrowRight') j = (i + 1) % tabs.length;
        if (e.key === 'ArrowLeft') j = (i - 1 + tabs.length) % tabs.length;
        if (j !== null) { e.preventDefault(); tabs[j].focus(); show(tabs[j].dataset.tab); }
      });
    });
  }

  function setupControls() {
    const opt = (v, t) => '<option value="' + esc(v) + '">' + esc(t) + '</option>';
    $('#f-dest').innerHTML = opt('', 'Any destination') + state.destinations.map(d => opt(d, cap(d))).join('');
    $('#f-flag').innerHTML = opt('', 'Any flag') + opt('__none', 'No flags') + state.flags.map(f => opt(f, cap(label(f)))).join('');
    $('#f-cat').innerHTML = opt('', 'Any category') + state.categories.map(c => opt(c, cap(c))).join('');
    $('#f-cond').innerHTML = opt('', 'Any condition') + state.conditions.map(c => opt(c, cap(c))).join('');
    $('#f-sort').innerHTML = Object.keys(SORTS).map(k => opt(k, SORTS[k].label)).join('');

    const bind = (id, key, evt) => $(id).addEventListener(evt, e => { state.lists[state.tab][key] = e.target.value; if (key === 'sort') syncControls(); render(); });
    bind('#f-search', 'search', 'input');
    bind('#f-dest', 'dest', 'change');
    bind('#f-flag', 'flag', 'change');
    bind('#f-cat', 'cat', 'change');
    bind('#f-cond', 'cond', 'change');
    bind('#f-sort', 'sort', 'change');
    $('#f-dir').addEventListener('click', () => {
      const st = state.lists[state.tab];
      st.dir = st.dir === 'desc' ? 'asc' : 'desc';
      syncControls(); render();
    });
    $('#f-clear').addEventListener('click', () => {
      Object.assign(state.lists[state.tab], blank());
      syncControls(); render();
    });
    syncControls();
  }

  function syncControls() {
    if (!isList()) return;
    const st = state.lists[state.tab];
    $('#f-search').value = st.search;
    $('#f-dest').value = st.dest;
    $('#f-flag').value = st.flag;
    $('#f-cat').value = st.cat;
    $('#f-cond').value = st.cond;
    $('#f-sort').value = st.sort;
    const dateSort = st.sort === 'returned_at';
    $('#f-dir').textContent = st.dir === 'desc' ? (dateSort ? 'Newest first' : 'High to low') : (dateSort ? 'Oldest first' : 'Low to high');
  }

  /* ---------- Data helpers ---------- */
  function visible(name) {
    const st = state.lists[name];
    const q = st.search.trim().toLowerCase();
    const rows = state.returns.filter(r => {
      if (r.status !== name) return false;
      if (st.dest && r.recommended_destination !== st.dest) return false;
      if (st.cat && r.category !== st.cat) return false;
      if (st.cond && r.condition !== st.cond) return false;
      if (st.flag === '__none' && r.flags.length) return false;
      if (st.flag && st.flag !== '__none' && !r.flags.includes(st.flag)) return false;
      if (q) {
        const hay = [r.return_id, r.sku, r.product, r.category, r.condition, r.return_reason, r.recommended_destination, r.justification, r.flags.map(label).join(' ')].join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const get = SORTS[st.sort].get;
    const sign = st.dir === 'desc' ? -1 : 1;
    rows.sort((a, b) => { const x = get(a), y = get(b); return (x < y ? -1 : x > y ? 1 : 0) * sign; });
    return rows;
  }

  /* ---------- Render ---------- */
  function render() {
    $('#count-queue').textContent = state.returns.filter(r => r.status === 'queue').length;
    $('#count-approved').textContent = state.returns.filter(r => r.status === 'approved').length;
    const list = isList();
    $('#side-list').hidden = !list;
    $('#side-reports').hidden = list;
    if (list) { renderList(); renderDetail(); } else { renderReports(); }
  }

  function renderList() {
    const name = state.tab;
    const st = state.lists[name];
    const all = state.returns.filter(r => r.status === name);
    const rows = visible(name);

    const key = [st.search, st.dest, st.cat, st.cond, st.flag, st.sort, st.dir].join('|');
    if (st.key !== key) { st.key = key; st.shown = PAGE; }
    if (!rows.some(r => r.return_id === state.sel[name])) state.sel[name] = rows.length ? rows[0].return_id : null;

    const shown = rows.slice(0, st.shown);
    $('#result').textContent = 'Showing ' + shown.length + ' of ' + rows.length + (rows.length !== all.length ? ' (' + all.length + ' total)' : '');
    const host = $('#list');
    if (!rows.length) {
      host.innerHTML = '<div class="empty"><strong>' +
        (all.length ? 'No returns match your search or filters.' : name === 'queue' ? 'The queue is empty.' : 'No approved returns yet.') + '</strong>' +
        (all.length ? 'Clear the filters to see every return.' : name === 'queue' ? 'Reopen a return from Approved to review it again.' : 'Approve a return from To review to see it here.') + '</div>';
      return;
    }
    host.innerHTML = '<ul class="items">' + shown.map((r, i) => {
      const urgent = r.flags.some(f => URGENT_FLAGS.includes(f));
      const on = r.return_id === state.sel[name];
      return '<li><button class="item' + (on ? ' is-selected' : '') + (urgent ? ' urgent' : '') + '" data-act="select" data-id="' + r.return_id + '"' + (on ? ' aria-current="true"' : '') + '>' +
        '<span class="n">' + (i + 1) + '</span><span class="t">' + esc(r.return_id) + '</span><span class="amt">' + money(r.expected_recovery_usd) + '</span>' +
        '<span class="s">' + esc(r.product) + ' &middot; ' + esc(r.recommended_destination) + (urgent ? ' &middot; <span class="u">Handle with care</span>' : '') + '</span></button></li>';
    }).join('') + '</ul>' +
      (rows.length > shown.length ? '<div class="more"><button class="btn btn-ghost" data-act="more">Show ' + Math.min(PAGE, rows.length - shown.length) + ' more</button></div>' : '');
  }

  function flagsHtml(flags) {
    if (!flags.length) return '<span class="none">None</span>';
    return '<div class="chips">' + flags.map(f => '<span class="chip' + (URGENT_FLAGS.includes(f) ? ' urgent' : '') + '">' + esc(cap(label(f))) + '</span>').join('') + '</div>';
  }

  function renderDetail() {
    const host = $('#detail');
    const r = byId(state.sel[state.tab]);
    if (!r) {
      host.innerHTML = '<div class="detail-body"><div class="empty"><strong>' +
        (state.tab === 'queue' ? 'Nothing to review.' : 'Nothing approved yet.') + '</strong>' +
        (state.tab === 'queue' ? 'Every return in view has been handled, or your filters hide them.' : 'Approve a return to see it here.') + '</div></div>';
      return;
    }
    const locked = r.status === 'approved';
    const changed = r.recommended_destination !== r.original_destination;
    const low = r.flags.includes('low_confidence');
    const gap = '<span class="none">Not in data</span>';
    const dest = r.recommended_destination;

    const segs = state.destinations.map(d =>
      '<button class="seg" data-act="dest" data-dest="' + esc(d) + '" aria-pressed="' + (d === dest) + '"' + (locked ? ' aria-disabled="true"' : '') + '>' +
      '<span class="name">' + esc(cap(d)) + '</span>' +
      (d === r.original_destination ? '<span class="pick">Agent’s pick</span>' : '') + '</button>').join('');

    let foot;
    if (locked) {
      foot = '<p>Approved as ' + esc(dest) + '. Reopen to send it back to the queue.</p><div class="btns"><button class="btn" data-act="reopen">Reopen</button></div>';
    } else if (changed) {
      foot = '<p>You changed the destination from ' + esc(r.original_destination) + ' to ' + esc(dest) + '.</p><div class="btns">' +
        '<button class="btn btn-ghost" data-act="reset">Reset to agent’s pick</button><button class="btn" data-act="approve">Approve ' + esc(dest) + '</button></div>';
    } else {
      foot = '<p>Approve the agent’s pick, or change it.</p><div class="btns">' +
        '<button class="btn btn-ghost" data-act="change">Change destination</button><button class="btn" data-act="approve">Approve ' + esc(dest) + '</button></div>';
    }

    host.innerHTML = '<div class="detail-body">' +
      '<div class="d-title"><h2>' + esc(r.return_id) + '</h2><span class="sku">SKU ' + esc(r.sku) + '</span></div>' +
      '<p class="d-product"><b>' + esc(r.product) + '</b>, ' + esc(r.category) + ', ' + esc(r.condition) + ' condition</p>' +
      '<div class="segments' + (locked ? ' locked' : '') + '" role="group" aria-label="Destination">' + segs + '</div>' +
      (changed && !locked ? '<p class="edit-note">Changed from the agent’s pick. Changes last until you reload the page.</p>' : '') +
      '<div class="stats">' +
      '<div class="stat"><div class="label">Expected recovery</div><div class="value">' + money(r.expected_recovery_usd) + '</div></div>' +
      '<div class="stat"><div class="label">Carbon avoided</div><div class="value">' + num1(r.estimated_carbon_emission_avoided_kg) + ' <small>kg CO₂e</small></div></div>' +
      '<div class="stat"><div class="label">Value at stake</div><div class="value">' + money(r.value_at_stake_usd) + '</div></div>' +
      '<div class="stat"><div class="label">Agent confidence</div><div class="value">' + pct(r.confidence) + '</div><div class="bar" role="img" aria-label="Confidence ' + pct(r.confidence) + '"><i class="' + (low ? 'low' : '') + '" style="width:' + pct(r.confidence) + '"></i></div></div>' +
      '</div>' +
      '<div class="d-section"><h3>Why this route</h3><p>' + esc(r.justification) + '</p></div>' +
      '<div class="d-section"><h3>Flags</h3>' + flagsHtml(r.flags) + '</div>' +
      '<div class="d-section"><h3>Return details</h3><dl class="dl">' +
      '<dt>Return reason</dt><dd>' + esc(r.return_reason) + '</dd>' +
      '<dt>Customer or store</dt><dd>' + gap + '</dd>' +
      '<dt>Date received</dt><dd>' + esc(fmtDate(r.returned_at)) + '</dd>' +
      '<dt>Weight</dt><dd>' + num1(r.weight_lbs) + ' lbs</dd>' +
      '<dt>Status</dt><dd>' + (locked ? 'Approved' : 'Waiting for review') + '</dd>' +
      '</dl></div></div>' +
      '<div class="actionbar">' + foot + '</div>';
  }

  /* ---------- Actions ---------- */
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const act = btn.dataset.act;
    const r = byId(state.sel[state.tab]);

    if (act === 'more') { state.lists[state.tab].shown += PAGE; renderList(); return; }
    if (act === 'select') {
      state.sel[state.tab] = btn.dataset.id;
      renderList(); renderDetail();
      if (window.matchMedia('(max-width: 900px)').matches) $('#main').scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if (!r) return;
    if (act === 'dest') {
      if (r.status === 'approved' || btn.dataset.dest === r.recommended_destination) return;
      r.recommended_destination = btn.dataset.dest;
      render();
      const again = $('.seg[aria-pressed="true"]'); if (again) again.focus();
      toast(r.return_id + ' destination changed to ' + r.recommended_destination);
    }
    if (act === 'reset') {
      r.recommended_destination = r.original_destination;
      render();
      toast(r.return_id + ' reset to the agent’s pick');
    }
    if (act === 'change') { const s = $('.seg[aria-pressed="true"]'); if (s) s.focus(); }
    if (act === 'approve') setStatus(r, 'approved');
    if (act === 'reopen') setStatus(r, 'queue');
  });

  function setStatus(r, status) {
    const from = state.tab;
    const idx = visible(from).findIndex(x => x.return_id === r.return_id);
    r.status = status;
    const after = visible(from);
    state.sel[from] = after.length ? after[Math.min(idx, after.length - 1)].return_id : null;
    state.sel[status] = r.return_id;
    render();
    toast(status === 'approved' ? r.return_id + ' approved and moved to Approved' : r.return_id + ' reopened and moved to To review');
  }

  function toast(msg) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.remove('show'), 3000);
  }

  /* ---------- Quarterly reports ---------- */
  const METRICS = [
    { key: 'money', title: 'Money saved', unit: 'USD', better: 'up', fmt: moneyWhole },
    { key: 'carbon', title: 'Carbon emissions reduced', unit: 'kg CO₂e', better: 'up', fmt: v => Math.round(v).toLocaleString('en-US') + ' kg' },
    { key: 'waste', title: 'Waste disposed', unit: 'lbs', better: 'down', fmt: v => Math.round(v).toLocaleString('en-US') + ' lbs' }
  ];

  function currentQuarter() {
    const latest = Math.max.apply(null, state.returns.map(r => Date.parse(r.returned_at)));
    return quarterOf(new Date(latest).toISOString());
  }

  function currentFigures(q) {
    const done = state.returns.filter(r => r.status === 'approved' && quarterOf(r.returned_at) === q);
    return {
      quarter: q,
      money: done.reduce((a, r) => a + r.expected_recovery_usd, 0),
      carbon: done.reduce((a, r) => a + r.estimated_carbon_emission_avoided_kg, 0),
      waste: done.filter(r => r.recommended_destination === 'recycle').reduce((a, r) => a + r.weight_lbs, 0),
      count: done.length
    };
  }

  function deltaInfo(m, cur, prev) {
    if (prev === 0) return { text: 'No prior figure', cls: 'flat' };
    const change = (cur - prev) / prev * 100;
    if (Math.abs(change) < 0.05) return { text: 'No change', cls: 'flat' };
    const improved = m.better === 'up' ? change > 0 : change < 0;
    return { text: (change > 0 ? '+' : '') + change.toFixed(1) + '%', cls: improved ? 'good' : 'bad', arrow: change > 0 ? '▲' : '▼' };
  }

  function renderReports() {
    const cur = currentFigures(currentQuarter());
    const series = SAMPLE_HISTORY.concat([cur]);
    const prev = SAMPLE_HISTORY[SAMPLE_HISTORY.length - 1];

    let h = '<div class="reports"><h2 class="page">Quarterly reports</h2>' +
      '<p class="report-note">' + cur.quarter + ' to date is based on ' + cur.count + ' approved return' + (cur.count === 1 ? '' : 's') + '; earlier quarters are sample data.</p>';

    h += '<div class="kpis">' + METRICS.map(m => {
      const d = deltaInfo(m, cur[m.key], prev[m.key]);
      return '<div class="kpi"><h3>' + m.title + '</h3><div class="big">' + m.fmt(cur[m.key]) + '</div>' +
        '<div class="delta ' + d.cls + '">' + (d.arrow ? d.arrow + ' ' : '') + d.text + '</div>' +
        '<div class="vs">vs ' + prev.quarter + ' (' + m.fmt(prev[m.key]) + '); ' + (m.better === 'up' ? 'higher' : 'lower') + ' is better</div></div>';
    }).join('') + '</div>';

    h += '<div class="charts">' + METRICS.map(m => chartHtml(m, series)).join('') + '</div>';

    h += '<h2 class="reports-heading">Tables</h2>';
    METRICS.forEach(m => {
      h += '<details class="report-section"><summary>' + m.title + ' by quarter (table)</summary><div class="table-scroll"><table><thead><tr><th>Quarter</th><th class="num">' + m.title + ' (' + m.unit + ')</th><th class="num">Change vs previous quarter</th></tr></thead><tbody>';
      series.forEach((s, i) => {
        const d = i === 0 ? { text: '—', cls: 'flat' } : deltaInfo(m, s[m.key], series[i - 1][m.key]);
        h += '<tr><td>' + s.quarter + (i === series.length - 1 ? ' (to date)' : '<span class="tag-sample">Sample</span>') + '</td><td class="num">' + m.fmt(s[m.key]) +
          '</td><td class="num"><span class="delta ' + d.cls + '">' + (d.arrow ? d.arrow + ' ' : '') + d.text + '</span></td></tr>';
      });
      h += '</tbody></table></div></details>';
    });
    $('#detail').innerHTML = h + '</div>';
  }

  function chartHtml(m, series) {
    const W = 360, H = 220, padL = 10, padR = 10, padT = 24, padB = 30;
    const max = Math.max.apply(null, series.map(s => s[m.key])) || 1;
    const bw = (W - padL - padR) / series.length;
    const bars = series.map((s, i) => {
      const v = s[m.key];
      const bh = (v / max) * (H - padT - padB);
      const x = padL + i * bw + bw * 0.18, w = bw * 0.64, y = H - padB - bh;
      const isCur = i === series.length - 1;
      return '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + w.toFixed(1) + '" height="' + Math.max(bh, 1).toFixed(1) + '" rx="3" fill="' + (isCur ? '#7c22e8' : '#c9c7d1') + '"/>' +
        '<text x="' + (x + w / 2).toFixed(1) + '" y="' + (y - 6).toFixed(1) + '" text-anchor="middle" font-size="11" font-weight="600">' + (m.key === 'money' ? moneyWhole(v) : Math.round(v).toLocaleString('en-US')) + '</text>' +
        '<text class="axis" x="' + (x + w / 2).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle">' + s.quarter + '</text>';
    }).join('');
    const summary = series.map(s => s.quarter + ': ' + m.fmt(s[m.key])).join('; ');
    return '<figure class="chart" id="chart-' + m.key + '"><h3>' + m.title + '</h3><div class="sub">' + m.unit + ' per quarter, ' + (m.better === 'up' ? 'higher is better' : 'lower is better') + '</div>' +
      '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(m.title + ' by quarter. ' + summary) + '">' +
      '<line x1="' + padL + '" y1="' + (H - padB) + '" x2="' + (W - padR) + '" y2="' + (H - padB) + '" stroke="#d9d2e4"/>' + bars + '</svg>' +
      '<div class="legend"><span><i style="background:#c9c7d1"></i>Sample quarters</span><span><i style="background:#7c22e8"></i>Current quarter to date</span></div></figure>';
  }
})();
