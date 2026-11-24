# -*- coding: utf-8 -*-
"""用已保存的会话进 Kalodata，把页面结构摸清楚：菜单在哪、导出按钮叫什么、数据走哪个接口。

跑之前先跑 kalodata_login.py 保存会话。

    python pipeline/tools/kalodata_probe.py

输出：
    pipeline/tools/_probe/ 下的截图与一份 report.txt

为什么要探：导出按钮的位置和文案没人写文档，只能看真实页面。
猜着写选择器，第一次跑就会静默拿不到文件，比报错更难查。
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_probe')
SECRET_DIR = os.path.join(os.path.expanduser('~'), '.workbuddy', 'secrets', 'kalodata')
STATE = os.path.join(SECRET_DIR, 'state.json')
# 首页是营销落地页，没数据。数据在商品排行榜，游客视角也能进，只是价格被打码。
DATA_URL = 'https://www.kalodata.com/product'
GUEST_MARKS = ('登录 / 注册', '登录/注册')


def main():
    if not os.path.exists(STATE):
        print('还没有会话。先跑：python pipeline/tools/kalodata_login.py')
        return 2
    try:
        from playwright.sync_api import sync_playwright, Error as PWError
    except ImportError:
        print('缺 playwright：pip install playwright && python -m playwright install chromium')
        return 2

    def safe_goto(page, url, wait=6000):
        """SPA 会自己跳页，Playwright 报「导航被打断」。那不是失败。"""
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except PWError as e:
            if 'interrupted by another navigation' not in str(e):
                raise
        page.wait_for_timeout(wait)
        return page.url

    os.makedirs(OUT, exist_ok=True)
    lines = []

    def say(s=''):
        print(s)
        lines.append(s)

    apis = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=STATE, locale='zh-CN',
                                  viewport={'width': 1500, 'height': 950})
        page = ctx.new_page()

        def on_resp(r):
            try:
                if r.request.resource_type in ('xhr', 'fetch'):
                    apis.append((r.status, r.url))
            except Exception:
                pass

        page.on('response', on_resp)

        safe_goto(page, DATA_URL)

        body = ''
        try:
            body = page.inner_text('body')
        except Exception:
            pass

        say('最终 URL: %s' % page.url)
        say('标题: %s' % page.title())
        guest = any(m in body for m in GUEST_MARKS)
        say('登录态: %s' % ('否（右上角还有登录入口，数据会被打码）' if guest else '是'))
        page.screenshot(path=os.path.join(OUT, '01_product.png'), full_page=False)

        if guest:
            say('')
            say('会话无效，仍是游客视角。先重跑 kalodata_login.py，别往下看了。')
            browser.close()
            path = os.path.join(OUT, 'report.txt')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print('')
            print('已写入 %s' % path)
            return 3

        # 表头决定 CSV 有哪些列
        heads = page.eval_on_selector_all(
            'table thead th, [role=columnheader]',
            """els => els.map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
                       .filter(Boolean)""")
        heads = list(dict.fromkeys(heads))
        say('')
        say('== 表头 %d 个 ==' % len(heads))
        say('  ' + ' | '.join(heads[:40]) if heads else '  （没找到表格）')

        rows = page.eval_on_selector_all('tbody tr', 'e => e.length')
        say('表格行数: %s' % rows)

        # 导出大概率藏在「批量操作」里
        btns = page.eval_on_selector_all(
            'button, [role=button]',
            """els => els.map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
                       .filter(Boolean)""")
        btns = list(dict.fromkeys(btns))
        say('')
        say('== 按钮文案 %d 个 ==' % len(btns))
        for b in btns[:50]:
            say('  %s' % b)

        # 试着展开「批量操作」，把菜单项记下来；点不开就算了，不硬来
        say('')
        say('== 批量操作菜单 ==')
        opened = False
        for sel_text in ('批量操作', 'Export', '导出'):
            try:
                loc = page.get_by_text(sel_text, exact=False).first
                if loc.count() == 0:
                    continue
                loc.click(timeout=5000)
                page.wait_for_timeout(1500)
                items = page.eval_on_selector_all(
                    '[role=menuitem], .ant-dropdown-menu-item, li',
                    """els => els.map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
                               .filter(t => t && t.length < 30)""")
                items = list(dict.fromkeys(items))
                if items:
                    say('  点了「%s」，弹出：%s' % (sel_text, ' / '.join(items[:20])))
                    opened = True
                    page.screenshot(path=os.path.join(OUT, '02_batch_menu.png'))
                    page.keyboard.press('Escape')
                    break
            except Exception as e:
                say('  点「%s」失败：%s' % (sel_text, str(e).split('\n')[0][:80]))
        if not opened:
            say('  没能展开，看 01_product.png 自己判断。')

        # 数据接口：能拿到就直接调，比点导出稳
        say('')
        seen = {}
        for st, u in apis:
            base = u.split('?')[0]
            seen.setdefault(base, (st, u))
        say('== XHR 接口 %d 个（去重后）==' % len(seen))
        for base, (st, full) in list(seen.items())[:40]:
            say('  %s %s' % (st, full[:170]))
        if not seen:
            say('  （没抓到，可能页面用了 WebSocket 或 Service Worker）')

        browser.close()

    path = os.path.join(OUT, 'report.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('')
    print('已写入 %s' % path)
    print('截图 %s' % os.path.join(OUT, '01_product.png'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
