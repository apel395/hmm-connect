"""Compact, Excel-compatible styling for the supplied P&L schedules."""
from decimal import Decimal
import re
from functools import lru_cache
from xml.sax.saxutils import escape



NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


@lru_cache(maxsize=1)
def template_styles():
    # Self-contained styles avoid dangling mc:Ignorable namespace declarations
    # from the legacy template (which cause Excel to repair styles.xml).
    fonts = ''.join(f'<font><sz val="{size}"/><color rgb="{color}"/><name val="Aptos"/>{"<b/>" if bold else ""}</font>' for size,color,bold in [(10,'FF243746',False),(16,'FFFFFFFF',True),(10,'FFFFFFFF',True),(10,'FF17394B',True)])
    fills = '<fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>' + ''.join(f'<fill><patternFill patternType="solid"><fgColor rgb="{c}"/><bgColor indexed="64"/></patternFill></fill>' for c in ['FF17394B','FFE8F2F2','FFF4F7FA','FF087E83'])
    xfs=[]
    for font,fill,border in [(0,0,0),(1,2,0),(2,2,0),(3,3,0),(3,3,1),(2,5,1),(0,4,0)]:
        for percent in (False,True):
            xfs.append(f'<xf numFmtId="{10 if percent else 164}" fontId="{font}" fillId="{fill}" borderId="{border}" xfId="0" applyNumberFormat="1" applyFill="1" applyFont="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>')
    xml=(f'<styleSheet xmlns="{NS}"><numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0;[Red](#,##0);&quot;–&quot;"/></numFmts><fonts count="4">{fonts}</fonts><fills count="6">{fills}</fills><borders count="2"><border/><border><top style="thin"><color rgb="FF92B4BD"/></top><bottom style="double"><color rgb="FF92B4BD"/></bottom></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="{len(xfs)}">{"".join(xfs)}</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    return xml, {i:i+1 if i % 2 == 0 else i for i in range(len(xfs))}


def row_style(index, row):
    label = str(row[0]).strip() if row else ''
    if index == 1: return 2
    if index == 6: return 4
    if index < 6: return 6
    key = re.sub('[^a-z]', '', label.casefold())
    if key in ('grossoperatingprofit','nettoperatingprofit','grossoperatingincomeprofitloss','netresult','nop','gopgol'):
        return 10
    if key.startswith(('total','netrevenue','grossprofit')): return 8
    if label and len(row) == 1: return 6
    return 12 if index % 2 == 0 and label else 0


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
        for col in range(1, count + 1):
            value = row[col-1] if col <= len(row) else None
            style = row_style(index, row)
            if rows.headers[col - 1] == '%':
                style = template_styles()[1][style]
            ref = column_name(col) + str(index)
            if value is None:
                cells.append(f'<c r="{ref}" s="{style}"/>')
            elif isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}" s="{style}" t="n"><v>{value}</v></c>')
            else:
                value = escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value)))
                cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{value}</t></is></c>')
        output.append(f'<row r="{index}" ht="{30 if index == 1 else 42 if index == 6 else 19 if row_style(index,row) in (6,8,10) else 17}" customHeight="1">{"".join(cells)}</row>')
    cols = []
    for col in range(1, count + 1):
        width = 58 if col == 1 else 8 if rows.headers[col-1] == '%' else 19
        cols.append(f'<col min="{col}" max="{col}" width="{width}" customWidth="1"/>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS}"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        f'<dimension ref="A1:{column_name(count)}{len(rows)}"/>'
        '<sheetViews><sheetView showGridLines="0" zoomScale="100" workbookViewId="0">'
        '<pane xSplit="1" ySplit="6" topLeftCell="B7" activePane="bottomRight" state="frozen"/>'
        '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/>'
        f'<cols>{"".join(cols)}</cols><sheetData>{"".join(output)}</sheetData>'
        f'<mergeCells count="4">{"".join(f'<mergeCell ref="A{i}:{column_name(count)}{i}"/>' for i in range(1,5))}</mergeCells>'
        '<printOptions horizontalCentered="1"/>'
        '<pageMargins left="0.25" right="0.25" top="0.35" bottom="0.35" header="0.15" footer="0.15"/>'
        '<pageSetup paperSize="8" orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
        '<headerFooter><oddFooter>&amp;L&amp;A&amp;RPage &amp;P of &amp;N</oddFooter></headerFooter></worksheet>')
