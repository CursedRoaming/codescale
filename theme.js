/* 主题切换：三套配色，选择存本机浏览器，不上传、不依赖服务端。
   本脚本分两段执行：head 里立即应用已存主题，避免先白后暗的闪烁；
   DOM 就绪后把切换器挂进左侧栏。 */

(function () {
  var KEY = 'codescale.theme.v1';
  var THEMES = [
    ['dark', '深'],
    ['light', '浅'],
    ['sepia', '暖']
  ];
  var valid = function (t) { return THEMES.some(function (x) { return x[0] === t; }); };

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function apply(t) {
    document.documentElement.setAttribute('data-theme', t);
  }
  function save(t) {
    try { localStorage.setItem(KEY, t); } catch (e) { /* 隐私模式下忽略 */ }
  }

  // 第一段：尽早应用，防止刷新时先显示默认主题再跳变
  var init = stored();
  apply(valid(init) ? init : 'dark');

  // 第二段：DOM 就绪后挂载切换器
  function mount() {
    var side = document.querySelector('.side');
    if (!side) return;

    var box = document.createElement('div');
    box.className = 'theme-pick';
    var label = document.createElement('span');
    label.className = 'tl';
    label.textContent = 'THEME';
    box.appendChild(label);

    THEMES.forEach(function (item) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = item[1];
      b.title = item[0] === 'dark' ? '深色' : (item[0] === 'light' ? '浅色' : '暖色护眼');
      b.setAttribute('data-t', item[0]);
      b.setAttribute('aria-label', '切换到' + b.title);
      b.addEventListener('click', function () {
        apply(item[0]);
        save(item[0]);
        sync();
        // 图表里的线色取自 CSS 变量，重绘一次才会更新
        if (typeof window.CSRedraw === 'function') window.CSRedraw();
      });
      box.appendChild(b);
    });
    side.appendChild(box);

    function sync() {
      var cur = document.documentElement.getAttribute('data-theme') || 'dark';
      var btns = box.querySelectorAll('button');
      for (var i = 0; i < btns.length; i++) {
        var on = btns[i].getAttribute('data-t') === cur;
        btns[i].className = on ? 'on' : '';
        btns[i].setAttribute('aria-pressed', on ? 'true' : 'false');
      }
    }
    sync();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
