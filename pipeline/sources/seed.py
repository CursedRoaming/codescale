# -*- coding: utf-8 -*-
"""本地样本源：读已落盘的市场样本，用于回放与口径校验。

这是目前唯一真正有数据的一路，来源是公开搜索索引快照（75 条，采集日 2026-11-06）。
它的价值不是「新」，是「可对照」：任何新接入的平台，口径对不对，先用它比一遍。
"""

import json
import os

from .base import Result

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# 样本文件按优先级找，第一个存在的就用
CANDIDATES = [
    os.path.join(ROOT, 'pipeline', 'seed', 'market_expanded.json'),
    os.path.join(os.path.dirname(ROOT), '06_第一个客户_电商', '09_终版交付', 'data', 'market_expanded.json'),
]


def _from_url(url):
    u = (url or '').lower()
    if 'shopee' in u:
        return 'Shopee'
    if 'mercadolivre' in u or 'mercadolibre' in u:
        return 'Mercado Livre'
    if 'tiktok' in u:
        return 'TikTok Shop'
    if 'amazon' in u:
        return 'Amazon'
    return '未标注平台'


def fetch(cfg, ctx):
    r = Result('seed', cfg.get('name', '本地样本'))
    path = next((p for p in CANDIDATES if os.path.exists(p)), None)
    if not path:
        return r.fail('not_configured', '样本文件不存在：%s' % CANDIDATES[0])

    with open(path, encoding='utf-8') as f:
        d = json.load(f)

    for p in d.get('products') or []:
        rec = dict(p)
        rec.setdefault('price_brl', p.get('price'))
        # 这版样本里有 51 条没写 platform，只能从 source_url 的域名倒推。
        # 不猜平台名的后果是它们全被归到 seed，页面上看起来像「本地样本」自产的。
        if not rec.get('platform'):
            rec['platform'] = _from_url(rec.get('source_url') or '')
        r.records.append(rec)

    if not r.records:
        return r.fail('empty', '样本文件里没有 products')
    # 采集日取样本自己的观测日，不是运行日。这两个数不同的时候要能看出来。
    dates = sorted({str(p.get('observed_at') or p.get('retrieved_date') or '')
                    for p in r.records} - {''})
    r.reason = '%s · 采集日 %s' % (os.path.basename(path), '、'.join(dates) or '未记录')
    return r
