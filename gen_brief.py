# -*- coding: utf-8 -*-
"""调 GLM（Anthropic 兼容端点）生成今日简报 HTML + content.json
输入: data/lithub.txt, data/podcasts.txt, data/wikipedia.txt, template/sample.html
输出: site/{today}.html, site/content_{today}.json, site/index.html
"""
import os, re, json, sys
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

===== 格式模板 sample.html（结构与内联样式照抄，内容全部替换为今日）=====
{read('template/sample.html')}

按系统提示词的规范与输出格式，生成今日简报。记住：数据里没有的不要编，播客必须是单集，文章必须带 lithub.txt 里的真实链接。"""

sys_prompt = open(os.path.join(BASE, 'PROMPT.md'), encoding='utf-8').read()

# ---- 调用 GLM Anthropic 兼容端点 ----
import requests
base = os.environ['GLM_BASE_URL'].rstrip('/')
token = os.environ['GLM_TOKEN']
r = requests.post(base + '/v1/messages', timeout=1200, headers={
    'x-api-key': token,
    'authorization': 'Bearer ' + token,
    'anthropic-version': '2023-06-01',
    'content-type': 'application/json',
}, json={
    'model': 'GLM-5.3',
    'max_tokens': 16000,
    'system': sys_prompt,
    'messages': [{'role': 'user', 'content': prompt}],
})
r.raise_for_status()
data = r.json()
if data.get('type') == 'error':
    raise SystemExit('API error: ' + json.dumps(data.get('error', {}), ensure_ascii=False)[:500])
text = ''.join(b.get('text', '') for b in data.get('content', []))
print('API usage:', data.get('usage'), 'output chars:', len(text))

# ---- 解析两个代码块 ----
html_m = re.search(r'```html\s*(.*?)\s*```', text, re.S)
json_m = re.search(r'```json\s*(.*?)\s*```', text, re.S)
if not html_m:
    # 兜底：找 <!DOCTYPE 开头的整段
    html_m = re.search(r'(<!DOCTYPE html.*)', text, re.S)
if not html_m:
    raise SystemExit('OUTPUT_NO_HTML\n' + text[:800])

html = html_m.group(1)
open(os.path.join(BASE, 'site', f'{TODAY}.html'), 'w', encoding='utf-8').write(html)

if json_m:
    try:
        cj = json.loads(json_m.group(1))
        open(os.path.join(BASE, 'site', f'content_{TODAY}.json'), 'w', encoding='utf-8').write(
            json.dumps(cj, ensure_ascii=False, indent=1))
    except Exception as e:
        print('WARN: content.json parse failed:', e)
else:
    print('WARN: no content.json block')

# ---- index.html：最新一期落地页 ----
issue = ''
m = re.search(r'第(\d+)期', html)
if m:
    issue = m.group(1)
index = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>图书信息简报</title><meta http-equiv="refresh" content="0; url={TODAY}.html">
</head><body><p>最新一期：{TODAY}（第{issue or '?'}期），<a href="{TODAY}.html">点此阅读</a></p></body></html>"""
open(os.path.join(BASE, 'site', 'index.html'), 'w', encoding='utf-8').write(index)
print('GENERATED:', TODAY, 'issue', issue)
