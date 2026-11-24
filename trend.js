/* 趋势预测页 · 只读本机 /api/trend，不在前端编造数据 */
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var BRL = function (v) { return v == null ? '--' : 'R$ ' + Number(v).toFixed(2); };
  var PCT = function (v) { return v == null ? '--' : (v * 100).toFixed(1) + '%'; };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function modeNote(r, viaService) {
    var t = $('mode-note');
    if (!viaService) {
      t.innerHTML = '<div class="verdict"><p><b>当前为静态站点，无本机数据接口。</b>' +
        '趋势与外推在本地计算，数据不上传。需要时请在项目根目录双击 <code>start.bat</code>，' +
        '再访问 <code>http://127.0.0.1:8765/trend.html</code>。</p></div>';
      return;
    }
    var stale = r.stale_days;
    var warn = stale != null && stale > 3;
    t.innerHTML = '<div class="verdict">' +
      '<p>本机共 <b>' + r.run_count + '</b> 次运行快照，按观测日去重后 <b>' + r.unique_observed +
      '</b> 个数据点。最新观测日 <b>' + (r.latest_observed || '--') + '</b>' +
      (stale == null ? '' : '，距今 <b>' + stale + '</b> 天') + '。</p>' +
      (warn ? '<p><span class="hl">观测日距今较久，下列数字只反映当时存量，不代表当前行情。</span></p>' : '') +
      '</div>';
  }

  function win(el, w) {
    if (!w.n) {
      el.innerHTML = '<div class="empty">窗口内无观测点</div>';
      return;
    }
    var pts = w.points;
    var med = pts.map(function (p) { return p.median; }).filter(function (v) { return v != null; });
    var last = pts[pts.length - 1];
    el.innerHTML =
      '<div class="wstat"><span>观测点</span><b>' + w.n + '</b></div>' +
      '<div class="wstat"><span>最新观测日</span><b>' + esc(last.data_date) + '</b></div>' +
      '<div class="wstat"><span>中位价</span><b>' + BRL(last.median) + '</b></div>' +
      '<div class="wstat"><span>保本价以上</span><b>' + PCT(last.over_be_ratio) + '</b></div>' +
      (med.length > 1 ? '<div class="wstat"><span>区间最低 / 最高</span><b>' +
        BRL(Math.min.apply(null, med)) + ' / ' + BRL(Math.max.apply(null, med)) + '</b></div>' : '');
  }

  function series(r) {
    var pts = [];
    (r.month.points || []).forEach(function (p) {
      pts.push({ d: p.data_date, m: p.median, o: p.over_be_ratio });
    });
    if (!pts.length) {
      $('series').innerHTML = '<div class="empty">近 30 天无观测点</div>';
      $('ser-meta').textContent = '0 条';
      return;
    }
    var rows = pts.map(function (p) {
      return '<tr><td>' + esc(p.d) + '</td><td>' + BRL(p.m) + '</td><td>' +
        PCT(p.o) + '</td><td style="color:var(--dim2)">' + (p.m != null ? '真实观测' : '--') + '</td></tr>';
    }).join('');
    $('series').innerHTML = '<table><thead><tr><th>观测日</th><th>中位价</th><th>保本价以上</th><th>来源</th></tr></thead><tbody>' +
      rows + '</tbody></table>';
    $('ser-meta').textContent = pts.length + ' 条真实观测';
  }

  function fcBlock(name, f, isRatio) {
    var fmt = isRatio ? PCT : BRL;
    if (!f || (f.value == null)) {
      return '<div class="empty">' + name + '：无外推结果</div>';
    }
    return '<div class="fc"><div class="fc-t">' + name + '</div>' +
      '<div class="fc-v">' + fmt(f.value) + '</div>' +
      '<div class="fc-r">区间 ' + fmt(f.low) + ' – ' + fmt(f.high) +
      ' · 依据 ' + f.basis_n + ' 点 · R² ' + (f.r2 == null ? '--' : f.r2) +
      ' · 目标日 ' + esc(f.target_date) + '</div></div>';
  }

  function forecast(r) {
    var f = r.forecast;
    if (!f.available) {
      $('forecast').innerHTML = '<div class="empty"><b>未做外推。</b>' + esc(f.reason || '数据不足') + '</div>';
      $('fc-meta').textContent = '数据不足';
      return;
    }
    $('forecast').innerHTML =
      '<div class="fc-grid">' +
      fcBlock('中位价', f.median, false) +
      fcBlock('保本价以上占比', f.over_be_ratio, true) +
      '</div>' +
      '<p class="rnote">方法：' + esc((f.median || {}).method || '线性最小二乘外推') +
      '。R² 越接近 1 说明历史线性程度越高，不代表外推必准。观测点少于 5 个时区间仅供观看。</p>';
    $('fc-meta').textContent = '线性外推 · ' + (f.median ? f.median.basis_n : 0) + ' 点';
  }

  function model() {
    $('model').innerHTML =
      '<table><thead><tr><th style="width:170px">项</th><th>说明</th></tr></thead><tbody>' +
      '<tr><td><b>当前实现</b></td><td style="text-align:left;color:var(--dim)">纯本机确定性算术。页面不请求外部服务，不上传任何填写内容。</td></tr>' +
      '<tr><td><b>模型位置</b></td><td style="text-align:left;color:var(--dim)">预留。待真实历史序列积累到可训练长度后再定接口与口径。</td></tr>' +
      '<tr><td><b>前置条件</b></td><td style="text-align:left;color:var(--dim)">先接通数据源，让观测日逐日变化。没有真实序列，接任何模型都得不出有效预测。</td></tr>' +
      '</tbody></table>';
  }

  function foot() {
    $('foot').innerHTML =
      '<b>口径</b>　按观测日聚合，不按运行日。同一观测日的多次运行只算一个点。<br>' +
      '<b>方法</b>　外推为最小二乘线性拟合，区间取残差标准差 1.96 倍，不构成定价建议。<br>' +
      '<b>范围</b>　本地服务仅监听 127.0.0.1，不联网，不上传。<br>' +
      '<b>码尺 CodeScale</b>　跨境选品数据台 · 本机计算';
  }

  async function boot() {
    var viaService = location.protocol === 'http:' || location.protocol === 'https:';
    var r = null;
    if (viaService) {
      try {
        var resp = await fetch('/api/trend', { cache: 'no-store' });
        if (resp.ok) r = await resp.json();
      } catch (e) { /* 静态站点下忽略 */ }
    }
    if (!r) {
      modeNote(null, false);
      $('mode-note').style.display = 'block';
      ['w7', 'w30', 'series', 'forecast'].forEach(function (id) {
        $(id).innerHTML = '<div class="empty">需通过本地服务查看</div>';
      });
      model(); foot();
      return;
    }
    modeNote(r, true);
    win($('w7'), r.week);
    win($('w30'), r.month);
    $('win-meta').textContent = '近 7 天 ' + r.week.n + ' 点 · 近 30 天 ' + r.month.n + ' 点';
    series(r);
    forecast(r);
    model();
    foot();
  }

  boot();
})();
