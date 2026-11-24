"""把每期快照转成可下载的 Word 报告。

输入是 pipeline 计算完成的 payload，不在此处重新计算任何业务指标。
数字口径与 render_html() 完全一致，只是换一种载体。
"""

import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from . import report as R

REPORTS = R.REPORTS


def _money(v):
    return R._brl(v)


def _rate(v, d=2):
    return R._pct(v, d)


def _signed(v):
    return R._signed(v)


def _count(v):
    return R._num(v)


def _set_font(doc):
    st = doc.styles['Normal']
    st.font.name = 'Microsoft YaHei'
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    for name in ('Title', 'Heading 1', 'Heading 2'):
        try:
            s = doc.styles[name]
            s.font.name = 'Microsoft YaHei'
            s.element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
        except KeyError:
            pass


def _table(doc, headers, rows, widths=None):
    if not headers:
        return
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Light Grid Accent 1'
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = str(h)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = '' if v is None else str(v)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                if w:
                    r.cells[i].width = w
    doc.add_paragraph()
    return t


def _lead(doc, text):
    p = doc.add_paragraph(text)
    p.paragraph_format.space_after = Pt(6)
    return p


def _note(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x66, 0x6C, 0x78)
    return p


def build(p):
    """返回 Document 对象。"""
    doc = Document()
    _set_font(doc)
    c = p['cost']
    meta = p['meta']

    title = doc.add_heading('码尺 CodeScale · 穿戴甲巴西站日报', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    sub = doc.add_paragraph(
        '%s 生成 · 数据观测日 %s · 样本 %d 条 · 口径 %s'
        % (meta['run_date'], meta.get('data_date') or '--', p['n'], c['product'])
    )
    sub.runs[0].font.size = Pt(9)
    sub.runs[0].font.color.rgb = RGBColor(0x70, 0x76, 0x84)

    # 状态提示：只在无新增数据时出现
    d = p.get('delta') or {}
    if not d.get('has_prev'):
        _lead(doc, '状态：首份快照，无上一版本可供比较。')
    elif d.get('changed') is False:
        lag = meta.get('freshness_days')
        extra = ('数据观测日仍为 %s，距今 %d 天。'
                 % (meta.get('data_date') or '--', lag)) if lag is not None and lag >= 3 else ''
        _lead(doc, '状态：本版无新增数据。样本数、商品与价格与 %s 版本逐项一致。%s'
              % (d.get('prev_date') or '上一', extra))

    # 结论
    doc.add_heading('结论', level=1)
    for text in R._conclusions(p):
        doc.add_paragraph(text.replace('<b>', '').replace('</b>', ''), style='List Bullet')

    # 关键指标
    doc.add_heading('关键指标', level=1)
    _table(doc, ['项目', '数值', '说明'], [
        ['本期样本', '%d 条' % p['n'], '去重后 · 原始 %d' % p['n_raw']],
        ['全样本中位价', _money(p['median']), '跨品类混合，不作定价依据'],
        ['不投流保本价', _money(c['be_org']), '投流需 %s' % _money(c['be_full'])],
        ['可比样本', '%d 条' % p['comparable_n'], '10 片或手工款'],
    ])

    # 一、成本
    doc.add_heading('一、成本与保本价', level=1)
    _lead(doc, '对标产品的成本结构独立于市场价格。所有保本判断以此为基础。')
    _table(doc, ['成本项', '金额'], [[lab, _money(v)] for lab, v in c['parts']] +
           [['到仓成本', _money(c['fixed'])]])
    _table(doc, ['费率项', '占售价'], [[lab, _rate(v)] for lab, v in c['rates']])
    _note(doc, '不投流口径只含平台佣金、税、SFP 包邮；投流口径再加广告与达人。')

    # 二、价格带
    doc.add_heading('二、价格带分布', level=1)
    _lead(doc, '%d 条报价按挂牌价分档。' % p['n'])
    _table(doc, ['价格带', '条数', '中位价', '高于不投流保本线'],
           [[b['label'], b['n'], _money(b['median']), '是' if b['over_break_even'] else '否']
            for b in p['bands']])

    # 三、规格与分层
    doc.add_heading('三、规格与分层', level=1)
    _lead(doc, '按标题里的片数分组。未标规格的样本占比越高，中位价越不可直接引用。')
    _table(doc, ['规格', '条数', '中位价', '25–75 分位', '区间'],
           [[s['label'], s['n'], _money(s['median']),
             '%s–%s' % (_money(s['p25']), _money(s['p75'])),
             '%s–%s' % (_money(s['min']), _money(s['max']))] for s in p['specs']])
    _lead(doc, '同一规格里再按品牌溢价拆一层：')
    _table(doc, ['分层', '条数', '中位价', '区间'],
           [[t['label'], t['n'], _money(t['median']),
             '%s–%s' % (_money(t['min']), _money(t['max']))] for t in p['tiers']])

    # 四、盈亏
    doc.add_heading('四、单副盈亏', level=1)
    _lead(doc, '到仓成本 %s／副固定。' % _money(c['fixed']))
    rows = []
    for e in p['econ']:
        mark = ''
        if abs(e['price'] - c['be_org']) < 0.05:
            mark = '（不投流保本）'
        elif abs(e['price'] - c['be_full']) < 0.05:
            mark = '（投流保本）'
        rows.append(['%s%s' % (_money(e['price']), mark), _money(c['fixed']),
                     _signed(e['full']), _signed(e['org'])])
    _table(doc, ['售价', '到仓成本', '投流净利', '不投流净利'], rows)

    # 五、规模
    sc = p.get('scale') or {}
    if sc.get('grid'):
        doc.add_heading('五、规模刻度', level=1)
        lead = R._scale_lead(sc).replace('<b>', '').replace('</b>', '')
        if lead:
            _lead(doc, lead)
        _note(doc, '月净利 =（售价 ×（1 − 费率）− 到仓成本）× 月单量。以下为不投流口径。')
        _table(doc, ['售价', '单件净利'] + ['%s 单' % _count(v) for v in sc['volumes']],
               [[_money(g['price']), _signed(g['unit_org'])] + [_count(x) for x in g['cells']]
                for g in sc['grid']])
        _lead(doc, '达到目标月净利所需单量：')
        _table(doc, ['售价', '单件净利'] + ['月利 %s' % _count(t['target']) for t in sc['targets']],
               [[_money(g['price']), _signed(g['unit_org'])] +
                [('%s 单' % _count(t['by_price'][i]['units'])) if t['by_price'][i]['units'] else '无法达到'
                 for t in sc['targets']]
                for i, g in enumerate(sc['grid'])])
        _note(doc, '单量为假设的横轴变量，不含退货、滞销、平台活动亏损与汇率波动。')

    # 六、敏感性
    se = p.get('sensitivity') or {}
    if se.get('rows'):
        doc.add_heading('六、成本敏感性', level=1)
        _lead(doc, '各成本项单独变动 %d%% 时保本价的对应变化。用于确定成本管控的优先顺序。'
              % int(round(se['step'] * 100)))
        def _range(a, b, fmt):
            lo, hi = min(a, b), max(a, b)
            if fmt == 'fx':
                one = lambda x: '¥%.2f' % x
            elif fmt == 'rate':
                one = lambda x: '%.2f%%' % (x * 100)
            else:
                one = _money
            return one(lo) if abs(hi - lo) < 1e-9 else '%s – %s' % (one(lo), one(hi))

        rows = []
        for r in se['rows']:
            full = r['scope'] == 'full'
            keys = (('be_full_low', 'be_full_high', 'net_full_low', 'net_full_high')
                    if full else ('be_org_low', 'be_org_high', 'net_low', 'net_high'))
            be = '%s – %s' % (_money(min(r[keys[0]], r[keys[1]])),
                              _money(max(r[keys[0]], r[keys[1]])))
            net = '%s – %s' % (_signed(min(r[keys[2]], r[keys[3]])),
                               _signed(max(r[keys[2]], r[keys[3]])))
            lab = r['label'] + ('（投流口径）' if full else '')
            rows.append([lab, _range(r['low'], r['high'], r.get('fmt', 'brl')),
                         be, '%.2f' % r['swing'], net])
        _table(doc, ['驱动项', '该项 ±%d%%' % int(round(se['step'] * 100)),
                     '保本价落在', '摆幅', 'R$ 39.90 时单件净利'], rows)
        _note(doc, '摆幅不可相加。汇率与采购成本构成同一笔支出的两个视角。本表不构成预测。')

    # 七、价格异动
    doc.add_heading('七、价格异动', level=1)
    movers = p.get('movers') or []
    if movers:
        _table(doc, ['商品', '上一版', '本版', '变动'],
               [[m.get('title', ''), _money(m.get('old')), _money(m.get('new')),
                 _signed((m.get('new') or 0) - (m.get('old') or 0))] for m in movers])
    else:
        _lead(doc, '本次运行无上一版本可供比较，或变动绝对值未达 R$0.50。')

    # 八、数据可靠性
    doc.add_heading('八、数据可靠性', level=1)
    _table(doc, ['数据源', '状态', '条数', '说明'],
           [[s['name'], R.STATUS_CN.get(s['status'], s['status']), s.get('records', 0),
             s.get('reason', '')] for s in p['sources']])

    # 口径
    doc.add_heading('口径与限制', level=1)
    _note(doc, '表内测算，非实际发生。全部金额为巴西雷亚尔，参考汇率 R$1 ≈ ¥%.2f。' % c['fx'])
    _note(doc, '不能得出的结论：全市场销量排名、哪个价格带成交最多、哪类款式在爆发。'
               '这几项需要连续多日样本与成交数据，当前样本不支持。')
    _note(doc, '可比性：对标产品为 %s，市场样本以 24 片机器甲为主，两者不可直接相减。'
               '本报告不提供定价结论。' % c['product'])
    _note(doc, '生成：%s · 管线自动生成，未经人工改写。' % meta['generated_at'])
    return doc


def write_docx(p):
    """写出 reports/<run_date>.docx，返回绝对路径。"""
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, p['meta']['run_date'] + '.docx')
    build(p).save(path)
    return path
