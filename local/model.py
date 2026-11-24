# -*- coding: utf-8 -*-
"""自有模型接入适配器。

   使用者填写 endpoint / 密钥 / 模型名，配置只存本机 runtime/，不进网页、
   不进仓库。密钥永不回显给页面，接口只返回「是否已配置」与掩码。
   未配置或调用失败时回退到内置线性规则，并标注结果来源。

   约定：endpoint 接受 OpenAI 兼容的 /v1/chat/completions 请求体。
   这是一条通用接口，不等于任何一家已实测通过；能否调用取决于使用者
   自己的服务是否在线、密钥是否有效。
"""

import json
import os
import re
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(ROOT, 'runtime')
CONF = os.path.join(RUNTIME, 'model.json')

FIELDS = ('endpoint', 'model', 'api_key')


def _ensure():
    os.makedirs(RUNTIME, exist_ok=True)


def load():
    if not os.path.exists(CONF):
        return {}
    try:
        with open(CONF, encoding='utf-8') as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def save(cfg):
    _ensure()
    out = {}
    for k in FIELDS:
        v = (cfg.get(k) or '').strip()
        if v:
            out[k] = v
    tmp = CONF + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CONF)
    return public()


def mask(secret):
    if not secret:
        return ''
    if len(secret) <= 8:
        return '*' * len(secret)
    return secret[:3] + '*' * (len(secret) - 6) + secret[-3:]


def public():
    """给页面看的配置：密钥只给掩码，不给原文。"""
    c = load()
    return {
        'configured': bool(c.get('endpoint') and c.get('model')),
        'endpoint': c.get('endpoint', ''),
        'model': c.get('model', ''),
        'api_key_set': bool(c.get('api_key')),
        'api_key_mask': mask(c.get('api_key', '')),
    }


def clear():
    if os.path.exists(CONF):
        os.remove(CONF)
    return public()


def _builtin(points):
    """内置回退：用现成的线性外推函数，不联网。"""
    import trend  # 同目录，server 已把 local 加进 sys.path
    fc = trend.forecast(points, 'median') if points else None
    if not fc:
        return {
            'origin': 'builtin', 'origin_label': '内置线性规则',
            'available': False, 'reason': '观测点不足，内置规则也无法外推。',
        }
    return {
        'origin': 'builtin', 'origin_label': '内置线性规则',
        'available': True, 'value': fc['value'],
        'low': fc['low'], 'high': fc['high'],
        'r2': fc['r2'], 'basis_n': fc['basis_n'],
        'target_date': fc['target_date'],
        'method': fc['method'],
        'note': '算术外推，不是模型预测。',
    }


def _call_remote(cfg, payload):
    body = json.dumps({
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content':
                '你是选品数据分析助手。只根据给定的观测序列做短期外推，'
                '输出严格 JSON：{"value":数字,"low":数字,"high":数字,"note":"简短理由"}。不要输出其他文字。'},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
        ],
        'temperature': 0,
    }).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if cfg.get('api_key'):
        headers['Authorization'] = 'Bearer ' + cfg['api_key']
    req = urllib.request.Request(cfg['endpoint'], data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read().decode('utf-8', 'replace')
    data = json.loads(raw)
    txt = data['choices'][0]['message']['content']
    m = re.search(r'\{[\s\S]*\}', txt)
    if not m:
        raise ValueError('模型未返回可解析的 JSON')
    obj = json.loads(m.group(0))
    return {
        'origin': 'model', 'origin_label': '自有模型',
        'available': True,
        'value': round(float(obj['value']), 2),
        'low': round(float(obj.get('low', obj['value'])), 2),
        'high': round(float(obj.get('high', obj['value'])), 2),
        'note': str(obj.get('note', ''))[:200],
        'model': cfg['model'],
        'method': '使用者自有模型（OpenAI 兼容接口）',
    }


def predict(points, use_model=True):
    """points 为 trend 去重后的观测序列。返回带来源标注的预测结果。"""
    cfg = load()
    if use_model and cfg.get('endpoint') and cfg.get('model'):
        payload = {
            'series': [{'date': p['data_date'], 'median': p.get('median')} for p in points[-30:]],
            'target': '下期中位价',
            'currency': 'BRL',
        }
        try:
            return _call_remote(cfg, payload)
        except Exception as e:  # noqa: BLE001
            r = _builtin(points)
            r['note'] = '自有模型调用失败（%s: %s），已回退到内置规则。' % (type(e).__name__, str(e)[:80])
            return r
    r = _builtin(points)
    r['note'] = (r.get('note', '') + ' 未接入自有模型。').strip()
    return r


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == 'status':
        print(json.dumps(public(), ensure_ascii=False))
    else:
        print('用法: python local/model.py status')
