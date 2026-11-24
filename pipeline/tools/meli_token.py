# -*- coding: utf-8 -*-
"""美客多 token 的读写与自动续期。采集器 import 这个，不要自己拼 OAuth。

    from meli_token import access_token
    tok = access_token()          # 过期就自动用 refresh_token 换新的

refresh_token 单次使用，换一次就作废并下发新的，所以每次刷新都必须落盘。
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

SECRET_DIR = os.path.join(os.path.expanduser('~'), '.workbuddy', 'secrets', 'meli')
APP = os.path.join(SECRET_DIR, 'app.json')
TOKEN = os.path.join(SECRET_DIR, 'token.json')
TOKEN_URL = 'https://api.mercadolibre.com/oauth/token'
# 提前 10 分钟续，避免跑到一半过期
SKEW = 600


class MeliAuthError(RuntimeError):
    pass


def _read(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _write(tok):
    tok = dict(tok)
    tok['_obtained_at'] = int(time.time())
    with open(TOKEN, 'w', encoding='utf-8') as f:
        json.dump(tok, f, ensure_ascii=False, indent=1)
    try:
        os.chmod(TOKEN, 0o600)
    except Exception:
        pass
    return tok


def _refresh(app, tok):
    data = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'client_id': app['client_id'],
        'client_secret': app['client_secret'],
        'refresh_token': tok['refresh_token'],
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method='POST', headers={
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        detail = ''
        try:
            detail = e.read().decode('utf-8')[:300]
        except Exception:
            pass
        raise MeliAuthError('refresh 失败：%s %s' % (e, detail))


def access_token(force=False):
    """返回可用的 access_token。过期或 force 时自动续期并落盘。"""
    if not os.path.exists(TOKEN):
        raise MeliAuthError('还没有 token，先跑 python pipeline/tools/meli_auth.py')
    if not os.path.exists(APP):
        raise MeliAuthError('缺 %s' % APP)

    tok = _read(TOKEN)
    age = time.time() - tok.get('_obtained_at', 0)
    if not force and tok.get('access_token') and age < tok.get('expires_in', 21600) - SKEW:
        return tok['access_token']

    if not tok.get('refresh_token'):
        raise MeliAuthError('token 里没有 refresh_token，重新跑 meli_auth.py')

    new = _refresh(_read(APP), tok)
    _write(new)
    return new['access_token']


if __name__ == '__main__':
    try:
        t = access_token()
        print('access_token 可用，前 16 位：%s...' % t[:16])
        tok = _read(TOKEN)
        age = int(time.time() - tok.get('_obtained_at', 0))
        print('已签发 %d 秒，总有效期 %s 秒' % (age, tok.get('expires_in')))
        print('refresh_token 存在：%s' % bool(tok.get('refresh_token')))
    except MeliAuthError as e:
        print(e)
        sys.exit(2)
