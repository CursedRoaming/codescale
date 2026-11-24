# -*- coding: utf-8 -*-
"""拿到 token 之后，试拉一次巴西穿戴甲，看接口给什么字段、能不能支撑定价。

    python pipeline/tools/meli_probe.py
"""

import json
import sys
import urllib.parse
import urllib.request

from meli_token import access_token, MeliAuthError

API = 'https://api.mercadolibre.com'
QUERIES = ['unhas posticas', 'unha postica', 'kit unhas posticas']


def get(path, token, **params):
    url = API + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': 'Bearer %s' % token,
        'accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except Exception as e:
        body = ''
        try:
            body = e.read().decode('utf-8')[:300]
        except Exception:
            pass
        return getattr(e, 'code', 0), {'error': str(e), 'body': body}


def main():
    try:
        tok = access_token()
    except MeliAuthError as e:
        print(e)
        return 2

    for q in QUERIES:
        st, j = get('/sites/MLB/search', tok, q=q, limit=50)
        print('')
        print('=== q=%r  HTTP %s ===' % (q, st))
        if st != 200:
            print('  ', json.dumps(j, ensure_ascii=False)[:260])
            continue
        res = j.get('results') or []
        total = (j.get('paging') or {}).get('total')
        print('  总数 %s，本次返回 %d 条' % (total, len(res)))
        for x in res[:10]:
            print('  %-46s R$%-9s sold=%-6s %s' % (
                (x.get('title') or '')[:44], x.get('price'),
                x.get('sold_quantity'), (x.get('date_created') or '')[:10]))
        if res:
            print('  字段:', ', '.join(sorted(res[0].keys())))

    # 单条详情，看有没有更细的规格
    st, j = get('/sites/MLB/search', tok, q='unhas posticas', limit=1)
    if st == 200 and j.get('results'):
        iid = j['results'][0]['id']
        st2, d = get('/items/%s' % iid, tok, include_attributes='all')
        print('')
        print('=== 单品 %s HTTP %s ===' % (iid, st2))
        if st2 == 200:
            print('  title:', d.get('title'))
            print('  price:', d.get('price'), d.get('currency_id'))
            print('  sold :', d.get('sold_quantity'))
            print('  date_created:', d.get('date_created'))
            attrs = d.get('attributes') or []
            print('  属性 %d 个：%s' % (len(attrs), ', '.join(
                (a.get('name') or '') for a in attrs[:14])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
