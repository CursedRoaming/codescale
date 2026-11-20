# -*- coding: utf-8 -*-
"""Kalodata 数据源（CSV 导入）。

2026-11-19 实测更正，三件事：
  1. 名字不是 koladata，是 Kalodata（www.kalodata.com）。koladata.com 不存在，四个子域全部连不上。
  2. 它没有开放 API。api.kalodata.com 与 open.kalodata.com 都不解析（DNS 立即失败）。
     产品形态是网页 + iOS/Android App，官方卖的是账号席位，不是接口。
  3. 所以「给一个 API key 就能每天自动拉数」这条路不存在。
     Kalodata 的数据出口是网页界面的导出（CSV），只能人工或半自动触发。

因此这一路适配器不做 HTTP，只做一件事：把导出的 CSV 读进来。
把文件丢进 pipeline/inbox/ 就行，不用改代码：

    pipeline/inbox/kalodata_20261119.csv
    pipeline/inbox/任意名字.csv      ← 文件名不参与解析，只做排序

支持的导出格式（不预设，按表头自动认）：
    中文表头：商品名称 / 价格 / 销量 / 销售额 / 评分 / 店铺 / 平台 / 商品链接
    英文表头：Product Name / Price / Units Sold / GMV / Rating / Shop / Platform / URL
    葡语表头：Nome do produto / Preço / Vendas / Faturamento / Avaliação / Loja / Link

数字清洗按巴西写法处理（这是最容易炸的一处）：
    "R$ 29,90"  -> 29.90        "1.234,56" -> 1234.56
    "1,234.56"  -> 1234.56      "1.2万"    -> 12000
    "12K"       -> 12000        "12,345"   -> 12345

平台归属：Kalodata Global 版含 Amazon + TikTok + Shopee 三个平台，
表里带「平台」列就按列走，没有就按 TikTok Shop 记（它 99% 的样本来自 TikTok）。
"""

import csv
import io
import os
import re

from .base import Result

INBOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'inbox')

# ---------------------------------------------------------------- 列名识别
# 顺序有意义：越具体的候选放前面，避免「价格」被「原价」抢走、「商品名称」被「名称」抢走。
COLS = {
    'title': ('商品名称', '商品标题', '商品名', '产品名称', '标题',
              'product name', 'product title', 'product', 'item name',
              'nome do produto', 'nome', 'produto', 'título'),
    'price_brl': ('商品价格', '售价', '现价', '价格', '单价',
                  'sale price', 'current price', 'price',
                  'preço', 'preco', 'valor'),
    'sold': ('月销量', '销量(件)', '销量', '已售', '成交件数', '成交单量',
             'units sold', 'sold', 'sales', 'orders',
             'vendas', 'vendidos', 'unidades vendidas'),
    'gmv': ('销售额', '成交金额', '营收', 'gmv',
            'revenue', 'faturamento', 'receita'),
    'rating': ('商品评分', '评分', '星级', 'rating', 'star rating', 'stars',
               'avaliação', 'avaliacao', 'nota'),
    'shop': ('店铺名称', '店铺', '商家', '卖家', 'shop name', 'shop', 'store', 'seller',
             'loja', 'vendedor'),
    'platform': ('平台', 'platform', 'marketplace', 'plataforma', 'canal'),
    'source_url': ('商品链接', '商品url', '链接', 'product url', 'item url', 'url', 'link',
                   'link do produto'),
    'category': ('类目', '分类', '品类', 'category', 'categoria'),
    'observed_at': ('采集日期', '统计日期', '快照日期', '日期',
                    'snapshot date', 'collected at', 'date', 'data'),
}

# price 不能被这些列抢走
PRICE_EXCLUDE = ('原价', '市场价', '划线价', '折扣前', 'original', 'list price', 'before',
                 'preço original', 'preco original', 'de ')

PLATFORM_MAP = (
    ('tiktok', 'tiktok_shop'), ('tik tok', 'tiktok_shop'), ('抖音', 'tiktok_shop'),
    ('shopee', 'shopee'), ('虾皮', 'shopee'),
    ('mercado', 'mercadolivre'), ('美客多', 'mercadolivre'), ('mlb', 'mercadolivre'),
    ('amazon', 'amazon'), ('亚马逊', 'amazon'),
)


def _norm(h):
    """表头归一：去 BOM、去空格、去全角括号内容、转小写。"""
    s = str(h or '').replace('\ufeff', '').strip().lower()
    s = re.sub(r'[（(][^)）]*[)）]', '', s)
    return re.sub(r'[\s_\-]+', ' ', s).strip()


def _map_header(headers):
    """表头 -> {标准字段: 列下标}。认不出就留空，不猜。"""
    norm = [_norm(h) for h in headers]
    used = set()
    out = {}
    for field, cands in COLS.items():
        for cand in cands:
            hit = None
            for i, h in enumerate(norm):
                if i in used or not h:
                    continue
                if h == cand:
                    hit = i
                    break
            if hit is None:
                for i, h in enumerate(norm):
                    if i in used or not h:
                        continue
                    if field == 'price_brl' and any(x in h for x in PRICE_EXCLUDE):
                        continue
                    if cand in h:
                        hit = i
                        break
            if hit is not None:
                out[field] = hit
                used.add(hit)
                break
    return out


# ---------------------------------------------------------------- 数字清洗
_UNIT = {'万': 1e4, 'w': 1e4, '千': 1e3, 'k': 1e3, '亿': 1e8, 'm': 1e6}


def num(s):
    """把 "R$ 1.234,56" / "29,90" / "1.2万" / "12K" 转成 float。认不出返回 None。

    判定规则只按「分隔符后几位」走，不猜语言：
        后 3 位  -> 千分位      "1,234"  = 1234      "1.234" = 1234
        后 1-2 位 -> 小数点     "29,90"  = 29.90     "29.9"  = 29.9
        两个分隔符都在，最后出现的那个是小数点
    这条规则的前提是巴西价格永远写两位小数（29,90）。三位小数在电商报价里不存在。
    """
    if s is None:
        return None
    if isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace('\xa0', ' ')
    if not t:
        return None

    # 去货币符号，再取量级后缀
    t = re.sub(r'(?i)(r\$|us\$|brl|usd|cny|rmb|eur|€|¥|\$)', '', t).strip()
    mult = 1.0
    m = re.search(r'(\d[\d\.,]*)\s*(万|亿|千|[kwmKWM])\s*$', t)
    if m:
        mult = _UNIT.get(m.group(2).lower(), 1.0)
        t = m.group(1)
    else:
        t = re.sub(r'[^\d\.,\-]', '', t)
    if not t or t in ('-', '.', ','):
        return None

    neg = t.startswith('-')
    t = t.lstrip('-')
    has_dot, has_comma = '.' in t, ',' in t

    if has_dot and has_comma:
        if t.rfind(',') > t.rfind('.'):          # 1.234,56
            t = t.replace('.', '').replace(',', '.')
        else:                                     # 1,234.56
            t = t.replace(',', '')
    elif has_comma:
        parts = t.split(',')
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            t = ''.join(parts)                # 1,234 / 12,345,678
        else:
            t = t.replace(',', '.')           # 29,90
    elif has_dot:
        parts = t.split('.')
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            t = ''.join(parts)                # 1.234 / 1.234.567
        # 其余按小数：29.9 / 29.90

    try:
        v = float(t) * mult
    except ValueError:
        return None
    return -v if neg else v


def price_of(s):
    v = num(s)
    if v is None or v <= 0 or v > 100000:
        return None
    return round(v, 2)


def sold_of(s):
    v = num(s)
    if v is None or v < 0:
        return None
    return int(round(v))


def _platform_of(s, default='tiktok_shop'):
    t = str(s or '').strip().lower()
    if not t:
        return default
    for k, v in PLATFORM_MAP:
        if k in t:
            return v
    return default


def _read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8-sig', 'utf-8', 'gb18030', 'cp1252'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace'), 'utf-8(替换非法字节)'


def _sniff_delim(text):
    head = text[:4000]
    counts = {d: head.count(d) for d in (',', ';', '\t', '|')}
    return max(counts, key=counts.get) if max(counts.values()) else ','


def _date_from_name(path):
    m = re.search(r'(20\d{2})[-_]?(\d{2})[-_]?(\d{2})', os.path.basename(path))
    if m:
        return '%s-%s-%s' % (m.group(1), m.group(2), m.group(3))
    return None


def fetch(cfg, ctx):
    r = Result('kalodata', cfg.get('name', 'Kalodata'))
    if not cfg.get('enabled', True):
        return r.fail('disabled', '配置里关掉了')

    if not os.path.isdir(INBOX):
        return r.fail('not_configured', '没有 pipeline/inbox 目录，先建一个再把导出的 CSV 放进去')

    files = sorted(f for f in os.listdir(INBOX)
                   if f.lower().endswith(('.csv', '.tsv', '.txt')))
    if not files:
        return r.fail('not_configured',
                      'inbox 为空。Kalodata 无公开 API，数据只能从网页导出 CSV 后放进来')

    run_date = ctx.get('run_date')
    origin = {}          # 平台 -> 条数，写进 reason，让人一眼看出这批是哪的
    skipped = 0
    bad_rows = []
    no_plat = []
    encs = set()
    for fn in files:
        path = os.path.join(INBOX, fn)
        text, enc = _read_text(path)
        encs.add(enc)
        r.bytes += len(text.encode('utf-8'))
        delim = _sniff_delim(text)
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        rows = [x for x in rows if any(str(c).strip() for c in x)]
        if len(rows) < 2:
            skipped += 1
            continue

        head_i, cols = None, None
        for i, cand in enumerate(rows[:8]):        # 有的导出前面带标题行
            m = _map_header(cand)
            if 'title' in m and 'price_brl' in m:
                head_i, cols = i, m
                break
        if cols is None:
            skipped += 1
            continue

        file_date = _date_from_name(path)
        ncol = len(rows[head_i])
        has_plat_col = 'platform' in cols
        got = 0
        shift = 0
        for row in rows[head_i + 1:]:
            # 列数不符 = 字段里带逗号却没加引号，整行已经错位，恢复不了，只能丢。
            # 静默接受会让价格和销量张冠李戴，比丢一行严重得多。
            if len(row) != ncol:
                shift += 1
                continue

            def cell(f, _row=row):
                i = cols.get(f)
                return _row[i] if i is not None and i < len(_row) else None

            title = str(cell('title') or '').strip()
            price = price_of(cell('price_brl'))
            if not title or price is None:
                continue
            plat = _platform_of(cell('platform'))
            obs = str(cell('observed_at') or '').strip() or file_date or run_date
            m = re.search(r'(20\d{2})[-/年.]?(\d{1,2})[-/月.]?(\d{1,2})', obs)
            if m:
                obs = '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3)))
            else:
                obs = file_date or run_date          # 列错到网址之类，退回文件名/运行日
            r.records.append({
                'title': title,
                'price_brl': price,
                'sold': sold_of(cell('sold')),
                'gmv': num(cell('gmv')),
                'rating': num(cell('rating')),
                'shop': str(cell('shop') or '').strip() or None,
                'source_url': str(cell('source_url') or '').strip() or None,
                'observed_at': obs,
                'platform': plat,
                'evidence_method': 'kalodata_csv',
            })
            origin[plat] = origin.get(plat, 0) + 1
            got += 1
        r.requests += 1
        if shift:
            bad_rows.append('%s %d 行' % (fn, shift))
        if not has_plat_col:
            no_plat.append(fn)
        if not got:
            skipped += 1

    if not r.records:
        if bad_rows:
            return r.fail('error',
                          '列数对不上（%s）：字段里带逗号却没加引号，行被切碎了。'
                          '导出时选「带引号 / Excel 兼容」格式再放进来'
                          % '、'.join(bad_rows))
        return r.fail('empty',
                      '认不出表头：%d 个文件都缺「商品名 + 价格」两列。'
                      '把导出文件的第一行表头发我，我加映射' % len(files))

    parts = ['%s %d 条' % (k, v) for k, v in sorted(origin.items(), key=lambda x: -x[1])]
    r.reason = '%d 个文件 / %s（%s）' % (
        len(files), '、'.join(parts),
        encs.pop() if len(encs) == 1 else '+'.join(sorted(encs)))
    if no_plat:
        r.reason += ' · 无平台列，按 TikTok Shop 记'
    if bad_rows:
        r.reason += ' · 丢弃错位行：' + '、'.join(bad_rows)
    if skipped:
        r.reason += ' · %d 个文件未识别' % skipped
    return r
