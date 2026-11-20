# -*- coding: utf-8 -*-
"""码尺平台 · 每日数据管线

    python pipeline/run.py                 跑今天
    python pipeline/run.py --date 2026-11-20  指定日期（回放/补跑）
    python pipeline/run.py --dry           只打印，不落盘

流程：采集 → 归一 → 去重 → 指标 → 落盘 → 出报告
任何一路源失败都不中断，失败原因原样记进 data 和网页。
"""

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from core import cost as cost_mod          # noqa: E402
from core import metrics, normalize, report, store   # noqa: E402
import sources as sources_pkg              # noqa: E402


def now_cn():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def platform_of(raw, default):
    """平台名归一。样本里同时存在 Shopee / Shopee BR / Shopee Brasil 三种写法，
    精确匹配会漏，所以按前缀认。"""
    name = str(raw.get('platform') or '').strip().lower()
    if not name:
        return default
    if name.startswith('mercado'):
        return 'mercadolivre'
    if name.startswith('shopee'):
        return 'shopee'
    if name.startswith('tiktok'):
        return 'tiktok_shop'
    if name.startswith('kola'):
        return 'kalodata'
    if name.startswith('amazon'):
        return 'amazon'
    if name.startswith('未标注'):
        return 'unknown'
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None, help='YYYY-MM-DD，默认今天（北京时间）')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    cfg = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
    run_date = a.date or now_cn().strftime('%Y-%m-%d')
    stamp = now_cn().isoformat(timespec='seconds')

    # ---------------- 采集
    results, raws = [], []
    for src in cfg['sources']:
        fn = sources_pkg.get(src['id'])
        if not fn:
            continue
        try:
            res = fn(src, {'run_date': run_date})
        except Exception as e:                              # noqa: BLE001
            from sources.base import Result
            res = Result(src['id'], src.get('name', src['id'])).fail('error', '%s: %s' % (type(e).__name__, e))
        results.append(res)
        raws.extend((platform_of(r, src['id']), src['id'], r) for r in res.records)

    # ---------------- 归一 + 去重
    recs = []
    # 不传 default_date：缺观测日的记录就留空。拿运行日顶替观测日，
    # 等于伪造新鲜度，这个数一旦写进网页就再也纠不回来了。
    for plat, sid, raw in raws:
        r = normalize.record(raw, plat, sid)
        if r:
            recs.append(r)
    kept, dup = normalize.dedupe(recs)

    prev = store.prev_run(run_date)
    prev_records = (prev or {}).get('records') or None
    prev_meta = (prev or {}).get('meta') or None

    p = metrics.compute(kept, [r.as_dict() for r in results], len(raws),
                        prev_records, prev_meta)
    p['sources'] = [r.as_dict() for r in results]
    p['dedupe'] = {'in': len(recs), 'kept': len(kept), 'dropped': dup,
                   'invalid': len(raws) - len(recs)}
    p['variants'] = metrics.versions(kept)
    # 单因素敏感性：哪一项动 10% 把保本线推得最远。纯算术，不依赖外部数据。
    p['sensitivity'] = cost_mod.sensitivity(cost_mod.model())

    dates = p['observed_dates']
    fresh = (datetime.date.fromisoformat(run_date) - datetime.date.fromisoformat(dates[-1])).days if dates else None

    p['meta'] = {
        'site': cfg['brand']['name'],
        'site_en': cfg['brand']['name_en'],
        'tagline': cfg['brand']['tagline'],
        'version': cfg['brand']['version'],
        'schema': 1,
        'run_date': run_date,
        'generated_at': stamp,
        'data_date': dates[-1] if dates else None,
        'freshness_days': fresh,
        'report_url': 'reports/%s.html' % run_date,
        'currency': cfg['cost']['currency'],
        'schedule': cfg['schedule'],
    }
    # 判读文案只在这里生成一次，网页与日报共用，避免两处口径打架
    p['verdict'] = report.conclusions(p)

    if a.dry:
        print(json.dumps({k: p[k] for k in ('n', 'median', 'comparable_n', 'over_be_ratio', 'sources')},
                         ensure_ascii=False, indent=1))
        return

    store.save(run_date, p, kept)
    hp, mp = report.write(p)

    # ---------------- 终端摘要
    c = p['cost']
    print('码尺 · %s 运行完成' % run_date)
    print('  样本 %d 条（原始 %d，无效 %d，重复 %d）' % (p['n'], p['n_raw'], p['dedupe']['invalid'], dup))
    print('  中位 %s ｜ 到仓 %s ｜ 不投流保本 %s ｜ 投流保本 %s'
          % (report._brl(p['median']), report._brl(c['fixed']),
             report._brl(c['be_org']), report._brl(c['be_full'])))
    print('  可比样本 %d 条 ｜ 保本线以上 %d/%d' % (p['comparable_n'], p['over_be'], p['n']))
    for s in p['sources']:
        print('  [%-14s] %-14s %4d 条  %s' % (s['status'], s['name'], s['records'], s['reason'][:56]))
    print('  → %s' % hp)
    print('  → %s' % mp)


if __name__ == '__main__':
    main()
