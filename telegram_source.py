"""Read one allowlisted channel; keep attachments and extracted text out of git."""
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timedelta, timezone

CHANNEL = 'demagazinesharing'
ROOT = Path(__file__).resolve().parent
TOPICS = re.compile(r'\b(book|books|reading|psycholog\w*|education|learning|language|science|research|technology|artificial intelligence|philosoph\w*|management|behavior\w*|behaviour\w*|culture|econom\w*|wellbeing|well-being|relationship\w*|b[üu]cher|bildung|forschung|wissenschaft)\b', re.I)
PRIORITY = re.compile(r'economist|financial|\bft\b|\bnyt\b|new york|nyrb|washington|\bwsj\b|scientist|scientific|atlantic|psycholog|spiegel|handelsblatt', re.I)


def extract(path):
    """Page numbers are PDF file pages, never inferred print pagination."""
    if path.suffix == '.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            return [(f'PDF文件第{i + 1}页', p.get_text(sort=True)) for i, p in enumerate(doc)]
    from docx import Document
    doc = Document(path)
    return [(f'Word段落{i + 1}（无可靠页码）', p.text) for i, p in enumerate(doc.paragraphs)]


def select_passages(pages, budget=10000):
    # Rank bounded windows instead of truncating whole papers at their front page.
    candidates = []
    for locator, text in pages:
        text = text.replace('\x00', '')
        for start in range(0, len(text), 2200):
            window = text[start:start + 2600]
            score = len(TOPICS.findall(window)) + 12 * len(re.findall(
                r'\b(book review|books|nonfiction|non-fiction|biography|memoir|publisher|novelist|literary)\b', window, re.I))
            if score:
                candidates.append((score, locator, window))
    chosen, used = [], 0
    for _, locator, window in sorted(candidates, key=lambda x: -x[0]):
        if used + len(window) > budget:
            continue
        chosen.append({'locator': locator, 'text': window})
        used += len(window)
    return chosen


async def collect(out_dir):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    logging.getLogger('telethon').setLevel(logging.CRITICAL)
    auth_raw = os.environ.get('TELEGRAM_AUTH_JSON')
    if not auth_raw:
        raise RuntimeError('authorization_missing')
    auth = json.loads(auth_raw)
    client = TelegramClient(StringSession(auth['session']), int(auth['api_id']), auth['api_hash'],
                            receive_updates=False, request_retries=2, connection_retries=2,
                            flood_sleep_threshold=0, device_model='Daily brief channel reader')
    state_path = ROOT / 'data/telegram_seen.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    state = {k: v for k, v in state.items() if v['date'] >= cutoff.isoformat()}
    records, skipped = [], []
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError('authorization_expired')
        entity = await client.get_entity(CHANNEL)
        if (entity.username or '').lower() != CHANNEL:
            raise RuntimeError('channel_mismatch')
        candidates = []
        async for msg in client.iter_messages(entity, limit=800):
            if msg.date < cutoff:
                break
            file = msg.file
            if not file or str(msg.id) in state:
                continue
            name = file.name or ''
            ext = Path(name).suffix.lower()
            if ext not in ('.pdf', '.docx'):
                continue
            if (file.size or 0) > 60 * 1024 * 1024:
                skipped.append({'message_id': msg.id, 'reason': 'over_60_MB'})
                continue
            candidates.append((bool(PRIORITY.search(name)), msg))
        # Newest first within preferred sources. Bound time/storage on the existing job.
        candidates.sort(key=lambda item: (item[0], item[1].date), reverse=True)
        hashes = {v['sha256'] for v in state.values()}
        total_size = 0
        for _, msg in candidates[:8]:
            if total_size + msg.file.size > 250 * 1024 * 1024:
                skipped.append({'message_id': msg.id, 'reason': 'daily_byte_budget'})
                continue
            total_size += msg.file.size
            path = out_dir / f'{msg.id}{Path(msg.file.name).suffix.lower()}'
            try:
                await asyncio.wait_for(client.download_media(msg, file=str(path)), timeout=150)
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                entry = {'date': msg.date.isoformat(), 'sha256': digest}
                if digest in hashes:
                    state[str(msg.id)] = entry
                    continue
                pages = await asyncio.to_thread(extract, path)
                if sum(len(text.strip()) for _, text in pages) < 200:
                    skipped.append({'message_id': msg.id, 'reason': 'scan_or_unreadable_needs_OCR'})
                    continue
                passages = select_passages(pages)
                records.append({'filename': msg.file.name, 'posted_at': msg.date.isoformat(),
                                'source': f'https://t.me/{CHANNEL}/{msg.id}',
                                'passages': passages, 'pages_or_paragraphs': len(pages)})
                hashes.add(digest)
                state[str(msg.id)] = entry
            except Exception as exc:
                # No exception message: network exceptions can carry credentials/URLs.
                skipped.append({'message_id': msg.id, 'reason': type(exc).__name__})
        payload = {'channel': CHANNEL, 'documents': records, 'skipped': skipped,
                   'pending_beyond_batch': max(0, len(candidates) - 8),
                   'notice': '频道发布日期不是刊期。片段可能不完整；仅在正文足以支持时引用。扫描件未OCR。'}
        (out_dir / 'source.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        # Commit only IDs/digests, and only when the normal generation/publish succeeds.
        state_path.parent.mkdir(exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2), encoding='utf-8')
        summary = f'Telegram: extracted={len(records)}, skipped={len(skipped)}, pending={payload["pending_beyond_batch"]}'
        print(summary)
        for item in skipped:
            print(f'Telegram skipped message {item["message_id"]}: {item["reason"]}')
        if candidates and not records and skipped:
            raise RuntimeError('no_readable_documents')
        return summary
    finally:
        await client.disconnect()


def main():
    out_dir = Path(os.environ.get('TELEGRAM_WORK_DIR', str(Path(tempfile.gettempdir()) / 'telegram-private')))
    out_dir.mkdir(parents=True, exist_ok=True)
    # Never consume yesterday's extract after an error.
    target = out_dir / 'source.json'
    target.write_text(json.dumps({'status': 'collection_incomplete'}), encoding='utf-8')
    try:
        asyncio.run(asyncio.wait_for(collect(out_dir), timeout=480))
    except Exception as exc:
        target.write_text(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}), encoding='utf-8')
        print(f'::warning::Telegram collection failed ({type(exc).__name__}); no credentials logged.')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
