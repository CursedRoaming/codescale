# -*- coding: utf-8 -*-
"""指标层的测试。跑法：

    python -m unittest discover -s pipeline/tests -v
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core.metrics import _is_item_url, _rec_key, _delta      # noqa: E402
from core import cost                                         # noqa: E402


class TestItemUrl(unittest.TestCase):
    """链接是不是指向「那一个商品」。

    判错的后果是实打实的：说成单品页，客户点进去看到一屏列表，
    这句「能回溯」就变成假话。所以正例反例都要锁住。
    """

    ITEM = [
        'https://produto.mercadolivre.com.br/MLB-2056194557-kit-unhas-posticas-100-un-_JM',
        'https://shopee.com.br/Kit-24-unhas-posticas-realista-floral-i.400179385.22994847146',
        'https://shopee.com.br/1-Kit-24-com-Unhas-i.1066587404.23793594600',
        'https://www.tiktok.com/product/12345',
    ]
    NOT_ITEM = [
        'https://lista.mercadolivre.com.br/kit-unhas-posticas-autocolantes',
        'https://shopee.com.br/list/Unha%20Posti%C3%A7a/Autocolante',
        'https://shopee.com.br/make.mania',          # 店铺首页
        'https://shopee.com.br/pressonnailss',       # 店铺首页
        '', None, 'https://example.com/x',
    ]

    def test_item_urls(self):
        for u in self.ITEM:
            self.assertTrue(_is_item_url(u), u)

    def test_not_item_urls(self):
        for u in self.NOT_ITEM:
            self.assertFalse(_is_item_url(u), u)


class TestRecKey(unittest.TestCase):
    """记录身份。标题写法差一个空格或大小写，不能算成两条不同的东西。"""

    def test_same_after_normalize(self):
        a = {'platform': 'shopee', 'title': 'Kit 24 Unhas Postiças'}
        b = {'platform': 'shopee', 'title': 'kit 24 unhas postiças  '}
        self.assertEqual(_rec_key(a), _rec_key(b))

    def test_platform_matters(self):
        a = {'platform': 'shopee', 'title': 'Kit 24 Unhas'}
        b = {'platform': 'mercadolivre', 'title': 'Kit 24 Unhas'}
        self.assertNotEqual(_rec_key(a), _rec_key(b))


class TestDelta(unittest.TestCase):
    """「这一版有没有新东西」的判定。判错的后果是每天发一份内容相同的日报。"""

    META = {'run_date': '2026-11-19', 'data_date': '2026-11-06'}

    def recs(self, prices):
        return [{'platform': 'shopee', 'title': 'item %d' % i, 'price': p}
                for i, p in enumerate(prices)]

    def test_no_prev(self):
        d = _delta(self.recs([10, 20]), None, None)
        self.assertFalse(d['has_prev'])
        self.assertIsNone(d['changed'])

    def test_identical_is_unchanged(self):
        r = self.recs([10, 20, 30])
        d = _delta(r, r, self.META)
        self.assertTrue(d['has_prev'])
        self.assertIs(d['changed'], False)
        self.assertEqual((d['new'], d['gone'], d['price_moved']), (0, 0, 0))

    def test_new_row_counts_as_change(self):
        d = _delta(self.recs([10, 20, 30]), self.recs([10, 20]), self.META)
        self.assertIs(d['changed'], True)
        self.assertEqual(d['new'], 1)

    def test_gone_row_counts_as_change(self):
        d = _delta(self.recs([10, 20]), self.recs([10, 20, 30]), self.META)
        self.assertIs(d['changed'], True)
        self.assertEqual(d['gone'], 1)

    def test_price_move_below_threshold_is_not_change(self):
        # 0.4 元的变动不触发，阈值是 0.5。这条锁住阈值本身，免得以后被悄悄改掉。
        old = self.recs([10, 20])
        new = self.recs([10, 20.4])
        d = _delta(new, old, self.META)
        self.assertEqual(d['price_moved'], 0)
        self.assertIs(d['changed'], False)

    def test_price_move_at_threshold_is_change(self):
        old = self.recs([10, 20])
        new = self.recs([10, 20.5])
        d = _delta(new, old, self.META)
        self.assertEqual(d['price_moved'], 1)
        self.assertIs(d['changed'], True)


class TestScale(unittest.TestCase):
    """规模刻度。纯算术，全部可以手算核对。"""

    def setUp(self):
        self.m = cost.model()
        self.s = cost.scale(self.m)

    def test_break_even_prices_match_cost_model(self):
        # 保本价处单件净利必须是零。这是整个成本模型的锚点。
        for p, key in ((self.m['be_org'], 'r_org'), (self.m['be_full'], 'r_full')):
            net = p * (1 - self.m[key]) - self.m['fixed']
            self.assertAlmostEqual(net, 0, places=1, msg='%s 保本价处净利应为 0' % key)

    def test_grid_consistent_with_unit(self):
        for g in self.s['grid']:
            for v, c in zip(self.s['volumes'], g['cells']):
                self.assertAlmostEqual(c, g['unit_org'] * v, places=2)

    def test_need_is_ceiling(self):
        # 所需单量必须是向上取整，少一单就到不了目标
        for t in self.s['targets']:
            for row in t['by_price']:
                if row['units'] is None:
                    continue
                self.assertGreaterEqual(row['units'] * row['unit_org'], t['target'])
                self.assertLess((row['units'] - 1) * row['unit_org'], t['target'])

    def test_loss_row_gives_none_not_huge_number(self):
        # 单件亏钱的档位返回 None。返回一个巨大数字会被读成「可行但很难」。
        lossp = cost.scale(self.m, prices=[self.m['be_org'] - 5])
        for t in lossp['targets']:
            self.assertIsNone(t['by_price'][0]['units'])

    def test_caveat_present(self):
        self.assertIn('不是预测', self.s['caveat'])


class TestSensitivity(unittest.TestCase):
    """单因素敏感性。每一项都能手算：保本价 = 固定成本 / (1 - 费率)。"""

    def setUp(self):
        self.m = cost.model()
        self.s = cost.sensitivity(self.m)

    def test_base_matches_cost_model(self):
        # 基准行必须与成本模型完全一致，否则表格与 KPI 上的保本价会打架。
        b = self.s['base']
        self.assertAlmostEqual(b['be_org'], self.m['be_org'], places=2)
        self.assertAlmostEqual(b['be_full'], self.m['be_full'], places=2)
        self.assertAlmostEqual(b['fixed'], self.m['fixed'], places=2)

    def test_fixed_driver_moves_by_weighted_step(self):
        # 固定成本项上下各动 10%，保本价两端之差 = 2 × 该项 × 10% / (1 - r_org)
        row = [r for r in self.s['rows'] if r['label'] == '头程运费'][0]
        expect = 2 * 3.60 * 0.10 / (1 - self.m['r_org'])
        self.assertAlmostEqual(row['be_org_swing'], expect, places=2)

    def test_ad_and_kol_do_not_move_org_break_even(self):
        # 广告与达人不进不投流口径，be_org 必须一动不动
        for label in ('广告费率', '达人佣金'):
            row = [r for r in self.s['rows'] if r['label'] == label][0]
            self.assertEqual(row['be_org_swing'], 0.0)
            self.assertGreater(row['be_full_swing'], 0)
            self.assertEqual(row['scope'], 'full')

    def test_rate_swing_scope_for_platform(self):
        row = [r for r in self.s['rows'] if r['label'] == '平台佣金'][0]
        self.assertGreater(row['be_org_swing'], 0)
        self.assertEqual(row['scope'], 'org')

    def test_fx_moves_opposite_to_purchase(self):
        # fx 上升意味着同样的人民币采购折成更少的雷亚尔，成本下降，保本价下移
        row = [r for r in self.s['rows'] if r['label'] == '汇率'][0]
        self.assertGreater(row['low'], row['high'])          # low 对应 fx 上升
        self.assertLess(row['be_org_low'], row['be_org_high'])

    def test_rows_sorted_by_swing(self):
        swings = [r['swing'] for r in self.s['rows']]
        self.assertEqual(swings, sorted(swings, reverse=True))

    def test_no_sum_warning_present(self):
        # 摆幅可加是这个表最容易被误用的地方，措辞必须写在返回值里
        self.assertIn('不能相加', self.s['no_sum'])


if __name__ == '__main__':
    unittest.main()
