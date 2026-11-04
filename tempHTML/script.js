(function () {
  'use strict';

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
    report: null,
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
  const getJson = url => fetch(url).then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); });
  Promise.all([getJson('queue.json'), getJson('quarterly_report.json').catch(() => null)])
    .then(([data, report]) => {
      state.report = report;
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

  /* ---------- Quarterly reports (from quarterly_report.json) ---------- */
  const compact = (n, pre, suf) => {
    const a = Math.abs(n);
    const v = a >= 1e9 ? (n / 1e9).toFixed(2) + 'B' : a >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : a >= 1e3 ? (n / 1e3).toFixed(0) + 'K' : String(Math.round(n));
    return (pre || '') + v + (suf || '');
  };
  const METRICS = [
    { key: 'returns_processed', id: 'returns', title: 'Returns processed', unit: 'returns', better: 'up', short: v => compact(v), full: v => v.toLocaleString('en-US') },
    { key: 'money_saved_usd', id: 'money', title: 'Money saved', unit: 'USD', better: 'up', short: v => compact(v, '$'), full: v => '$' + v.toLocaleString('en-US') },
    { key: 'carbon_emissions_kg', id: 'carbon', title: 'Carbon emissions', unit: 'kg', better: 'up', short: v => compact(v, '', ' kg'), full: v => v.toLocaleString('en-US') + ' kg' },
    { key: 'waste_disposed_lbs', id: 'waste', title: 'Waste disposed', unit: 'lbs', better: 'down', short: v => compact(v, '', ' lbs'), full: v => v.toLocaleString('en-US') + ' lbs' }
  ];
  // Strip order: kept destinations first, waste last.
  const DISPOSITIONS = [
    { key: 'restock', name: 'Restock', better: 'up' },
    { key: 'resell', name: 'Resell', better: 'up' },
    { key: 'refurbish', name: 'Refurbish', better: 'up' },
    { key: 'donate', name: 'Donate', better: 'up' },
    { key: 'waste', name: 'Waste', better: 'down' }
  ];

  function deltaInfo(better, cur, prev, points) {
    if (!prev && !points) return { text: 'No prior figure', cls: 'flat' };
    const change = points ? cur - prev : (cur - prev) / prev * 100;
    if (Math.abs(change) < 0.05) return { text: 'No change', cls: 'flat' };
    const improved = better === 'up' ? change > 0 : change < 0;
    const text = (change > 0 ? '+' : '') + change.toLocaleString('en-US', { minimumFractionDigits: points ? 0 : 1, maximumFractionDigits: points ? 0 : 1 }) + (points ? ' pts' : '%');
    return { text: text, cls: improved ? 'good' : 'bad', arrow: change > 0 ? '▲' : '▼' };
  }
  const deltaHtml = d => '<span class="delta ' + d.cls + '">' + (d.arrow ? d.arrow + ' ' : '') + d.text + '</span>';

  function renderReports() {
    const r = state.report;
    if (!r || !r.quarters || r.quarters.length < 2) {
      $('#detail').innerHTML = '<div class="reports"><h2 class="page">Quarterly reports</h2><div class="empty"><strong>Quarterly report data did not load.</strong>Check that quarterly_report.json is in the same folder and that the page is served from a local server.</div></div>';
      return;
    }
    const qs = r.quarters;
    const cur = qs[qs.length - 1];
    const prev = qs[qs.length - 2];
    const launch = qs.find((s, i) => s.agent_in_use && i > 0 && !qs[i - 1].agent_in_use);

    let h = '<div class="reports"><div class="page-head"><h2 class="page">Quarterly reports</h2>' + (r.sample_data ? '<span class="tag-sample">Sample data</span>' : '') + '</div>' +
      '<p class="lede">' + (launch ? 'The agent system went live in ' + esc(launch.quarter) + '. Each figure compares ' + esc(cur.quarter) + ' with the quarters before it.' :
        esc(cur.quarter) + ' is the current quarter, compared with the quarters before it.') + '</p>';

    h += '<section class="hero" aria-labelledby="hero-title"><h3 id="hero-title">Where returns go</h3><p class="hero-sub">Share of all returns by destination, per quarter</p>' +
      '<ul class="key">' + DISPOSITIONS.map(d => '<li><i class="sw ' + d.key + '"></i>' + d.name + '</li>').join('') + '</ul>' + stripsHtml(qs) + '</section>';

    h += '<div class="kpis">' + METRICS.map(m => {
      const d = deltaInfo(m.better, cur[m.key], prev[m.key]);
      return '<div class="kpi"><h3>' + m.title + '</h3><div class="big">' + m.short(cur[m.key]) + '</div>' + deltaHtml(d) +
        '<div class="vs">vs ' + esc(prev.quarter) + ' (' + m.short(prev[m.key]) + ')' + (m.better === 'down' ? '; lower is better' : '') + '</div></div>';
    }).join('') + '</div>';

    h += '<div class="charts">' + METRICS.map(m => chartHtml(m, qs)).join('') + '</div>';

    h += '<h2 class="reports-heading" id="data-tables">Data tables</h2>';
    METRICS.forEach(m => {
      h += '<details class="report-section"><summary>' + m.title + ' by quarter</summary><div class="table-scroll"><table><thead><tr><th>Quarter</th><th class="num">' + m.title + ' (' + m.unit + ')</th><th class="num">Change vs previous quarter</th></tr></thead><tbody>';
      qs.forEach((s, i) => {
        const d = i === 0 ? { text: '—', cls: 'flat' } : deltaInfo(m.better, s[m.key], qs[i - 1][m.key]);
        h += '<tr><td>' + esc(s.quarter) + (s.is_current ? ' (current)' : '') + '</td><td class="num">' + s[m.key].toLocaleString('en-US') + '</td><td class="num">' + deltaHtml(d) + '</td></tr>';
      });
      h += '</tbody></table></div></details>';
    });
    h += '<details class="report-section"><summary>Where returns go by quarter</summary><div class="table-scroll"><table><thead><tr><th>Destination</th>' +
      qs.map(s => '<th class="num">' + esc(s.quarter) + '</th>').join('') + '<th class="num">Change vs previous quarter</th></tr></thead><tbody>';
    DISPOSITIONS.forEach(d => {
      const c = cur.disposition_breakdown_pct[d.key], p = prev.disposition_breakdown_pct[d.key];
      h += '<tr><td>' + d.name + '</td>' + qs.map(s => '<td class="num">' + s.disposition_breakdown_pct[d.key] + '%</td>').join('') +
        '<td class="num">' + deltaHtml(deltaInfo(d.better, c, p, true)) + '</td></tr>';
    });
    h += '</tbody></table></div></details>';
    $('#detail').innerHTML = h + '</div>';
  }

  function stripsHtml(qs) {
    let h = '';
    qs.forEach((s, i) => {
      if (s.agent_in_use && i > 0 && !qs[i - 1].agent_in_use) h += '<div class="launch"><span>Agent system live</span></div>';
      const b = s.disposition_breakdown_pct;
      const segs = DISPOSITIONS.filter(d => b[d.key] > 0).map(d =>
        '<div class="seg-bar ' + d.key + '" style="flex-grow:' + b[d.key] + '" title="' + d.name + ' ' + b[d.key] + '%">' +
        '<b>' + b[d.key] + '%</b>' + (b[d.key] >= 12 ? '<span>' + d.name + '</span>' : '') + '</div>').join('');
      const aria = DISPOSITIONS.map(d => d.name + ' ' + b[d.key] + '%').join(', ');
      h += '<div class="strip-row"><div class="strip-q">' + esc(s.quarter) + '</div><div class="strip" role="img" aria-label="' + esc(s.quarter + ': ' + aria) + '">' + segs + '</div></div>';
    });
    return h;
  }

  function chartHtml(m, qs) {
    const W = 360, H = 220, padL = 10, padR = 10, padT = 24, padB = 30;
    const max = Math.max.apply(null, qs.map(s => s[m.key])) || 1;
    const bw = (W - padL - padR) / qs.length;
    const bars = qs.map((s, i) => {
      const v = s[m.key];
      const bh = (v / max) * (H - padT - padB);
      const x = padL + i * bw + bw * 0.18, w = bw * 0.64, y = H - padB - bh;
      return '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + w.toFixed(1) + '" height="' + Math.max(bh, 2).toFixed(1) + '" rx="3" fill="' + (s.agent_in_use ? '#7c22e8' : '#c9c7d1') + '"/>' +
        '<text x="' + (x + w / 2).toFixed(1) + '" y="' + (y - 6).toFixed(1) + '" text-anchor="middle" font-size="11" font-weight="600">' + m.short(v) + '</text>' +
        '<text class="axis" x="' + (x + w / 2).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle">' + esc(s.quarter) + '</text>';
    }).join('');
    const summary = qs.map(s => s.quarter + ': ' + m.full(s[m.key])).join('; ');
    return '<figure class="chart" id="chart-' + m.id + '"><h3>' + m.title + '</h3><div class="sub">' + m.unit + ' per quarter, ' + (m.better === 'up' ? 'higher is better' : 'lower is better') + '</div>' +
      '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(m.title + ' by quarter. ' + summary) + '">' +
      '<line x1="' + padL + '" y1="' + (H - padB) + '" x2="' + (W - padR) + '" y2="' + (H - padB) + '" stroke="#d9d2e4"/>' + bars + '</svg>' +
      '<div class="legend"><span><i style="background:#c9c7d1"></i>Before the agent</span><span><i style="background:#7c22e8"></i>With the agent</span></div></figure>';
  }
})();
