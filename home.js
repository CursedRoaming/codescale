/* 首页：只读取 latest.js 暴露的快照，不在此计算业务指标。 */
(function () {
  var m = window.__CODESCALE__;
  if (!m || !m.data) {
    document.getElementById('sub').textContent = '未找到数据文件。请在项目根目录执行 python pipeline/run.py。';
    document.getElementById('stamp').innerHTML = '<span>无数据</span>';
    return;
  }
  var d = m.data, c = d.cost, meta = d.meta;
  var BRL = function (v) { return v == null ? '--' : 'R$ ' + Number(v).toFixed(2); };
  var ok = (d.sources || []).filter(function (s) { return s.status === 'ok'; }).length;
  var lag = meta.freshness_days;

  document.getElementById('stamp').innerHTML = '<span class="pulse"></span><span>数据 ' +
    (lag == null ? '--' : lag <= 1 ? '今日' : lag + ' 天前') + ' · 源 ' + ok + '/' + (d.sources || []).length + '</span>';
  document.getElementById('sub').textContent = '面向巴西市场的商品行情、成本线与保本价测算。当前快照：样本 ' +
    d.n + ' 条 · 观测日 ' + ((d.observed_dates || []).join('、') || '--') +
    (lag == null ? '' : ' · 距今 ' + lag + ' 天') + '。';

  var cards = [
    ['本期样本', d.n + ' 条', '去重后 · 原始 ' + d.n_raw, ''],
    ['全样本中位价', BRL(d.median), '跨品类混合，不作定价依据', 'warn'],
    ['不投流保本价', BRL(c.be_org), '投流需 ' + BRL(c.be_full), 'bad'],
    ['可比样本', d.comparable_n + ' 条', '10 片或手工款', d.comparable_n ? 'ok' : 'bad']
  ];
  document.getElementById('kpis').innerHTML = cards.map(function (x) {
    return '<div class="kpi ' + x[3] + '"><div class="lab">' + x[0] + '</div>' +
      '<div class="val">' + x[1] + '</div><div class="note">' + x[2] + '</div></div>';
  }).join('');
  document.getElementById('snap-meta').textContent = meta.run_date + ' 运行';

  document.getElementById('foot').innerHTML =
    '<b>口径</b>　' + c.status + '。全部金额为巴西雷亚尔，参考汇率 R$1 ≈ ¥' + c.fx + '。<br>' +
    '<b>限制</b>　本页不提供定价结论。样本与观测日以看板和分析报告标注为准。<br>' +
    '<b>生成</b>　' + meta.generated_at + ' · 管线自动生成，未经人工改写 · 版本 v' + meta.version;
})();
