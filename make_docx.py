# -*- coding: utf-8 -*-
"""图书信息简报 · 固定排版脚本：content.json -> docx（样式与2026-09-16样刊一致）
用法: python make_docx.py <content.json> <输出.docx>
content.json 结构:
{
  "date": "2026-09-17", "issue": 2,
  "sections": [
    {"title": "一、...", "color": [192,57,43], "source_note": "数据源：...（可空）",
     "items": [{"head": "...", "meta": "…（可空）", "body": "..."}]}
  ],
  "notes": ["诚实框条目", ...]
}
"""
import sys, json
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

def main():
    cfg = json.load(open(sys.argv[1], encoding='utf-8'))
    doc = Document()
    st = doc.styles['Normal']
    st.font.name = 'Times New Roman'
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    def para(text, size=10.5, color=(40, 40, 40), bold=False, center=False, bullet=False):
        p = doc.add_paragraph(style='List Bullet' if bullet else None)
        r = p.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
        r.font.color.rgb = RGBColor(*color)
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return p

    para('图书信息简报', 16, (26, 26, 46), True, True)
    para(f"大愚文化 · 每日推送 ｜ {cfg['date']} ｜ 第{cfg['issue']:03d}期", 9, (150, 150, 150), center=True)

    for sec in cfg['sections']:
        color = tuple(sec.get('color', (60, 60, 60)))
        para(sec['title'], 13, color, True)
        if sec.get('source_note'):
            para(sec['source_note'], 9, (120, 120, 120))
        for it in sec['items']:
            para(it['head'], 10.5, tuple(sec.get('head_color', color)), True)
            if it.get('meta'):
                para(it['meta'], 9, (120, 120, 120))
            para(it['body'], 10.5)

    para('📌 数据与口径说明（诚实框）', 13, (130, 130, 130), True)
    for n in cfg.get('notes', []):
        para(n, 9, (130, 130, 130), bullet=True)
    para('大愚文化 · 图书信息简报｜每天早上7点，5分钟看懂全球书情', 8.5, (170, 170, 170), center=True)

    doc.save(sys.argv[2])
    print('DOCX SAVED:', sys.argv[2])

if __name__ == '__main__':
    main()
