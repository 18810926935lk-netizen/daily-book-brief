"""Read only the allowlisted public channel through official WebA."""
import json
import os
import re
import time
import hashlib
import tempfile
from pathlib import Path
from datetime import date, datetime, timezone
from urllib.parse import quote
from telegram_web_state import filter_state
from telegram_publications import select_issues, issue_date
from telegram_source import extract, select_passages

CHANNEL = 'demagazinesharing'


def channel_url(post=None):
    link = 'tg://resolve?domain=' + CHANNEL
    if post:
        link += '&post=' + str(int(post))
    return 'https://web.telegram.org/a/#?tgaddr=' + quote(link, safe='')


def inventory(page):
    page.goto(channel_url(), timeout=90000)
    page.locator('.MessageList .File.interactive').first.wait_for(timeout=120000)
    listing = page.locator('.MessageList').filter(has=page.locator('.File.interactive')).last
    # First reach the latest messages, regardless of the account's unread position.
    for _ in range(5):
        listing.evaluate('(e) => { e.scrollTop = e.scrollHeight; }')
        page.wait_for_timeout(900)
    found = {}
    unchanged = 0
    for _ in range(75):
        rows = listing.locator('.File.interactive').evaluate_all('''es => es.map(e => {
          const m=e.closest('[data-message-id]');
          return {id: m?.getAttribute('data-message-id'),
            filename:e.querySelector('.file-title')?.getAttribute('title'),
            size:e.querySelector('.file-subtitle')?.textContent};
        })''')
        before = len(found)
        for row in rows:
            if row['id'] and re.fullmatch(r'\d+', row['id']) and row['filename']:
                found[row['id']] = row
        unchanged = unchanged + 1 if len(found) == before else 0
        if unchanged >= 4 or len(found) >= 800:
            break
        listing.evaluate('(e) => { e.scrollTop = 0; }')
        page.wait_for_timeout(1000)
    if not found:
        raise RuntimeError('channel_inventory_empty')
    return sorted(found.values(), key=lambda x: int(x['id']), reverse=True)


def size_bytes(text):
    match = re.search(r'([\d.]+)\s*(KB|MB|GB|B)\b', text or '', re.I)
    if not match:
        return None
    return int(float(match[1]) * {'B':1, 'KB':1024, 'MB':1024**2, 'GB':1024**3}[match[2].upper()])


def collect(page, rows, out_dir):
    state_path = Path(__file__).parent / 'data/telegram_web_seen.json'
    seen = json.loads(state_path.read_text()) if state_path.exists() else {}
    groups = select_issues(rows, seen, date.today())
    documents, skipped = [], []
    total = 0
    deadline = time.monotonic() + 600
    hashes = {v['sha256'] for v in seen.values()}
    for variants in groups:
        if time.monotonic() > deadline:
            skipped.append({'reason': 'run_time_budget'})
            break
        # Prefer a smaller usable regional edition; try another only on failure.
        variants.sort(key=lambda x: size_bytes(x.get('size')) or 10**12)
        for item in variants:
            size = size_bytes(item.get('size'))
            if not size or size > 60*1024**2 or total + size > 250*1024**2:
                skipped.append({'message_id': item['id'], 'reason': 'size_limit_or_unknown'})
                continue
            total += size
            path = out_dir / (item['id'] + Path(item['filename']).suffix.lower())
            try:
                page.goto(channel_url(item['id']), timeout=45000)
                attachment = page.locator('.MessageList .File.interactive').filter(has_text=item['filename']).first
                attachment.wait_for(timeout=45000)
                attachment.click(button='right')
                with page.expect_download(timeout=90000) as pending:
                    page.get_by_role('menuitem', name='Download', exact=True).click()
                download = pending.value
                if download.failure():
                    raise RuntimeError('download_failed')
                download.save_as(path)
                if path.stat().st_size > 60*1024**2:
                    raise ValueError('file_size_exceeds_limit')
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                pages = extract(path)
                if sum(len(t.strip()) for _, t in pages) < 200:
                    raise ValueError('scan_needs_ocr')
                key = item['issue_key']
                actual_key = key
                if not item['issue_date_candidate']:
                    front = re.sub(r'\s+', ' ', pages[0][1][:1600])
                    actual_date = issue_date(front, date.today())
                    if not actual_date:
                        raise ValueError('undated_issue_not_verified')
                    actual_key = 'financial-times:' + actual_date.isoformat()
                entry = {'message_id': item['id'], 'sha256': digest,
                         'collected_at': datetime.now(timezone.utc).isoformat()}
                if digest not in hashes and actual_key not in seen:
                    passages = select_passages(pages, budget=6000)
                    documents.append({'filename': item['filename'], 'publication_candidate': item['publication'],
                        'issue_date_candidate': item['issue_date_candidate'],
                        'source': f'https://t.me/{CHANNEL}/{item["id"]}',
                        'passages': passages, 'pages_or_paragraphs': len(pages)})
                    hashes.add(digest)
                    print(f'EXTRACTED: {item["publication"]}; message={item["id"]}; pages={len(pages)}; passages={len(passages)}; regional_alternatives_skipped={len(variants)-1}')
                seen[key] = entry
                seen[actual_key] = entry
                break
            except Exception as exc:
                reason = str(exc) if str(exc) in {
                    'download_failed', 'file_size_exceeds_limit', 'scan_needs_ocr',
                    'undated_issue_not_verified'} else type(exc).__name__
                skipped.append({'message_id': item['id'], 'reason': reason})
                print(f'SKIPPED: {item["publication"]}; message={item["id"]}; reason={reason}', flush=True)
            finally:
                path.unlink(missing_ok=True)
    payload = {'channel': CHANNEL, 'documents': documents, 'skipped': skipped,
               'notice': '只检查最近至多约800条附件，每刊选择最新一期的一版。刊期候选来自文件名，月刊日期的01只是去重标识，不代表出版日；必须以正文核实。扫描件未OCR。'}
    while len(json.dumps(payload, ensure_ascii=False)) > 84000 and any(d['passages'] for d in documents):
        max(documents, key=lambda d: sum(len(p['text']) for p in d['passages']))['passages'].pop()
    (out_dir/'source.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    print(f'Telegram Web: inventory={len(rows)}, selected_issues={len(groups)}, extracted={len(documents)}, skipped={len(skipped)}')
    if groups and not documents and skipped:
        raise RuntimeError('no_readable_documents')
    if skipped:
        print('::warning::Some Telegram attachments could not be processed; source payload contains explicit skips.')
    # Only IDs, issue keys and hashes go into git after successful normal publication.
    state_path.parent.mkdir(exist_ok=True)
    state_path.write_text(json.dumps(seen, indent=2), encoding='utf-8')


def main():
    from playwright.sync_api import sync_playwright
    out_dir = Path(os.environ.get('TELEGRAM_WORK_DIR', tempfile.gettempdir() + '/telegram-private'))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/'source.json').write_text('{"status":"collection_incomplete"}')
    state = filter_state(json.loads(os.environ['TELEGRAM_WEB_STATE']))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=state, accept_downloads=True, locale='en-US')
        page = context.new_page()
        rows = inventory(page)
        if os.environ.get('TELEGRAM_INVENTORY_ONLY') != 'true':
            collect(page, rows, out_dir)
        browser.close()
    if os.environ.get('TELEGRAM_INVENTORY_ONLY') == 'true':
        print('Public channel inventory count: ' + str(len(rows)))
        for row in rows:
            print(json.dumps(row, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAIL: ' + type(exc).__name__ + '; no session or private chat details logged.')
        raise SystemExit(1)
