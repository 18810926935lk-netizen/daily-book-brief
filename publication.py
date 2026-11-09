"""One versioned manuscript for all delivery channels."""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

POLICY_VERSION = '2026-11-09.1'
SECTIONS = ['今日概览', '国际非虚构新书排行榜', '国际非虚构新书、新书评与重要书单',
            '重要图书奖项与机构', '知名非虚构作家', '国际重要图书及出版事件',
            '十大文化热点', '公众号选题建议', '来源']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ranking_html(payload):
    chart = payload['chart']
    out = ['<div id="verified-rankings">']
    if chart['status'] == 'ok':
        out.append('<p>' + escape(chart['name']) + '｜' + escape(chart['country']) +
                   '｜榜期：' + escape(chart['issue_date']) + '（周榜沿用至更新）</p>')
        out.append('<p>' + escape(chart['scope']) + '。榜期依据：' + escape(chart['date_basis']) + '</p>')
        out.append('<p><a href="' + escape(chart['url'], quote=True) + '">官方完整榜单</a>。中文译名、作者简介和内容摘要尚未逐书核实；以下保留官方原名，不猜译。</p>')
        out.append('<table><thead><tr><th>排名</th><th>原书名</th><th>作者</th><th>出版信息（榜单所载）</th></tr></thead><tbody>')
        for b in chart['books']:
            out.append('<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in
                       (b['rank'], b['title'], b['author'], b['publisher'] + ' / ' + b['publication_date'])) + '</tr>')
        out.append('</tbody></table>')
    else:
        out.append('<p>本次没有取得可完整核实的官方非虚构榜单；最近可核实榜期未知，未编造排名。</p>')
    out.append('<ul>')
    for a in payload['attempts']:
        out.append('<li><a href="' + escape(a['url'], quote=True) + '">' + escape(a['name']) +
                   '</a>：' + escape(a['status'] + ('；' + a['reason'] if a.get('reason') else '')) + '</li>')
    out.append('</ul><p>榜单核查时间：' + escape(payload['checked_at']) + '</p></div>')
    return ''.join(out)


def telegram_status(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'status': 'unavailable', 'documents': 0, 'skipped': 0}
    docs, skipped = data.get('documents', []), data.get('skipped', [])
    if docs:
        status = 'partial' if skipped else 'ok'
    elif data.get('status'):
        status = data['status']
    else:
        status = 'no_new_readable_documents' if not skipped else 'failed'
    return {'status': status, 'documents': len(docs), 'skipped': len(skipped)}


def validate_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    headings = [h.get_text(' ', strip=True) for h in soup.select('h1,h2,h3')]
    missing = [s for s in SECTIONS if not any(s in h for h in headings)]
    if missing:
        raise ValueError('missing_sections: ' + ', '.join(missing))
    if re.search(r'诺贝尔|诺奖|\bNobel\b', soup.get_text(' ', strip=True), re.I):
        raise ValueError('removed_topic_reintroduced')
    if html.count('id="verified-rankings"') != 1:
        raise ValueError('missing_verified_rankings')
    if '</html>' not in html.lower():
        raise ValueError('truncated_html')
    if soup.select('script,iframe,form'):
        raise ValueError('active_content_not_allowed')
    for el in soup.find_all(True):
        if any(k.lower().startswith('on') for k in el.attrs):
            raise ValueError('active_attribute_not_allowed')
        for attr in ('href', 'src'):
            value = el.get(attr, '')
            if value and not value.startswith(('https://', '#')):
                raise ValueError('non_public_link')


def publish(html, base, date, telegram_path):
    base = Path(base)
    if html.count('<!-- NONFICTION_RANKINGS -->') != 1:
        raise ValueError('rankings_placeholder_missing_or_duplicated')
    rankings = json.loads((base / 'data/rankings.json').read_text(encoding='utf-8'))
    html = html.replace('<!-- NONFICTION_RANKINGS -->', ranking_html(rankings))
    tg = telegram_status(telegram_path)
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    footer = ('<section><h2>发布校验</h2><p>简报日期：' + date + '；生成时间：' + stamp +
              '；编辑规范：' + POLICY_VERSION + '</p><p>Telegram 本次接入：' + escape(tg['status']) +
              '；可读资料 ' + str(tg['documents']) + '；跳过 ' + str(tg['skipped']) +
              '。两渠道共同读取此份成稿。</p></section>')
    html = html.replace('</body>', footer + '</body>')
    validate_html(html)
    html_bytes = html.encode('utf-8')
    revision = digest(html_bytes)[:16]
    stem = date + '-' + revision
    md = markdownify(str(BeautifulSoup(html, 'html.parser').body), heading_style='ATX')
    md_bytes = md.encode('utf-8')
    manifest = {'date': date, 'revision': revision, 'policy_version': POLICY_VERSION,
                'generated_at': stamp, 'git_sha': os.environ.get('GITHUB_SHA', ''),
                'run_id': os.environ.get('GITHUB_RUN_ID', ''),
                'html': stem + '.html', 'markdown': stem + '.md',
                'html_sha256': digest(html_bytes), 'markdown_sha256': digest(md_bytes),
                'telegram': tg, 'ranking_status': rankings['chart']['status'],
                'ranking_issue': rankings['chart'].get('issue_date'),
                'prompt_sha256': digest((base / 'PROMPT.md').read_bytes())}
    site = base / 'site'
    site.mkdir(exist_ok=True)
    (site / (stem + '.html')).write_bytes(html_bytes)
    (site / (stem + '.md')).write_bytes(md_bytes)
    (site / (date + '.html')).write_bytes(html_bytes)
    (site / (date + '.json')).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (site / 'latest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (site / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=' + stem + '.html"><a href="' + stem + '.html">最新简报</a>', encoding='utf-8')
    return manifest
