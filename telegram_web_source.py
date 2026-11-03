"""Read only the allowlisted public channel through official WebA."""
import json
import os
import re
import time
from urllib.parse import quote
from telegram_web_state import filter_state

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


def main():
    from playwright.sync_api import sync_playwright
    state = filter_state(json.loads(os.environ['TELEGRAM_WEB_STATE']))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=state, accept_downloads=True, locale='en-US')
        page = context.new_page()
        rows = inventory(page)
        browser.close()
    print('Public channel inventory count: ' + str(len(rows)))
    for row in rows:
        print(json.dumps(row, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAIL: ' + type(exc).__name__ + '; no session or private chat details logged.')
        raise SystemExit(1)
