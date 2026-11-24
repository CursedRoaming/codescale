/* 全站左侧导航。只在这里维护入口，页面里放 #side-slot 即可。 */
(function () {
  var BOARD = [
    ['行情', 's-bands'], ['规格', 's-spec'], ['盈亏', 's-econ'], ['规模', 's-scale'],
    ['敏感', 's-sens'], ['对标', 's-comp'], ['数据源', 's-src'], ['归档', 's-runs']
  ];
  var MAIN = [
    ['home', '首页', 'index.html', ''],
    ['app', '工作台', 'app.html', '<span class="tmp">本机</span>'],
    ['board', '看板', 'board.html', ''],
    ['trend', '趋势预测', 'trend.html', '<span class="tmp">本机</span>'],
    ['report', '分析报告', 'report.html', ''],
    ['connect', '接入中心', 'connect.html', ''],
    ['security', '安全说明', 'security.html', ''],
    ['needs', '数据需求', 'data-needs.html', '<span class="tmp">临时</span>']
  ];
  var cs = getComputedStyle(document.documentElement);
  var cv = function (n) { return cs.getPropertyValue(n).trim(); };
  var logo = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none">' +
    '<rect x="1.5" y="1.5" width="21" height="21" rx="6" stroke="' + cv('--acc') + '" stroke-width="1.5"/>' +
    '<path d="M7 16.5V7.5h6.4L17 11.1v5.4z" stroke="' + cv('--ink') + '" stroke-width="1.4" stroke-linejoin="round"/>' +
    '<path d="M9.6 11.2h2.2M9.6 13.6h4.2" stroke="' + cv('--acc') + '" stroke-width="1.3" stroke-linecap="round"/>' +
    '</svg>';
  var h = '<aside class="side"><div class="brand"><div class="bt">' + logo +
    '<div class="bn">码尺<em>CODESCALE</em></div></div>' +
    '<div class="bs">跨境选品数据台 · 巴西站</div></div><nav class="side-nav">' +
    '<a href="index.html" data-k="home">首页</a>';
  MAIN.slice(1).forEach(function (m) {
    if (m[0] === 'board') {
      h += '<a href="board.html" data-k="board">看板</a>';
      BOARD.forEach(function (b) {
        h += '<a class="sub" href="board.html#' + b[1] + '">' + b[0] + '</a>';
      });
    } else {
      h += '<a href="' + m[2] + '" data-k="' + m[0] + '">' + m[1] + m[3] + '</a>';
    }
  });
  h += '</nav><div class="side-foot">每日 20:00 自动生成快照<br>数据观测日以页面标注为准</div></aside>';

  var slot = document.getElementById('side-slot');
  if (slot) slot.innerHTML = h;

  var page = document.body.getAttribute('data-page') || '';
  var links = document.querySelectorAll('.side-nav a[data-k]');
  for (var i = 0; i < links.length; i++) {
    if (links[i].getAttribute('data-k') === page) links[i].className += ' on';
  }
})();
