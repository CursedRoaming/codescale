# -*- coding: utf-8 -*-
"""码尺 CodeScale · 本地服务

   双击 start.bat 启动；浏览器打开 http://127.0.0.1:8765/

   只绑定 127.0.0.1，局域网与外网都访问不到。
   账号、演示快照、模型配置只存本机 runtime/ 与 local/history/，不联网上传。
   密钥只写本机、只回显掩码；模型调用由服务端代为发起。
   静态文件走白名单，pipeline/ 与 local/ 目录不对外。
"""

import datetime
import http.server
import json
import os
import socketserver
import sys
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import trend  # noqa: E402
import auth   # noqa: E402
import feed   # noqa: E402
import model  # noqa: E402

PORT = int(os.environ.get('CODESCALE_PORT', '8765'))

OK_EXT = ('.html', '.css', '.js', '.json', '.docx', '.md', '.png', '.svg', '.ico')
OK_DIRS = ('data', 'reports')
BLOCK = ('local', 'pipeline', '.git', 'accounts', 'cloudflare', '.workbuddy', 'runtime')
COOKIE = 'codescale_sid'


def _json(handler, obj, code=200, extra_headers=None):
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    for k, v in (extra_headers or {}).items():
        handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)


def _cookie(handler):
    raw = handler.headers.get('Cookie', '')
    for part in raw.split(';'):
        k, _, v = part.strip().partition('=')
        if k == COOKIE:
            return v
    return ''


def _body(handler):
    try:
        n = int(handler.headers.get('Content-Length', '0'))
    except ValueError:
        return {}
    if n <= 0 or n > 1 << 20:
        return {}
    try:
        raw = handler.rfile.read(n).decode('utf-8')
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def _need_user(handler):
    u = auth.verify(_cookie(handler))
    if not u:
        _json(handler, {'error': '未登录', 'need_login': True}, 401)
        return None
    return u


def _points():
    """去重后的观测序列，供预测使用。"""
    return trend.dedupe_by_observed(trend.load_snapshots(feed.HISTORY))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        if args and str(args[1]).startswith(('4', '5')):
            super().log_message(fmt, *args)

    # ---------------- GET ----------------
    def do_GET(self):
        path = self.path.split('?', 1)[0]

        if path == '/api/health':
            return _json(self, {
                'ok': True, 'scope': '127.0.0.1', 'port': PORT,
                'logged_in': bool(auth.verify(_cookie(self))),
            })

        if path == '/api/session':
            u = auth.verify(_cookie(self))
            return _json(self, {'logged_in': bool(u), 'user': u})

        if path == '/api/app/state':
            if not _need_user(self):
                return
            try:
                fp = os.path.join(ROOT, 'data', 'latest.json')
                with open(fp, encoding='utf-8') as f:
                    p = json.load(f)
                return _json(self, {
                    'baseline': {
                        'run_date': p['meta']['run_date'],
                        'data_date': p['meta']['data_date'],
                        'n': p['n'], 'median': p['median'],
                        'sources_ok': p['sources_ok'], 'sources_total': p['sources_total'],
                    },
                    'feed': feed.status(),
                    'today': datetime.date.today().isoformat(),
                })
            except Exception as e:  # noqa: BLE001
                return _json(self, {'error': '%s: %s' % (type(e).__name__, e)}, 500)

        if path == '/api/app/trend':
            if not _need_user(self):
                return
            try:
                q = self.path.split('?', 1)[1] if '?' in self.path else ''
                params = dict(kv.split('=', 1) for kv in q.split('&') if '=' in kv)
                today = (datetime.date.fromisoformat(params['today'])
                         if params.get('today') else datetime.date.today())
                r = trend.analyze(feed.HISTORY, today=today)
                pts = trend.dedupe_by_observed(trend.load_snapshots(feed.HISTORY))
                use_model = params.get('model', '1') != '0'
                r['prediction'] = model.predict(pts, use_model=use_model)
                r['feed'] = feed.status()
                return _json(self, r)
            except Exception as e:  # noqa: BLE001
                return _json(self, {'error': '%s: %s' % (type(e).__name__, e)}, 500)

        if path == '/api/model/config':
            if not _need_user(self):
                return
            return _json(self, model.public())

        # 兼容旧的只读端点：看真实历史，不掺演示数据
        if path == '/api/trend':
            try:
                q = self.path.split('?', 1)[1] if '?' in self.path else ''
                params = dict(kv.split('=', 1) for kv in q.split('&') if '=' in kv)
                today = (datetime.date.fromisoformat(params['today'])
                         if params.get('today') else datetime.date.today())
                return _json(self, trend.analyze(os.path.join(ROOT, 'data', 'history'), today=today))
            except Exception as e:  # noqa: BLE001
                return _json(self, {'error': '%s: %s' % (type(e).__name__, e)}, 500)

        if path == '/api/state':
            fp = os.path.join(ROOT, 'data', 'latest.json')
            try:
                with open(fp, encoding='utf-8') as f:
                    p = json.load(f)
                return _json(self, {
                    'run_date': p['meta']['run_date'],
                    'data_date': p['meta']['data_date'],
                    'freshness_days': p['meta']['freshness_days'],
                    'n': p['n'], 'median': p['median'],
                    'sources_ok': p['sources_ok'], 'sources_total': p['sources_total'],
                })
            except Exception as e:  # noqa: BLE001
                return _json(self, {'error': '%s: %s' % (type(e).__name__, e)}, 500)

        # 静态文件白名单
        rel = path.lstrip('/').replace('/', os.sep)
        if rel in ('', '.'):
            rel = 'index.html'
        low = rel.lower()
        if any(b in low for b in BLOCK):
            return self.send_error(404)
        top = rel.split(os.sep)[0].lower()
        if not (low.endswith(OK_EXT) and (top in OK_DIRS or os.sep not in rel)):
            return self.send_error(404)
        fp = os.path.join(ROOT, rel)
        if not os.path.isfile(fp):
            return self.send_error(404)
        return super().do_GET()

    # ---------------- POST ----------------
    def do_POST(self):
        path = self.path.split('?', 1)[0]

        if path == '/api/auth/register':
            b = _body(self)
            ok = auth.register(b.get('username'), b.get('password'))
            return _json(self, {'ok': ok, 'reason': '' if ok else '用户名或密码不合要求，或用户名已存在'}, 200 if ok else 400)

        if path == '/api/auth/login':
            b = _body(self)
            tok = auth.login(b.get('username'), b.get('password'))
            if not tok:
                return _json(self, {'error': '用户名或密码错误'}, 401)
            # 登录即更新当天快照
            try:
                refreshed = feed.ensure_today()
            except Exception as e:  # noqa: BLE001
                refreshed = {'error': '%s: %s' % (type(e).__name__, e)}
            hdr = {'Set-Cookie': '%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d'
                   % (COOKIE, tok, auth.SESSION_TTL)}
            return _json(self, {'ok': True, 'user': auth.verify(tok), 'refresh': refreshed}, 200, hdr)

        if path == '/api/auth/logout':
            auth.logout(_cookie(self))
            hdr = {'Set-Cookie': '%s=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0' % COOKIE}
            return _json(self, {'ok': True}, 200, hdr)

        if path == '/api/feed/refresh':
            if not _need_user(self):
                return
            try:
                return _json(self, feed.ensure_today())
            except Exception as e:  # noqa: BLE001
                return _json(self, {'error': '%s: %s' % (type(e).__name__, e)}, 500)

        if path == '/api/model/config':
            if not _need_user(self):
                return
            b = _body(self)
            if b.get('action') == 'clear':
                return _json(self, model.clear())
            return _json(self, model.save(b))

        return self.send_error(404)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    srv = Server(('127.0.0.1', PORT), Handler)
    url = 'http://127.0.0.1:%d/' % PORT
    print('码尺 CodeScale · 本地服务已启动')
    print('  地址: ' + url)
    print('  范围: 仅本机，不联网上传')
    print('  本机账号: %d 个' % len(auth.user_list()))
    print('  停止: 在本窗口按 Ctrl+C')
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
        srv.server_close()


if __name__ == '__main__':
    main()
