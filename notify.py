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
    print('WARN: 今日 HTML 不存在，跳过推送（工作流仍标记成功以便排查日志）')
    raise SystemExit(0)

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

（每日 06:25 自动生成 · 大愚文化）"""

if not key or 'SERVERCHAN' in key:
    print('WARN: SERVERCHAN_KEY 未配置，仅打印不推送')
    print(title)
    print(desp)
    raise SystemExit(0)

import requests
r = requests.post(f'https://sctapi.ftqq.com/{key}.send', data={'title': title, 'desp': desp}, timeout=30)
print('serverchan:', r.status_code, r.text[:200])
