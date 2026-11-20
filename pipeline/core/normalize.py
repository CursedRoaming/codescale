# -*- coding: utf-8 -*-
"""归一化：把各来源的原始记录压成统一结构。

三条铁律（改代码前先读）：
  1. 缺值写 None，不写 0。0 会被后面所有统计当成真值。
  2. 规格与品牌从标题抽，抽不到就标 None，不猜。
  3. 每条记录都带 dedupe_key 与 evidence_method，没有证据的记录不许进报表。
"""

import hashlib
import re
import unicodedata

# 国际品牌（有品牌溢价的对照组）
BRAND_KW = ('kiss', 'impress', 'one love', 'dashing diva', 'gluroo', 'curvlife')

# 手工 / 定制（跟自家 10 片手工甲同类，是唯一可对标的池子）
HAND_KW = ('artesanal', 'artesanais', 'feito a mao', 'feita a mao', 'feitos a mao',
           'handmade', 'sob medida', 'personalizad', 'customizad')

# 标题里的数字未必是片数（「24 Coracoes」= 24 颗水钻）
SPEC_FALSE_POS = ('coracoes', 'corações')

# 裸数字白名单：只在没有「24 un / 24 pcs」这类显式写法时才认。
# 10 不在里面：型号里的 10 太常见（如 Olho de Gato FM411 10），实测会误判。
SPEC_BARE = (12, 16, 20, 24, 30, 32, 36, 48, 72, 100)


def num(v):
    """巴西格式数字。返回 float 或 None。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if v is None:
        return None
    s = str(v).strip().replace('R$', '').replace('\u00a0', '').replace(' ', '')
    if s in ('', '-', '--', 'N/A', 'nan'):
        return None
    if re.match(r'^-?[\d.]*,\d+$', s):
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def normalize_text(t):
    t = unicodedata.normalize('NFKD', str(t or ''))
    t = ''.join(ch for ch in t if not unicodedata.combining(ch))
    t = t.lower()
    t = re.sub(r'[^a-z0-9]+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def spec_of(title):
    """片数。返回 int / 'child' / 'fp'(数字非片数) / None。"""
    t = normalize_text(title)
    if any(k in t for k in SPEC_FALSE_POS):
        return 'fp'
    if 'infantil' in t or 'crianca' in t:
        return 'child'
    m = re.search(r'(\d{2,3})\s*(?:un|unhas|unha|unid|unidade|unidades|pecas|peca|pcs|tips|dicas|cartela)\b', t)
    if m:
        return int(m.group(1))
    m = re.search(r'\b(\d{2,3})\b', t)
    if m and int(m.group(1)) in SPEC_BARE:
        return int(m.group(1))
    return None


def tier_of(title, spec):
    """款式分层：brand / handmade / white / unknown。"""
    t = normalize_text(title)
    if any(k in t for k in BRAND_KW):
        return 'brand'
    if any(k in t for k in HAND_KW):
        return 'handmade'
    if spec in (24, 10) or isinstance(spec, int):
        return 'white'
    return 'unknown'


def variant_key(platform, title, spec):
    """粗归一键：同平台同规格同前三个词，视为同一款的不同卖家/变体。
    这不是精确 SKU 归一，只用来做「疑似重复」提示，别拿它当唯一键。
    """
    words = [w for w in normalize_text(title).split() if not w.isdigit()][:3]
    return '%s|%s|%s' % (platform, spec, '-'.join(words))


def dedupe_key(platform, title, price):
    """完全重复判据：同平台 + 同标题 + 同价。与紫竹页面口径一致，便于对照。"""
    raw = '%s|%s|%.2f' % (platform, normalize_text(title), price or 0)
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]


def record(raw, platform, source_id, default_date=None):
    """把一条原始记录转成标准记录。缺价的直接返回 None（不进统计）。"""
    title = (raw.get('title') or '').strip()
    price = num(raw.get('price_brl') if 'price_brl' in raw else raw.get('price'))
    if not title or price is None or price <= 0:
        return None
    spec = spec_of(title)
    return {
        'platform': platform,
        'source': source_id,
        'title': title,
        'price': round(price, 2),
        'original_price': num(raw.get('original_price_brl') or raw.get('original_price')),
        'discount_pct': num(raw.get('discount_pct')),
        'rating': num(raw.get('rating')),
        'sold': num(raw.get('sold') or raw.get('monthly_sold_display') or raw.get('sold_signal')),
        'spec': spec,
        'tier': tier_of(title, spec),
        'url': raw.get('source_url') or raw.get('url') or '',
        'observed_at': raw.get('observed_at') or raw.get('retrieved_date') or default_date,
        'evidence_method': raw.get('evidence_method') or 'unknown',
        'snapshot_at': raw.get('snapshot_at') or '',
        'dedupe_key': dedupe_key(platform, title, price),
        'variant_key': variant_key(platform, title, spec),
    }


def dedupe(records):
    """去掉完全重复。返回 (保留, 重复条数)。"""
    seen, keep = set(), []
    for r in records:
        if r['dedupe_key'] in seen:
            continue
        seen.add(r['dedupe_key'])
        keep.append(r)
    return keep, len(records) - len(keep)
