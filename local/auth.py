# -*- coding: utf-8 -*-
"""本地账号系统：注册 / 登录 / 会话 / 登出。

   只服务于 127.0.0.1 的本地服务。账号存本机 runtime/，不入库、不上网。
   密码用 PBKDF2-HMAC-SHA256 加盐哈希，明文不落盘、不进内存缓存。
   会话令牌随机生成，仅存服务端内存，进程重启即失效。
"""

import datetime
import hashlib
import hmac
import json
import os
import secrets
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(ROOT, 'runtime')
ACCOUNTS = os.path.join(RUNTIME, 'accounts.json')

ITER = 200000
SESSION_TTL = 12 * 3600  # 12 小时

# 令牌 -> {user, exp}
_sessions = {}


def _ensure():
    os.makedirs(RUNTIME, exist_ok=True)
    if not os.path.exists(ACCOUNTS):
        with open(ACCOUNTS, 'w', encoding='utf-8') as f:
            json.dump({'accounts': []}, f)


def _load():
    _ensure()
    try:
        with open(ACCOUNTS, encoding='utf-8') as f:
            return json.load(f)
    except (ValueError, OSError):
        return {'accounts': []}


def _save(data):
    _ensure()
    tmp = ACCOUNTS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ACCOUNTS)


def _hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITER).hex()


def valid_username(name):
    if not isinstance(name, str):
        return False
    n = name.strip()
    return 3 <= len(n) <= 32 and n.isalnum() or ('_' in n and 3 <= len(n) <= 32 and n.replace('_', '').isalnum())


def valid_password(pw):
    return isinstance(pw, str) and 8 <= len(pw) <= 128


def register(username, password):
    """成功返回 True；用户名重复或格式不合返回 False。"""
    name = (username or '').strip()
    if not valid_username(name) or not valid_password(password):
        return False
    data = _load()
    if any(a['user'].lower() == name.lower() for a in data['accounts']):
        return False
    salt = secrets.token_bytes(16)
    data['accounts'].append({
        'user': name,
        'salt': salt.hex(),
        'hash': _hash(password, salt),
        'created': datetime.datetime.now().isoformat(timespec='seconds'),
    })
    _save(data)
    return True


def login(username, password):
    """成功返回令牌，失败返回 None。用常量时间比较，避免时序泄露。"""
    name = (username or '').strip()
    data = _load()
    rec = next((a for a in data['accounts'] if a['user'].lower() == name.lower()), None)
    if not rec:
        # 用一个假哈希做等时比较，掩盖用户是否存在
        _hash(password or '', b'\x00' * 16)
        return None
    calc = _hash(password or '', bytes.fromhex(rec['salt']))
    if not hmac.compare_digest(calc, rec['hash']):
        return None
    tok = secrets.token_urlsafe(32)
    _sessions[tok] = {'user': rec['user'], 'exp': time.time() + SESSION_TTL}
    return tok


def verify(token):
    if not token:
        return None
    s = _sessions.get(token)
    if not s:
        return None
    if s['exp'] < time.time():
        _sessions.pop(token, None)
        return None
    return s['user']


def logout(token):
    if token:
        _sessions.pop(token, None)


def user_list():
    """仅返回用户名，供本机管理查看；不含哈希与盐。"""
    return [a['user'] for a in _load()['accounts']]


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == 'list':
        print(user_list() or '（暂无账号）')
    else:
        print('用法: python local/auth.py list')
