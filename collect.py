# -*- coding: utf-8 -*-
"""图书信息简报 · 固定采集脚本（无头受限模式专用）
用法:
  python collect.py lithub                     # Lit Hub 当日首页文章+链接
  python collect.py podcasts "节目名" "节目名" # 各节目RSS最近3集
  python collect.py wikipedia <页面名>          # 维基wikitext(截2万字符)
  python collect.py fetch <url>                # 抓任意网页转纯文本(截6千字符)
"""
import sys, re, json, urllib.request, email.utils

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()

def lithub():
    h = get('https://lithub.com/').decode('utf-8', 'ignore')
    pat = re.compile(r'<h[23][^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    seen = set()
    for url, title in pat.findall(h):
        t = re.sub(r'<[^>]+>', '', title).strip()
        if t and t not in seen and not url.startswith('#'):
            seen.add(t)
            print(t, '||', url)

def podcasts(names):
    for name in names:
        try:
            q = urllib.parse.quote(name)
            data = json.loads(get(f'https://itunes.apple.com/search?term={q}&media=podcast&limit=3').decode('utf-8'))
            feed = next((r['feedUrl'] for r in data.get('results', []) if r.get('feedUrl')), None)
            if not feed:
                print(f'== {name} | NO FEED'); continue
            xml = get(feed).decode('utf-8', 'ignore')
            print(f'\n===== {name} | {feed[:80]}')
            shown = 0
            for it in re.findall(r'<item>(.*?)</item>', xml, re.S):
                t = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', it, re.S)
                d = re.search(r'<pubDate>(.*?)</pubDate>', it)
                desc = re.search(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', it, re.S)
                if not t:
                    continue
                date = email.utils.parsedate_to_datetime(d.group(1)).strftime('%Y-%m-%d') if d else '?'
                dd = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', desc.group(1) if desc else '')).strip()[:400]
                print(f'  [{date}]', re.sub(r'\s+', ' ', t.group(1)).strip())
                print(f'      {dd}')
                shown += 1
                if shown >= 3:
                    break
        except Exception as e:
            print(f'== {name} | ERR {e}')

def wikipedia(page):
    url = ('https://en.wikipedia.org/w/api.php?action=parse&page='
           + urllib.parse.quote(page) + '&format=json&prop=wikitext')
    wt = json.loads(get(url).decode('utf-8'))['parse']['wikitext']['*']
    print(wt[:20000])

def fetch(url):
    h = get(url).decode('utf-8', 'ignore')
    txt = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', h, flags=re.S | re.I)
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt)
    print(txt[:6000])

if __name__ == '__main__':
    import urllib.parse
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'lithub':
        lithub()
    elif cmd == 'podcasts':
        podcasts(sys.argv[2:])
    elif cmd == 'wikipedia':
        wikipedia(sys.argv[2])
    elif cmd == 'fetch':
        fetch(sys.argv[2])
    else:
        print(__doc__)
