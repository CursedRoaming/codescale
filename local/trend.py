# -*- coding: utf-8 -*-
"""趋势与预测：只读本机历史快照，纯算术，不联网。

原则：
  1. 观测日（data_date）不等于运行日（run_date）。同一观测日只算一个点，
     重复运行不产生新数据点，否则一条旧样本会被画成一条假趋势。
  2. 观测日少于 3 个，不做预测，返回 insufficient，缺口照实写明。
  3. 外推只用线性最小二乘，附带区间与残差，不冒充模型预测。
"""

import datetime
import json
import os


def _read(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def load_snapshots(history_dir):
    """把每次运行压成一条精简快照。文件缺失即跳过，不报错中断。"""
    ip = os.path.join(history_dir, 'index.json')
    if not os.path.exists(ip):
        return []
    out = []
    for run in _read(ip).get('runs', []):
        d = run.get('date')
        if not d:
            continue
        fp = os.path.join(history_dir, d + '.json')
        if not os.path.exists(fp):
            continue
        p = _read(fp)
        meta = p.get('meta') or {}
        out.append({
            'run_date': d,
            'data_date': meta.get('data_date'),
            'generated_at': meta.get('generated_at'),
            'n': p.get('n'),
            'median': p.get('median'),
            'over_be_ratio': p.get('over_be_ratio'),
            'sources_ok': p.get('sources_ok'),
            'sources_total': p.get('sources_total'),
        })
    return sorted(out, key=lambda x: x['run_date'])


def dedupe_by_observed(snaps):
    """同一观测日只留最新一次运行。当前五期快照观测日都是 11-06，
    去重后只剩一个点，这是下面拒绝预测的直接依据。"""
    best = {}
    for s in snaps:
        dd = s.get('data_date')
        if not dd:
            continue
        cur = best.get(dd)
        if cur is None or s['run_date'] > cur['run_date']:
            best[dd] = s
    return [best[k] for k in sorted(best)]


def window(points, days, today):
    """近 N 天窗口，按观测日算，不按运行日。"""
    lo = today - datetime.timedelta(days=days - 1)
    out = []
    for p in points:
        try:
            d = datetime.date.fromisoformat(p['data_date'])
        except (ValueError, TypeError, KeyError):
            continue
        if lo <= d <= today:
            out.append(p)
    return out


def linreg(points, key):
    """最小二乘 y = a + b*x，x 为距首个观测日的天数。样本不足返回 None。"""
    xs, ys = [], []
    try:
        d0 = datetime.date.fromisoformat(points[0]['data_date'])
    except (ValueError, TypeError, KeyError):
        return None
    for p in points:
        try:
            d = datetime.date.fromisoformat(p['data_date'])
        except (ValueError, TypeError, KeyError):
            continue
        y = p.get(key)
        if y is None:
            continue
        xs.append((d - d0).days)
        ys.append(y)
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in resid)
    syy = sum((y - my) ** 2 for y in ys)
    return {
        'a': round(a, 4), 'b': round(b, 4), 'n': n,
        'r2': round(1 - sse / syy, 4) if syy else None,
        'resid_sd': round((sse / (n - 2)) ** 0.5, 4) if n > 2 else None,
    }


def forecast(points, key, horizon_days=7):
    """按现有观测间隔外推一期。区间用残差标准差，不编造置信度。"""
    fit = linreg(points, key)
    if not fit:
        return None
    try:
        d0 = datetime.date.fromisoformat(points[0]['data_date'])
        dlast = datetime.date.fromisoformat(points[-1]['data_date'])
    except (ValueError, TypeError, KeyError):
        return None
    xnext = (dlast - d0).days + horizon_days
    val = fit['a'] + fit['b'] * xnext
    band = fit['resid_sd'] or 0.0
    return {
        'target_date': (dlast + datetime.timedelta(days=horizon_days)).isoformat(),
        'value': round(val, 2),
        'low': round(val - 1.96 * band, 2),
        'high': round(val + 1.96 * band, 2),
        'basis_n': fit['n'],
        'r2': fit['r2'],
        'method': '线性最小二乘外推',
    }


def analyze(history_dir, today=None):
    today = today or datetime.date.today()
    snaps = load_snapshots(history_dir)
    points = dedupe_by_observed(snaps)
    w7 = window(points, 7, today)
    w30 = window(points, 30, today)

    def series(pts):
        return [{
            'data_date': p['data_date'], 'median': p.get('median'),
            'over_be_ratio': p.get('over_be_ratio'), 'n': p.get('n'),
        } for p in pts]

    result = {
        'today': today.isoformat(),
        'run_count': len(snaps),
        'unique_observed': len(points),
        'latest_observed': points[-1]['data_date'] if points else None,
        'stale_days': (today - datetime.date.fromisoformat(points[-1]['data_date'])).days
        if points and points[-1].get('data_date') else None,
        'week': {'days': 7, 'n': len(w7), 'points': series(w7)},
        'month': {'days': 30, 'n': len(w30), 'points': series(w30)},
        'forecast': {'available': False, 'reason': '', 'median': None, 'over_be_ratio': None},
    }

    if len(points) >= 3:
        result['forecast'] = {
            'available': True,
            'reason': '',
            'median': forecast(points, 'median'),
            'over_be_ratio': forecast(points, 'over_be_ratio'),
        }
    else:
        result['forecast']['reason'] = (
            '只有 %d 个不同观测日，至少需要 3 个才做外推。'
            '重复运行同一批样本不产生新数据点，此处不以估算值填充。' % len(points)
        )
    return result


if __name__ == '__main__':
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'history')
    print(json.dumps(analyze(root), ensure_ascii=False, indent=2))
