# -*- coding: utf-8 -*-
"""美客多 OAuth 授权一次，把 refresh_token 存到本机，之后自动续期。

前置：在美客多开发者中心建好应用，拿到 App ID 和 Secret Key。
凭证放这里（不进仓库、不进对话）：

    %USERPROFILE%\\.workbuddy\\secrets\\meli\\app.json

    {"client_id": "1234567890123456", "client_secret": "xxxxxxxx"}

然后跑：

    python pipeline/tools/meli_auth.py

浏览器会打开授权页，你点「授权」，脚本自动收回调、换 token、落盘。
access_token 有效期 6 小时，refresh_token 180 天且每次刷新会换新的，脚本自己管。

注意 redirect_uri 必须与应用后台登记的完全一致，默认 http://localhost:3333/callback。
若后台不接受这个地址，改成 https://localhost/callback 登记，然后在 app.json 里
加一行 "redirect_uri": "https://localhost/callback"，同时自己把回调地址那一跳对准。
"""

import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request

SECRET_DIR = os.path.join(os.path.expanduser('~'), '.workbuddy', 'secrets', 'meli')
APP = os.path.join(SECRET_DIR, 'app.json')
TOKEN = os.path.join(SECRET_DIR, 'token.json')

AUTH_URL = 'https://auth.mercadolivre.com.br/authorization'
TOKEN_URL = 'https://api.mercadolibre.com/oauth/token'
DEFAULT_REDIRECT = 'http://localhost:3333/callback'
# 只申请读权限。搜索公开商品价格不需要写权限，别要多了让客户警觉。
SCOPES = ['offline_access', 'read']


def load_app():
    if not os.path.exists(APP):
        print('还没有应用凭证。先到 developers.mercadolivre.com.br 建一个应用，')
        print('把 App ID 和 Secret Key 填进来（输一次，之后不再问）。')
        print('')
        try:
            cid = input('App ID (client_id): ').strip()
            sec = input('Secret Key (client_secret): ').strip()
        except EOFError:
            print('当前环境不能输入，手工建 %s' % APP)
            return None
        if not cid or not sec:
            print('没填全，退出。')
            return None
        os.makedirs(SECRET_DIR, exist_ok=True)
        app = {'client_id': cid, 'client_secret': sec, 'redirect_uri': DEFAULT_REDIRECT}
        with open(APP, 'w', encoding='utf-8') as f:
            json.dump(app, f, ensure_ascii=False, indent=1)
        try:
            os.chmod(APP, 0o600)
        except Exception:
            pass
        print('已写入 %s' % APP)
        return app

    with open(APP, encoding='utf-8') as f:
        app = json.load(f)
    if not app.get('client_id') or not app.get('client_secret'):
        print('app.json 里缺 client_id 或 client_secret')
        return None
    app.setdefault('redirect_uri', DEFAULT_REDIRECT)
    return app


def post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method='POST', headers={
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def save_token(tok):
    import time
    tok = dict(tok)
    tok['_obtained_at'] = int(time.time())
    os.makedirs(SECRET_DIR, exist_ok=True)
    with open(TOKEN, 'w', encoding='utf-8') as f:
        json.dump(tok, f, ensure_ascii=False, indent=1)
    try:
        os.chmod(TOKEN, 0o600)
    except Exception:
        pass


def main():
    app = load_app()
    if not app:
        return 2

    redirect = app['redirect_uri']
    parsed = urllib.parse.urlparse(redirect)
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    if parsed.scheme != 'http':
        print('本地回收调只支持 http。redirect_uri 现在是 %s' % redirect)
        print('要么改成 http://localhost:%d/callback，要么手工把浏览器地址栏里的 code 摘下来。' % port)
        return 2

    state = secrets.token_urlsafe(12)
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items() if v})
            body = ('<meta charset="utf-8"><h2>授权完成</h2>'
                    '<p>可以关掉这个页面，回到终端。</p>').encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(('127.0.0.1', port), Handler)
    t = threading.Thread(target=srv.handle_request, daemon=True)
    t.start()

    url = '%s?%s' % (AUTH_URL, urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': app['client_id'],
        'redirect_uri': redirect,
        'state': state,
        'scope': ' '.join(SCOPES),
    }))
    print('在浏览器里打开下面这个地址，登录后点「授权」：')
    print('')
    print(url)
    print('')
    print('本机正在 %s 上等回调，别关这个窗口。' % redirect)

    t.join(timeout=300)
    srv.server_close()

    if not got:
        print('五分钟内没收到回调。检查 redirect_uri 与后台是否一字不差。')
        return 3
    if got.get('state') != state:
        print('state 不匹配，放弃。收到的是 %r' % got.get('state'))
        return 4
    if 'code' not in got:
        print('回调里没有 code：%s' % got)
        return 5

    print('')
    print('收到 code，正在换 token...')
    try:
        tok = post_form(TOKEN_URL, {
            'grant_type': 'authorization_code',
            'client_id': app['client_id'],
            'client_secret': app['client_secret'],
            'code': got['code'],
            'redirect_uri': redirect,
        })
    except Exception as e:
        print('换 token 失败：%s' % e)
        try:
            print(e.read().decode('utf-8')[:400])
        except Exception:
            pass
        return 6

    save_token(tok)
    print('')
    print('成功。')
    print('user_id      : %s' % tok.get('user_id'))
    print('access_token : %s 秒后过期' % tok.get('expires_in'))
    print('refresh_token: 已保存（180 天，用一次换一个）')
    print('落盘位置     : %s' % TOKEN)
    print('')
    print('下一步：python pipeline/tools/meli_probe.py  # 试拉巴西穿戴甲')
    return 0


if __name__ == '__main__':
    sys.exit(main())
