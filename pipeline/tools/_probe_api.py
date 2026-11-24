# -*- coding: utf-8 -*-
"""摸 product/queryList 的请求体与响应结构。只用来看接口长什么样，不产出数据。

    python pipeline/tools/_probe_api.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_probe')
STATE = os.path.join(os.path.expanduser('~'), '.workbuddy', 'secrets', 'kalodata', 'state.json')
URL = 'https://www.kalodata.com/product'


def main():
    from playwright.sync_api import sync_playwright, Error as PWError

    os.makedirs(OUT, exist_ok=True)
    caught = []

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        c = b.new_context(storage_state=STATE, locale='zh-CN',
                          viewport={'width': 1500, 'height': 950})
        pg = c.new_page()

        def on_resp(r):
            if 'queryList' in r.url or 'product/count' in r.url:
                try:
                    body = r.text()
                except Exception:
                    body = ''
                caught.append({
                    'url': r.url,
                    'status': r.status,
                    'method': r.request.method,
                    'post': r.request.post_data,
                    'body': body,
                })

        pg.on('response', on_resp)
        try:
            pg.goto(URL, wait_until='domcontentloaded', timeout=60000)
        except PWError as e:
            if 'interrupted by another navigation' not in str(e):
                raise
        pg.wait_for_timeout(9000)
        b.close()

    print('抓到 %d 个响应' % len(caught))
    for i, h in enumerate(caught):
        print('')
        print('=== #%d %s %s' % (i, h['status'], h['url'].split('?')[0]))
        print('method:', h['method'])
        print('post  :', (h['post'] or '')[:600])
        print('body  : %d 字节' % len(h['body']))
        try:
            j = json.loads(h['body'])
        except Exception:
            print('  不是 JSON，前 300 字：', h['body'][:300])
            continue

        def walk(o, prefix='', depth=0):
            if depth > 2:
                return
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, (dict, list)):
                        print('  %s%s : %s(%d)' % (prefix, k, type(v).__name__, len(v)))
                        walk(v, prefix + '  ', depth + 1)
                    else:
                        print('  %s%s = %s' % (prefix, k, str(v)[:50]))
            elif isinstance(o, list):
                if o and isinstance(o[0], dict):
                    print('  %s[0] 字段: %s' % (prefix, list(o[0].keys())))
                    print('  %s[0] 值  : %s' % (prefix, json.dumps(o[0], ensure_ascii=False)[:400]))

        walk(j)
        path = os.path.join(OUT, 'queryList_%d.json' % i)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(h['body'])
        print('  已存原文:', path)

    return 0


if __name__ == '__main__':
    sys.exit(main())
