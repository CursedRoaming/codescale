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
