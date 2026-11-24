/* 本机工作台：登录、当日更新、窗口、外推、模型配置。全部走本地服务接口。 */
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  }); };
  var BRL = function (v) { return 'R$ ' + (v == null ? '--' : Number(v).toFixed(2)); };
  var PCT = function (v) { return v == null ? '--' : (Number(v) * 100).toFixed(1) + '%'; };

  function show(id, on) { $(id).style.display = on ? '' : 'none'; }

  function api(path, opt) {
    opt = opt || {};
    opt.credentials = 'same-origin';
    if (opt.body && typeof opt.body !== 'string') {
      opt.body = JSON.stringify(opt.body);
      opt.headers = Object.assign({'Content-Type': 'application/json'}, opt.headers || {});
    }
    return fetch(path, opt).then(function (r) {
      return r.json().then(function (j) { return {status: r.status, data: j}; });
    });
  }

  function msg(id, text, bad) {
    $(id).innerHTML = esc(text);
    $(id).style.color = bad ? 'var(--warn)' : 'var(--dim2)';
  }

  function stat(label, value, note) {
    return '<div class="wk-kpi"><div class="k">' + esc(label) + '</div>' +
      '<div class="v">' + esc(value) + '</div><div class="n">' + esc(note || '') + '</div></div>';
  }

  function winBox(w) {
    if (!w || !w.n) return '<div class="tip">窗口内暂无观测点。</div>';
    var last = w.points[w.points.length - 1];
    var first = w.points[0];
    return '<div class="wstat"><span>观测点</span><b>' + w.n + ' 个</b></div>' +
      '<div class="wstat"><span>起止</span><b>' + esc(first.data_date) + ' → ' + esc(last.data_date) + '</b></div>' +
      '<div class="wstat"><span>最新中位价</span><b>' + BRL(last.median) + '</b></div>' +
      '<div class="wstat"><span>保本价以上占比</span><b>' + PCT(last.over_be_ratio) + '</b></div>';
  }

  function fcBox(f, title) {
    if (!f || !f.available) {
      return '<div class="tip">' + esc(title) + '：' + esc((f && f.reason) || '无结果') + '</div>';
    }
    return '<div class="fc-t">' + esc(title) + ' · ' + esc(f.origin_label || '内置') + '</div>' +
      '<div class="fc-v">' + BRL(f.value) + '</div>' +
      '<div class="fc-r">区间 ' + BRL(f.low) + ' – ' + BRL(f.high) +
      ' · 目标 ' + esc(f.target_date || '--') +
      (f.r2 != null ? ' · R² ' + f.r2 : '') +
      (f.basis_n != null ? ' · 依据 ' + f.basis_n + ' 点' : '') +
      '</div><div class="tip" style="margin-top:8px">' + esc(f.note || f.method || '') + '</div>';
  }

  function checkSession() {
    return api('/api/session').then(function (x) {
      if (x.status === 200 && x.data.logged_in) {
        enter(x.data.user);
      } else {
        show('workspace', false);
        show('loginbox', true);
      }
    }).catch(function () {
      msg('lmsg', '无法连接本地服务。请确认已双击 start.bat 启动。', true);
      show('loginbox', true);
    });
  }

  function enter(user) {
    show('loginbox', false);
    show('workspace', true);
    $('who').textContent = user || '';
    loadState();
    loadTrend();
    loadModel();
  }

  function doAuth(kind) {
    var u = $('lu').value.trim(), p = $('lp').value;
    if (!u || !p) { msg('lmsg', '请填写用户名与密码。', true); return; }
    msg('lmsg', '处理中…');
    api('/api/auth/' + kind, {method: 'POST', body: {username: u, password: p}})
      .then(function (x) {
        if (kind === 'register') {
          msg('lmsg', x.status === 200 ? '注册成功，请点「登录」进入。' : (x.data.reason || '注册失败'), x.status !== 200);
          return null;
        }
        if (x.status !== 200) { msg('lmsg', x.data.error || '登录失败', true); return null; }
        return x;
      })
      .then(function (x) {
        if (x && x.data && x.data.ok) {
          var r = x.data.refresh || {};
          enter(x.data.user);
          if (r.written) msg('feed-line', '登录已更新当天快照：' + r.date, false);
        }
      })
      .catch(function () { msg('lmsg', '请求失败，请确认本地服务在运行。', true); });
  }

  $('btn-login').addEventListener('click', function () { doAuth('login'); });
  $('btn-reg').addEventListener('click', function () { doAuth('register'); });
  $('lp').addEventListener('keydown', function (e) { if (e.key === 'Enter') doAuth('login'); });

  function loadState() {
    api('/api/app/state').then(function (x) {
      if (x.status === 401) return checkSession();
      if (x.status !== 200) throw new Error(x.data.error || '读取失败');
      var d = x.data, f = d.feed, b = d.baseline;
      $('banner').innerHTML = '<div class="verdict"><p><b>数据来源提示。</b>' +
        '工作台快照来自本机' + esc(f.source_kinds.join('、') || '演示源') +
        '，基线观测日 ' + esc(b.data_date) + '。演示快照按日期确定性生成，不是真实市场观测。</p></div>';
      $('kpis').innerHTML =
        stat('本机快照', f.count + ' 条', (f.first || '--') + ' → ' + (f.last || '--')) +
        stat('基线样本', b.n + ' 条', '观测日 ' + b.data_date) +
        stat('基线中位价', BRL(b.median), '仅作对照') +
        stat('今天', d.today, '登录自动更新');
      $('feed-meta').textContent = f.history_dir;
      var demo = f.demo ? '<span class="badge warn">演示数据</span>' : '<span class="badge ok">已接入</span>';
      $('feed-line').innerHTML = demo + '　本机已存 ' + f.count + ' 条快照，首条 ' +
        esc(f.first || '--') + '，末条 ' + esc(f.last || '--') + '。来源：' +
        esc(f.source_kinds.join('、') || '--') + '。';
    }).catch(function (e) { msg('feed-line', String(e.message || e), true); });
  }

  $('btn-refresh').addEventListener('click', function () {
    var b = $('btn-refresh'); b.disabled = true; b.textContent = '更新中…';
    api('/api/feed/refresh', {method: 'POST'}).then(function (x) {
      b.disabled = false; b.textContent = '立即更新当天';
      if (x.status === 401) return checkSession();
      if (x.status !== 200) throw new Error(x.data.error || '更新失败');
      var r = x.data;
      msg('feed-line', r.written ? ('已写入 ' + r.date + '，来源 ' + (r.source_label || r.source_kind)) : ('当天已存在：' + r.date), false);
      loadState(); loadTrend();
    }).catch(function (e) { b.disabled = false; b.textContent = '立即更新当天'; msg('feed-line', String(e.message || e), true); });
  });

  function loadTrend() {
    return api('/api/app/trend').then(function (x) {
      if (x.status === 401) return checkSession();
      if (x.status !== 200) throw new Error(x.data.error || '读取失败');
      var d = x.data;
      $('win-meta').textContent = '按观测日去重 · ' + d.unique_observed + ' 个观测点';
      $('w7').innerHTML = winBox(d.week);
      $('w30').innerHTML = winBox(d.month);
      $('tr-meta').textContent = '最新观测 ' + (d.latest_observed || '--') + ' · 滞后 ' + (d.stale_days == null ? '--' : d.stale_days + ' 天');
      var fm = (d.forecast && d.forecast.median) || {};
      $('fc-builtin').innerHTML = fcBox({
        available: !!(d.forecast && d.forecast.available),
        value: fm.value, low: fm.low, high: fm.high,
        target_date: fm.target_date, r2: fm.r2, basis_n: fm.basis_n,
        origin_label: '内置线性规则', method: '线性最小二乘外推',
        reason: d.forecast && d.forecast.reason, note: '算术延展，非模型预测。'
      }, '中位价');
      $('fc-model').innerHTML = fcBox(d.prediction, '中位价预测');
      var rows = ((d.week && d.week.points) || []).map(function (q) {
        return q.data_date + '   n=' + q.n + '   中位 ' + BRL(q.median) + '   保本以上 ' + PCT(q.over_be_ratio);
      });
      $('series').textContent = rows.length ? rows.join('\n') : '观测序列为空。';
    }).catch(function (e) { msg('series', String(e.message || e), true); });
  }

  function fillModel(c) {
    $('me').value = c.endpoint || '';
    $('mm').value = c.model || '';
    $('mk').value = '';
    $('model-meta').textContent = c.configured ? '已配置 · 密钥 ' + (c.api_key_mask || '') : '未配置 · 使用内置规则';
    msg('model-msg', c.configured
      ? ('接口 ' + c.endpoint + ' · 模型 ' + c.model + ' · 已保存密钥 ' + (c.api_key_mask || ''))
      : '未配置。预测走内置线性规则，不调用外部服务。');
  }

  function loadModel() {
    return api('/api/model/config').then(function (x) {
      if (x.status === 401) return checkSession();
      if (x.status === 200) fillModel(x.data);
    });
  }

  function cfgFromForm() {
    return {endpoint: $('me').value.trim(), model: $('mm').value.trim(), api_key: $('mk').value};
  }

  $('btn-model-save').addEventListener('click', function () {
    api('/api/model/config', {method: 'POST', body: cfgFromForm()}).then(function (x) {
      if (x.status === 401) return checkSession();
      if (x.status !== 200) throw new Error(x.data.error || '保存失败');
      fillModel(x.data);
      msg('model-msg', '已保存到本机。密钥仅显示掩码，原文不回显。');
      loadTrend();
    }).catch(function (e) { msg('model-msg', String(e.message || e), true); });
  });

  $('btn-model-clear').addEventListener('click', function () {
    api('/api/model/config', {method: 'POST', body: {action: 'clear'}}).then(function (x) {
      if (x.status === 200) { fillModel(x.data); loadTrend(); }
    });
  });

  $('btn-model-test').addEventListener('click', function () {
    var b = $('btn-model-test'); b.disabled = true; b.textContent = '试算中…';
    api('/api/model/config', {method: 'POST', body: cfgFromForm()}).then(function () {
      return api('/api/app/trend?model=1');
    }).then(function (x) {
      b.disabled = false; b.textContent = '用新配置试算';
      var p = x.data.prediction || {};
      msg('model-msg', '来源：' + (p.origin_label || '--') + '。' +
        (p.available ? ('结果 ' + BRL(p.value) + '（区间 ' + BRL(p.low) + ' – ' + BRL(p.high) + '）') : (p.note || p.reason || '无结果')) +
        (p.note && p.available ? '　' + p.note : ''), p.origin === 'builtin' && cfgFromForm().endpoint ? true : false);
      loadModel();
    }).catch(function (e) {
      b.disabled = false; b.textContent = '用新配置试算';
      msg('model-msg', String(e.message || e), true);
    });
  });

  checkSession();
})();
