/* 分析报告页：把每期快照按报告章节展开，并链接同源生成的 Word 版本。
   页面中不计算业务指标，所有数字来自快照字段。 */
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var BRL = function (v) { return v == null ? '--' : 'R$ ' + Number(v).toFixed(2); };
  var PCT = function (v, d) { return v == null ? '--' : (Number(v) * 100).toFixed(d == null ? 0 : d) + '%'; };
  var NUM = function (v) { return v == null ? '--' : Number(v).toLocaleString('pt-BR'); };
  var SIGN = function (v) {
    if (v == null) return '--';
    var n = Number(v);
    return (n > 0 ? '+' : n < 0 ? '\u2212' : '') + Math.abs(n).toFixed(2);
  };
  var SSTATUS = { ok: '已接入', empty: '无新数据', not_configured: '待配置',
    disabled: '未接入', blocked: '被拦截', error: '出错' };
  var esc = function (s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  };

  var TOC = [
    ['r-conc', '结论'], ['r-kpi', '关键指标'], ['r-cost', '成本'], ['r-band', '价格带'],
    ['r-spec', '规格分层'], ['r-econ', '盈亏'], ['r-scale', '规模'], ['r-sens', '敏感性'],
    ['r-move', '异动'], ['r-src', '数据可靠性'], ['r-note', '口径']
  ];
  $('toc').innerHTML = TOC.map(function (x) {
    return '<a href="#' + x[0] + '">' + x[1] + '</a>';
  }).join('');

  function tbl(headers, rows) {
    if (!headers.length) return '';
    return '<div class="tscroll"><table><thead><tr>' + headers.map(function (h) {
      return '<th>' + esc(h) + '</th>';
    }).join('') + '</tr></thead><tbody>' + rows.map(function (r) {
      return '<tr>' + r.map(function (v) { return '<td>' + v + '</td>'; }).join('') + '</tr>';
    }).join('') + '</tbody></table></div>';
  }
  function lead(html) { return '<p class="lead" style="margin-top:14px">' + html + '</p>'; }

  function conclusions(d) {
    var c = d.cost, out = [], comp = d.comparable;
    if (!d.comparable_n) {
      out.push('本期样本中无 10 片手工甲记录，对标产品当前无可比价格。以下市场价仅作行情参考，不作为定价依据。');
    } else {
      var net = Math.round((comp.median * (1 - c.r_org) - c.fixed) * 100) / 100;
      out.push('10 片手工甲／手工款样本 ' + comp.n + ' 条，中位 ' + BRL(comp.median) +
        '（' + BRL(comp.p25) + '–' + BRL(comp.p75) + '）。按该价位销售，不投流' +
        (net >= 0 ? '净利 ' + SIGN(net) : '每副亏损 ' + BRL(Math.abs(net))) + '。');
      if (comp.n < 5) out.push('该组样本仅 ' + comp.n + ' 条且部分同价，仅可作为价格上限参考，不足以支撑定价。样本需补充至 20 条以上后再进行定价分析。');
    }
    out.push('到仓成本 ' + BRL(c.fixed) + '，不投流保本 ' + BRL(c.be_org) + '，投流保本 ' + BRL(c.be_full) +
      '。全样本 ' + d.n + ' 条报价里，' + d.over_be + ' 条（' + PCT(d.over_be_ratio) + '）站在不投流保本线以上，' +
      d.over_be_full + ' 条（' + PCT(d.over_be_full_ratio) + '）站在投流保本线以上。');
    var u = d.urls || {}, link;
    if (!u.is_item_level) {
      link = d.n + ' 条记录对应 ' + u.total + ' 个链接，其中指向具体商品的为 ' + u.item_links +
        ' 个，其余为搜索列表页和店铺首页。其中 ' + u.item_records + ' 条（' + PCT(u.item_ratio) +
        '）可回溯至对应商品页面，其余记录无法核对价格来源。';
    } else if (d.snapshot_rate < 0.99) {
      link = '链接指向单品，但未保存页面快照，无法提供采集时的截图佐证。';
    } else {
      link = '每条记录均可回溯至采集时页面。';
    }
    out.push('数据侧：' + d.sources_total + ' 路源里 ' +
      (d.sources || []).filter(function (s) { return s.status === 'ok'; }).length +
      ' 路有数，快照留存率 ' + PCT(d.snapshot_rate, 0) + '。' + link);
    return out;
  }

  function fmtPair(a, b, fmt) {
    if (a == null || b == null) return '--';
    var lo = Math.min(a, b), hi = Math.max(a, b), one;
    if (fmt === 'fx') one = function (x) { return '¥' + x.toFixed(2); };
    else if (fmt === 'rate') one = function (x) { return (x * 100).toFixed(2) + '%'; };
    else one = BRL;
    return Math.abs(hi - lo) < 1e-9 ? one(lo) : one(lo) + ' – ' + one(hi);
  }

  function render(d) {
    var c = d.cost, m = d.meta;

    $('sub').textContent = m.run_date + ' 生成 · 数据观测日 ' + (m.data_date || '--') +
      ' · 样本 ' + d.n + ' 条 · 口径 ' + c.product;
    var ok = (d.sources || []).filter(function (s) { return s.status === 'ok'; }).length;
    $('stamp').innerHTML = '<span class="pulse"></span><span>数据 ' +
      (m.freshness_days == null ? '--' : m.freshness_days <= 1 ? '今日' : m.freshness_days + ' 天前') +
      ' · 源 ' + ok + '/' + (d.sources || []).length + '</span>';

    var x = d.delta || {};
    if (!x.has_prev) {
      $('banner').innerHTML = '<div class="warnbar"><span><b>首份快照</b>　无上一版本可供比较。后续版本将显示样本数、商品与价格的变动。</span></div>';
    } else if (x.changed === false) {
      $('banner').innerHTML = '<div class="warnbar"><span><b>本版无新增数据</b>　本次运行未获取到新记录，样本数、商品与价格与 ' +
        (x.prev_date || '上一版本') + ' 逐项一致。当前内容为既有数据的重新统计。数据观测日仍为 ' +
        (m.data_date || '--') + '，距今 ' + m.freshness_days + ' 天。</span></div>';
    } else {
      $('banner').innerHTML = '';
    }

    $('conc').innerHTML = '<div class="hd">全部结论由快照数字驱动</div>' +
      conclusions(d).map(function (t) { return '<p>' + t + '</p>'; }).join('');

    var kp = [
      ['本期样本', d.n + ' 条', '去重后 · 原始 ' + d.n_raw, ''],
      ['全样本中位价', BRL(d.median), '跨品类混合，不作定价依据', 'warn'],
      ['不投流保本价', BRL(c.be_org), '投流需 ' + BRL(c.be_full), 'bad'],
      ['可比样本', d.comparable_n + ' 条', '10 片或手工款', d.comparable_n ? 'ok' : 'bad']
    ];
    $('kpis').innerHTML = kp.map(function (v) {
      return '<div class="kpi ' + v[3] + '"><div class="lab">' + v[0] + '</div>' +
        '<div class="val">' + v[1] + '</div><div class="note">' + v[2] + '</div></div>';
    }).join('');

    $('cost-body').innerHTML =
      tbl(['成本项', '金额'], c.parts.map(function (v) { return [esc(v[0]), BRL(v[1])]; })) +
      lead('到仓成本 <b>' + BRL(c.fixed) + '</b> ＝ 采购 ＋ 头程 ＋ 仓储。费率如下（占售价）：') +
      tbl(['费率项', '比例'], c.rates.map(function (v) { return [esc(v[0]), PCT(v[1], 2)]; })) +
      '<p class="rnote">不投流口径只含平台佣金、税、SFP 包邮；投流口径再加广告与达人。</p>';

    $('band-body').innerHTML = tbl(['价格带', '条数', '中位价', '高于不投流保本线'],
      d.bands.map(function (b) {
        return [esc(b.label), b.n, BRL(b.median), b.over_break_even ? '是' : '否'];
      }));

    $('spec-body').innerHTML = tbl(['规格', '条数', '中位价', '25–75 分位', '区间'],
      d.specs.map(function (s) {
        return [esc(s.label), s.n, BRL(s.median), BRL(s.p25) + '–' + BRL(s.p75), BRL(s.min) + '–' + BRL(s.max)];
      }));
    $('tier-body').innerHTML = lead('按品牌溢价分层：') +
      tbl(['分层', '条数', '中位价', '区间'], d.tiers.map(function (t) {
        return [esc(t.label), t.n, BRL(t.median), BRL(t.min) + '–' + BRL(t.max)];
      }));

    $('econ-body').innerHTML = tbl(['售价', '到仓成本', '投流净利', '不投流净利'],
      d.econ.map(function (e) {
        var mark = '';
        if (Math.abs(e.price - c.be_org) < 0.05) mark = '（不投流保本）';
        else if (Math.abs(e.price - c.be_full) < 0.05) mark = '（投流保本）';
        return [BRL(e.price) + mark, BRL(c.fixed), SIGN(e.full), SIGN(e.org)];
      }));

    var sc = d.scale || {};
    if (sc.grid && sc.grid.length) {
      var lo = sc.grid[0], mid = sc.grid.slice(1).reduce(function (a, b) {
        return Math.abs(b.unit_org - 10) < Math.abs(a.unit_org - 10) ? b : a;
      });
      var tg = (sc.targets || [])[Math.floor((sc.targets || []).length / 2)];
      $('scale-lead').textContent = tg ? ('按 ' + BRL(lo.price) + ' 定价时，单件净利为 ' + SIGN(lo.unit_org) +
        '，达到 R$' + NUM(tg.target) + ' 的月净利需 ' + NUM(tg.by_price[0].units) + ' 单；定价提高至 ' +
        BRL(mid.price) + ' 后，单件净利 ' + SIGN(mid.unit_org) + '，所需单量为 ' +
        NUM(tg.by_price[sc.grid.indexOf(mid)].units) + ' 单。') : '按价位列示单件净利与月净利所需的单量。';
      $('scale-body').innerHTML =
        tbl(['售价', '单件净利'].concat((sc.volumes || []).map(function (v) { return NUM(v) + ' 单'; })),
          sc.grid.map(function (g) {
            return [BRL(g.price), SIGN(g.unit_org)].concat(g.cells.map(function (v) { return NUM(v); }));
          })) +
        lead('达到目标月净利所需单量，按价位列示：') +
        tbl(['售价', '单件净利'].concat((sc.targets || []).map(function (t) { return '月利 ' + NUM(t.target); })),
          sc.grid.map(function (g, i) {
            return [BRL(g.price), SIGN(g.unit_org)].concat((sc.targets || []).map(function (t) {
              var u = t.by_price[i].units;
              return u ? NUM(u) + ' 单' : '无法达到';
            }));
          })) +
        '<p class="rnote">单量为假设的横轴变量，不含退货、滞销、平台活动亏损与汇率波动。本表回答「达到该销量时账目结果如何」，不回答「能否达到该销量」。</p>';
    } else {
      $('scale-body').innerHTML = '<div class="empty">本期无规模刻度数据。</div>';
    }

    var se = d.sensitivity || {};
    if (se.rows && se.rows.length) {
      $('sens-body').innerHTML = tbl(['驱动项', '该项 ±10%', '保本价落在', '摆幅', 'R$ 39.90 时单件净利'],
        se.rows.map(function (r) {
          var full = r.scope === 'full';
          var bk = full ? ['be_full_low', 'be_full_high'] : ['be_org_low', 'be_org_high'];
          var nk = full ? ['net_full_low', 'net_full_high'] : ['net_low', 'net_high'];
          return [esc(r.label) + (full ? '（投流口径）' : ''),
            fmtPair(r.low, r.high, r.fmt),
            BRL(Math.min(r[bk[0]], r[bk[1]])) + ' – ' + BRL(Math.max(r[bk[0]], r[bk[1]])),
            '<b>' + r.swing.toFixed(2) + '</b>',
            SIGN(Math.min(r[nk[0]], r[nk[1]])) + ' – ' + SIGN(Math.max(r[nk[0]], r[nk[1]]))];
        })) + '<p class="rnote">摆幅不可相加。汇率与采购成本构成同一笔支出的两个视角。本表不构成预测。</p>';
    } else {
      $('sens-body').innerHTML = '<div class="empty">本期无敏感性数据。</div>';
    }

    var mv = d.movers || [];
    $('move-body').innerHTML = mv.length
      ? tbl(['商品', '上一版', '本版', '变动'], mv.map(function (v) {
          return [esc(v.title || v.name || ''), BRL(v.old), BRL(v.new), SIGN((v.new || 0) - (v.old || 0))];
        }))
      : '<div class="empty">本次运行无上一版本可供比较，或变动绝对值未达 R$0.50。</div>';

    $('src-body').innerHTML = tbl(['数据源', '状态', '条数', '说明'],
      (d.sources || []).map(function (s) {
        return [esc(s.name), SSTATUS[s.status] || s.status, s.records || 0, esc(s.reason || '')];
      }));

    $('note-body').innerHTML = '<p class="lead">' +
      '<b>口径</b>　' + esc(c.status) + '。全部金额为巴西雷亚尔，参考汇率 R$1 ≈ ¥' + c.fx + '。<br>' +
      '<b>不能得出的结论</b>　全市场销量排名、哪个价格带成交最多、哪类款式在爆发、评论比例代表整体偏好。这几项需要连续多日样本与成交数据。<br>' +
      '<b>可比性</b>　对标产品为 ' + esc(c.product) + '，市场样本以 24 片机器甲为主，两者不可直接相减。<br>' +
      '<b>生成</b>　' + esc(m.generated_at) + ' · 管线自动生成，未经人工改写 · 版本 v' + m.version +
      '</p>';

    $('foot').innerHTML = '<b>报告</b>　' + m.run_date + ' · 数据观测日 ' + (m.data_date || '--') +
      '<br><b>Word 版</b>　与本章节同源生成，口径一致。' +
      '<br><b>码尺 CodeScale</b>　' + esc(m.tagline);
  }

  var m0 = window.__CODESCALE__;
  if (!m0 || !m0.data) {
    $('sub').textContent = '未找到数据文件。请在项目根目录执行 python pipeline/run.py。';
    $('stamp').innerHTML = '<span>无数据</span>';
    return;
  }
  var runs = m0.runs || [];
  var sel = $('period');
  runs.forEach(function (r, i) {
    var o = document.createElement('option');
    o.value = r.date;
    o.textContent = r.date + (r.data_date ? ' · 观测 ' + r.data_date : '') + (r.changed === false ? ' · 无新增' : '');
    if (i === runs.length - 1) o.selected = true;
    sel.appendChild(o);
  });
  if (!runs.length) {
    var o = document.createElement('option');
    o.value = m0.data.meta.run_date;
    o.textContent = m0.data.meta.run_date;
    sel.appendChild(o);
  }

  function setLinks(date) {
    $('dl').href = 'reports/' + date + '.docx';
    $('dl').setAttribute('download', '码尺日报_' + date + '.docx');
    $('raw').href = 'reports/' + date + '.html';
  }
  setLinks(sel.value || m0.data.meta.run_date);
  render(m0.data);

  sel.addEventListener('change', function () {
    var date = sel.value;
    setLinks(date);
    if (date === m0.data.meta.run_date) { render(m0.data); return; }
    fetch('data/history/' + date + '.json', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () { $('sub').textContent = '该期快照读取失败，请查看印刷版。'; });
  });
})();
