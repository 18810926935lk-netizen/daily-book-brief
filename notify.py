# -*- coding: utf-8 -*-
"""Server酱微信推送：摘要 + Pages 全文链接"""
import os, re, json
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
TODAY = datetime.now(CST).strftime('%Y-%m-%d')
BASE = os.path.dirname(os.path.abspath(__file__))
key = os.environ.get('SERVERCHAN_KEY', '')
site_base = os.environ.get('SITE_BASE', '').rstrip('/')

html_path = os.path.join(BASE, 'site', f'{TODAY}.html')
if not os.path.exists(html_path):
    raise SystemExit('ERROR: 今日 HTML 不存在，推送失败')

html = open(html_path, encoding='utf-8').read()
plain = re.sub(r'<[^>]+>', ' ', html)
plain = re.sub(r'\s+', ' ', plain)

# 摘要：报头日期段 + 每个栏目标题行
issue = (re.search(r'第(\d+)期', plain) or [None, '?'])[1]
title = f'📖 图书信息简报 {TODAY}（第{issue}期）'

heads = re.findall(r'[一二三四五六七八]、[^ ]{2,20}', plain)[:7]
url = f'{site_base}/{TODAY}.html' if site_base else '(SITE_BASE 未配置)'

desp = f"""**今日简报已生成** [点此阅读全文]({url})

""" + '\n'.join('- ' + h.strip() for h in heads) + f"""

（每日 06:00 自动生成 · 大愚文化）"""

if not key or 'SERVERCHAN' in key:
    raise SystemExit('ERROR: SERVERCHAN_KEY 未配置')
if not site_base.startswith('https://') or len(plain.strip()) < 100:
    raise SystemExit('ERROR: SITE_BASE 无效或简报内容为空')

import requests
import time
# Wait until the published full text is available before sending its link.
for attempt in range(30):
    try:
        page = requests.get(url, timeout=20)
        if page.status_code == 200 and page.content == html.encode('utf-8'):
            break
    except requests.RequestException:
        pass
    time.sleep(10)
else:
    raise SystemExit('ERROR: 今日全文尚未发布，停止推送无效链接')

try:
    r = requests.post(f'https://sctapi.ftqq.com/{key}.send', data={'title': title, 'desp': desp}, timeout=30)
except requests.RequestException:
    raise SystemExit('ERROR: ServerChan 网络请求失败（隐藏含密钥的请求地址）')
try:
    result = r.json()
except ValueError:
    raise SystemExit(f'ERROR: ServerChan HTTP {r.status_code}, invalid JSON')
code = result.get('code')
errno = result.get('data', {}).get('errno')
print(f'serverchan: HTTP {r.status_code}, code={code}, errno={errno}')
if r.status_code != 200 or code != 0 or errno not in (None, 0):
    raise SystemExit('ERROR: ServerChan 未确认发送成功')
print('WeChat push accepted; published full text verified.')
