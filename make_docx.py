# -*- coding: utf-8 -*-
"""HTML -> docx（htmldocx 转换，保留内联样式）
用法: python make_docx.py <输入.html> <输出.docx>
"""
import sys
from htmldocx import Htmldocx

def main():
    html = open(sys.argv[1], encoding='utf-8').read()
    h = Htmldocx()
    h.add_html(html)
    h.doc.save(sys.argv[2])
    print('DOCX SAVED:', sys.argv[2])

if __name__ == '__main__':
    main()
