# -*- coding: utf-8 -*-
"""成本模型与保本价。

口径（2026-11-18 客户口述后更新，比之前的版本更硬）：
    产品       手工甲，10 片/套，单件 20g
    采购       R$ 13.23（NA-001/002/003/005/009 五款均值）
    头程       R$ 3.60（D 口述 180 BRL/kg x 0.02kg = 3.60）
    仓储       R$ 3.00（按件入库/出库计费）
    到仓合计   R$ 19.83

费率（占售价比例）：
    平台佣金 22.78% / 广告 12.46% / 达人 11.69% / 税 4.46% / SFP 包邮 6.00%
    投流口径   = 平台 + 广告 + 达人 + 税 + SFP = 47.39%
    不投流口径 = 平台 + 税 + SFP           = 33.24%

⚠ 这两个数是自家 10 片手工甲的成本，不是市场 24 片机器甲的成本。
  任何「拿 19.83 减 24 片市场价」的算法都是错的，品类不同。
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(os.path.dirname(HERE), 'config.json')


def load():
    with open(CONFIG, encoding='utf-8') as f:
        return json.load(f)['cost']


def model(cfg=None):
    c = cfg or load()
    fixed = c['purchase'] + c['first_mile'] + c['warehouse']
    r_full = c['platform'] + c['ad'] + c['kol'] + c['tax'] + c['sfp']
    r_org = c['platform'] + c['tax'] + c['sfp']
    return {
        'currency': c['currency'],
        'fixed': round(fixed, 2),
        'r_full': r_full,
        'r_org': r_org,
        'be_org': round(fixed / (1 - r_org), 2),
        'be_full': round(fixed / (1 - r_full), 2),
        'parts': [
            ('采购', c['purchase']),
            ('头程入仓', c['first_mile']),
            ('海外仓储', c['warehouse']),
        ],
        'rates': [
            ('平台佣金', c['platform']),
            ('广告', c['ad']),
            ('达人佣金', c['kol']),
            ('税', c['tax']),
            ('SFP 包邮', c['sfp']),
        ],
        'fx': c.get('fx_brl_to_cny'),
        'status': c.get('status', ''),
        'product': c.get('product', ''),
    }


def econ(price, m=None):
    """给定售价，返回三种口径下的净利。"""
    m = m or model()
    return {
        'price': round(price, 2),
        'gross': round(price - m['fixed'], 2),
        'full': round(price * (1 - m['r_full']) - m['fixed'], 2),
        'org': round(price * (1 - m['r_org']) - m['fixed'], 2),
    }


# 规模刻度用的档位。价格取电商常见尾数，且最低一档在保本价之上，
# 免得表格里出现一排「这价必亏」的空行。单量档跨两个数量级。
SCALE_PRICES = (29.90, 34.90, 39.90, 49.90, 59.90, 69.00)
SCALE_VOLUMES = (100, 300, 500, 1000, 3000)
# 目标月净利。取值参考：R$3000 约合 ¥4100，是一个人一个月的量级。
SCALE_TARGETS = (1500, 3000, 6000)


def scale(m=None, prices=None, volumes=None, targets=None):
    """售价 × 月单量 → 月净利。以及反过来：要拿到目标月利，需要多少单。

    ⚠ 这是刻度，不是预测。单量是假设出来的横轴，不含退货、滞销、平台活动
      亏损、汇率波动。它回答的是「如果卖到这个量，账上会是什么样」，
      不回答「能不能卖到这个量」。后者只有成交数据能答。
    """
    m = m or model()
    prices = list(prices or SCALE_PRICES)
    volumes = list(volumes or SCALE_VOLUMES)
    targets = list(targets or SCALE_TARGETS)

    unit = {p: round(p * (1 - m['r_org']) - m['fixed'], 2) for p in prices}
    unit_full = {p: round(p * (1 - m['r_full']) - m['fixed'], 2) for p in prices}

    grid = []
    for p in prices:
        grid.append({
            'price': p,
            'unit_org': unit[p],
            'unit_full': unit_full[p],
            # 每档单量下的月净利（不投流口径）。负数照实给，不置零。
            'cells': [round(unit[p] * v, 2) for v in volumes],
        })

    # 目标月利 → 需要多少单。分母 ≤0 时不给数，返回 None，
    # 因为「这个价怎么卖都到不了」写成一个巨大的数字会被误读成可行。
    need = []
    for t in targets:
        row = {'target': t, 'by_price': []}
        for p in prices:
            u = unit[p]
            row['by_price'].append({
                'price': p,
                'units': (int(-(-t // u)) if u > 0 else None),
                'unit_org': u,
            })
        need.append(row)

    return {
        'prices': prices,
        'volumes': volumes,
        'grid': grid,
        'targets': need,
        'basis': '不投流',
        'r_org': round(m['r_org'], 4),
        'r_full': round(m['r_full'], 4),
        'caveat': '单量是假设的横轴，不是预测。不含退货、滞销、活动亏损与汇率波动。',
    }


# 敏感性分析的驱动项。(标签, 类型, config 字段, 是否进不投流口径)
# 采购、头程、仓储是固定成本；平台/税/SFP 同时进两个费率口径；
# 广告与达人只进投流口径，所以它们动的时候 be_org 不动，be_full 才动。
DRIVERS = (
    ('采购价', 'fixed', 'purchase', True),
    ('头程运费', 'fixed', 'first_mile', True),
    ('仓储费', 'fixed', 'warehouse', True),
    ('平台佣金', 'rate', 'platform', True),
    ('税费', 'rate', 'tax', True),
    ('SFP 包邮', 'rate', 'sfp', True),
    ('广告费率', 'rate', 'ad', False),
    ('达人佣金', 'rate', 'kol', False),
)


def sensitivity(m=None, step=0.10, anchor=39.90):
    """单因素敏感性：每个驱动项各动 ±step，保本价与单件净利跟着动多少。

    做法是一次只动一个变量，其余按住不动。这不是预测，是排优先级用的：
    哪一项动 10% 会把保本线推得最远，就先盯哪一项。

    汇率单独处理，因为它不是成本项，是计价尺。采购以人民币结算，
    所以 1 BRL 能换多少 CNY 一变，同一件货的雷亚尔成本就反着变。
    fx 上升（雷亚尔更贵）→ 同样的人民币采购折成更少的雷亚尔 → 成本降。
    """
    m = m or model()
    c = load()
    base_fixed = c['purchase'] + c['first_mile'] + c['warehouse']
    base_r_org = c['platform'] + c['tax'] + c['sfp']
    base_r_full = base_r_org + c['ad'] + c['kol']

    def be(fixed, r):
        return round(fixed / (1 - r), 2) if r < 1 else None

    def net(price, fixed, r):
        return round(price * (1 - r) - fixed, 2)

    rows = []

    def push(label, kind, value, lo, hi, fmt, lo_v=None, hi_v=None, scope='org'):
        """lo / hi 是同一组 (fixed, r_org, r_full) 三元组；lo_v / hi_v 是该变量自身的新值。

        scope 说明这一项动的时候哪个口径跟着动。广告与达人只进投流口径，
        所以它们的摆幅要按 be_full 算，按 be_org 算会得到 0，看上去像是没影响。
        """
        be_lo = be(lo[0], lo[1])
        be_hi = be(hi[0], hi[1])
        be_full_lo = be(lo[0], lo[2])
        be_full_hi = be(hi[0], hi[2])
        swing_org = round(abs((be_hi or 0) - (be_lo or 0)), 2)
        swing_full = round(abs((be_full_hi or 0) - (be_full_lo or 0)), 2)
        rows.append({
            'label': label,
            'kind': kind,
            'value': value,
            'fmt': fmt,
            'scope': scope,
            'low': round(lo_v, 2) if fmt == 'brl' else round(lo_v, 4),
            'high': round(hi_v, 2) if fmt == 'brl' else round(hi_v, 4),
            'be_org_low': be_lo,
            'be_org_high': be_hi,
            'be_org_swing': swing_org,
            'be_full_low': be_full_lo,
            'be_full_high': be_full_hi,
            'be_full_swing': swing_full,
            'swing': swing_org if scope == 'org' else swing_full,
            'net_low': net(anchor, lo[0], lo[1]),
            'net_high': net(anchor, hi[0], hi[1]),
            'net_swing': round(abs(net(anchor, hi[0], hi[1]) - net(anchor, lo[0], lo[1])), 2),
            # 只进投流口径的项（广告、达人）在不投流净利上不会有任何变化，
            # 用它得出一排「+6.81 不变」等于告诉读者这项没影响，是错的。
            'net_full_low': net(anchor, lo[0], lo[2]),
            'net_full_high': net(anchor, hi[0], hi[2]),
        })

    for label, kind, key, in_org in DRIVERS:
        v = c[key]
        scope = 'org' if in_org else 'full'
        if kind == 'fixed':
            fixed_lo = base_fixed - v * step
            fixed_hi = base_fixed + v * step
            push(label, kind, v, (fixed_lo, base_r_org, base_r_full),
                 (fixed_hi, base_r_org, base_r_full), 'brl',
                 lo_v=v * (1 - step), hi_v=v * (1 + step), scope=scope)
        else:
            r_org_lo = base_r_org - (v * step if in_org else 0)
            r_org_hi = base_r_org + (v * step if in_org else 0)
            r_full_lo = base_r_full - v * step
            r_full_hi = base_r_full + v * step
            push(label, kind, v, (base_fixed, r_org_lo, r_full_lo),
                 (base_fixed, r_org_hi, r_full_hi), 'rate',
                 lo_v=v * (1 - step), hi_v=v * (1 + step), scope=scope)

    # 汇率：把采购折成人民币固定，再看 fx 上下 10% 时折回多少雷亚尔。
    fx = c.get('fx_brl_to_cny')
    if fx:
        cny = c['purchase'] * fx
        p_lo = cny / (fx * (1 + step))   # fx 上升 → 雷亚尔成本下降
        p_hi = cny / (fx * (1 - step))
        fixed_lo = base_fixed - c['purchase'] + p_lo
        fixed_hi = base_fixed - c['purchase'] + p_hi
        push('汇率', 'fx', fx, (fixed_lo, base_r_org, base_r_full),
             (fixed_hi, base_r_org, base_r_full), 'fx',
             lo_v=fx * (1 + step), hi_v=fx * (1 - step), scope='org')
        rows[-1]['cny_purchase'] = round(cny, 2)

    rows.sort(key=lambda r: r['swing'], reverse=True)

    base = {
        'fixed': round(base_fixed, 2),
        'r_org': round(base_r_org, 4),
        'r_full': round(base_r_full, 4),
        'be_org': be(base_fixed, base_r_org),
        'be_full': be(base_fixed, base_r_full),
        'net_org': net(anchor, base_fixed, base_r_org),
        'net_full': net(anchor, base_fixed, base_r_full),
    }

    return {
        'step': step,
        'anchor': anchor,
        'base': base,
        'rows': rows,
        'top': rows[0]['label'] if rows else None,
        'caveat': '一次只动一个变量，其余按住。这不是预测，是排优先级：'
                  '哪一项动 10% 把保本线推得最远，就先盯哪一项。',
        'no_sum': '摆幅不能相加。汇率与采购是同一笔钱的两个视角，同时动不等于两项相加。',
    }
