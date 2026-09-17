# -*- coding: utf-8 -*-
"""调 GLM（Anthropic 兼容端点）生成今日简报 HTML
输入: data/lithub.txt, data/podcasts.txt, data/wikipedia.txt, template/sample.html
输出: site/{today}.html, site/index.html
"""
import os, re, sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
TODAY = datetime.now(CST).strftime('%Y-%m-%d')
BASE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE, 'site'), exist_ok=True)

def read(p, cap=14000):
    fp = os.path.join(BASE, p)
    if not os.path.exists(fp):
        return '(数据源缺失)'
    s = open(fp, encoding='utf-8', errors='ignore').read().strip()
    return s[:cap] if s else '(空)'

prompt = f"""今天是{TODAY}。以下是今日采集的数据：

===== Lit Hub 当日热文（标题 || 链接）=====
{read('data/lithub.txt')}

===== 播客榜单头部节目最近单集（RSS核实）=====
{read('data/podcasts.txt')}

===== NYT 榜首书维基表（交叉验证，可能滞后到上月末）=====
{read('data/wikipedia.txt')}

===== 诺奖文学奖预测（谷歌新闻聚合，注意文件头标注的时间窗口）=====
{read('data/nobel_lit.txt', 10000)}

===== 诺奖经济学奖预测（谷歌新闻聚合）=====
{read('data/nobel_econ.txt', 8000)}

===== 文学圈近期报道（仅当文学奖小节无新预测时选读一篇）=====
{read('data/fallback_lit.txt', 6000)}

===== 经济学圈近期报道（仅当经济学奖小节无新预测时选读一篇）=====
{read('data/fallback_econ.txt', 6000)}

===== 国际版权贸易报道（rights/交易/拍卖）=====
{read('data/rights.txt', 10000)}

===== 格式模板 sample.html（结构与内联样式照抄，内容全部替换为今日）=====
{read('template/sample.html')}

按系统提示词的规范，输出今日简报的完整 HTML（```html 代码块）。只输出这一个代码块。"""

sys_prompt = open(os.path.join(BASE, 'PROMPT.md'), encoding='utf-8').read()
# 输出格式段落动态替换：只要 HTML
sys_prompt = sys_prompt.split('## 输出格式')[0] + """
## 输出格式（严格遵守）

只输出一个 ```html 代码块，即完整的今日简报 HTML 文件。不要输出其他内容。
"""

import requests
base = os.environ['GLM_BASE_URL'].rstrip('/')
token = os.environ['GLM_TOKEN']
r = requests.post(base + '/v1/messages', timeout=1800, headers={
    'x-api-key': token,
    'authorization': 'Bearer ' + token,
    'anthropic-version': '2023-06-01',
    'content-type': 'application/json',
}, json={
    'model': 'GLM-5.3',
    'max_tokens': 32000,
    'system': sys_prompt,
    'messages': [{'role': 'user', 'content': prompt}],
})
r.raise_for_status()
data = r.json()
if data.get('type') == 'error':
    raise SystemExit('API error: ' + json.dumps(data.get('error', {}), ensure_ascii=False)[:500])
text = ''.join(b.get('text', '') for b in data.get('content', []))
print('API usage:', data.get('usage'), 'stop:', data.get('stop_reason'), 'output chars:', len(text))

m = re.search(r'```html\s*(.*?)\s*```', text, re.S) or re.search(r'(<!DOCTYPE html.*)', text, re.S)
if not m:
    raise SystemExit('OUTPUT_NO_HTML\n' + text[:800])
html = m.group(1).strip()

if '</html>' not in html:
    raise SystemExit('HTML_TRUNCATED (no </html>) len=' + str(len(html)))

open(os.path.join(BASE, 'site', f'{TODAY}.html'), 'w', encoding='utf-8').write(html)

issue = ''
m2 = re.search(r'第(\d+)期', html)
if m2:
    issue = m2.group(1)
index = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>图书信息简报</title><meta http-equiv="refresh" content="0; url={TODAY}.html">
</head><body><p>最新一期：{TODAY}（第{issue or '?'}期），<a href="{TODAY}.html">点此阅读</a></p></body></html>"""
open(os.path.join(BASE, 'site', 'index.html'), 'w', encoding='utf-8').write(index)
print('GENERATED:', TODAY, 'issue', issue, 'len', len(html))
