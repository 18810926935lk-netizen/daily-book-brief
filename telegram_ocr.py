"""Bounded local OCR on the runner; images/text are never uploaded as artifacts."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor


def ocr_pdf(path, pages, seconds=240, max_pages=120):
    import pymupdf
    deadline = time.monotonic() + seconds
    targets = [i for i, (_, text) in enumerate(pages) if len(text.strip()) < 100][:max_pages]
    results = dict(enumerate(pages))
    def read_page(index):
        if time.monotonic() >= deadline:
            return index, None
        with tempfile.TemporaryDirectory(prefix='brief-ocr-') as folder:
            image = Path(folder) / 'page.png'
            with pymupdf.open(path) as doc:
                doc[index].get_pixmap(dpi=135).save(image)
            try:
                result = subprocess.run(['tesseract', str(image), 'stdout', '-l', 'eng', '--psm', '3'],
                    capture_output=True, text=True, encoding='utf-8',
                    timeout=max(1, min(35, deadline-time.monotonic())),
                    env={**os.environ, 'OMP_THREAD_LIMIT': '1'}, check=True)
                return index, result.stdout
            except (subprocess.SubprocessError, OSError):
                return index, None
    with ThreadPoolExecutor(max_workers=2) as pool:
        for i, text in pool.map(read_page, targets):
            if text and len(text.strip()) > len(pages[i][1].strip()):
                results[i] = (pages[i][0] + '（OCR识别，可能有字词错误）', text)
    ordered = [results[i] for i in range(len(pages))]
    unread = sum(len(text.strip()) < 100 for _, text in ordered)
    return ordered, unread
