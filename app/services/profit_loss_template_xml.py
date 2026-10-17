"""XLSX worksheet XML using the supplied PL template's own cell styles."""
from decimal import Decimal
import re
from copy import deepcopy
from functools import lru_cache
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from app.services.profit_loss_template import col_number, ROOT

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


@lru_cache(maxsize=1)
def template_styles():
    root = ET.fromstring((ROOT / 'pl_styles.xml').read_bytes())
    xfs = root.find(f'{{{NS}}}cellXfs')
    percent = {}
    for index, xf in enumerate(list(xfs)):
        if int(xf.get('numFmtId', '0')) in (9, 10):
            percent[index] = index
        else:
            clone = deepcopy(xf)
            clone.set('numFmtId', '10')
            clone.set('applyNumberFormat', '1')
            percent[index] = len(xfs)
            xfs.append(clone)
    xfs.set('count', str(len(xfs)))
    return ET.tostring(root, encoding='unicode'), percent


def column_name(index):
    result = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def worksheet(rows):
    count = len(rows.headers)
    output = []
    for index, row in enumerate(rows, 1):
        cells = []
        styles = rows.cell_styles.get(index, {})
        for col in range(1, count + 1):
            value = row[col-1] if col <= len(row) else None
            style = styles.get(col, styles.get(2, 0))
            if rows.headers[col - 1] == '%' and isinstance(value, (Decimal, int, float)):
                style = template_styles()[1][style]
            ref = column_name(col) + str(index)
            if value is None:
                cells.append(f'<c r="{ref}" s="{style}"/>')
            elif isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}" s="{style}" t="n"><v>{value}</v></c>')
            else:
                value = escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value)))
                cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{value}</t></is></c>')
        output.append(f'<row r="{index}" ht="{rows.row_heights.get(index,15)}" customHeight="1">{"".join(cells)}</row>')
    cols = []
    for col in range(1, count + 1):
        original = next((c for c in rows.template_profile['columns'] if int(c['min']) <= col <= int(c['max'])), {})
        width = original.get('width', 26)
        cols.append(f'<col min="{col}" max="{col}" width="{width}" customWidth="1"/>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS}"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        f'<dimension ref="A1:{column_name(count)}{len(rows)}"/>'
        '<sheetViews><sheetView showGridLines="1" zoomScale="100" workbookViewId="0">'
        '<pane xSplit="1" ySplit="6" topLeftCell="B7" activePane="bottomRight" state="frozen"/>'
        '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/>'
        f'<cols>{"".join(cols)}</cols><sheetData>{"".join(output)}</sheetData>'
        '<printOptions horizontalCentered="1"/>'
        '<pageMargins left="0.25" right="0.25" top="0.35" bottom="0.35" header="0.15" footer="0.15"/>'
        '<pageSetup paperSize="8" orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
        '<headerFooter><oddFooter>&amp;L&amp;A&amp;RPage &amp;P of &amp;N</oddFooter></headerFooter></worksheet>')
