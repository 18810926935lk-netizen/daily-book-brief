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


def upload_date(page, message_id):
    stamp = page.locator(f'.MessageList [data-message-id="{int(message_id)}"] .message-time').first
    stamp.hover(timeout=5000)
    for _ in range(5):
        title = stamp.get_attribute('title')
        if title:
            first_line = title.splitlines()[0]
            # Web context uses en-US and Asia/Shanghai explicitly.
            numeric = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})/(20\d{2})', first_line)
            if numeric:
                return date(int(numeric[3]), int(numeric[1]), int(numeric[2]))
            return issue_date(first_line, date.today())
        page.wait_for_timeout(200)
    return None



def locate_attachment(page, item):
    """Locate a Telegram attachment by its stable message ID, then filename fallback."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    message_selector = f'.MessageList [data-message-id="{int(item["id"])}"] .File.interactive'
    by_message = page.locator(message_selector).first
    try:
        by_message.wait_for(state='visible', timeout=90000)
        by_message.scroll_into_view_if_needed(timeout=20000)
        return by_message, 'message_id'
    except PlaywrightTimeoutError:
        # Some WebA builds virtualize message rows and omit the data-message wrapper
        # after deep-link navigation. Keep a bounded filename fallback for those builds.
        by_name = page.locator('.MessageList .File.interactive').filter(has_text=item['filename']).first
        by_name.wait_for(state='visible', timeout=30000)
        by_name.scroll_into_view_if_needed(timeout=20000)
        return by_name, 'filename_fallback'


def collect(page, rows, out_dir):
    state_path = Path(__file__).parent / 'data/telegram_web_seen.json'
    seen = json.loads(state_path.read_text()) if state_path.exists() else {}
    groups = select_issues(rows, seen, date.today())
    documents, skipped = [], []
    archive_path = Path(__file__).parent / 'data/telegram_web_archive_index.json'
    archive = json.loads(archive_path.read_text(encoding='utf-8')) if archive_path.exists() else {'schema_version': 1, 'items': []}
    archived_hashes = {x.get('sha256') for x in archive.get('items', [])}
    total = 0
    deadline = time.monotonic() + 1200
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
                # WebA consumes tgaddr on initial load, not subsequent hash navigation.
                stage = 'navigate_to_message'
                page.goto('about:blank')
                page.goto(channel_url(item['id']), timeout=90000, wait_until='domcontentloaded')
                stage = 'locate_attachment'
                attachment, locator_mode = locate_attachment(page, item)
                print(f'TELEGRAM_DIAGNOSTIC: publication={item["publication"]}; message={item["id"]}; stage=attachment_found; locator={locator_mode}; url_host={page.url.split("/")[2] if "/" in page.url else "unknown"}', flush=True)
                posted = None
                if item['publication'] == 'Financial Times':
                    try:
                        posted = upload_date(page, item['id'])
                    except Exception:
                        pass  # Explicit header date can still establish the issue.
                stage = 'open_context_menu'
                attachment.click(button='right', timeout=30000)
                stage = 'wait_download_menu'
                menu_item = page.get_by_role('menuitem', name='Download', exact=True)
                menu_item.wait_for(state='visible', timeout=30000)
                stage = 'click_download_and_wait_event'
                with page.expect_download(timeout=120000) as pending:
                    menu_item.click(timeout=30000)
                download = pending.value
                stage = 'download_completion'
                if download.failure():
                    raise RuntimeError('download_failed')
                download.save_as(path)
                if path.stat().st_size > 60*1024**2:
                    raise ValueError('file_size_exceeds_limit')
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                pages = extract(path)
                unread = 0
                if path.suffix == '.pdf' and sum(len(t.strip()) >= 100 for _, t in pages) < max(1, len(pages)*0.3):
                    from telegram_ocr import ocr_pdf
                    pages, unread = ocr_pdf(path, pages, seconds=max(1, min(240, deadline-time.monotonic())))
                    print(f'OCR: {item["publication"]}; pages={len(pages)}; low_text_pages_remaining={unread}', flush=True)
                if sum(len(t.strip()) for _, t in pages) < 200:
                    raise ValueError('scan_ocr_failed')
                key = item['issue_key']
                actual_key = key
                issue_basis = 'filename_candidate'
                resolved_date = item['issue_date_candidate']
                if not item['issue_date_candidate']:
                    front = re.sub(r'\s+', ' ', pages[0][1][:1600])
                    actual_date = issue_date(front, date.today())
                    issue_basis = 'first_page_date_candidate'
                    if not actual_date:
                        actual_date = posted
                        issue_basis = 'upload_date_estimate_user_authorized_may_differ_by_one_day'
                    if not actual_date:
                        raise ValueError('undated_issue_not_verified')
                    resolved_date = actual_date.isoformat()
                    actual_key = 'financial-times:' + actual_date.isoformat()
                entry = {'message_id': item['id'], 'sha256': digest,
                         'collected_at': datetime.now(timezone.utc).isoformat()}
                if digest not in archived_hashes:
                    archive['items'].append({'publication': item['publication'],
                        'filename': item['filename'], 'message_id': item['id'],
                        'issue_key': actual_key, 'issue_date': resolved_date,
                        'issue_date_basis': issue_basis, 'source': f'https://t.me/{CHANNEL}/{item["id"]}',
                        'sha256': digest, 'collected_at': entry['collected_at'],
                        'pages': len(pages), 'ocr_low_text_pages_remaining': unread})
                    archived_hashes.add(digest)
                if digest not in hashes and actual_key not in seen:
                    passages = select_passages(pages, budget=6000)
                    documents.append({'filename': item['filename'], 'publication_candidate': item['publication'],
                        'issue_date_candidate': resolved_date, 'issue_date_basis': issue_basis,
                        'posted_date': posted.isoformat() if posted else None,
                        'source': f'https://t.me/{CHANNEL}/{item["id"]}',
                        'ocr_low_text_pages_remaining': unread,
                        'passages': passages, 'pages_or_paragraphs': len(pages)})
                    hashes.add(digest)
                    print(f'EXTRACTED: {item["publication"]}; message={item["id"]}; pages={len(pages)}; passages={len(passages)}; regional_alternatives_skipped={len(variants)-1}')
                seen[key] = entry
                seen[actual_key] = entry
                break
            except Exception as exc:
                reason = str(exc) if str(exc) in {
                    'download_failed', 'file_size_exceeds_limit', 'scan_ocr_failed',
                    'undated_issue_not_verified'} else type(exc).__name__
                failed_stage = locals().get('stage', 'unknown')
                skipped.append({'message_id': item['id'], 'reason': reason, 'stage': failed_stage})
                print(f'SKIPPED: {item["publication"]}; message={item["id"]}; reason={reason}; stage={failed_stage}', flush=True)
            finally:
                path.unlink(missing_ok=True)
    payload = {'channel': CHANNEL, 'documents': documents, 'skipped': skipped,
               'notice': '只检查最近约800条附件，每刊选择最新一期的一版。刊期候选来自文件名，月刊日期的01只是去重标识，不代表出版日；必须以正文核实。OCR段落已标记，识别可能有错；剩余低文字页数包含空白页、广告及未识别页面，不能声称已读完整期。'}
    while len(json.dumps(payload, ensure_ascii=False)) > 84000 and any(d['passages'] for d in documents):
        max(documents, key=lambda d: sum(len(p['text']) for p in d['passages']))['passages'].pop()
    (out_dir/'source.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    print(f'Telegram Web: inventory={len(rows)}, selected_issues={len(groups)}, extracted={len(documents)}, skipped={len(skipped)}')
    if groups and not documents and skipped:
        raise RuntimeError('no_readable_documents')
    if skipped:
        print('::warning::Some Telegram attachments could not be processed; source payload contains explicit skips.')
    # Durable catalog contains bibliographic/provenance metadata only; no PDFs or full text.
    archive['items'].sort(key=lambda x: (x.get('publication', ''), x.get('issue_date') or '', x.get('message_id', '')))
    archive_path.parent.mkdir(exist_ok=True)
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding='utf-8')
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
        context = browser.new_context(storage_state=state, accept_downloads=True, locale='en-US', timezone_id='Asia/Shanghai')
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
