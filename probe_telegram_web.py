"""Diagnostic only: restore fresh login and download one known channel PDF."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote
from telegram_web_state import filter_state


def main():
    from playwright.sync_api import sync_playwright
    import pymupdf
    state = filter_state(json.loads(os.environ['TELEGRAM_WEB_STATE']))
    with tempfile.TemporaryDirectory(prefix='telegram-probe-') as folder:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=state, accept_downloads=True)
            page = context.new_page()
            link = quote('tg://resolve?domain=demagazinesharing&post=31288', safe='')
            page.goto('https://web.telegram.org/a/#?tgaddr=' + link, timeout=90000)
            attachment = page.locator('.File.interactive').filter(has_text='The Economist_3110.pdf').first
            attachment.wait_for(timeout=120000)
            attachment.click(button='right')
            with page.expect_download(timeout=180000) as pending:
                page.get_by_role('menuitem', name='Download', exact=True).click()
            download = pending.value
            if download.failure():
                raise RuntimeError('download_failed')
            path = Path(folder) / 'sample.pdf'
            download.save_as(path)
            browser.close()
        if not 1000 < path.stat().st_size < 60 * 1024 * 1024:
            raise ValueError('unexpected_file_size')
        with pymupdf.open(path) as doc:
            pages = len(doc)
            chars = sum(len(page.get_text()) for page in doc)
        if pages < 10 or chars < 10000:
            raise ValueError('pdf_not_readable')
        print(f'PASS: login restored; target attachment downloaded; PDF pages={pages}; text chars={chars}')
        print('Public sample SHA256: ' + hashlib.sha256(path.read_bytes()).hexdigest())
        print('No PDF, text, browser profile or session uploaded as artifacts. Daily collection remains disabled.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAIL: ' + type(exc).__name__ + '; login/download not verified. No secret details logged.')
        raise SystemExit(1)
