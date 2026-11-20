# -*- coding: utf-8 -*-
"""Kalodata CSV 导入器的单元测试。

只用标准库，跑法：

    cd 09_码尺平台
    python -m unittest discover -s pipeline/tests -v

为什么要有这个文件：巴西数字格式是这一路最容易出错的地方，错法还很隐蔽，
「1.234」到底是 1234 还是 1.234 取决于语境，静默算错比报错危险得多。
所以规则写死在 num() 里，用例写死在这里，改动后重跑就知道有没有把别处弄坏。
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from sources import kalodata                                    # noqa: E402
from sources.kalodata import num, price_of, sold_of, _map_header, _platform_of  # noqa: E402


class TestNum(unittest.TestCase):
    """数字清洗：分隔符后 3 位当千分位，1-2 位当小数点。"""

    CASES = [
        # 巴西写法：点做千分、逗号做小数
        ('R$ 1.234,56', 1234.56),
        ('R$ 1.099,00', 1099.00),
        ('R$ 29,90', 29.90),
        ('R$ 189,00', 189.00),
        ('R$45,90', 45.90),                 # 货币符号后无空格
        ('BR$ 45,90', 45.90),
        ('7,99', 7.99),
        ('45,9', 45.90),                    # 一位小数也认
        # 英文写法：逗号做千分、点做小数
        ('1,234.56', 1234.56),
        ('29.90', 29.90),
        # 千分位
        ('1,234', 1234.0),
        ('1.234', 1234.0),
        ('12,345,678', 12345678.0),
        ('1.234.567', 1234567.0),
        # 量级后缀
        ('1.2万', 12000.0),
        ('12K', 12000.0),
        ('12k', 12000.0),
        ('2.5w', 25000.0),
        ('3千', 3000.0),
        # 空白与负数
        ('  89,99  ', 89.99),
        ('-5,50', -5.50),
    ]

    def test_cases(self):
        for raw, want in self.CASES:
            with self.subTest(raw=raw):
                got = num(raw)
                self.assertIsNotNone(got, '认不出：%r' % raw)
                self.assertAlmostEqual(got, want, places=2, msg='%r -> %r' % (raw, got))

    def test_none_and_garbage(self):
        for raw in ('', '   ', '-', '—', 'N/A', '面议', 'sk-xxx', None, True, False):
            with self.subTest(raw=raw):
                self.assertIsNone(num(raw), '本该认不出，却给了值：%r' % (raw,))

    def test_price_bounds(self):
        self.assertIsNone(price_of('0'))
        self.assertIsNone(price_of('-5'))
        self.assertIsNone(price_of('200000'))       # 超过 10 万当脏数据
        self.assertEqual(price_of('R$ 29,90'), 29.9)
        self.assertEqual(price_of('7,99'), 7.99)

    def test_sold_int(self):
        self.assertEqual(sold_of('1,234'), 1234)
        self.assertEqual(sold_of('1.2万'), 12000)
        self.assertIsNone(sold_of('-1'))


class TestHeader(unittest.TestCase):
    """表头识别：三套语言都要认，且不能串列。"""

    def test_chinese(self):
        m = _map_header(['商品名称', '商品价格', '月销量', '销售额', '评分', '店铺名称', '平台', '商品链接'])
        self.assertEqual(m['title'], 0)
        self.assertEqual(m['price_brl'], 1)
        self.assertEqual(m['sold'], 2)
        self.assertEqual(m['gmv'], 3)
        self.assertEqual(m['rating'], 4)
        self.assertEqual(m['shop'], 5)
        self.assertEqual(m['platform'], 6)
        self.assertEqual(m['source_url'], 7)

    def test_english(self):
        m = _map_header(['Product Name', 'Price', 'Units Sold', 'GMV', 'Rating', 'Shop', 'Platform', 'URL'])
        self.assertEqual(m['title'], 0)
        self.assertEqual(m['price_brl'], 1)
        self.assertEqual(m['sold'], 2)
        self.assertEqual(m['gmv'], 3)

    def test_portuguese(self):
        m = _map_header(['Nome do produto', 'Preço', 'Vendas', 'Faturamento', 'Avaliação', 'Loja'])
        self.assertEqual(m['title'], 0)
        self.assertEqual(m['price_brl'], 1)
        self.assertEqual(m['sold'], 2)
        self.assertEqual(m['gmv'], 3)

    def test_bom_and_parens(self):
        m = _map_header(['\ufeff商品名称', '商品价格(雷亚尔)', '销量（件）'])
        self.assertEqual(m['title'], 0)
        self.assertEqual(m['price_brl'], 1)
        self.assertEqual(m['sold'], 2)

    def test_price_not_hijacked_by_original(self):
        """「原价」不能被当成售价。"""
        m = _map_header(['商品名称', '原价', '商品价格'])
        self.assertEqual(m['price_brl'], 2, '价格列被抓到原价上了')

    def test_unknown_returns_empty(self):
        self.assertEqual(_map_header(['foo', 'bar', 'baz']), {})


class TestPlatform(unittest.TestCase):
    def test_map(self):
        self.assertEqual(_platform_of('TikTok Shop'), 'tiktok_shop')
        self.assertEqual(_platform_of('Shopee'), 'shopee')
        self.assertEqual(_platform_of('Mercado Livre'), 'mercadolivre')
        self.assertEqual(_platform_of('Amazon'), 'amazon')
        self.assertEqual(_platform_of('', 'tiktok_shop'), 'tiktok_shop')
        self.assertEqual(_platform_of(None, 'tiktok_shop'), 'tiktok_shop')


class TestFetch(unittest.TestCase):
    """整条链路：造文件 -> fetch -> 检查记录。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = kalodata.INBOX
        kalodata.INBOX = self.tmp

    def tearDown(self):
        kalodata.INBOX = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _put(self, name, content, enc='utf-8'):
        with io.open(os.path.join(self.tmp, name), 'w', encoding=enc, newline='') as f:
            f.write(content)

    def _run(self):
        return kalodata.fetch({'id': 'kalodata', 'name': 'Kalodata', 'enabled': True},
                              {'run_date': '2026-11-19'})

    def test_empty_inbox(self):
        r = self._run()
        self.assertEqual(r.status, 'not_configured')
        self.assertEqual(len(r.records), 0)
        self.assertIn('inbox', r.reason)

    def test_chinese_with_bom_and_title_row(self):
        self._put('k.csv', '''Kalodata 商品榜 · 巴西
商品名称,商品价格,月销量,销售额,评分,店铺名称,平台,商品链接,采集日期
"Unhas Postiças Artesanais 10 Peças","R$ 45,90","1.200","R$ 55.080,00",4.8,Nail Studio,TikTok Shop,https://ex.com/a,2026-11-19
"Fita LED","R$ 7,99","1.2万","R$ 95.880,00",4.5,Generic,Shopee,https://ex.com/d,2026-11-19
''', enc='utf-8-sig')
        r = self._run()
        self.assertEqual(r.status, 'ok')
        self.assertEqual(len(r.records), 2)
        a, b = r.records
        self.assertEqual(a['price_brl'], 45.9)
        self.assertEqual(a['sold'], 1200)
        self.assertEqual(a['gmv'], 55080.0)
        self.assertEqual(a['rating'], 4.8)
        self.assertEqual(a['platform'], 'tiktok_shop')
        self.assertEqual(a['observed_at'], '2026-11-19')
        self.assertEqual(b['platform'], 'shopee')
        self.assertEqual(b['sold'], 12000)

    def test_semicolon_portuguese_no_platform_col(self):
        self._put('e.csv', '''Nome do produto;Preço;Vendas;Faturamento
Unhas Postiças 10 Peças;R$ 58,00;210;R$ 12.180,00
''')
        r = self._run()
        self.assertEqual(r.status, 'ok')
        self.assertEqual(len(r.records), 1)
        self.assertEqual(r.records[0]['price_brl'], 58.0)
        self.assertEqual(r.records[0]['platform'], 'tiktok_shop')
        self.assertIn('无平台列', r.reason)

    def test_unquoted_commas_are_dropped_not_silently_accepted(self):
        """字段带逗号没加引号 -> 整行错位。必须丢掉并报出来，不能算进去。"""
        self._put('bad.csv', '''商品名称,商品价格,月销量
Produto A,R$ 45,90,1200
Produto B,R$ 19,99,9800
''')
        r = self._run()
        self.assertEqual(r.status, 'error')
        self.assertEqual(len(r.records), 0)
        self.assertIn('列数对不上', r.reason)

    def test_bad_rows_counted_among_good(self):
        self._put('mix.csv', '''商品名称,商品价格,月销量
Produto A,"R$ 45,90",1200
Produto B,R$ 19,99,9800
''')
        r = self._run()
        self.assertEqual(r.status, 'ok')
        self.assertEqual(len(r.records), 1)
        self.assertIn('丢弃错位行', r.reason)

    def test_skip_blank_and_no_price(self):
        self._put('s.csv', '''商品名称,商品价格
"",""
"Preço a combinar",面议
"Ok","R$ 12,00"
''')
        r = self._run()
        self.assertEqual(len(r.records), 1)
        self.assertEqual(r.records[0]['price_brl'], 12.0)

    def test_unrecognized_file_skipped(self):
        self._put('x.csv', 'foo,bar\n1,2\n')
        r = self._run()
        self.assertEqual(r.status, 'empty')
        self.assertIn('认不出表头', r.reason)

    def test_filename_date_fallback(self):
        self._put('kalodata_20261118.csv', '''商品名称,商品价格
"Produto","R$ 10,00"
''')
        r = self._run()
        self.assertEqual(r.records[0]['observed_at'], '2026-11-18')


if __name__ == '__main__':
    unittest.main(verbosity=2)
