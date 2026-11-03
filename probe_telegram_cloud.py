"""Unauthenticated connectivity check from the existing cloud runner."""
import json
import re
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse

url = 'https://web.telegram.org/a/'
with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as response:
    html = response.read(2_000_000).decode('utf-8')
    print(json.dumps({'target': 'Telegram WebA', 'status': response.status,
                      'html_bytes': len(html), 'has_telegram_title': 'Telegram' in html}))
scripts = re.findall(r'<script\b[^>]*\bsrc=["\']([^"\']+)', html)
tested = 0
for src in scripts:
    asset = urljoin(url, src)
    if urlparse(asset).netloc != 'web.telegram.org':
        continue
    with urlopen(Request(asset, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as response:
        data = response.read(20_000_000)
        print(json.dumps({'javascript_status': response.status, 'bytes': len(data)}))
        tested += 1
    if tested >= 2:
        break
if not tested:
    raise SystemExit('No same-origin JavaScript entry point found')
print('PASS: cloud HTTPS and WebA JavaScript delivery. Login, WebSocket and downloads NOT tested.')
