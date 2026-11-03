import json
from pathlib import Path
import tempfile
import unittest
from datetime import date
from unittest.mock import MagicMock, patch
import telegram_web_source as source


class CollectionTests(unittest.TestCase):
    def test_ft_upload_date_fallback_is_explicit_and_only_one_edition(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            page = MagicMock()
            page.locator.return_value.first.get_attribute.return_value = '11/3/2026, 1:02:03 PM'
            download = page.expect_download.return_value.__enter__.return_value.value
            download.failure.return_value = None
            download.save_as.side_effect = lambda path: path.write_bytes(b'synthetic fixture')
            rows = [{'id': str(i), 'filename': f'FT {edition}.pdf', 'size':'1 MB'}
                    for i, edition in [(100,'UK'),(101,'US'),(102,'EU')]]
            with patch.object(source, '__file__', str(root/'source.py')), patch.object(
                    source, 'extract', return_value=[('PDF文件第1页', 'A nonfiction book review. ' * 30)]):
                source.collect(page, rows, root)
            payload = json.loads((root/'source.json').read_text(encoding='utf-8'))
            self.assertEqual(download.save_as.call_count, 1)
            record = payload['documents'][0]
            self.assertEqual(record['issue_date_candidate'], '2026-11-03')
            self.assertIn('upload_date_estimate', record['issue_date_basis'])

    def test_one_edition_downloaded_and_successful_issue_not_downloaded_again(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            page = MagicMock()
            download = page.expect_download.return_value.__enter__.return_value.value
            download.failure.return_value = None
            def save(path):
                doc = pymupdf.open()
                p = doc.new_page()
                p.insert_textbox((40,40,550,750), 'A book review of a new nonfiction book. ' * 30)
                doc.save(path)
                doc.close()
            download.save_as.side_effect = save
            day = date.today().isoformat()
            rows = [{'id': str(i), 'filename': f'The Economist {edition} {day}.pdf', 'size':'1 MB'}
                    for i, edition in [(100,'Europe'),(101,'USA'),(102,'Asia')]]
            with patch.object(source, '__file__', str(root/'source.py')):
                source.collect(page, rows, root)
                self.assertEqual(download.save_as.call_count, 1)
                payload = json.loads((root/'source.json').read_text(encoding='utf-8'))
                self.assertEqual(len(payload['documents']), 1)
                state = (root/'data/telegram_web_seen.json').read_text()
                self.assertNotIn('A book review', state)
                self.assertFalse(list(root.glob('*.pdf')))
                source.collect(page, rows, root)
                self.assertEqual(download.save_as.call_count, 1)


if __name__ == '__main__':
    unittest.main()
