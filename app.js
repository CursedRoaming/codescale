/* 码尺 CodeScale · 前端
   无依赖、无构建。所有数字来自 data/latest.json，本页不计算业务指标，
   仅负责呈现既有数据。计算逻辑位于 pipeline/core。 */

const $ = (id) => document.getElementById(id);
const BRL = (v) => (v == null ? '--' : 'R$ ' + Number(v).toFixed(2));
const PCT = (v, d = 0) => (v == null ? '--' : (v * 100).toFixed(d) + '%');
const NUM = (v) => (v == null ? '--' : Number(v).toLocaleString('pt-BR'));
/* 颜色从主题变量读，切换主题时图表随之变化。 */
const CV = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const C_ACC = () => CV('--acc');
const C_ACC2 = () => CV('--acc2');
const C_UP = () => CV('--up');
const C_DOWN = () => CV('--down');
const C_DIM = () => CV('--dim');
const C_DIM2 = () => CV('--dim2');

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
      } catch (e) { /* 归档缺失不影响主页面 */ }
      return { data, runs };
    }
  } catch (e) { /* file:// 场景 */ }
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
/* 仅在本次运行无新增内容时显示。定时任务每日执行，数据源未接通时结果相同，
   该状态需在页面显著位置标明。 */
function notice(d) {
  const x = d.delta || {};
  const lag = d.meta.freshness_days;
  let html = '';
  if (!x.has_prev) {
    html = `<div class="warnbar"><span><b>首份快照</b>　无上一版本可供比较。后续版本将显示样本数、商品与价格的变动。</span></div>`;
  } else if (x.changed === false) {
    html = `<div class="warnbar"><span><b>本版无新增数据</b>　本次运行未获取到新记录，
      样本数、商品与价格与 ${x.prev_date || '上一版本'} 逐项一致。当前内容为既有数据的重新统计。` +
      (lag != null && lag >= 3
        ? `　数据观测日仍为 <b>${d.meta.data_date || '--'}</b>，距今 <b>${lag}</b> 天。数据更新需通过数据源接入。`
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
    ['本期样本', NUM(d.n), `去重后 · 原始 ${d.n_raw} 条`, ''],
    ['全样本中位价', BRL(d.median), '跨品类混合，不作定价依据', 'warn'],
    ['不投流保本价', BRL(c.be_org), `投流需 ${BRL(c.be_full)}`, 'bad'],
    ['手工款可比样本', `${d.comparable_n} 条`,
      noComp ? '暂无可比样本' : `中位 ${BRL(d.comparable.median)}`, noComp ? 'bad' : 'ok'],
  ];
  $('kpis').innerHTML = cards.map(([l, v, note, k]) =>
    `<div class="kpi ${k}"><div class="lab">${l}</div><div class="val">${v}</div>
     <div class="note">${note}</div></div>`).join('');
}

function verdict(d) {
  const v = d.verdict || [];
  $('verdict').innerHTML = v.length
    ? `<div class="hd">本期判读</div>` + v.map((s) => `<p>${s}</p>`).join('')
    : `<div class="hd">本期判读</div><p>本次运行未生成判读内容，详见日报。</p>`;
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
  $('axis').innerHTML = `<span>${lo}</span><span>深色：高于不投流保本价 ${BRL(d.cost.be_org)}</span><span>${hi}</span>`;
  $('bands-meta').textContent = `${d.n} 条 · 保本价以上 ${d.over_be} 条`;
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
  // 零轴以下区域使用浅色底纹，与盈利区区分
  const lossBand = `<rect x="${L}" y="${Y(0)}" width="${W - L - R}" height="${Y(ymin) - Y(0)}"
    fill="rgba(var(--up-rgb),.05)"/>`;

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
      ${line(c.r_full, C_ACC(), true)}${line(c.r_org, C_ACC2(), false)}
      ${mark(c.be_org, C_ACC2(), '不投流保本')}${mark(c.be_full, C_ACC(), '投流保本')}
      ${yt}${xt}
      <text class="lbl" x="${W - R}" y="${Y(0) - 7}" text-anchor="end">零轴</text>
    </svg>
    <div class="legend">
      <span><i style="background:var(--acc2)"></i>不投流（平台+税+SFP ${PCT(c.r_org, 1)}）</span>
      <span><i style="background:var(--acc)"></i>投流（含广告+达人 ${PCT(c.r_full, 1)}）</span>
      <span style="color:var(--dim2)">横轴：售价 BRL　纵轴：单副净利 BRL</span>
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
    $('scale-lead').innerHTML = '<div class="empty">本版未生成规模刻度。</div>';
    $('scale-meta').textContent = '--';
    return;
  }
  const grid = s.grid, targets = s.targets || [];

  // 取最低价档与单件净利最接近十元的一档做对比，使用绝对数值
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
        按 ${BRL(lo.price)} 定价时，单件净利为 <b class="pos">${SGN(lo.unit_org)}</b>，
        达到 <b>R$ ${NUMK(t.target)}</b> 的月净利需 <b>${NUMK(uLo)} 单</b>。
        定价提高至 ${BRL(mid.price)} 后，单件净利 <b class="pos">${SGN(mid.unit_org)}</b>，
        所需单量为 <b>${NUMK(uMid)} 单</b>。</div>`;
    }
  }
  $('scale-lead').innerHTML = lead;

  // 行底色按单件净利分档
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
      <span><i style="background:var(--down)"></i>绿色：该档位单件盈利</span>
      <span><i style="background:var(--up)"></i>红色：该档位单件亏损</span>
      <span style="color:var(--dim2)">月净利 =（售价 ×（1 − 费率）− 到仓成本）× 月单量</span>
    </div>`;

  // 反向：目标月利 → 需要多少单
  const tHead = targets.map((x) => `<th>月利 ${NUMK(x.target)}</th>`).join('');
  const tRows = grid.map((g, i) => {
    const cells = targets.map((x) => {
      const b = x.by_price[i];
      return b.units
        ? `<td>${NUMK(b.units)} 单</td>`
        : `<td style="color:var(--up)">无法达到</td>`;
    }).join('');
    return `<tr><td>${BRL(g.price)}</td><td>${SGN(g.unit_org)}</td>${cells}</tr>`;
  }).join('');
  $('scale-need').innerHTML = `
    <table><thead><tr><th>售价</th><th>单件净利</th>${tHead}</tr></thead><tbody>${tRows}</tbody></table>
    <div class="warnbar" style="margin-top:14px"><span>
      <b>刻度说明</b>　单量为假设的横轴变量，不含退货、滞销、活动亏损与汇率波动。
      本表回答「达到该销量时账目结果如何」，不回答「能否达到该销量」。</span></div>`;

  $('scale-meta').textContent = `${grid.length} 档售价 × ${s.volumes.length} 档单量 · ${s.basis}口径`;
}

/* ---------------- 成本敏感性 ---------------- */
/* 每次仅变动一个变量。表中区间为该变量 ±step 时保本价的落点，
   按变量列出而非按正负排序，避免反向变动的行被误读。 */
function sens(d) {
  const s = d.sensitivity;
  if (!s || !s.rows || !s.rows.length) {
    $('sens-lead').innerHTML = '<div class="empty">本版未生成敏感性表。</div>';
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
    const nLo = full ? r.net_full_low : r.net_low;
    const nHi = full ? r.net_full_high : r.net_high;
    return `<tr>
      <td>${r.label}${full ? ' <span class="tag off">投流口径</span>' : ''}</td>
      <td style="color:var(--dim)">${pair(r.low, r.high, r.fmt)}</td>
      <td>${pair(beLo, beHi, 'brl')}</td>
      <td><b>${r.swing.toFixed(2)}</b></td>
      <td class="${(nLo < 0 || nHi < 0) ? 'neg' : 'pos'}">${pairSigned(nLo, nHi)}</td>
    </tr>`;
  }).join('');

  const top = s.rows[0];
  $('sens-lead').innerHTML = `
    <div class="verdict" style="margin:0 0 4px">
      按摆幅排序，影响最大的一项为 <b>${top.label}</b>，变动 ${step}% 时保本价移动 <b>${BRL(top.swing)}</b>。
      摆幅用于确定关注优先级：汇率属于外部因素，不可直接调整；采购价属于可协商项。
      成本管控的优先顺序为采购价、头程运费、费率。</div>`;

  $('sens-table').innerHTML = `
    <table><thead><tr>
      <th>驱动项</th><th>该项 ±${step}%</th>
      <th>保本价落在</th><th>摆幅</th>
      <th>${BRL(s.anchor)} 时单件净利</th>
    </tr></thead><tbody>${rows}</tbody></table>
    <div class="legend" style="margin-top:10px">
      <span style="color:var(--dim2)">摆幅：该变量单独变动 ${step}% 时保本价的变化额，其余变量保持不变</span>
    </div>
    <div class="warnbar" style="margin-top:14px"><span>
      <b>摆幅不可相加</b>　汇率与采购成本构成同一笔支出的两个视角，两项同时变动不等于两者相加。
      本表用于确定关注顺序，不构成预测。</span></div>`;

  $('sens-meta').textContent = `${s.rows.length} 项 · 单项 ±${step}% · 基准 ${BRL(b.be_org)}`;
}

/* ---------------- 手工款对标 ---------------- */
function comp(d) {
  const c = d.cost, n = d.comparable_n;
  if (!n) {
    $('comp').innerHTML = `<div class="empty">
      本版无 10 片手工甲可比样本。建立该样本池需通过 Kalodata 导出，或由客户提供竞品清单。<br>
      缺少该类样本时，不给出定价结论。</div>`;
    $('comp-meta').textContent = '0 条';
    return;
  }
  const s = d.comparable;
  const net = s.median * (1 - c.r_org) - c.fixed;
  const items = (d.comparable_items || []).map((x) => `
    <tr><td>${x.title}</td><td>${BRL(x.price)}</td><td style="color:var(--dim)">${PLATFORM[x.platform] || x.platform}</td></tr>`).join('');
  $('comp').innerHTML = `
    <div class="kpis" style="margin:0 0 16px">
      <div class="kpi"><div class="lab">样本</div><div class="val">${s.n}</div><div class="note">手工或定制款</div></div>
      <div class="kpi"><div class="lab">中位价</div><div class="val">${BRL(s.median)}</div>
        <div class="note">${BRL(s.p25)} – ${BRL(s.p75)}</div></div>
      <div class="kpi ${net >= 0 ? 'ok' : 'bad'}"><div class="lab">按中位价销售 · 不投流净利</div>
        <div class="val">${net >= 0 ? '+' : ''}${net.toFixed(2)}</div><div class="note">已扣除 ${BRL(c.fixed)} 到仓成本</div></div>
      <div class="kpi"><div class="lab">相对不投流保本价</div><div class="val">${(s.median / c.be_org).toFixed(2)}×</div>
        <div class="note">保本价 ${BRL(c.be_org)}</div></div>
    </div>
    <table><thead><tr><th>商品</th><th>挂牌价</th><th>平台</th></tr></thead><tbody>${items}</tbody></table>
    ${s.n < 5 ? `<div class="warnbar"><span><b>样本量不足</b>　当前 ${s.n} 条且部分同价，仅可作为价格上限参考。样本达到 20 条以上后再进行定价分析。</span></div>` : ''}`;
  $('comp-meta').textContent = `${s.n} 条 · 中位 ${BRL(s.median)}`;
}

/* ---------------- 数据源 ---------------- */
function srcs(d) {
  $('srcs').innerHTML = (d.sources || []).map((s) => {
    const [cn, cls, dot] = STATUS[s.status] || ['未知', 'off', 's-off'];
    return `<div class="src">
      <div><span class="dot ${dot}"></span>${s.name}</div>
      <div><span class="tag ${cls}">${cn}</span></div>
      <div style="color:var(--dim)">${s.records} 条</div>
      <div class="why">${s.reason || ''}</div>
    </div>`;
  }).join('');
  const okN = (d.sources || []).filter((s) => s.status === 'ok').length;
  $('src-meta').textContent = `${okN}/${d.sources.length} 路有数`;

  if (d.snapshot_rate < 0.99) {
    $('warn').innerHTML = `<div class="warnbar"><span>
      <b>证据链缺口</b>　快照留存率 ${PCT(d.snapshot_rate)}。记录缺少采集时的页面快照，
      链接所示价格可能与表内数据不一致，且无法提供截图佐证。补充页面快照为后续版本的优先事项。</span></div>`;
  } else {
    $('warn').innerHTML = '';
  }
}

/* ---------------- 归档 ---------------- */
function runs(d, list) {
  if (!list.length) {
    $('runs').innerHTML = `<div class="empty">暂无历史快照。</div>`;
  } else {
    $('runs').innerHTML = list.slice().reverse().map((r) => {
      // 数据未变化的版本需明确标记，避免归档看起来每日都在更新
      const mark = r.changed === false ? ' <span class="tag off">未变</span>'
        : r.changed === true ? ' <span class="tag ok">有变</span>' : '';
      return `
      <div class="run">
        <div class="d">${r.date}</div>
        <div>${r.n} 条${mark}</div>
        <div>${BRL(r.median)}</div>
        <div>保本价以上 ${PCT(r.over_be_ratio)} · 源 ${r.sources_ok}/${r.sources_total}
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
    <b>不可比</b>　对标产品为 ${c.product}，市场样本以 24 片机器甲为主，两者不可直接相减。本页不提供定价结论，仅提供成本线与行情分布。<br>
    <b>生成</b>　${m.generated_at} · 管线自动生成，未经人工改写 · 版本 v${m.version} / schema ${m.schema}<br>
    <b>码尺 CodeScale</b>　${m.tagline} · 每日 ${(m.schedule && m.schedule.cron) || '20:00'} 自动更新`;
}

let CS_STATE = null;
function paint(got) {
  const { data, runs: list } = got;
  head(data); notice(data); kpis(data); verdict(data); bands(data); specs(data);
  econ(data); scale(data); sens(data); comp(data); srcs(data); runs(data, list); foot(data);
}
// 主题切换后重绘图表，让 SVG 线条随 CSS 变量换色
window.CSRedraw = function () { if (CS_STATE) paint(CS_STATE); };

(async function () {
  const got = await load();
  if (!got) {
    $('sub').textContent = '未找到数据文件。请在项目根目录执行 python pipeline/run.py。';
    $('stamp').innerHTML = '<span>无数据</span>';
    return;
  }
  CS_STATE = got;
  paint(got);
})();
