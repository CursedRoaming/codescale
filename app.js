/* 码尺 CodeScale · 前端
   无依赖、无构建。所有数字来自 data/latest.json，页面自己不算任何业务指标，
   只做「把已有数字放好」这一件事。算数的地方在 pipeline/core，改口径去改那边。 */

const $ = (id) => document.getElementById(id);
const BRL = (v) => (v == null ? '--' : 'R$ ' + Number(v).toFixed(2));
const PCT = (v, d = 0) => (v == null ? '--' : (v * 100).toFixed(d) + '%');
const NUM = (v) => (v == null ? '--' : Number(v).toLocaleString('pt-BR'));

const STATUS = {
  ok: ['已接入', 'ok', 's-ok'],
  empty: ['无新数据', 'off', 's-warn'],
  not_configured: ['待配置', 'off', 's-off'],
  disabled: ['未接入', 'off', 's-off'],
  blocked: ['被拦截', 'bad', 's-block'],
  error: ['出错', 'bad', 's-block'],
};

const PLATFORM = {
  mercadolivre: 'Mercado Livre', shopee: 'Shopee', tiktok_shop: 'TikTok Shop',
  kalodata: 'Kalodata', amazon: 'Amazon', unknown: '未标注', seed: '本地样本',
};

async function load() {
  try {
    const r = await fetch('data/latest.json', { cache: 'no-store' });
    if (r.ok) {
      const data = await r.json();
      let runs = [];
      try {
        const ri = await fetch('data/history/index.json', { cache: 'no-store' });
        if (ri.ok) runs = (await ri.json()).runs || [];
      } catch (e) { /* 归档拿不到不影响主页面 */ }
      return { data, runs };
    }
  } catch (e) { /* file:// 下会走到这里 */ }
  const m = window.__CODESCALE__;
  if (m) return { data: m.data, runs: m.runs || [] };
  return null;
}

/* ---------------- 头部 ---------------- */
function head(d) {
  const m = d.meta, c = d.cost;
  const lag = m.freshness_days;
  $('eyebrow').textContent = `${m.site_en} · 巴西站 · ${m.run_date}`;
  $('sub').innerHTML =
    `样本 <b>${d.n}</b> 条 · 观测日 <b>${(d.observed_dates || []).join('、') || '--'}</b>` +
    (lag == null ? '' : ` · 距今 <b>${lag}</b> 天`) +
    ` · 口径 <b>${c.product}</b>`;

  const okN = (d.sources || []).filter((s) => s.status === 'ok').length;
  const fresh = lag == null ? '' : lag <= 1 ? '今日' : `${lag} 天前`;
  $('stamp').innerHTML =
    `<span class="pulse"></span><span>数据 ${fresh} · 源 ${okN}/${d.sources.length}</span>`;
}

/* ---------------- 本版变化 ---------------- */
/* 只在「这一版其实没有新东西」时出现。每天自动跑，源没接通时每次结果都一样，
   不承认这件事就等于每天用同一批数冒充新一期。 */
function notice(d) {
  const x = d.delta || {};
  const lag = d.meta.freshness_days;
  let html = '';
  if (!x.has_prev) {
    html = `<div class="warnbar"><span><b>第一份快照</b>　没有上一版可比。明天这一页会显示条数、商品与价格的变动。</span></div>`;
  } else if (x.changed === false) {
    html = `<div class="warnbar"><span><b>本版没有新数据</b>　本次运行没有取到任何新记录，
      条数、商品、价格与 ${x.prev_date || '上一版'} 逐项相同。这不是新一期行情，是同一批数据的再次统计。` +
      (lag != null && lag >= 3
        ? `　数据观测日仍是 <b>${d.meta.data_date || '--'}</b>，距今 <b>${lag}</b> 天。要换一批数，只能从数据源进来。`
        : '') +
      `</span></div>`;
  }
  $('notice').innerHTML = html;
}

/* ---------------- KPI ---------------- */
function kpis(d) {
  const c = d.cost;
  const noComp = d.comparable_n === 0;
  const cards = [
    ['今日样本', NUM(d.n), `去重后 · 原始 ${d.n_raw} 条`, ''],
    ['全样本中位价', BRL(d.median), '跨品类混合，不作定价依据', 'warn'],
    ['不投流保本价', BRL(c.be_org), `投流需 ${BRL(c.be_full)}`, 'bad'],
    ['手工款可比样本', `${d.comparable_n} 条`,
      noComp ? '今天没有可比的' : `中位 ${BRL(d.comparable.median)}`, noComp ? 'bad' : 'ok'],
  ];
  $('kpis').innerHTML = cards.map(([l, v, note, k]) =>
    `<div class="kpi ${k}"><div class="lab">${l}</div><div class="val">${v}</div>
     <div class="note">${note}</div></div>`).join('');
}

function verdict(d) {
  const v = d.verdict || [];
  $('verdict').innerHTML = v.length
    ? `<div class="hd">今日判读</div>` + v.map((s) => `<p>${s}</p>`).join('')
    : `<div class="hd">今日判读</div><p>本次运行没有生成判读，请看报告原文。</p>`;
}

/* ---------------- 价格带 ---------------- */
function bands(d) {
  const bs = d.bands || [];
  const max = Math.max(1, ...bs.map((b) => b.n));
  $('bands').innerHTML = bs.map((b) => `
    <div class="band ${b.over_break_even ? 'over' : ''}">
      <div class="nm">${b.label}</div>
      <div class="track"><div class="fill" style="width:${(b.n / max) * 100}%"></div></div>
      <div class="vv"><b>${b.n}</b>${b.median == null ? '' : BRL(b.median)}</div>
    </div>`).join('');
  const lo = bs.length ? bs[0].label : '', hi = bs.length ? bs[bs.length - 1].label : '';
  $('axis').innerHTML = `<span>${lo}</span><span>深色 = 站在保本线 ${BRL(d.cost.be_org)} 以上</span><span>${hi}</span>`;
  $('bands-meta').textContent = `${d.n} 条 · 保本线以上 ${d.over_be} 条`;
}

/* ---------------- 规格 / 分层 ---------------- */
function specs(d) {
  const rows = (d.specs || []).map((s) => `
    <tr><td>${s.label}</td><td>${s.n}</td><td>${BRL(s.median)}</td>
    <td>${BRL(s.p25)} – ${BRL(s.p75)}</td><td>${BRL(s.min)} – ${BRL(s.max)}</td></tr>`).join('');
  $('specs').innerHTML = `
    <table><thead><tr><th>规格</th><th>条数</th><th>中位价</th><th>25–75 分位</th><th>区间</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
  $('spec-meta').textContent = `${(d.specs || []).length} 个分组`;

  const trs = (d.tiers || []).map((t) => `
    <tr><td>${t.label}</td><td>${t.n}</td><td>${BRL(t.median)}</td>
    <td>${BRL(t.min)} – ${BRL(t.max)}</td></tr>`).join('');
  $('tiers').innerHTML = `
    <table><thead><tr><th>分层</th><th>条数</th><th>中位价</th><th>区间</th></tr></thead>
    <tbody>${trs}</tbody></table>`;
}

/* ---------------- 盈亏曲线 ---------------- */
function econ(d) {
  const c = d.cost;
  const W = 820, H = 262, L = 48, R = 16, T = 16, B = 30;
  const xmin = 12, xmax = 88;
  const net = (p, r) => p * (1 - r) - c.fixed;
  const X = (p) => L + ((p - xmin) / (xmax - xmin)) * (W - L - R);

  const samples = [xmin, xmax];
  const ys = [];
  samples.forEach((p) => { ys.push(net(p, c.r_org), net(p, c.r_full)); });
  let ymax = Math.ceil(Math.max(...ys, 0) / 10) * 10;
  let ymin = Math.floor(Math.min(...ys, 0) / 10) * 10;
  if (ymax - ymin < 30) ymax = ymin + 30;
  const Y = (v) => T + ((ymax - v) / (ymax - ymin)) * (H - T - B);

  let grid = '', xt = '', yt = '';
  for (let v = ymin; v <= ymax; v += 10) {
    grid += `<line x1="${L}" y1="${Y(v)}" x2="${W - R}" y2="${Y(v)}"/>`;
    yt += `<text class="lbl" x="${L - 8}" y="${Y(v) + 3}" text-anchor="end">${v}</text>`;
  }
  for (let p = 20; p <= xmax - 3; p += 10) {
    xt += `<text class="lbl" x="${X(p)}" y="${H - 8}" text-anchor="middle">${p}</text>`;
  }

  const line = (r, col, dash) => `<polyline points="${X(xmin)},${Y(net(xmin, r))} ${X(xmax)},${Y(net(xmax, r))}"
    fill="none" stroke="${col}" stroke-width="2.2" ${dash ? 'stroke-dasharray="5 4"' : ''}/>`;
  // 不再填充线下面积：零轴以下那段填出来和盈利区同色，反而会让人把亏损读成收益
  const lossBand = `<rect x="${L}" y="${Y(0)}" width="${W - L - R}" height="${Y(ymin) - Y(0)}"
    fill="rgba(255,90,110,.05)"/>`;

  const mark = (p, col, label) => {
    const v = net(p, c.r_org);
    return `<circle cx="${X(p)}" cy="${Y(v)}" r="3.4" fill="${col}"/>
      <line x1="${X(p)}" y1="${Y(v)}" x2="${X(p)}" y2="${Y(0)}" stroke="${col}" stroke-width="1" stroke-dasharray="3 3" opacity=".55"/>
      <text class="lbl" x="${X(p)}" y="${Y(v) - 9}" text-anchor="middle" fill="${col}">${label} ${BRL(p)}</text>`;
  };

  $('econ-chart').innerHTML = `
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="售价与净利的关系">
      ${grid}${lossBand}
      <line class="zero" x1="${L}" y1="${Y(0)}" x2="${W - R}" y2="${Y(0)}"/>
      ${line(c.r_full, '#7c5cff', true)}${line(c.r_org, '#22d3ee', false)}
      ${mark(c.be_org, '#22d3ee', '不投流保本')}${mark(c.be_full, '#7c5cff', '投流保本')}
      ${yt}${xt}
      <text class="lbl" x="${W - R}" y="${Y(0) - 7}" text-anchor="end">零轴</text>
    </svg>
    <div class="legend">
      <span><i style="background:#22d3ee"></i>不投流（平台+税+SFP ${PCT(c.r_org, 1)}）</span>
      <span><i style="background:#7c5cff"></i>投流（再加广告+达人 ${PCT(c.r_full, 1)}）</span>
      <span style="color:#5f6478">横轴：售价 BRL　纵轴：单副净利 BRL</span>
    </div>`;

  const rows = (d.econ || []).map((e) => {
    const be = Math.abs(e.price - c.be_org) < 0.05 || Math.abs(e.price - c.be_full) < 0.05;
    const tag = Math.abs(e.price - c.be_org) < 0.05 ? '（不投流保本）'
      : Math.abs(e.price - c.be_full) < 0.05 ? '（投流保本）' : '';
    return `<tr class="${be ? 'be' : ''}"><td>${BRL(e.price)}${tag}</td><td>${BRL(c.fixed)}</td>
      <td class="${e.full < 0 ? 'neg' : 'pos'}">${e.full > 0 ? '+' : ''}${e.full.toFixed(2)}</td>
      <td class="${e.org < 0 ? 'neg' : 'pos'}">${e.org > 0 ? '+' : ''}${e.org.toFixed(2)}</td></tr>`;
  }).join('');
  $('econ-table').innerHTML = `
    <table><thead><tr><th>售价</th><th>到仓成本</th><th>投流净利</th><th>不投流净利</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
  $('econ-meta').textContent = `到仓 ${BRL(c.fixed)}`;
}

/* ---------------- 规模刻度 ---------------- */
const NUMK = (v) => (v == null ? '--' : Math.round(v).toLocaleString('en-US'));
const SGN = (v) => (v == null ? '--' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2));

function scale(d) {
  const s = d.scale;
  if (!s || !s.grid || !s.grid.length) {
    $('scale-lead').innerHTML = '<div class="empty">这一版没有生成规模刻度。</div>';
    $('scale-meta').textContent = '--';
    return;
  }
  const grid = s.grid, targets = s.targets || [];

  // 开场句：最低价档 vs 单件净利最接近十元那档，都用绝对数，不写倍数
  const lo = grid[0];
  const rest = grid.slice(1);
  const mid = rest.length ? rest.reduce((a, b) =>
    Math.abs(b.unit_org - 10) < Math.abs(a.unit_org - 10) ? b : a) : lo;
  const t = targets.length ? targets[Math.floor(targets.length / 2)] : null;
  let lead = '';
  if (t && grid.length > 1) {
    const uLo = t.by_price[grid.indexOf(lo)].units;
    const uMid = t.by_price[grid.indexOf(mid)].units;
    if (uLo && uMid) {
      lead = `<div class="verdict" style="margin:0 0 4px">
        贴着保本线定价（${BRL(lo.price)}）时单件只赚 <b class="pos">${SGN(lo.unit_org)}</b>，
        要卖 <b>${NUMK(uLo)} 单</b>才够 <b>R$ ${NUMK(t.target)}</b> 的月净利。
        把价抬到 ${BRL(mid.price)}，单件 <b class="pos">${SGN(mid.unit_org)}</b>，
        <b>${NUMK(uMid)} 单</b>就够。</div>`;
    }
  }
  $('scale-lead').innerHTML = lead;

  // 行底色按单件净利分档，一眼看出哪档的斜率最陡
  const lv = (u) => (u <= 0 ? 's-lv0' : u < 5 ? 's-lv1' : u < 15 ? 's-lv2' : 's-lv3');
  const head = s.volumes.map((v) => `<th>${NUMK(v)} 单</th>`).join('');
  const rows = grid.map((g) => {
    const cells = g.cells.map((c) => `<td class="${c < 0 ? 'neg' : 'pos'}">${NUMK(c)}</td>`).join('');
    return `<tr class="${lv(g.unit_org)}"><td>${BRL(g.price)}</td>
      <td class="${g.unit_org < 0 ? 'neg' : 'pos'}">${SGN(g.unit_org)}</td>${cells}</tr>`;
  }).join('');
  $('scale-grid').innerHTML = `
    <table><thead><tr><th>售价</th><th>单件净利</th>${head}</tr></thead><tbody>${rows}</tbody></table>
    <div class="legend" style="margin-top:10px">
      <span><i style="background:#2bd98a"></i>绿 = 这一档单件盈利</span>
      <span><i style="background:#ff5a6e"></i>红 = 每卖一副都在亏</span>
      <span style="color:#5f6478">月净利 =（售价 ×（1 − 费率）− 到仓成本）× 月单量</span>
    </div>`;

  // 反向：目标月利 → 需要多少单
  const tHead = targets.map((x) => `<th>月利 ${NUMK(x.target)}</th>`).join('');
  const tRows = grid.map((g, i) => {
    const cells = targets.map((x) => {
      const b = x.by_price[i];
      return b.units
        ? `<td>${NUMK(b.units)} 单</td>`
        : `<td style="color:#ff5a6e">到不了</td>`;
    }).join('');
    return `<tr><td>${BRL(g.price)}</td><td>${SGN(g.unit_org)}</td>${cells}</tr>`;
  }).join('');
  $('scale-need').innerHTML = `
    <table><thead><tr><th>售价</th><th>单件净利</th>${tHead}</tr></thead><tbody>${tRows}</tbody></table>
    <div class="warnbar" style="margin-top:14px"><span>
      <b>这是刻度，不是预测</b>　单量是假设出来的横轴，不含退货、滞销、活动亏损与汇率波动。
      它回答「卖到这个量账上是什么样」，不回答「能不能卖到这个量」。</span></div>`;

  $('scale-meta').textContent = `${grid.length} 档售价 × ${s.volumes.length} 档单量 · ${s.basis}口径`;
}

/* ---------------- 成本敏感性 ---------------- */
/* 一次只动一个变量。表里的区间是该变量 ±step 时保本价的落点，
   不按正负排序，只给区间，免得汇率那种反向变动的行被读错方向。 */
function sens(d) {
  const s = d.sensitivity;
  if (!s || !s.rows || !s.rows.length) {
    $('sens-lead').innerHTML = '<div class="empty">这一版没有生成敏感性表。</div>';
    $('sens-meta').textContent = '--';
    return;
  }
  const b = s.base, step = Math.round(s.step * 100);

  const pair = (a, c, fmt) => {
    if (a == null || c == null) return '--';
    const lo = Math.min(a, c), hi = Math.max(a, c);
    const one = (x) => fmt === 'fx' ? '¥' + Number(x).toFixed(2)
      : fmt === 'rate' ? (x * 100).toFixed(2) + '%' : BRL(x);
    return lo === hi ? one(lo) : one(lo) + ' – ' + one(hi);
  };
  const pairSigned = (a, c) => {
    if (a == null || c == null) return '--';
    const lo = Math.min(a, c), hi = Math.max(a, c);
    return lo === hi ? SGN(lo) : SGN(lo) + ' – ' + SGN(hi);
  };

  const rows = s.rows.map((r) => {
    const full = r.scope === 'full';
    const beLo = full ? r.be_full_low : r.be_org_low;
    const beHi = full ? r.be_full_high : r.be_org_high;
    return `<tr>
      <td>${r.label}${full ? ' <span class="tag off">仅投流口径</span>' : ''}</td>
      <td style="color:#8b91a8">${pair(r.low, r.high, r.fmt)}</td>
      <td>${pair(beLo, beHi, 'brl')}</td>
      <td><b>${r.swing.toFixed(2)}</b></td>
      <td class="${(r.net_low < 0 || r.net_high < 0) ? 'neg' : 'pos'}">${pairSigned(r.net_low, r.net_high)}</td>
    </tr>`;
  }).join('');

  const top = s.rows[0];
  $('sens-lead').innerHTML = `
    <div class="verdict" style="margin:0 0 4px">
      单看摆幅，最大的一项是 <b>${top.label}</b>，动 ${step}% 就让每副的保本线挪 <b>${BRL(top.swing)}</b>。
      但摆幅最大不等于最该动：汇率是被动风险，砍不动；采购价是唯一既动得大又谈得下来的。
      想降价，先谈采购，再谈头程，最后才是费率。</div>`;

  $('sens-table').innerHTML = `
    <table><thead><tr>
      <th>驱动项</th><th>该项 ±${step}%</th>
      <th>保本价落在（不投流）</th><th>摆幅</th>
      <th>${BRL(s.anchor)} 时单件净利</th>
    </tr></thead><tbody>${rows}</tbody></table>
    <div class="legend" style="margin-top:10px">
      <span style="color:#5f6478">摆幅 = 该项单独动 ${step}% 时保本价的变动额，其余变量按住不动</span>
    </div>
    <div class="warnbar" style="margin-top:14px"><span>
      <b>摆幅不能相加</b>　汇率与采购是同一笔钱的两个视角，两项同时动不等于两数相加。
      这是排优先级用的尺子，不是预测。</span></div>`;

  $('sens-meta').textContent = `${s.rows.length} 项 · 单项 ±${step}% · 基准 ${BRL(b.be_org)}`;
}

/* ---------------- 手工款对标 ---------------- */
function comp(d) {
  const c = d.cost, n = d.comparable_n;
  if (!n) {
    $('comp').innerHTML = `<div class="empty">
      今天没有 10 片手工甲的可比样本。要建这个池子，需要 Kalodata 导出或客户提供竞品清单。<br>
      在没有这组样本之前，任何「该定多少钱」的结论都是猜的。</div>`;
    $('comp-meta').textContent = '0 条';
    return;
  }
  const s = d.comparable;
  const net = s.median * (1 - c.r_org) - c.fixed;
  const items = (d.comparable_items || []).map((x) => `
    <tr><td>${x.title}</td><td>${BRL(x.price)}</td><td style="color:#8b91a8">${PLATFORM[x.platform] || x.platform}</td></tr>`).join('');
  $('comp').innerHTML = `
    <div class="kpis" style="margin:0 0 16px">
      <div class="kpi"><div class="lab">样本</div><div class="val">${s.n}</div><div class="note">手工/定制款</div></div>
      <div class="kpi"><div class="lab">中位价</div><div class="val">${BRL(s.median)}</div>
        <div class="note">${BRL(s.p25)} – ${BRL(s.p75)}</div></div>
      <div class="kpi ${net >= 0 ? 'ok' : 'bad'}"><div class="lab">按中位价卖 · 不投流净利</div>
        <div class="val">${net >= 0 ? '+' : ''}${net.toFixed(2)}</div><div class="note">已扣 ${BRL(c.fixed)} 到仓</div></div>
      <div class="kpi"><div class="lab">相对不投流保本</div><div class="val">${(s.median / c.be_org).toFixed(2)}×</div>
        <div class="note">保本 ${BRL(c.be_org)}</div></div>
    </div>
    <table><thead><tr><th>商品</th><th>挂牌价</th><th>平台</th></tr></thead><tbody>${items}</tbody></table>
    ${s.n < 5 ? `<div class="warnbar"><span><b>样本不足</b>　${s.n} 条且部分同价，只能当价格上限看。补到 20 条以上再谈定价。</span></div>` : ''}`;
  $('comp-meta').textContent = `${s.n} 条 · 中位 ${BRL(s.median)}`;
}

/* ---------------- 数据源 ---------------- */
function srcs(d) {
  $('srcs').innerHTML = (d.sources || []).map((s) => {
    const [cn, cls, dot] = STATUS[s.status] || ['未知', 'off', 's-off'];
    return `<div class="src">
      <div><span class="dot ${dot}"></span>${s.name}</div>
      <div><span class="tag ${cls}">${cn}</span></div>
      <div style="color:#8b91a8">${s.records} 条</div>
      <div class="why">${s.reason || ''}</div>
    </div>`;
  }).join('');
  const okN = (d.sources || []).filter((s) => s.status === 'ok').length;
  $('src-meta').textContent = `${okN}/${d.sources.length} 路有数`;

  if (d.snapshot_rate < 0.99) {
    $('warn').innerHTML = `<div class="warnbar"><span>
      <b>证据链缺口</b>　快照留存 ${PCT(d.snapshot_rate)}。记录里没有当时的页面快照，
      客户点开链接看到的价格可能和表里不一致，而我们拿不出截图。补快照是下一版的头号任务。</span></div>`;
  } else {
    $('warn').innerHTML = '';
  }
}

/* ---------------- 归档 ---------------- */
function runs(d, list) {
  if (!list.length) {
    $('runs').innerHTML = `<div class="empty">还没有历史快照，明天这时会有第二份。</div>`;
  } else {
    $('runs').innerHTML = list.slice().reverse().map((r) => {
      // 数据没变的那几版要标出来。否则归档看上去像每天都在更新，
      // 其实只是同一批数又算了一遍。
      const mark = r.changed === false ? ' <span class="tag off">未变</span>'
        : r.changed === true ? ' <span class="tag ok">有变</span>' : '';
      return `
      <div class="run">
        <div class="d">${r.date}</div>
        <div>${r.n} 条${mark}</div>
        <div>${BRL(r.median)}</div>
        <div>保本线以上 ${PCT(r.over_be_ratio)} · 源 ${r.sources_ok}/${r.sources_total}
          ${r.data_date ? ` · 观测日 ${r.data_date}` : ''}</div>
        <div><a href="${r.report || 'reports/' + r.date + '.html'}">日报</a></div>
      </div>`;
    }).join('');
  }
  $('runs-meta').textContent = `${list.length} 份快照`;
}

function foot(d) {
  const c = d.cost, m = d.meta;
  $('foot').innerHTML = `
    <b>口径</b>　${c.status}。全部金额为巴西雷亚尔，参考汇率 R$1 ≈ ¥${c.fx}。<br>
    <b>不可比</b>　自家 ${c.product}，市场样本以 24 片机器甲为主，两者不能相减。本页不给"该定多少钱"的结论，只给成本线与行情分布。<br>
    <b>生成</b>　${m.generated_at} · 管线自动生成，未经人工改写 · 版本 v${m.version} / schema ${m.schema}<br>
    <b>码尺 CodeScale</b>　${m.tagline} · 每日 ${(m.schedule && m.schedule.cron) || '20:00'} 自动更新`;
}

(async function () {
  const got = await load();
  if (!got) {
    $('sub').textContent = '没有找到数据。先在项目根目录跑 python pipeline/run.py。';
    $('stamp').innerHTML = '<span>无数据</span>';
    return;
  }
  const { data, runs: list } = got;
  head(data); notice(data); kpis(data); verdict(data); bands(data); specs(data);
  econ(data); scale(data); sens(data); comp(data); srcs(data); runs(data, list); foot(data);
})();
