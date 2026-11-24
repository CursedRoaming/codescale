# -*- coding: utf-8 -*-
"""码尺 CodeScale · 本地服务

   双击 start.bat 启动；浏览器打开 http://127.0.0.1:8765/

   只绑定 127.0.0.1，局域网与外网都访问不到。
   只读本机 data/ 与 reports/，不联网、不上传、不收集任何填写内容。
   静态文件走白名单，pipeline/ 与 local/ 目录不对外。
"""

import datetime
import http.server
import json
import os
import socketserver
import sys
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import trend  # noqa: E402

PORT = int(os.environ.get('CODESCALE_PORT', '8765'))

# 允许对外提供的文件后缀，以及仅这些目录。其余一律 404。
OK_EXT = ('.html', '.css', '.js', '.json', '.docx', '.md', '.png', '.svg', '.ico')
OK_DIRS = ('data', 'reports')
BLOCK = ('local', 'pipeline', '.git', 'accounts', 'cloudflare', '.workbuddy')


def _json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        # 本地使用，只打印错误，避免刷屏
        if args and str(args[1]).startswith(('4', '5')):
            super().log_message(fmt, *args)

    def do_GET(self):
        path = self.path.split('?', 1)[0]

        if path == '/api/health':
            return _json(self, {'ok': True, 'scope': '127.0.0.1', 'port': PORT})

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


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    srv = Server(('127.0.0.1', PORT), Handler)
    url = 'http://127.0.0.1:%d/' % PORT
    print('码尺 CodeScale · 本地服务已启动')
    print('  地址: ' + url)
    print('  范围: 仅本机，不联网，不上传')
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
