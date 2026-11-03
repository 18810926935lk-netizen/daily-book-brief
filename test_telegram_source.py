import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import telegram_source as source


class TelegramTests(unittest.TestCase):
    def test_relevant_passage_keeps_locator(self):
        result = source.select_passages([('PDF文件第17页', 'Education and psychology research. ' * 20),
                                         ('PDF文件第1页', 'Advertisement. ' * 20)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['locator'], 'PDF文件第17页')

    def test_pdf_and_docx_extraction(self):
        import pymupdf
        from docx import Document
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            with pymupdf.open() as pdf:
                pdf.new_page().insert_text((50, 50), 'Education and science research')
                pdf.save(path / 'sample.pdf')
            self.assertIn('Education', source.extract(path / 'sample.pdf')[0][1])
            doc = Document()
            doc.add_paragraph('Psychology and learning research')
            doc.save(path / 'sample.docx')
            self.assertIn('无可靠页码', source.extract(path / 'sample.docx')[0][0])

    def test_channel_download_dedup_and_private_output(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / 'private'
            private.mkdir()
            doc = Document()
            doc.add_paragraph('Psychology and education research improves learning. ' * 20)
            doc.save(private / 'fixture.docx')
            body = (private / 'fixture.docx').read_bytes()
            downloads = []

            class Client:
                def __init__(self, *args, **kwargs): pass
                async def connect(self): pass
                async def disconnect(self): pass
                async def is_user_authorized(self): return True
                async def get_entity(self, name):
                    assert name == 'demagazinesharing'
                    return SimpleNamespace(username=name)
                async def iter_messages(self, entity, limit):
                    for mid in (2, 1):
                        yield SimpleNamespace(id=mid, date=datetime.now(timezone.utc),
                                              file=SimpleNamespace(name='sample.docx', size=len(body)))
                async def download_media(self, msg, file):
                    downloads.append(msg.id)
                    Path(file).write_bytes(body)

            with patch.object(source, 'ROOT', root), patch.dict(os.environ, {
                'TELEGRAM_AUTH_JSON': json.dumps({'session': '', 'api_id': 1, 'api_hash': 'test'})
            }), patch('telethon.TelegramClient', Client):
                asyncio.run(source.collect(private))
                payload = json.loads((private / 'source.json').read_text(encoding='utf-8'))
                self.assertEqual(len(payload['documents']), 1)
                self.assertTrue(payload['documents'][0]['passages'])
                state_text = (root / 'data/telegram_seen.json').read_text()
                self.assertNotIn('Psychology', state_text)
                self.assertNotIn('session', state_text)
                self.assertEqual(len(json.loads(state_text)), 2)
                asyncio.run(source.collect(private))
                self.assertEqual(len(downloads), 2)  # second run did not re-download

    def test_missing_auth_replaces_stale_text_and_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'source.json'
            path.write_text('STALE PRIVATE TEXT')
            with patch.dict(os.environ, {'TELEGRAM_WORK_DIR': temp}, clear=True):
                with self.assertRaises(SystemExit) as error:
                    source.main()
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(json.loads(path.read_text())['status'], 'failed')
            self.assertNotIn('STALE', path.read_text())


if __name__ == '__main__':
    unittest.main()
