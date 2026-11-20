# -*- coding: utf-8 -*-
"""数据源适配器接口。

每个适配器只做一件事：产出原始记录列表。归一化、去重、快照由 core 统一处理，
适配器不许自己算指标，也不许自己写文件——这样换平台时只改一个文件。

状态码（会直接显示在网页的「数据源健康」面板上，别乱用）：
    ok              拿到数据
    empty           连通但今天没有新数据
    not_configured  缺凭据（key / 账号 / endpoint）
    blocked         被平台风控或权限挡住，属于事实，不是故障
    disabled        配置里关掉了
    error           代码或网络出错，需要人看
"""

import json
import os
import time
import urllib.error
import urllib.request

TIMEOUT = 25
UA = 'CodeScaleBot/0.1 (+https://codescale.example; contact@codescale.example)'


class Result:
    def __init__(self, source_id, name):
        self.id = source_id
        self.name = name
        self.status = 'ok'
        self.reason = ''
        self.records = []
        self.requests = 0
        self.bytes = 0

    def fail(self, status, reason):
        self.status = status
        self.reason = reason
        return self

    def as_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'reason': self.reason,
            'records': len(self.records),
            'requests': self.requests,
            'bytes': self.bytes,
        }


def http_json(url, headers=None, method='GET', body=None, result=None):
    """取 JSON。返回 (data, err)。err 为 None 表示成功。"""
    h = {'User-Agent': UA, 'Accept': 'application/json'}
    h.update(headers or {})
    data = json.dumps(body).encode('utf-8') if body is not None else None
    if data:
        h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    if result is not None:
        result.requests += 1
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            if result is not None:
                result.bytes += len(raw)
            return json.loads(raw.decode('utf-8')), None
    except urllib.error.HTTPError as e:
        return None, 'HTTP %d' % e.code
    except urllib.error.URLError as e:
        return None, 'URLError %s' % e.reason
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, 'not_json'
    except Exception as e:                                   # noqa: BLE001
        return None, '%s: %s' % (type(e).__name__, e)


def read_secret(name):
    """从 ~/.workbuddy/secrets/<name> 读一行凭据。没有就返回 None。
    凭据不进仓库、不进对话、不进日志。"""
    home = os.path.expanduser('~')
    p = os.path.join(home, '.workbuddy', 'secrets', name)
    if not os.path.exists(p):
        return None
    v = open(p, encoding='utf-8').read().strip()
    return v or None


def wait(sec):
    time.sleep(sec)
