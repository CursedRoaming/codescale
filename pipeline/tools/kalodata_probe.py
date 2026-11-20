# -*- coding: utf-8 -*-
"""用已保存的会话进 Kalodata，把页面结构摸清楚：菜单在哪、导出按钮叫什么、下载走哪条路。

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
HOME_URL = 'https://www.kalodata.com/'


def main():
    if not os.path.exists(STATE):
        print('还没有会话。先跑：python pipeline/tools/kalodata_login.py')
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('缺 playwright：pip install playwright && python -m playwright install chromium')
        return 2

    os.makedirs(OUT, exist_ok=True)
    lines = []

    def say(s=''):
        print(s)
        lines.append(s)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=STATE, viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        page.goto(HOME_URL, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(4000)

        say('最终 URL: %s' % page.url)
        say('标题: %s' % page.title())
        say('登录态: %s' % ('否（被弹回登录页）' if 'login' in page.url.lower() else '是'))
        page.screenshot(path=os.path.join(OUT, '01_home.png'), full_page=True)

        # 导航链接：菜单名与地址，用来判断商品/类目/达人各在哪个路径
        links = page.eval_on_selector_all(
            'a[href]',
            """els => els.map(e => ({
                text: (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 40),
                href: e.href
            })).filter(x => x.text && x.href.includes('kalodata'))""")
        seen, uniq = set(), []
        for l in links:
            k = (l['text'], l['href'])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(l)
        say('')
        say('== 站内链接 %d 个 ==' % len(uniq))
        for l in uniq[:60]:
            say('  %-28s %s' % (l['text'], l['href']))

        # 按钮：导出/下载通常是个按钮而不是链接
        btns = page.eval_on_selector_all(
            'button, [role=button]',
            """els => els.map(e => (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 30))
                       .filter(Boolean)""")
        btns = list(dict.fromkeys(btns))
        say('')
        say('== 按钮文案 %d 个 ==' % len(btns))
        for b in btns[:60]:
            say('  %s' % b)

        # 表格与表头：数据页必然有表，表头决定 CSV 有哪些列
        heads = page.eval_on_selector_all(
            'table thead th, [role=columnheader]',
            """els => els.map(e => (e.innerText || '').trim()).filter(Boolean)""")
        heads = list(dict.fromkeys(heads))
        say('')
        say('== 表头 %d 个 ==' % len(heads))
        say('  ' + ' | '.join(heads[:40]) if heads else '  （首页没有表格，数据在内页）')

        # 有没有「商品」这类入口，先记下 href
        say('')
        say('== 含 export / download / csv / 导出 字样的元素 ==')
        hits = page.eval_on_selector_all(
            '*',
            """els => els.filter(e => {
                    const t = (e.innerText || '').trim();
                    if (!t || t.length > 20) return false;
                    return /导出|下载|export|download|csv/i.test(t);
                }).slice(0, 20).map(e => ({
                    tag: e.tagName, text: (e.innerText || '').trim().slice(0, 20),
                    cls: (e.className && e.className.toString().slice(0, 60)) || ''
                }))""")
        for h in hits:
            say('  <%s> %s   [%s]' % (h['tag'], h['text'], h['cls']))
        if not hits:
            say('  （首页没有，多半在具体数据页里）')

        browser.close()

    path = os.path.join(OUT, 'report.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('')
    print('已写入 %s' % path)
    print('截图 %s' % os.path.join(OUT, '01_home.png'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
