"""Small numeric XLSX exports using only the Python standard library.

Large import/export jobs remain on EC2. This writer packages already-computed
financial report rows and does not load a worker-only spreadsheet library.
"""
from decimal import Decimal
from io import BytesIO
import re
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def worksheet(rows):
    output = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for column_index, value in enumerate(row, 1):
            if value is None:
                continue
            ref = column_name(column_index) + str(row_index)
            if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}" s="2" t="n"><v>{value}</v></c>')
            else:
                # Inline strings cannot execute formulas from account names.
                text = escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value)))
                style = ' s="1"' if row_index == 2 else ""
                cells.append(f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>')
        output.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    count = max((len(row) for row in rows), default=2)
    columns = "".join(f'<col min="{i}" max="{i}" width="{48 if i == 2 else 24}" customWidth="1"/>' for i in range(1, count+1))
    return (XML + f'<worksheet xmlns="{NS}">' +
        '<sheetViews><sheetView workbookViewId="0"><pane xSplit="2" ySplit="2" topLeftCell="C3" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>' +
        f'<cols>{columns}</cols><sheetData>{"".join(output)}</sheetData>' +
        f'<autoFilter ref="A2:{column_name(count)}{len(rows)}"/></worksheet>')


def build_xlsx(sheets):
    """Sheets are (title, rows); return a workbook with numeric money cells."""
    content = XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +\
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>' +\
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +\
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +\
        "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1)) + '</Types>'
    workbook = XML + f'<workbook xmlns="{NS}" xmlns:r="{DOC_REL}"><sheets>' +\
        "".join(f'<sheet name={quoteattr(title)} sheetId="{i}" r:id="rId{i}"/>' for i,(title,_) in enumerate(sheets,1)) + '</sheets></workbook>'
    relationships = XML + f'<Relationships xmlns="{REL}">' +\
        "".join(f'<Relationship Id="rId{i}" Type="{DOC_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1)) +\
        f'<Relationship Id="styles" Type="{DOC_REL}/styles" Target="styles.xml"/></Relationships>'
    styles = XML + f'<styleSheet xmlns="{NS}">' +\
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00;[Red](#,##0.00)"/></numFmts>' +\
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>' +\
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1E293B"/></patternFill></fill></fills>' +\
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +\
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +\
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>' +\
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content)
        archive.writestr("_rels/.rels", XML + f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{DOC_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/styles.xml", styles)
        for i,(_,rows) in enumerate(sheets,1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", worksheet(rows))
    return output.getvalue()
