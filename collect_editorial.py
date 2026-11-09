"""Collect dated, attributed candidates and an intact official nonfiction chart."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
CST = timezone(timedelta(hours=8))
PW = 'https://www.publishersweekly.com/pw/nielsen/hardcovernonfiction.html'
NYT = 'https://www.nytimes.com/books/best-sellers/hardcover-nonfiction/'
FEEDS = [
    ('Guardian Books', '图书、作者', 'https://www.theguardian.com/books/rss'),
    ('Guardian Science', '科研、心理', 'https://www.theguardian.com/science/rss'),
    ('Guardian Education', '教育、学习', 'https://www.theguardian.com/education/rss'),
    ('Guardian Money', '个人财务', 'https://www.theguardian.com/money/rss'),
    ('Nature', '科研', 'https://www.nature.com/nature.rss'),
    ('MIT News', '技术、学习、管理', 'https://news.mit.edu/rss/feed'),
    ('ScienceDaily Mind', '心理、认知', 'https://www.sciencedaily.com/rss/mind_brain.xml'),
    ('The Conversation', '社会、知识', 'https://theconversation.com/global/articles.atom'),
    ('NPR Books', '图书', 'https://feeds.npr.org/1032/rss.xml'),
    ('DW Culture', '跨文化', 'https://rss.dw.com/rdf/rss-en-cul'),
    ('Le Monde Livres', '法语图书', 'https://www.lemonde.fr/livres/rss_full.xml'),
]


def fetch(url):
    r = requests.get(url, timeout=(10, 30), headers={'User-Agent': 'Mozilla/5.0 (compatible; DailyBookBrief/2.0)'})
    r.raise_for_status()
    return r.content


def parse_pw(content):
    soup = BeautifulSoup(content, 'html.parser')
    heading = soup.select_one('.nielsen-header')
    if not heading or heading.get_text(' ', strip=True) != 'Hardcover Frontlist Nonfiction':
        raise ValueError('unexpected_chart')
    books, history_dates = [], []
    for row in soup.select('table.nielsen-table > tr, table.nielsen-table > tbody > tr'):
        rank = row.select_one('.nielsen-rank')
        if not rank:
            continue
        info = row.select_one('.nielsen-bookinfo')
        title = info.select_one('.nielsen-booktitle').get_text(' ', strip=True)
        author = info.find_all('div', recursive=False)[1].get_text(' ', strip=True)
        history = info.select_one('.nielsen_stat_details')
        if history:
            dates = re.findall(r'(\d{2}/\d{2}/\d{4}),\s*(\d+)', history.get_text(' ', strip=True))
            if dates:
                latest = max(dates, key=lambda d: datetime.strptime(d[0], '%m/%d/%Y'))
                if int(latest[1]) != int(rank.get_text(strip=True)):
                    raise ValueError('history_rank_mismatch')
                history_dates.append(datetime.strptime(latest[0], '%m/%d/%Y').date().isoformat())
        isbn = info.select_one('.nielsen-isbn')
        publisher = ''.join(str(t) for t in isbn.contents if isinstance(t, str)).strip().split('$')[0].rstrip(', ')
        cells = row.find_all('td', recursive=False)
        books.append({'rank': int(rank.get_text(strip=True)), 'title': title,
                      'author': re.sub(r',\s*Author\s*$', '', author),
                      'publisher': publisher, 'publication_date': cells[-2].get_text(' ', strip=True)})
    if len(books) != 25 or [b['rank'] for b in books] != list(range(1, 26)):
        raise ValueError('incomplete_chart')
    if len(history_dates) < 3 or len(set(history_dates)) != 1:
        raise ValueError('unverified_chart_date')
    return {'status': 'ok', 'name': 'Publishers Weekly Hardcover Frontlist Nonfiction',
            'country': '美国', 'url': PW, 'issue_date': history_dates[0],
            'date_basis': '官方页面各书销售历史的最近共同榜期；不是网页抓取日期',
            'scope': '精装前台非虚构销售榜，完整25名；非全球混合榜，非编辑推荐榜', 'books': books}


def collect_rankings():
    attempts = []
    # A blocked NYT page must never silently turn into a made-up chart.
    try:
        fetch(NYT)
        attempts.append({'name': 'NYT Hardcover Nonfiction', 'url': NYT,
                         'status': 'not_verified', 'reason': '页面可达但完整榜期与排名未结构化核实'})
    except requests.RequestException as e:
        attempts.append({'name': 'NYT Hardcover Nonfiction', 'url': NYT,
                         'status': 'unavailable', 'reason': type(e).__name__})
    try:
        chart = parse_pw(fetch(PW))
    except (requests.RequestException, ValueError, AttributeError, IndexError) as e:
        chart = {'status': 'unavailable', 'name': 'Publishers Weekly Hardcover Frontlist Nonfiction',
                 'url': PW, 'reason': type(e).__name__, 'books': []}
    attempts.append({k: v for k, v in chart.items() if k != 'books'})
    return {'checked_at': datetime.now(CST).isoformat(), 'attempts': attempts, 'chart': chart}


def collect_feed(spec):
    name, topic, url = spec
    result = {'name': name, 'topic': topic, 'url': url, 'items': []}
    now = datetime.now(timezone.utc)
    try:
        feed = feedparser.parse(fetch(url))
        if not feed.entries:
            raise ValueError('empty_or_invalid_feed')
        for entry in feed.entries:
            dt = entry.get('published_parsed') or entry.get('updated_parsed')
            if not dt or not entry.get('link'):
                continue
            date = datetime(*dt[:6], tzinfo=timezone.utc)
            if not now - timedelta(days=7) <= date <= now:
                continue
            excerpt = BeautifulSoup(entry.get('summary', ''), 'html.parser').get_text(' ', strip=True)
            item = {'title': entry.get('title', ''), 'url': entry.link, 'date': date.isoformat(),
                    'date_basis': 'published' if entry.get('published_parsed') else 'updated_only_not_first_publication',
                    'excerpt': excerpt[:1500], 'evidence': 'feed_excerpt_only'}
            try:
                article = BeautifulSoup(fetch(entry.link), 'html.parser')
                body = article.select_one('article')
                if body:
                    for el in body.select('script,style,nav,aside,footer,form'):
                        el.decompose()
                    paragraphs = [p.get_text(' ', strip=True) for p in body.select('p')]
                    text = '\n'.join(p for p in paragraphs if len(p) > 50)
                    if len(text) > 400:
                        item.update(excerpt=text[:6500], evidence='article_partial_text')
            except requests.RequestException:
                item['article_access'] = 'unavailable'
            result['items'].append(item)
            if len(result['items']) >= 3:
                break
        result['status'] = 'ok'
    except (requests.RequestException, ValueError) as e:
        result.update(status='unavailable', reason=type(e).__name__)
    return result


def main():
    (BASE / 'data').mkdir(exist_ok=True)
    rankings = collect_rankings()
    (BASE / 'data/rankings.json').write_text(json.dumps(rankings, ensure_ascii=False, indent=2), encoding='utf-8')
    with ThreadPoolExecutor(max_workers=6) as pool:
        sources = list(pool.map(collect_feed, FEEDS))
    (BASE / 'data/editorial.json').write_text(json.dumps({'checked_at': datetime.now(CST).isoformat(), 'sources': sources}, ensure_ascii=False), encoding='utf-8')
    print('EDITORIAL:', [(s['name'], s['status'], len(s['items'])) for s in sources])
    print('RANKINGS:', rankings['chart']['status'], len(rankings['chart']['books']))


if __name__ == '__main__':
    main()
