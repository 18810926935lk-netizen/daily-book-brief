# -*- coding: utf-8 -*-
"""Server酱微信推送：摘要 + Pages 全文链接"""
import os, re, json
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
TODAY = datetime.now(CST).strftime('%Y-%m-%d')
BASE = os.path.dirname(os.path.abspath(__file__))
key = os.environ.get('SERVERCHAN_KEY', '')
site_base = os.environ.get('SITE_BASE', '').rstrip('/')

from publication import digest
manifest = json.loads(open(os.path.join(BASE, 'site', TODAY + '.json'), encoding='utf-8').read())
if manifest['date'] != TODAY:
    raise SystemExit('ERROR: manifest date mismatch')
html_path = os.path.join(BASE, 'site', manifest['html'])
html = open(html_path, encoding='utf-8').read()
if digest(html.encode('utf-8')) != manifest['html_sha256']:
    raise SystemExit('ERROR: manuscript hash mismatch')
plain = re.sub(r'<[^>]+>', ' ', html)
plain = re.sub(r'\s+', ' ', plain)

# 摘要：报头日期段 + 每个栏目标题行
issue = (re.search(r'第(\d+)期', plain) or [None, '?'])[1]
title = f'📖 全球图书与文化简报 {TODAY}'

from bs4 import BeautifulSoup
heads = [h.get_text(' ', strip=True) for h in BeautifulSoup(html, 'html.parser').select('h2')][:9]
url = f"{site_base}/{manifest['html']}" if site_base else '(SITE_BASE 未配置)'

desp = f"""**今日简报已生成**（版本 {manifest['revision']}） [点此阅读全文]({url})

""" + '\n'.join('- ' + h.strip() for h in heads) + f"""

（每日计划北京时间06:00启动；实际发布时间以成稿为准 · 大愚文化）"""

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
        if page.status_code == 200 and page.content == html.encode('utf-8') and requests.get(f'{site_base}/{TODAY}.json', timeout=20).json() == manifest:
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
