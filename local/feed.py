# -*- coding: utf-8 -*-
"""数据源适配器与每日入库。

   产品层与采集器解耦：页面只认「某天有一条快照」，不关心数据从哪来。
   当前内置 DemoSource，用本机真实样本做基线，按日期生成确定性演示快照，
   全程标注 demo，不冒充真实采集。采集器接通后只需实现同样接口替换即可。

   接口约定： Source.fetch(day) -> snapshot dict，且 snapshot['meta']['data_date'] == day。
"""

import copy
import datetime
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, 'data', 'latest.json')
RUNTIME = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(RUNTIME, 'history')  # local/history，与真实 data/history 完全隔离


class Source(object):
    kind = 'base'
    label = '基类'

    def fetch(self, day):
        raise NotImplementedError


class DemoSource(Source):
    """演示源：以真实样本为基线，按日期做确定性小幅漂移。

    漂移只用于演示产品层的时序、窗口与预测链路，不是市场观测值。
    同样的日期永远得到同样的数值，便于复现与测试。
    """

    kind = 'demo'
    label = '演示数据（非真实采集）'

    def __init__(self, baseline=BASELINE):
        with open(baseline, encoding='utf-8') as f:
            self.base = json.load(f)

    @staticmethod
    def _drift(day_str, salt):
        h = hashlib.sha256((day_str + '|' + salt).encode('utf-8')).digest()
        return (int.from_bytes(h[:4], 'big') / 0xFFFFFFFF) * 2 - 1  # [-1,1)

    def fetch(self, day):
        if isinstance(day, datetime.datetime):
            day = day.date()
        ds = day.isoformat()
        days = (day - datetime.date(2026, 11, 6)).days  # 基线观测日
        p = copy.deepcopy(self.base)

        dm = self._drift(ds, 'median') * 1.2 + days * 0.02
        med = round(max(1.0, p['median'] + dm), 2)
        ratio = round(max(0.0, min(1.0, p['over_be_ratio'] + self._drift(ds, 'ratio') * 0.02 + days * 0.0004)), 4)
        n = max(1, p['n'] + round(self._drift(ds, 'n') * 2))

        p['median'] = med
        p['mean'] = round(max(1.0, p['mean'] + dm * 0.8), 2)
        p['over_be_ratio'] = ratio
        p['over_be'] = round(n * ratio)
        p['n'] = n
        p['n_raw'] = n

        meta = p['meta']
        meta['data_date'] = ds
        meta['run_date'] = ds
        meta['generated_at'] = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        meta['freshness_days'] = 0
        meta['source_kind'] = self.kind
        meta['source_label'] = self.label
        meta['demo'] = True
        meta['demo_note'] = '按日期确定性生成的演示快照，用于验证产品链路，非真实市场观测。'
        meta['report_url'] = ''
        meta['is_latest'] = True
        return p


def _load_index():
    fp = os.path.join(HISTORY, 'index.json')
    if not os.path.exists(fp):
        return {'runs': []}
    try:
        with open(fp, encoding='utf-8') as f:
            return json.load(f)
    except (ValueError, OSError):
        return {'runs': []}


def _write_index(idx):
    os.makedirs(HISTORY, exist_ok=True)
    tmp = os.path.join(HISTORY, 'index.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(HISTORY, 'index.json'))


def ingest(day=None, source=None, force=False):
    """把某天快照写入 local/history。幂等：已有同名文件则跳过。

    返回 {'date','written','path','source_kind','source_label'}。
    """
    if day is None:
        day = datetime.date.today()
    if isinstance(day, datetime.datetime):
        day = day.date()
    ds = day.isoformat()
    fp = os.path.join(HISTORY, ds + '.json')
    if os.path.exists(fp) and not force:
        return {'date': ds, 'written': False, 'path': fp, 'reason': 'exists'}

    src = source or DemoSource()
    p = src.fetch(day)
    meta = p.get('meta') or {}
    if meta.get('data_date') != ds:
        raise ValueError('source 返回的 data_date(%s) 与请求日期(%s) 不一致' % (meta.get('data_date'), ds))

    os.makedirs(HISTORY, exist_ok=True)
    tmp = fp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False)
    os.replace(tmp, fp)

    idx = _load_index()
    idx['runs'] = [r for r in idx['runs'] if r.get('date') != ds]
    idx['runs'].append({
        'date': ds,
        'run_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'n': p.get('n'),
        'median': p.get('median'),
        'over_be_ratio': p.get('over_be_ratio'),
        'data_date': ds,
        'source_kind': meta.get('source_kind'),
        'demo': bool(meta.get('demo')),
    })
    idx['runs'].sort(key=lambda r: r['date'])
    _write_index(idx)
    return {
        'date': ds, 'written': True, 'path': fp,
        'source_kind': meta.get('source_kind'),
        'source_label': meta.get('source_label'),
        'demo': bool(meta.get('demo')),
    }


def ensure_today(today=None):
    """登录时调用：保证今天有一条快照。"""
    return ingest(today or datetime.date.today())


def status():
    idx = _load_index()
    runs = idx.get('runs', [])
    return {
        'history_dir': os.path.relpath(HISTORY, ROOT).replace(os.sep, '/'),
        'count': len(runs),
        'first': runs[0]['date'] if runs else None,
        'last': runs[-1]['date'] if runs else None,
        'demo': all(bool(r.get('demo')) for r in runs) if runs else False,
        'source_kinds': sorted(set(str(r.get('source_kind')) for r in runs)),
    }


if __name__ == '__main__':
    import sys
    day = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today()
    print(json.dumps(ingest(day), ensure_ascii=False))
    print(json.dumps(status(), ensure_ascii=False))
