# -*- coding: utf-8 -*-
"""本地产品层测试：认证、演示源、入库、趋势、模型回退。
   全部在临时目录运行，不碰真实 runtime/ 与 local/history/。"""

import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import auth   # noqa: E402
import feed   # noqa: E402
import model  # noqa: E402
import trend  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.patches = [
            mock.patch.object(auth, 'RUNTIME', self.d),
            mock.patch.object(auth, 'ACCOUNTS', os.path.join(self.d, 'accounts.json')),
            mock.patch.object(feed, 'HISTORY', os.path.join(self.d, 'history')),
            mock.patch.object(model, 'RUNTIME', self.d),
            mock.patch.object(model, 'CONF', os.path.join(self.d, 'model.json')),
        ]
        for p in self.patches:
            p.start()
        auth._sessions.clear()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        auth._sessions.clear()
        self.tmp.cleanup()


class AuthTest(Base):
    def test_register_login_logout(self):
        self.assertTrue(auth.register('alice', 'password123'))
        self.assertFalse(auth.register('alice', 'other12345'))  # 重名
        self.assertIsNone(auth.login('alice', 'wrongpass'))
        tok = auth.login('alice', 'password123')
        self.assertTrue(tok)
        self.assertEqual(auth.verify(tok), 'alice')
        self.assertIsNone(auth.verify('bad-token'))
        auth.logout(tok)
        self.assertIsNone(auth.verify(tok))

    def test_password_not_in_plaintext(self):
        auth.register('bob', 'supersecret99')
        with open(auth.ACCOUNTS, encoding='utf-8') as f:
            raw = f.read()
        self.assertNotIn('supersecret99', raw)
        rec = json.loads(raw)['accounts'][0]
        self.assertIn('salt', rec)
        self.assertIn('hash', rec)
        self.assertNotEqual(rec['hash'], rec['salt'])

    def test_format_rules(self):
        self.assertFalse(auth.register('ab', 'password123'))   # 用户名过短
        self.assertFalse(auth.register('carol', 'short'))      # 密码过短
        self.assertTrue(auth.register('carol_1', 'password123'))


class FeedTest(Base):
    def test_demo_deterministic_and_labeled(self):
        src = feed.DemoSource()
        day = datetime.date(2026, 11, 20)
        a = src.fetch(day)
        b = src.fetch(day)
        self.assertEqual(a['median'], b['median'])
        self.assertEqual(a['meta']['data_date'], '2026-11-20')
        self.assertTrue(a['meta']['demo'])
        self.assertEqual(a['meta']['source_kind'], 'demo')

    def test_different_days_differ(self):
        src = feed.DemoSource()
        a = src.fetch(datetime.date(2026, 11, 20))
        b = src.fetch(datetime.date(2026, 11, 21))
        self.assertNotEqual(a['median'], b['median'])

    def test_ingest_idempotent_and_index(self):
        r1 = feed.ingest(datetime.date(2026, 11, 20))
        self.assertTrue(r1['written'])
        r2 = feed.ingest(datetime.date(2026, 11, 20))
        self.assertFalse(r2['written'])
        feed.ingest(datetime.date(2026, 11, 21))
        feed.ingest(datetime.date(2026, 11, 22))
        st = feed.status()
        self.assertEqual(st['count'], 3)
        self.assertTrue(st['demo'])
        self.assertEqual(st['first'], '2026-11-20')
        self.assertEqual(st['last'], '2026-11-22')


class TrendOnDemoTest(Base):
    def test_forecast_available_after_three_observed_days(self):
        for d in (20, 21, 22, 23):
            feed.ingest(datetime.date(2026, 11, d))
        r = trend.analyze(feed.HISTORY, today=datetime.date(2026, 11, 23))
        self.assertEqual(r['unique_observed'], 4)
        self.assertTrue(r['forecast']['available'])
        self.assertIsNotNone(r['forecast']['median']['value'])


class ModelTest(Base):
    def test_fallback_when_unconfigured(self):
        pts = [{'data_date': '2026-11-%02d' % d, 'median': 20 + d} for d in (20, 21, 22)]
        r = model.predict(pts)
        self.assertEqual(r['origin'], 'builtin')
        self.assertTrue(r['available'])

    def test_key_masked_not_echoed(self):
        pub = model.save({'endpoint': 'https://api.example.com/v1/chat/completions',
                          'model': 'demo-model', 'api_key': 'sk-1234567890abcdef'})
        self.assertTrue(pub['configured'])
        self.assertTrue(pub['api_key_set'])
        self.assertNotIn('sk-1234567890abcdef', json.dumps(pub, ensure_ascii=False))
        self.assertIn('*', pub['api_key_mask'])
        with open(model.CONF, encoding='utf-8') as f:
            raw = f.read()
        self.assertIn('sk-1234567890abcdef', raw)  # 原文只落本机文件

    def test_clear(self):
        model.save({'endpoint': 'https://x/v1', 'model': 'm'})
        pub = model.clear()
        self.assertFalse(pub['configured'])
        self.assertFalse(os.path.exists(model.CONF))


if __name__ == '__main__':
    unittest.main(verbosity=2)
