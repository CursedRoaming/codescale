# -*- coding: utf-8 -*-
"""看国家/市场怎么切：点顶部那个 US，抓弹窗选项和切换时发出的请求。"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_probe')
STATE = os.path.join(os.path.expanduser('~'), '.workbuddy', 'secrets', 'kalodata', 'state.json')


def main():
    from playwright.sync_api import sync_playwright, Error as PWError

    os.makedirs(OUT, exist_ok=True)
    reqs = []

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        c = b.new_context(storage_state=STATE, locale='zh-CN',
                          viewport={'width': 1500, 'height': 950})
        pg = c.new_page()

        def on_req(r):
            u = r.url
            if any(k in u for k in ('country', 'Country', 'region', 'Region', 'market')):
                reqs.append((r.method, u[:150], (r.post_data or '')[:300]))

        pg.on('request', on_req)
        try:
            pg.goto('https://www.kalodata.com/product', wait_until='domcontentloaded', timeout=60000)
        except PWError as e:
            if 'interrupted by another navigation' not in str(e):
                raise
        pg.wait_for_timeout(7000)

        # 顶部市场按钮
        print('--- 顶部候选元素 ---')
        cands = pg.eval_on_selector_all(
            'header *, [class*=header] *',
            """els => els.filter(e => {
                const t = (e.innerText || '').trim();
                return t && t.length <= 24 && /^[A-Z]{2}$|美国|巴西|US|BR/.test(t);
            }).slice(0, 12).map(e => ({
                tag: e.tagName, text: (e.innerText || '').trim(),
                cls: (e.className && e.className.toString().slice(0, 50)) || ''
            }))""")
        for x in cands:
            print('  <%s> %r  [%s]' % (x['tag'], x['text'], x['cls']))

        clicked = False
        for loc in (pg.get_by_text('US', exact=True), pg.get_by_text('美国', exact=True)):
            try:
                if loc.count():
                    loc.first.click(timeout=5000)
                    clicked = True
                    break
            except Exception as e:
                print('点不动:', str(e).split('\n')[0][:70])
        print('点开市场选择器:', clicked)
        pg.wait_for_timeout(2000)
        pg.screenshot(path=os.path.join(OUT, '03_country_menu.png'))

        if clicked:
            items = pg.eval_on_selector_all(
                'li, [role=menuitem], [role=option], [class*=dropdown] *',
                """els => els.map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
                           .filter(t => t && t.length <= 30)""")
            items = list(dict.fromkeys(items))
            print('--- 弹窗里的选项（前 60）---')
            for t in items[:60]:
                print('  ', t)

        print('')
        print('--- 含 country/region 的请求 ---')
        seen = set()
        for m, u, pd in reqs:
            k = (m, u.split('?')[0])
            if k in seen:
                continue
            seen.add(k)
            print('  %s %s' % (m, u))
            if pd:
                print('     post:', pd)

        b.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
