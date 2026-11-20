# -*- coding: utf-8 -*-
"""数据源注册表。加一个平台只改这里 + 写一个 fetch 函数。"""

from . import kalodata, marketplaces, seed

REGISTRY = {
    'kalodata': kalodata.fetch,
    'tiktok_shop': marketplaces.fetch_tiktok_shop,
    'shopee': marketplaces.fetch_shopee,
    'mercadolivre': marketplaces.fetch_mercadolivre,
    'seed': seed.fetch,
}


def get(source_id):
    return REGISTRY.get(source_id)
