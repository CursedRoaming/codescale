# -*- coding: utf-8 -*-
"""日报生成：一份能直接发给老板看的 HTML，一份能贴进微信的短文案。

每条结论都必须挂数字，算不出的写「--」并说明为什么算不出。
报告里不许出现「显著」「大幅」这类没有阈值的词。
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORTS = os.path.join(ROOT, 'reports')

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font:15px/1.75 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:#16181d;background:#f4f5f7;padding:28px 14px}
.wrap{max-width:900px;margin:0 auto;background:#fff;border-radius:14px;padding:40px 44px;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.kicker{font-size:11.5px;letter-spacing:2.4px;color:#8e93a0;text-transform:uppercase}
h1{font-size:26px;letter-spacing:-.5px;margin:8px 0 6px}
.sub{color:#767c8a;font-size:12.5px;margin-bottom:26px}
.lead3{border-left:3px solid #5b47c7;background:#f7f5ff;padding:16px 20px;border-radius:0 8px 8px 0;margin-bottom:26px}
.lead3 p{font-size:15px;margin-bottom:7px}
.lead3 p:last-child{margin-bottom:0}
.lead3 b{color:#3d2f9e}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:30px}
.kpi{border:1px solid #eaecf0;border-radius:10px;padding:14px 16px}
.kpi .lab{font-size:11.5px;color:#767c8a}
.kpi .val{font-size:21px;font-weight:600;margin-top:4px;font-variant-numeric:tabular-nums}
.kpi .note{font-size:11px;color:#9aa1ae;margin-top:2px;line-height:1.45}
.kpi.bad .val{color:#c62828}
.kpi.warn .val{color:#a86400}
.kpi.ok .val{color:#0b7a3e}
h2{font-size:16.5px;margin:34px 0 4px;padding-bottom:8px;border-bottom:1px solid #eaecf0}
.lead{font-size:13px;color:#5a606e;margin:9px 0 14px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px 8px;border-bottom:1px solid #f0f1f4;text-align:right;font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left}
th{color:#767c8a;font-weight:500;font-size:11.5px}
tr.be td{background:#f2f6ff;font-weight:600}
tr.hi td{background:#fff9f0}
.neg{color:#c62828}.pos{color:#0b7a3e}
.bars{margin-top:8px}
.bar{display:grid;grid-template-columns:96px 1fr 74px;gap:10px;align-items:center;margin-bottom:7px;font-size:12.5px}
.bar .tr{height:20px;background:#f2f3f6;border-radius:4px;overflow:hidden}
.bar .fl{height:100%;background:#c9ccd4;border-radius:4px}
.bar.over .fl{background:#5b47c7}
.bar .vv{text-align:right;color:#5a606e}
.src{display:grid;grid-template-columns:130px 88px 1fr;gap:10px;font-size:12.5px;padding:9px 0;border-bottom:1px solid #f4f5f7;align-items:start}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px}
.d-ok{background:#0b7a3e}.d-off{background:#c9ccd4}.d-block{background:#c62828}.d-warn{background:#e08a00}
.foot{margin-top:32px;padding-top:16px;border-top:1px solid #eaecf0;font-size:11.5px;color:#9aa1ae;line-height:1.9}
.flag{display:inline-block;font-size:11px;padding:2px 7px;border-radius:5px;background:#fff1f0;color:#c62828;margin-left:6px}
.alert{border:1px solid #f0c9a0;background:#fffaf2;border-radius:10px;padding:14px 18px;margin-bottom:24px}
.alert .t{font-size:13px;font-weight:600;color:#8a5200;margin-bottom:5px}
.alert p{font-size:12.5px;color:#6b5a44;line-height:1.7}
.alert b{color:#8a5200}
@media print{body{background:#fff;padding:0}.wrap{box-shadow:none;padding:0;max-width:none}}
@media(max-width:760px){.kpis{grid-template-columns:1fr 1fr}.wrap{padding:26px 20px}}
"""


def _brl(v):
    return '--' if v is None else 'R$ %.2f' % v


def _pct(v, d=0):
    return '--' if v is None else ('%.*f%%' % (d, v * 100))


def _signed(v):
    if v is None:
        return '--'
    if abs(v) < 0.005:
        return '0.00'
    return ('−' if v < 0 else '+') + ('%.2f' % abs(v))


def _num(v):
    """带千分位的金额。用于月净利这种四位数以上的量。"""
    if v is None:
        return '--'
    return '{:,.0f}'.format(v)


def _dot(status):
    return {'ok': 'd-ok', 'empty': 'd-warn', 'not_configured': 'd-off',
            'disabled': 'd-off', 'blocked': 'd-block', 'error': 'd-block'}.get(status, 'd-off')


STATUS_CN = {'ok': '已接入', 'empty': '无新数据', 'not_configured': '待配置',
             'disabled': '未接入', 'blocked': '被拦截', 'error': '出错'}


def _banner(p):
    """只在「这份报告其实没有新东西」时才出现。

    每天自动跑一次，源没接通时每次跑出来的数完全一样。若不承认这件事，
    就会每天发一份内容相同的「新一期」给客户，那比不发更糟。
    所以这里把没有变化这件事做成页面最上面的一块，不藏在脚注里。
    """
    d = p.get('delta') or {}
    lag = p['meta'].get('freshness_days')
    stale = lag is not None and lag >= 3

    if not d.get('has_prev'):
        head = '这是第一份快照，没有上一版可比'
        body = ('从今天起每天落一份不可变快照。明天的这一页会显示条数、商品和价格的变动。')
    elif d.get('changed') is False:
        head = '本版没有新数据'
        body = ('本次运行没有取到任何新记录：条数、商品、价格与 %s 那版逐项相同。'
                '这不是新一期行情，是同一批数据的再次统计。'
                % (d.get('prev_date') or '上一'))
    else:
        # 有变化就不需要这块了，变化本身写在第五节
        return ''

    if stale:
        body += ('<br>数据观测日仍是 <b>%s</b>，距今 <b>%d 天</b>。'
                 '要换一批数，只能从数据源进来：Kalodata 导出的 CSV 放进 '
                 '<code>pipeline/inbox/</code>，或接通任一平台源。'
                 % (p['meta'].get('data_date') or '--', lag))

    return '<div class="alert"><div class="t">%s</div><p>%s</p></div>' % (head, body)


def _scale_lead(sc):
    """规模刻度那一节的开场句。用最低价档和「单件净利最接近十元」那档做对比，
    因为这两档的差距最能说明「贴着保本线定价」有多不划算。"""
    grid, targets = sc.get('grid') or [], sc.get('targets') or []
    if len(grid) < 2 or not targets:
        return ''
    lo = grid[0]
    mid = min(grid[1:], key=lambda g: abs(g['unit_org'] - 10))
    t = targets[len(targets) // 2]
    i_lo, i_mid = grid.index(lo), grid.index(mid)
    u_lo, u_mid = t['by_price'][i_lo]['units'], t['by_price'][i_mid]['units']

    if not u_lo or not u_mid:
        return ''
    return ('贴着保本线定价（%s）时单件只赚 %s，要卖 <b>%s 单</b>才够 R$%s 的月净利。'
            '把价抬到 %s，单件 %s，<b>%s 单</b>就够。'
            % (_brl(lo['price']), _signed(lo['unit_org']), _num(u_lo), _num(t['target']),
               _brl(mid['price']), _signed(mid['unit_org']), _num(u_mid)))


def _conclusions(p):
    """三句话结论。全部由数字驱动，不含形容词。"""
    c = p['cost']
    out = []
    if p['comparable_n'] == 0:
        out.append('今天的样本里，<b>没有一条</b>是 10 片手工甲，自家产品当前<b>没有可比价格</b>。'
                   '下面的市场价只能当行情看，不能当定价依据。')
    else:
        comp = p['comparable']
        net = round(comp['median'] * (1 - c['r_org']) - c['fixed'], 2)
        out.append('10 片手工甲／手工款样本 <b>%d 条</b>，中位 %s（%s–%s）。'
                   '按这个价位卖，不投流%s。'
                   % (comp['n'], _brl(comp['median']), _brl(comp['p25']), _brl(comp['p75']),
                      ('净利 %s' % _signed(net)) if net >= 0 else ('每副亏 %s' % _brl(abs(net)))))
        if comp['n'] < 5:
            out.append('但这组只有 %d 条，且部分同价，<b>只能当价格上限看</b>，不足以定价。'
                       '要定价，样本得先补到 20 条以上。' % comp['n'])
    out.append('到仓成本 %s，不投流保本 <b>%s</b>，投流保本 <b>%s</b>。'
               '全样本 %d 条报价里，%s 条（%s）站在不投流保本线以上，%s 条（%s）站在投流保本线以上。'
               % (_brl(c['fixed']), _brl(c['be_org']), _brl(c['be_full']),
                  p['n'], p['over_be'], _pct(p['over_be_ratio']),
                  p['over_be_full'], _pct(p['over_be_full_ratio'])))
    ok = [s for s in p['sources'] if s['status'] == 'ok']
    u = p.get('urls') or {}
    if not u.get('is_item_level'):
        link = ('%d 条记录只对应 <b>%d 个链接</b>，其中指向具体商品的只有 %d 个，'
                '其余是搜索列表页和店铺首页。数据里只有 <b>%d 条</b>（%s）点进去能看到那个商品，'
                '剩下的都找不到这条价格的原处。'
                % (u.get('total', 0), u.get('unique', 0), u.get('item_links', 0),
                   u.get('item_records', 0), _pct(u.get('item_ratio'))))
    elif p['snapshot_rate'] < 0.99:
        link = '链接指向单品，但<b>没有存页面快照</b>，客户追问时拿不出当时的截图。'
    else:
        link = '每条都能回溯到当时页面。'
    out.append('数据侧：%d 路源里 %d 路有数，快照留存率 %s。%s'
               % (p['sources_total'], len(ok), _pct(p['snapshot_rate'], 0), link))
    return out


def render_html(p):
    c = p['cost']
    kpi = [
        ('今日样本', '%d 条' % p['n'], '去重后 · 原始 %d' % p['n_raw'], ''),
        ('全样本中位价', _brl(p['median']), '跨品类混合，不作定价依据', 'warn'),
        ('不投流保本价', _brl(c['be_org']), '投流需 %s' % _brl(c['be_full']), 'bad'),
        ('可比样本', '%d 条' % p['comparable_n'], '10 片或手工款', 'bad' if p['comparable_n'] == 0 else 'ok'),
    ]
    kpis = ''.join('<div class="kpi %s"><div class="lab">%s</div><div class="val">%s</div>'
                   '<div class="note">%s</div></div>' % (k, l, v, nt) for l, v, nt, k in kpi)

    # 一、成本
    parts = ''.join('<div class="bar"><div>%s</div><div class="tr"><div class="fl" '
                    'style="width:%.0f%%"></div></div><div class="vv">%s</div></div>'
                    % (lab, v / c['fixed'] * 100, _brl(v)) for lab, v in c['parts'])
    rates = ''.join('<tr><td>%s</td><td>%s</td></tr>' % (lab, _pct(v, 2)) for lab, v in c['rates'])

    # 二、价格带
    mx = max([b['n'] for b in p['bands']] or [1]) or 1
    bars = ''.join(
        '<div class="bar%s"><div>%s</div><div class="tr"><div class="fl" style="width:%.0f%%"></div></div>'
        '<div class="vv">%d 条</div></div>'
        % (' over' if b['over_break_even'] else '', b['label'], b['n'] / mx * 100, b['n'])
        for b in p['bands'])

    # 三、规格
    rows_spec = ''.join(
        '<tr><td>%s</td><td>%d</td><td>%s</td><td>%s–%s</td><td>%s–%s</td></tr>'
        % (s['label'], s['n'], _brl(s['median']), _brl(s['p25']), _brl(s['p75']),
           _brl(s['min']), _brl(s['max'])) for s in p['specs'])

    rows_tier = ''.join(
        '<tr><td>%s</td><td>%d</td><td>%s</td><td>%s–%s</td></tr>'
        % (t['label'], t['n'], _brl(t['median']), _brl(t['min']), _brl(t['max']))
        for t in p['tiers'])

    # 四、盈亏
    rows_e = ''
    for e in p['econ']:
        mark = ''
        if abs(e['price'] - c['be_org']) < 0.05 or abs(e['price'] - c['be_full']) < 0.05:
            mark = ' class="be"'
        rows_e += ('<tr%s><td>%s%s</td><td>%s</td><td class="%s">%s</td><td class="%s">%s</td></tr>'
                   % (mark, _brl(e['price']),
                      '（不投流保本）' if abs(e['price'] - c['be_org']) < 0.05 else
                      ('（投流保本）' if abs(e['price'] - c['be_full']) < 0.05 else ''),
                      _brl(c['fixed']),
                      'neg' if e['full'] < 0 else 'pos', _signed(e['full']),
                      'neg' if e['org'] < 0 else 'pos', _signed(e['org'])))

    # 五、规模刻度
    sc = p.get('scale') or {}
    rows_sc, rows_need, scale_lead = '', '', ''
    if sc.get('grid'):
        head_v = ''.join('<th>%s 单</th>' % _num(v) for v in sc['volumes'])
        rows_sc = ''.join(
            '<tr><td>%s</td><td class="%s">%s</td>%s</tr>'
            % (_brl(g['price']),
               'neg' if g['unit_org'] < 0 else 'pos', _signed(g['unit_org']),
               ''.join('<td class="%s">%s</td>'
                       % ('neg' if c < 0 else 'pos', _num(c)) for c in g['cells']))
            for g in sc['grid'])
        rows_sc = ('<table><thead><tr><th>售价</th><th>单件净利</th>%s</tr></thead>'
                   '<tbody>%s</tbody></table>' % (head_v, rows_sc))

        th_t = ''.join('<th>月利 %s</th>' % _num(t['target']) for t in sc['targets'])
        body = ''
        for i, g in enumerate(sc['grid']):
            cells = ''
            for t in sc['targets']:
                b = t['by_price'][i]
                cells += ('<td>%s</td>' % (_num(b['units']) + ' 单')) if b['units'] \
                    else '<td style="color:#c62828">到不了</td>'
            body += '<tr><td>%s</td><td>%s</td>%s</tr>' % (_brl(g['price']), _signed(g['unit_org']), cells)
        rows_need = ('<table><thead><tr><th>售价</th><th>单件净利</th>%s</tr></thead>'
                     '<tbody>%s</tbody></table>' % (th_t, body))
        scale_lead = _scale_lead(sc)

    # 六、异动
    if p['movers']:
        rows_mv = ('<table><thead><tr><th>商品</th><th>平台</th><th>上一版</th><th>本版</th><th>变动</th>'
                   '</tr></thead><tbody>'
                   + ''.join(
                       '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>'
                       % (m['title'], m['platform'], _brl(m['from']), _brl(m['to']),
                          'neg' if m['delta'] > 0 else 'pos', _pct(m['pct'], 1))
                       for m in p['movers'])
                   + '</tbody></table>')
    else:
        rows_mv = '<div class="lead" style="margin:0">本次运行没有可比的上一版数据，价格变动从明天起可见。</div>'

    # 六、源
    srcs = ''.join(
        '<div class="src"><div><span class="dot %s"></span>%s</div><div>%s · %d 条</div>'
        '<div style="color:#767c8a">%s</div></div>'
        % (_dot(s['status']), s['name'], STATUS_CN.get(s['status'], s['status']),
           s['records'], s['reason']) for s in p['sources'])

    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(site)s 日报 %(date)s</title><style>%(css)s</style></head><body><div class="wrap">
<div class="kicker">%(site_en)s · DAILY READS</div>
<h1>穿戴甲 · 巴西站日报</h1>
<div class="sub">%(date)s 生成 · 数据观测日 %(obs)s · 样本 %(n)d 条 · 口径 %(product)s</div>

%(banner)s
<div class="lead3">%(concl)s</div>
<div class="kpis">%(kpis)s</div>

<h2>一、成本与保本价</h2>
<div class="lead">自家产品的成本，与市场价无关。所有保本判断都从这里出发。</div>
<div class="bars">%(parts)s</div>
<div class="lead" style="margin-top:16px">到仓成本 %(fixed)s ＝ 采购 ＋ 头程 ＋ 仓储。费率如下（占售价）：</div>
<table style="max-width:440px"><thead><tr><th>费率项</th><th>比例</th></tr></thead><tbody>%(rates)s</tbody></table>
<div class="lead">不投流口径只含平台佣金、税、SFP 包邮，合计 %(r_org)s；投流口径再加广告与达人，合计 %(r_full)s。</div>

<h2>二、价格带分布</h2>
<div class="lead">%(n)d 条报价按价格分档。深色档位整体站在不投流保本线 %(be_org)s 以上。</div>
<div class="bars">%(bars)s</div>

<h2>三、规格与分层</h2>
<div class="lead">按标题里的片数分组。未标规格的样本占比越高，中位价越不可直接引用。</div>
<table><thead><tr><th>规格</th><th>条数</th><th>中位价</th><th>25–75 分位</th><th>区间</th></tr></thead>
<tbody>%(rows_spec)s</tbody></table>
<div class="lead" style="margin-top:18px">同一规格里再按品牌溢价拆一层：</div>
<table><thead><tr><th>分层</th><th>条数</th><th>中位价</th><th>区间</th></tr></thead>
<tbody>%(rows_tier)s</tbody></table>

<h2>四、单副盈亏</h2>
<div class="lead">到仓成本 %(fixed)s／副固定。蓝色行是保本点。</div>
<table><thead><tr><th>售价</th><th>到仓成本</th><th>投流净利</th><th>不投流净利</th></tr></thead>
<tbody>%(rows_e)s</tbody></table>

<h2>五、规模刻度</h2>
<div class="lead">%(scale_lead)s</div>
<div class="lead" style="margin-top:2px">月净利 =（售价 ×（1 − 费率）− 到仓成本）× 月单量。下面是<b>不投流</b>口径，费率 %(r_org)s。</div>
%(rows_sc)s
<div class="lead" style="margin-top:18px">反过来看：要拿到目标月净利，各个价位分别需要多少单。</div>
%(rows_need)s
<div class="lead" style="margin-top:12px;color:#8a5200">
<b>这是刻度，不是预测。</b>单量是假设出来的横轴，不含退货、滞销、平台活动亏损与汇率波动。
它回答「卖到这个量，账上是什么样」，不回答「能不能卖到这个量」。</div>

<h2>六、价格异动</h2>
<div class="lead">与上一版快照比较，变动绝对值 ≥ R$0.50 的记录。</div>
%(rows_mv)s

<h2>七、数据可靠性</h2>
<div class="lead">每路源的真实状态。状态是事实，不是故障报告。</div>
%(srcs)s
<div class="foot">
<b>口径</b>：%(status)s。全部金额为巴西雷亚尔，参考汇率 R$1 ≈ ¥%(fx)s。<br>
<b>不能得出的结论</b>：全市场销量排名、哪个价格带成交最多、哪类款式在爆发、评论比例代表整体偏好。
这几项需要连续多日样本与成交数据，当前样本不支持。<br>
<b>可比性</b>：自家产品为 10 片手工甲，市场样本以 24 片机器甲为主，两者不可直接相减。
本报告不给出「自家产品应当定价多少」的结论，只给成本线与行情分布。<br>
<b>生成</b>：%(run_at)s · 管线自动生成，未经人工改写
</div>
</div></body></html>""" % {
        'css': CSS, 'site': p['meta']['site'], 'site_en': p['meta']['site_en'],
        'date': p['meta']['run_date'], 'obs': '、'.join(p['observed_dates']) or '--',
        'n': p['n'], 'product': c['product'],
        'concl': ''.join('<p>%s</p>' % s for s in _conclusions(p)),
        'banner': _banner(p),
        'kpis': kpis, 'parts': parts, 'rates': rates,
        'fixed': _brl(c['fixed']), 'r_org': _pct(c['r_org'], 1), 'r_full': _pct(c['r_full'], 1),
        'be_org': _brl(c['be_org']), 'bars': bars,
        'rows_spec': rows_spec, 'rows_tier': rows_tier, 'rows_e': rows_e,
        'rows_mv': rows_mv, 'srcs': srcs,
        'rows_sc': rows_sc, 'rows_need': rows_need, 'scale_lead': scale_lead,
        'status': c['status'], 'fx': c['fx'], 'run_at': p['meta']['generated_at'],
    }


def render_md(p):
    """微信短版。控制在 10 行内，直接可粘。"""
    c = p['cost']
    d = p.get('delta') or {}
    L = ['**码尺日报 · 穿戴甲巴西站 · %s**' % p['meta']['run_date'], '']
    if d.get('has_prev') and d.get('changed') is False:
        L.append('> 本次无新数据：与 %s 那版逐项相同，数据观测日仍是 %s。不是新一期行情。'
                 % (d.get('prev_date') or '上一', p['meta'].get('data_date') or '--'))
        L.append('')
    L.append('样本 %d 条（去重后），观测日 %s。' % (p['n'], '、'.join(p['observed_dates']) or '--'))
    L.append('全样本中位 %s；到仓成本 %s。' % (_brl(p['median']), _brl(c['fixed'])))
    L.append('不投流保本 %s，投流保本 %s。' % (_brl(c['be_org']), _brl(c['be_full'])))
    if p['comparable_n'] == 0:
        L.append('10 片手工甲的可比样本 0 条，今天不给定价结论。')
    else:
        L.append('10 片手工甲可比样本 %d 条，中位 %s。' % (p['comparable_n'], _brl(p['comparable']['median'])))
    L.append('市场报价里 %s 站在不投流保本线以上（%d/%d）。' % (_pct(p['over_be_ratio']), p['over_be'], p['n']))
    ok = [s for s in p['sources'] if s['status'] == 'ok']
    L.append('数据源 %d/%d 有数，快照留存 %s。' % (len(ok), p['sources_total'], _pct(p['snapshot_rate'])))
    L.append('')
    L.append('全文：reports/%s.html' % p['meta']['run_date'])
    return '\n'.join(L)


conclusions = _conclusions


def write(p):
    os.makedirs(REPORTS, exist_ok=True)
    d = p['meta']['run_date']
    hp = os.path.join(REPORTS, d + '.html')
    mp = os.path.join(REPORTS, d + '.md')
    with open(hp, 'w', encoding='utf-8') as f:
        f.write(render_html(p))
    with open(mp, 'w', encoding='utf-8') as f:
        f.write(render_md(p))
    return hp, mp
