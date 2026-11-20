# -*- coding: utf-8 -*-
"""落盘：每天一份不可变快照，再更新 latest 与索引。

这样设计的原因：报告一旦发出去，数据就不能再变。所以 history 只写不改，
latest 只是指向最新那天的副本。要回溯任何一天的数字，读 history 里那一份就行。
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, 'data')
HIST = os.path.join(DATA, 'history')


def _w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _r(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def prev_run(date):
    """上一天（严格早于 date）的快照。没有就返回 None。"""
    if not os.path.isdir(HIST):
        return None
    files = sorted(f[:-5] for f in os.listdir(HIST)
                   if f.endswith('.json') and f[:-5] != 'index' and f[:-5] < date)
    if not files:
        return None
    return _r(os.path.join(HIST, files[-1] + '.json'))


def _backfill(runs):
    """整理索引条目，返回可保留的那些。

    做两件事：
    1. 快照文件已经不存在的条目直接剔除。索引每次 save 都从旧索引重建，
       如果只删了 json 却没删条目，归档页会出现一条点开就 404 的记录。
    2. 早期条目没有 changed / data_date 两个字段，从各自的快照里补。
       补不出来就留 None，不猜。快照本身不动，只修索引。
    """
    alive = []
    for r in runs:
        path = os.path.join(HIST, r['date'] + '.json')
        if not os.path.exists(path):
            continue
        if not (r.get('data_date') is not None and 'changed' in r):
            snap = _r(path) or {}
            if r.get('data_date') is None:
                r['data_date'] = (snap.get('meta') or {}).get('data_date')
            if 'changed' not in r:
                d = snap.get('delta') or {}
                # 没有 delta 段的旧快照补不出「变了没」，留 None，页面就不显示标记
                r['changed'] = d.get('changed') if d.get('has_prev') else None
        alive.append(r)
    return alive


def save(date, payload, records):
    snap = dict(payload)
    snap['records'] = records
    _w(os.path.join(HIST, date + '.json'), snap)

    latest = dict(snap)
    latest['meta'] = dict(snap['meta'], is_latest=True)
    _w(os.path.join(DATA, 'latest.json'), latest)

    idx = _r(os.path.join(HIST, 'index.json')) or {'runs': []}
    runs = [r for r in idx['runs'] if r['date'] != date]
    runs.append({
        'date': date,
        'run_at': payload['meta']['generated_at'],
        'n': payload['n'],
        'median': payload['median'],
        'over_be_ratio': payload['over_be_ratio'],
        'sources_ok': payload['sources_ok'],
        'sources_total': payload['sources_total'],
        'report': payload['meta'].get('report_url'),
        # 这一版和上一版比有没有新东西。归档页靠它把「同一批数据的第 N 次统计」
        # 标出来，否则列表会长成一串一模一样的行，看着像每天都在更新。
        'changed': (payload.get('delta') or {}).get('changed'),
        'data_date': payload['meta'].get('data_date'),
    })
    runs.sort(key=lambda r: r['date'])
    runs = _backfill(runs)
    _w(os.path.join(HIST, 'index.json'), {'runs': runs})

    # file:// 双击打开时 fetch 会被 CORS 挡掉，所以再落一份 JS 镜像作为兜底。
    # 它只是镜像，真源始终是 data/latest.json，页面优先读 JSON。
    mirror = 'window.__CODESCALE__=%s;\n' % json.dumps(
        {'data': latest, 'runs': runs}, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(DATA, 'latest.js'), 'w', encoding='utf-8') as f:
        f.write(mirror)

    _bust_cache(payload['meta']['generated_at'])
    return snap


def _bust_cache(stamp):
    """把 index.html 里 latest.js 的引用换成本次运行的时间戳。

    不这么做的话，浏览器会拿缓存里的 old latest.js 渲染，页面显示的是上一次的数字，
    而且完全看不出来 —— 数据看着正常，只是停在昨天。file:// 和 Pages 上都会这样。
    每次运行换一个 URL，浏览器就必须重新拉。
    """
    import re
    page = os.path.join(ROOT, 'index.html')
    if not os.path.exists(page):
        return
    with open(page, encoding='utf-8') as f:
        html = f.read()
    v = re.sub(r'\D', '', stamp)[:14]
    new = re.sub(r'(src="data/latest\.js)(\?v=\d+)?(")',
                 r'\g<1>?v=%s\g<3>' % v, html)
    if new != html:
        with open(page, 'w', encoding='utf-8') as f:
            f.write(new)


def index():
    return _r(os.path.join(HIST, 'index.json')) or {'runs': []}
