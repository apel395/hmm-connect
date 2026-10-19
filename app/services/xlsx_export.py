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


def worksheet(rows, first_column_width=None):
    if hasattr(rows, 'template_profile'):
        from app.services.profit_loss_template_xml import worksheet as template_worksheet
        return template_worksheet(rows)
    if hasattr(rows, 'styles'):
        return statement_worksheet(rows)
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
    columns = "".join(f'<col min="{i}" max="{i}" width="{(first_column_width if i == 1 else 26) if first_column_width else (48 if i == 2 else 24)}" customWidth="1"/>' for i in range(1, count+1))
    return (XML + f'<worksheet xmlns="{NS}">' +
        '<sheetViews><sheetView workbookViewId="0"><pane xSplit="2" ySplit="2" topLeftCell="C3" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>' +
        f'<cols>{columns}</cols><sheetData>{"".join(output)}</sheetData>' +
        f'<autoFilter ref="A2:{column_name(count)}{len(rows)}"/></worksheet>')


def statement_worksheet(rows):
    """Template P&L presentation without changing other export layouts."""
    output = []
    percentages = {3, 5, 7, 9}
    for index, row in enumerate(rows, 1):
        kind = rows.styles.get(index)
        cells = []
        for col in range(1, 16):
            value = row[col-1] if col <= len(row) else None
            numeric = isinstance(value, (Decimal, int, float)) and not isinstance(value, bool)
            style = {'header': 12, 'title': 11, 'section': 3, 'total': 4, 'grand': 5}.get(kind, 0)
            if numeric:
                style = 6 if index in getattr(rows, 'percent_rows', ()) else (10 if col in percentages else 9) if kind == 'grand' else (8 if col in percentages else 7) if kind == 'total' else 6 if col in percentages else 2
            ref = f'{column_name(col)}{index}'
            if value is None:
                cells.append(f'<c r="{ref}" s="{style}"/>')
            elif numeric:
                cells.append(f'<c r="{ref}" s="{style}" t="n"><v>{value}</v></c>')
            else:
                value = escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value)))
                cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{value}</t></is></c>')
        height = 34 if kind == 'header' else 20 if kind in ('title', 'grand') else 17
        output.append(f'<row r="{index}" ht="{height}" customHeight="1">{"".join(cells)}</row>')
    columns = ''.join(f'<col min="{i}" max="{i}" width="{54 if i == 1 else 9 if i in percentages else 19}" customWidth="1"/>' for i in range(1, 16))
    return (XML + f'<worksheet xmlns="{NS}"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><dimension ref="A1:O{len(rows)}"/>'
            '<sheetViews><sheetView showGridLines="0" zoomScale="85" workbookViewId="0">'
            '<pane xSplit="1" ySplit="6" topLeftCell="B7" activePane="bottomRight" state="frozen"/>'
            '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="17"/>'
            f'<cols>{columns}</cols><sheetData>{"".join(output)}</sheetData>'
            '<mergeCells count="4"><mergeCell ref="A1:O1"/><mergeCell ref="A2:O2"/>'
            '<mergeCell ref="A3:O3"/><mergeCell ref="A4:O4"/></mergeCells>'
            '<printOptions horizontalCentered="1"/>'
            '<pageMargins left="0.25" right="0.25" top="0.35" bottom="0.35" header="0.15" footer="0.15"/>'
            '<pageSetup paperSize="8" orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
            '<headerFooter><oddFooter>&amp;L&amp;A&amp;RPage &amp;P of &amp;N</oddFooter></headerFooter>'
            '</worksheet>')


def build_xlsx(sheets, *, first_column_width=None):
    """Sheets are (title, rows); return a workbook with numeric money cells."""
    content = XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +\
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>' +\
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +\
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +\
        "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1)) + '</Types>'
    workbook = XML + f'<workbook xmlns="{NS}" xmlns:r="{DOC_REL}"><sheets>' +\
        "".join(f'<sheet name={quoteattr(title)} sheetId="{i}" r:id="rId{i}"/>' for i,(title,_) in enumerate(sheets,1)) + '</sheets>' +\
        '<definedNames>' + ''.join(f'<definedName name="_xlnm.Print_Titles" localSheetId="{i}">{escape(chr(39)+title.replace(chr(39),chr(39)*2)+chr(39))}!$1:$6</definedName>' for i,(title,rows) in enumerate(sheets) if hasattr(rows,'styles') or hasattr(rows,'template_profile')) + '</definedNames><calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/></workbook>'
    relationships = XML + f'<Relationships xmlns="{REL}">' +\
        "".join(f'<Relationship Id="rId{i}" Type="{DOC_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1)) +\
        f'<Relationship Id="styles" Type="{DOC_REL}/styles" Target="styles.xml"/></Relationships>'
    styles = XML + f'<styleSheet xmlns="{NS}">' +\
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00;[Red](#,##0.00)"/></numFmts>' +\
        '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>' +\
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1E293B"/></patternFill></fill></fills>' +\
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +\
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +\
        '<cellXfs count="13"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>' +\
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>' +\
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>' +\
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>' +\
        '<xf numFmtId="10" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>' +\
        '<xf numFmtId="164" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyNumberFormat="1"/>' +\
        '<xf numFmtId="10" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyNumberFormat="1"/>' +\
        '<xf numFmtId="164" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyNumberFormat="1"/>' +\
        '<xf numFmtId="10" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyNumberFormat="1"/>' +\
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>' +\
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf></cellXfs>' +\
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
    template_export = bool(sheets) and all(hasattr(rows, 'template_profile') for _, rows in sheets)
    if template_export:
        from app.services.profit_loss_template import ROOT
        from app.services.profit_loss_template_xml import template_styles
        styles = template_styles()[0]
        content = content.replace('</Types>', '<Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/></Types>')
        relationships = relationships.replace('</Relationships>', f'<Relationship Id="theme" Type="{DOC_REL}/theme" Target="theme/theme1.xml"/></Relationships>')
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content)
        archive.writestr("_rels/.rels", XML + f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{DOC_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/styles.xml", styles)
        if template_export:
            archive.writestr("xl/theme/theme1.xml", (ROOT / "pl_theme.xml").read_bytes())
        for i,(_,rows) in enumerate(sheets,1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", worksheet(rows,first_column_width=first_column_width))
    return output.getvalue()
