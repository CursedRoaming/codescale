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
# 登录前后的差别不在 URL 上：未登录也能进 /product，只是价格被打成 ₱***。
# 唯一稳的判据是右上角那个「登录 / 注册」按钮还在不在。
CHECK_URL = 'https://www.kalodata.com/product'
GUEST_MARKS = ('登录 / 注册', '登录/注册')

# 未登录时首页会自动跳到 /signup 或 /login。这是客户端的主动跳转，
# Playwright 会把它当成「导航被另一次导航打断」抛出来。那不是错误，是页面走了。
MAX_TRIES = 3


def looks_logged_in(page):
    """登录态判据：不是 URL，是页面右上角还有没有登录入口。"""
    u = (page.url or '').lower()
    if 'login' in u or 'signup' in u:
        return False
    try:
        text = page.inner_text('body')[:6000]
    except Exception:
        return False
    return not any(m in text for m in GUEST_MARKS)


def main():
    try:
        from playwright.sync_api import sync_playwright, Error as PWError
    except ImportError:
        print('缺 playwright。先跑：pip install playwright && python -m playwright install chromium')
        return 2

    def safe_goto(page, url, wait=2500):
        """吞掉 SPA 自行跳转造成的中断，返回稳定后的 URL。"""
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except PWError as e:
            if 'interrupted by another navigation' not in str(e):
                raise
        page.wait_for_timeout(wait)
        return page.url

    os.makedirs(SECRET_DIR, exist_ok=True)
    has_old = os.path.exists(STATE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(storage_state=STATE if has_old else None)
        page = ctx.new_page()
        try:
            safe_goto(page, HOME_URL if has_old else LOGIN_URL)
            print('当前页面：%s' % page.url)
            print('浏览器已打开。')
            print('请在窗口里登录 Kalodata（账号密码你自己输，脚本不碰）。')
            print('登录成功、能看到后台数据之后，回到这里按回车。')
            if has_old:
                print('（检测到旧会话，若仍是登录状态，可直接按回车刷新一份。）')

            ok = False
            url = page.url
            for i in range(MAX_TRIES):
                try:
                    input('')
                except EOFError:
                    print('当前环境不能交互，请在本地终端里跑这个脚本。')
                    return 3

                url = safe_goto(page, CHECK_URL, wait=5000)
                if looks_logged_in(page):
                    ok = True
                    break
                print('页面还停在 %s，右上角仍有「登录 / 注册」入口。' % url)
                print('看起来没登进去。检查浏览器窗口，登好后再按一次回车（还剩 %d 次）。'
                      % (MAX_TRIES - i - 1))

            cookies = ctx.cookies()
            ctx.storage_state(path=STATE)
            print('')
            print('已保存会话：%s' % STATE)
            print('cookie 数量：%d' % len(cookies))
            print('当前页面：%s' % url)
            print('cookie 名：%s' % ', '.join(sorted({c['name'] for c in cookies})[:12]))

            if not ok:
                print('')
                print('三次都停在登录页。文件已经写下去了，但它大概率无效。')
                print('下次跑采集器会报会话无效，不会静默给空数据。')
                return 4

            print('')
            print('会话看起来是登录状态。')
            print('下一步：python pipeline/tools/kalodata_probe.py   # 看看导出按钮在哪、下什么格式')
            return 0
        finally:
            browser.close()


if __name__ == '__main__':
    sys.exit(main())
