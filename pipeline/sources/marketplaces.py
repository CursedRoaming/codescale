# -*- coding: utf-8 -*-
"""三个电商平台的数据源。都没接上，原因写在每条里，不遮掩。

为什么不做公开页爬虫：2026-11-06 那轮 23 次直连采集全部失败（22 次解析不出结构化商品，
1 次 503），Shopee 与 TikTok 的反爬把这条路整体堵死。再写一遍爬虫是重复劳动，
而且采到的也不会比搜索快照更可采信。正确做法是走授权接口，或者买第三方数据（Kalodata 就是这类）。

下面每条只写实测到的事实。资质门槛（要不要企业、要不要本地主体）以对方商务回复为准，
这里不写，因为核不到原始条款。
"""

from .base import Result

BLOCKERS = {
    # 11-06 实测：23 次直连采集全败，22 次解析不出结构化商品，1 次 503
    'tiktok_shop': '11-06 实测 23 次直连采集全败；需卖家授权或 Partner API',
    # 11-06 实测：列表页只返回 JS 壳，无结构化商品
    'shopee': '11-06 实测列表页只返回 JS 壳；需 Open Platform 账号授权',
    # 11-19 实测：/sites/MLB 200，/sites/MLB/search 403 {"message":"forbidden"}
    'mercadolivre': '11-19 实测商品搜索 403 forbidden，需 access_token；站点元数据仍是 200',
}


def _stub(cfg):
    r = Result(cfg['id'], cfg.get('name', cfg['id']))
    if not cfg.get('enabled'):
        return r.fail('disabled', BLOCKERS.get(cfg['id'], '配置里关掉了'))
    return r.fail('not_configured', '已启用但适配器未实现：' + BLOCKERS.get(cfg['id'], ''))


def fetch_tiktok_shop(cfg, ctx):
    return _stub(cfg)


def fetch_shopee(cfg, ctx):
    return _stub(cfg)


def fetch_mercadolivre(cfg, ctx):
    return _stub(cfg)
