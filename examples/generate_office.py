#!/usr/bin/env python3
"""Generate fictional OOXML fixtures using only the Python standard library."""
from pathlib import Path
import argparse
import io
import zipfile
from xml.sax.saxutils import escape

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
O = 'urn:schemas-microsoft-com:office:office'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def archive(parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in sorted(parts.items()):
            member = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(member, content)
    return stream.getvalue()


def para(text, properties=''):
    return '<w:p>' + properties + '<w:r><w:t xml:space="preserve">' + escape(text) + '</w:t></w:r></w:p>'


def word(body, extra=None, relations=''):
    defaults = '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
    if extra:
        defaults += '<Default Extension="docx" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"/><Default Extension="xlsx" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>'
    parts = {
        '[Content_Types].xml': f'<Types xmlns="{CT}">{defaults}<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
        '_rels/.rels': f'<Relationships xmlns="{P}"><Relationship Id="main" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/document.xml': f'<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:o="{O}"><w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>',
        'word/styles.xml': f'<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Review"><w:name w:val="Review"/><w:basedOn w:val="Normal"/><w:rPr><w:strike/><w:highlight w:val="yellow"/></w:rPr></w:style></w:styles>',
        'word/_rels/document.xml.rels': f'<Relationships xmlns="{P}"><Relationship Id="styles" Type="{R}/styles" Target="styles.xml"/>{relations}</Relationships>',
    }
    if extra:
        parts.update(extra)
    return archive(parts)


def workbook():
    return archive({
        '[Content_Types].xml': f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels': f'<Relationships xmlns="{P}"><Relationship Id="main" Type="{R}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Synthetic approvals" sheetId="1" r:id="sheet"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{P}"><Relationship Id="sheet" Type="{R}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{S}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Role</t></is></c><c r="B1" t="inlineStr"><is><t>Count</t></is></c></row><row r="2" hidden="1"><c r="A2" t="inlineStr"><is><t>Two different Reviewers</t></is></c><c r="B2"><v>2</v></c><c r="C2"><f>2*3</f></c></row></sheetData></worksheet>',
    })


def generate(destination):
    destination.mkdir(parents=True, exist_ok=False)
    child = word(para('Synthetic annex: changing a template affects future requests only.') + para('Existing submissions are retained; price editing is not defined.'))
    nested = '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="2400"/></w:tblGrid><w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>Do not trim requestId without a defined normalization rule.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    table = '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="2400"/><w:gridCol w:w="2400"/></w:tblGrid><w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>' + para('Merged field: requestId') + '</w:tc></w:tr><w:tr><w:tc><w:tcPr/>' + para('Nested rule') + '</w:tc><w:tc><w:tcPr/>' + nested + para('Read nested table with parent context.') + '</w:tc></w:tr></w:tbl>'
    objects = ''
    for rel in ['annex', 'annex', 'matrix']:
        objects += para('Synthetic attachment: ' + rel) + f'<w:p><w:r><w:object><o:OLEObject Type="Embed" DrawAspect="Icon" ProgID="{"Word.Document.12" if rel == "annex" else "Excel.Sheet.12"}" r:id="{rel}"/></w:object></w:r></w:p>'
    body = para('Synthetic requirements: fictional data only.') + para('Amount >= 1200 test units requires two different Reviewers.')
    body += para('Proposed automatic registration; business status is unresolved.', '<w:pPr><w:pStyle w:val="Review"/></w:pPr>')
    body += '<w:p><w:pPr><w:pStyle w:val="Review"/></w:pPr><w:r><w:rPr><w:strike w:val="0"/></w:rPr><w:t>Explicit strike off; do not infer approval.</w:t></w:r></w:p>'
    body += '<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>Hidden synthetic condition: emergency requests cannot be withdrawn.</w:t></w:r></w:p>'
    body += table + objects
    relations = f'<Relationship Id="annex" Type="{R}/oleObject" Target="embeddings/annex.docx"/><Relationship Id="matrix" Type="{R}/oleObject" Target="embeddings/matrix.xlsx"/>'
    original = word(body, {'word/embeddings/annex.docx': child, 'word/embeddings/matrix.xlsx': workbook()}, relations)
    (destination / 'requirements.docx').write_bytes(original)
    (destination / 'README.txt').write_text('Fictional test inputs only. Select requirements.docx explicitly; its attachments are embedded. No author names, project identifiers or original customer materials are included.\n', encoding='utf-8')
    return destination / 'requirements.docx'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(generate(parser.parse_args().output))
