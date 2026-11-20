# -*- coding: utf-8 -*-
"""Kalodata 登录一次，把登录态存到本机，之后每天自动沿用。

为什么要这一步：Kalodata 没有公开 API，数据出口只有网页上的导出按钮。
要每天自动拉，只能用浏览器把你登录后的会话保存下来，第二天带着这个会话去点导出。
密码不存、不传、不写进任何文件；存的是浏览器会话（cookie），过期就重新跑一次这个脚本。

用法（在你自己的终端里跑，不要在无界面环境跑）：

    python pipeline/tools/kalodata_login.py

浏览器会自己打开。你在里面登录，登录完回到终端按回车。
会话存在 ~/.workbuddy/secrets/kalodata/state.json，不进仓库、不进对话。
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

SECRET_DIR = os.path.join(os.path.expanduser('~'), '.workbuddy', 'secrets', 'kalodata')
STATE = os.path.join(SECRET_DIR, 'state.json')
LOGIN_URL = 'https://www.kalodata.com/login'
HOME_URL = 'https://www.kalodata.com/'


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('缺 playwright。先跑：pip install playwright && python -m playwright install chromium')
        return 2

    os.makedirs(SECRET_DIR, exist_ok=True)
    has_old = os.path.exists(STATE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # 有旧会话就带上，省得每次都从头登录
        ctx = browser.new_context(storage_state=STATE if has_old else None)
        page = ctx.new_page()
        page.goto(HOME_URL, wait_until='domcontentloaded', timeout=60000)

        print('浏览器已打开。')
        print('请在窗口里登录 Kalodata（账号密码你自己输，脚本不碰）。')
        print('登录成功、能看到后台数据之后，回到这里按回车。')
        if has_old:
            print('（检测到旧会话，若仍是登录状态，可直接按回车刷新一份。）')
        try:
            input()
        except EOFError:
            print('当前环境不能交互，请在本地终端里跑这个脚本。')
            browser.close()
            return 3

        # 走一圈首页，让会话把必要 cookie 都写全，再判断是否真的登进去了
        page.goto(HOME_URL, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(2500)
        url = page.url
        cookies = ctx.cookies()
        names = {c['name'] for c in cookies}

        ctx.storage_state(path=STATE)
        browser.close()

    print('')
    print('已保存会话：%s' % STATE)
    print('cookie 数量：%d' % len(cookies))
    print('当前页面：%s' % url)

    # 只报事实，不猜。真正的登录校验交给采集器运行时判断：
    # 会话失效时它会拿到登录页，届时状态会变成 blocked，不会静默给空数据。
    if 'login' in url.lower():
        print('')
        print('注意：保存时页面还停在登录页，这份会话大概率没有效。')
        print('如果确实已经登录了，忽略这句；下次运行采集器会告诉你到底通不通。')
    else:
        print('会话看起来是登录状态。')

    print('')
    print('下一步：python pipeline/tools/kalodata_probe.py   # 看看导出按钮在哪、下什么格式')
    return 0


if __name__ == '__main__':
    sys.exit(main())
