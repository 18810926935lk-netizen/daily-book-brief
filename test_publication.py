import json
import tempfile
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
from collect_editorial import parse_pw
from publication import SECTIONS, publish, digest, telegram_status, validate_html

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'data').mkdir()
        (self.root/'PROMPT.md').write_text('test policy',encoding='utf-8')
        self.payload={'checked_at':'2026-11-09T13:00:00+08:00','attempts':[], 'chart': {'status':'unavailable','books':[]}}
        self.save()
        self.html='<html><body>'+''.join('<h2>'+s+'</h2>' for s in SECTIONS)+'<!-- NONFICTION_RANKINGS --><p>正文</p></body></html>'
    def save(self):
        (self.root/'data/rankings.json').write_text(json.dumps(self.payload),encoding='utf-8')
    def build(self, html=None):
        return publish(html or self.html,self.root,'2026-11-09', self.root/'absent.json')
    def test_channels_share_hash_verified_manuscript(self):
        m=self.build()
        self.assertEqual(digest((self.root/'site'/m['html']).read_bytes()),m['html_sha256'])
        self.assertEqual(digest((self.root/'site'/m['markdown']).read_bytes()),m['markdown_sha256'])
        self.assertEqual(json.loads((self.root/'site/latest.json').read_text(encoding='utf-8')),m)
        self.assertIn('正文',(self.root/'site'/m['markdown']).read_text(encoding='utf-8'))
    def test_missing_section_blocks_publication(self):
        with self.assertRaises(ValueError): self.build(self.html.replace('<h2>十大文化热点</h2>',''))
        self.assertFalse((self.root/'site/latest.json').exists())
    def test_legacy_topic_blocks_publication(self):
        with self.assertRaises(ValueError): self.build(self.html.replace('正文','诺奖观察'))
    def test_duplicate_rankings_blocks_publication(self):
        with self.assertRaises(ValueError): self.build(self.html.replace('正文','<!-- NONFICTION_RANKINGS -->'))
    def test_script_blocks_publication(self):
        with self.assertRaises(ValueError): self.build(self.html.replace('正文','<script>alert(1)</script>'))
    def test_local_links_block_publication(self):
        with self.assertRaises(ValueError): self.build(self.html.replace('正文','<a href="file:///tmp/x">文件</a>'))
    def test_partial_telegram_status(self):
        p=self.root/'tg.json';p.write_text('{"documents":[{}],"skipped":[{}]}')
        self.assertEqual(telegram_status(p),{'status':'partial','documents':1,'skipped':1})
    def test_rerun_retains_old_version(self):
        a=self.build();b=self.build(self.html.replace('正文','新版'))
        self.assertNotEqual(a['html'],b['html'])
        self.assertTrue((self.root/'site'/a['html']).exists())
    def test_intact_official_chart(self):
        rows=[]
        for rank in range(1,26):
            rows.append(f'<tr><td class="nielsen-rank">{rank}</td><td class="nielsen-bookinfo"><div class="nielsen-booktitle">Book {rank}</div><div>Writer, Author</div><div class="nielsen-isbn">Publisher, $20<div class="nielsen_stat_details">11/09/2026, {rank}</div></div></td><td>Nov 2026</td><td>100</td></tr>')
        page='<div class="nielsen-header">Hardcover Frontlist Nonfiction</div><table class="nielsen-table">'+''.join(rows)+'</table>'
        chart=parse_pw(page)
        self.assertEqual(len(chart['books']),25)
        self.assertEqual(chart['issue_date'],'2026-11-09')
        with self.assertRaises(ValueError): parse_pw(page.replace(rows[-1],''))

if __name__=='__main__': unittest.main()
