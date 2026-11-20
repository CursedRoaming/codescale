# -*- coding: utf-8 -*-
"""指标计算：把归一后的记录压成网页和报告要的一组数。

原则：所有比率用「合计÷合计」重算，不对逐条比率取平均。
      样本不足的指标返回 None，不返回 0 —— 0 会被当成「真的是零」。
"""

import re
import statistics

from . import cost as cost_mod
from .normalize import normalize_text

# 价格带边界（BRL）。自家保本价 29.70 落在 25–30 与 30–40 之间，所以单独画线。
BANDS = [
    (0, 15, 'R$15 以下'),
    (15, 20, 'R$15–20'),
    (20, 25, 'R$20–25'),
    (25, 30, 'R$25–30'),
    (30, 40, 'R$30–40'),
    (40, 55, 'R$40–55'),
    (55, 10 ** 9, 'R$55 以上'),
]

SPEC_LABEL = {
    'child': '儿童款',
    'fp': '数字非片数',
    None: '未标规格',
}
TIER_LABEL = {'brand': '国际品牌', 'handmade': '手工/定制', 'white': '白牌/供应链', 'unknown': '未分层'}


def _q(v):
    if not v:
        return None
    v = sorted(v)
    if len(v) >= 4:
        qs = statistics.quantiles(v, n=4)
        p25, p75 = qs[0], qs[2]
    else:
        p25, p75 = v[0], v[-1]
    return {'n': len(v), 'median': round(statistics.median(v), 2),
            'p25': round(p25, 2), 'p75': round(p75, 2),
            'min': round(v[0], 2), 'max': round(v[-1], 2)}


def spec_label(s):
    return SPEC_LABEL.get(s, ('%d 片' % s) if isinstance(s, int) else str(s))


def _rec_key(r):
    """记录的身份。平台 + 规范标题。改一个字段就换一次身份，所以标题写法变了
    会被算成「消失一条 + 新增一条」，这是有意的：宁可报变化，不要漏变化。"""
    return (r['platform'], normalize_text(r['title']))


def _delta(records, prev_records, prev_meta):
    """与上一版比，到底有没有新东西。

    存在的理由：每天自动跑一遍，源没接通时每次跑出来的数完全一样。
    如果报告不承认这件事，就会每天发一份内容相同的「新一期」给客户，
    那比不发更糟。所以这里把「没变化」做成一个明确的结论，让报告能照实写。
    """
    if not prev_records:
        return {
            'has_prev': False, 'prev_date': None, 'changed': None,
            'new': 0, 'gone': 0, 'price_moved': 0, 'n_delta': None,
            'median_from': None, 'median_to': None,
            'days_between': None,
            'note': '没有上一版可比，这是第一份快照。',
        }

    cur = {}
    for r in records:
        cur[_rec_key(r)] = r['price']
    old = {}
    for r in prev_records:
        old[_rec_key(r)] = r['price']

    new_k = cur.keys() - old.keys()
    gone_k = old.keys() - cur.keys()
    moved = sum(1 for k in cur.keys() & old.keys() if abs(cur[k] - old[k]) >= 0.5)

    med_now = round(statistics.median(list(cur.values())), 2) if cur else None
    med_old = round(statistics.median(list(old.values())), 2) if old else None

    # 中位价这一项也要过阈值。否则会出现「判定为有新数据，但异动表一条都列不出来」，
    # 那是自相矛盾的：报告说变了，读者翻到异动那节却是空的。
    med_moved = (med_now is not None and med_old is not None
                 and abs(med_now - med_old) >= 0.5)
    changed = bool(new_k or gone_k or moved) or med_moved
    d0 = (prev_meta or {}).get('run_date')
    d1 = (prev_meta or {}).get('data_date')
    days = None
    if d1:
        import datetime
        try:
            days = (datetime.date.today() - datetime.date.fromisoformat(d1)).days
        except ValueError:
            days = None

    note = '本次运行取到了新数据。'
    if not changed:
        note = ('本次运行没有取到任何新记录：条数、商品、价格与上一版完全一致。'
                '下面所有数字来自同一批数据，不是新一期行情。')

    return {
        'has_prev': True, 'prev_date': d0, 'changed': changed,
        'new': len(new_k), 'gone': len(gone_k), 'price_moved': moved,
        'n_delta': len(cur) - len(old),
        'median_from': med_old, 'median_to': med_now,
        'days_between': days,
        'note': note,
    }


def _is_item_url(u):
    """这个链接点进去是不是「那一个商品」。
    列表页和店铺首页都不算：点进去看到的是一屏东西，找不到这条价格的出处。"""
    u = (u or '').lower()
    if not u:
        return False
    if 'mercadolivre' in u:
        return '/mlb-' in u or 'produto.' in u
    if 'shopee' in u:
        # Shopee 单品形如 /Kit-24-unhas-...-i.400179385.22994847146
        # 店铺首页是 /make.mania，没有 i.数字.数字 这一段
        return bool(re.search(r'[./\-]i\.\d+\.\d+', u))
    if 'tiktok' in u:
        return '/product/' in u or '/pdp/' in u
    return False


def compute(records, sources, records_all, prev_records=None, prev_meta=None):
    """records      参与统计的记录（已去重、已剔无效）
       records_all  含被剔除项的原始条数，用来说明剔了多少
       prev_records 上一次运行的记录，用来看价格变动
       prev_meta    上一次运行的 meta，用来说明对比的是哪一天
    """
    m = cost_mod.model()
    prices = [r['price'] for r in records]
    n = len(records)

    # ---- 价格带
    bands = []
    for lo, hi, label in BANDS:
        g = [p for p in prices if lo <= p < hi]
        cover = (lo >= m['be_org']) if hi < 10 ** 9 else (lo >= m['be_org'])
        bands.append({
            'label': label, 'lo': lo, 'hi': None if hi > 10 ** 8 else hi,
            'n': len(g), 'share': round(len(g) / n, 4) if n else 0,
            'median': round(statistics.median(g), 2) if g else None,
            'over_break_even': bool(cover),
        })

    # ---- 保本覆盖率
    over = [p for p in prices if p >= m['be_org']]
    over_full = [p for p in prices if p >= m['be_full']]

    # ---- 规格 × 分层
    spec_groups = {}
    for r in records:
        spec_groups.setdefault(r['spec'], []).append(r['price'])
    specs = []
    for k in sorted(spec_groups, key=lambda x: (not isinstance(x, int), x if isinstance(x, int) else 999)):
        st = _q(spec_groups[k])
        st['key'] = k
        st['label'] = spec_label(k)
        specs.append(st)

    tiers = {}
    for r in records:
        tiers.setdefault(r['tier'], []).append(r['price'])
    tier_rows = [dict(_q(v), key=k, label=TIER_LABEL.get(k, k)) for k, v in
                 sorted(tiers.items(), key=lambda kv: -len(kv[1]))]

    # ---- 自家 10 片 / 手工款的直接对标池（唯一可比的池子）
    comparable = [r for r in records if r['spec'] == 10 or r['tier'] == 'handmade']
    comp = _q([r['price'] for r in comparable])
    comp_items = sorted(({'title': r['title'], 'price': r['price'], 'platform': r['platform'],
                          'url': r['url']} for r in comparable), key=lambda x: -x['price'])[:12]

    # ---- 盈亏表：围绕保本价与市场中位取点
    anchors = sorted({round(p, 2) for p in
                      [m['be_org'], m['be_full'], 25.0, 29.7, 35.0, 49.9, 69.0]
                      if p})
    econ = [cost_mod.econ(p, m) for p in anchors]

    # ---- 价格变动（与上一次运行比）
    movers = []
    if prev_records:
        pk = {_rec_key(r): r['price'] for r in prev_records}
        for r in records:
            k = _rec_key(r)
            if k in pk and abs(pk[k] - r['price']) >= 0.5:
                delta = round(r['price'] - pk[k], 2)
                movers.append({'title': r['title'][:70], 'platform': r['platform'],
                               'from': pk[k], 'to': r['price'], 'delta': delta,
                               'pct': round(delta / pk[k], 4)})
        movers.sort(key=lambda x: -abs(x['pct']))

    # ---- 数据健康
    ok_src = [s for s in sources if s['status'] == 'ok']
    snap = [r for r in records if r.get('snapshot_at')]
    dates = sorted({r['observed_at'] for r in records if r.get('observed_at')})
    # 链接是否指向单品。样本采集自搜索列表页，多个商品共用同一个 URL，
    # 这样的链接点进去看到的是一整个列表，不是价格出处。
    urls = [r['url'] for r in records if r.get('url')]
    url_uniq = len(set(urls))
    item_recs = sum(1 for r in records if _is_item_url(r.get('url')))
    item_urls = sum(1 for u in set(urls) if _is_item_url(u))

    return {
        'n': n,
        'n_raw': records_all,
        'samples': n,
        'median': round(statistics.median(prices), 2) if prices else None,
        'mean': round(sum(prices) / n, 2) if n else None,
        'p25': _q(prices)['p25'] if prices else None,
        'p75': _q(prices)['p75'] if prices else None,
        'min': min(prices) if prices else None,
        'max': max(prices) if prices else None,
        'bands': bands,
        'specs': specs,
        'tiers': tier_rows,
        'comparable': comp,
        'comparable_n': len(comparable),
        'comparable_items': comp_items,
        'over_be': len(over),
        'over_be_ratio': round(len(over) / n, 4) if n else None,
        'over_be_full': len(over_full),
        'over_be_full_ratio': round(len(over_full) / n, 4) if n else None,
        'econ': econ,
        'movers': movers[:12],
        'delta': _delta(records, prev_records, prev_meta),
        'scale': cost_mod.scale(m),
        'sources_ok': len(ok_src),
        'sources_total': len(sources),
        'snapshot_rate': round(len(snap) / n, 4) if n else 0,
        'urls': {
            'total': len(urls),
            'unique': url_uniq,
            'item_records': item_recs,
            'item_links': item_urls,
            'item_ratio': round(item_recs / n, 4) if n else 0,
            'is_item_level': item_recs >= 0.9 * n if n else False,
        },
        'observed_dates': dates,
        'cost': {
            'fixed': m['fixed'], 'be_org': m['be_org'], 'be_full': m['be_full'],
            'parts': m['parts'], 'rates': m['rates'],
            'r_org': round(m['r_org'], 4), 'r_full': round(m['r_full'], 4),
            'fx': m['fx'], 'product': m['product'], 'status': m['status'],
        },
    }


def versions(records):
    """同一款的不同卖家/变体提示。只提示，不合并。"""
    g = {}
    for r in records:
        g.setdefault(r['variant_key'], []).append(r)
    dup = [v for v in g.values() if len(v) > 1]
    return {
        'variant_groups': len(g),
        'multi_seller_groups': len(dup),
        'examples': [{'key': v[0]['variant_key'],
                      'n': len(v),
                      'prices': sorted({x['price'] for x in v})[:6],
                      'title': v[0]['title'][:60]} for v in dup[:8]],
    }
