"""Behavioral tests with synthetic, project-neutral sources; stdlib unittest."""
from pathlib import Path
import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile

SCRIPT=Path(__file__).with_name('docpack.py')
spec=importlib.util.spec_from_file_location('docpack',SCRIPT)
d=importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

W=d.W[1:-1]; R=d.R[1:-1]; O=d.O[1:-1]


def archive(path,parts):
    with zipfile.ZipFile(path,'w') as z:
        for name,data in parts.items(): z.writestr(name,data)


def xlsx(path):
    archive(path,{
        'xl/workbook.xml':f'<workbook xmlns="{d.S[1:-1]}" xmlns:r="{R}"><sheets><sheet name="Matrix" sheetId="1" r:id="rId1" state="hidden"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':'<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml':f'<worksheet xmlns="{d.S[1:-1]}"><cols><col min="2" max="2" hidden="1"/></cols><sheetData><row r="1" hidden="1"><c r="A1" t="inlineStr"><is><t>Approval condition</t></is></c><c r="B1"><f>2*3</f></c></row></sheetData><mergeCells><mergeCell ref="A2:B2"/></mergeCells></worksheet>'})


def png():
    f=d.fitz_module()
    pix=f.Pixmap(f.csRGB,f.IRect(0,0,40,30))
    pix.clear_with(220)
    return pix.tobytes('png')


def docx(path,word='Generic technical workflow'):
    img=png()
    tmp=path.parent/'internal.xlsx';xlsx(tmp)
    body=f'''<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>{word}</w:t></w:r></w:p>
    <w:p><w:r><w:t>Before object</w:t></w:r><w:commentRangeStart w:id="1"/><w:ins w:id="2"><w:r><w:t>Inserted condition</w:t></w:r></w:ins><w:del w:id="3"><w:r><w:delText>Deleted condition</w:delText></w:r></w:del></w:p>
    <w:p><w:r><w:object><v:shape id="shape1"><v:imagedata r:id="icon"/></v:shape><o:OLEObject r:id="object" ShapeID="shape1" DrawAspect="Icon"/></w:object></w:r></w:p>
    <w:p><w:r><a:blip r:embed="image1"/></w:r></w:p><w:p><w:r><a:blip r:embed="image2"/></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Outer cell</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Inner cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:tc></w:tr></w:tbl>'''
    archive(path,{
        'word/document.xml':f'<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:o="{O}" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><w:body>{body}</w:body></w:document>',
        'word/styles.xml':f'<w:styles xmlns:w="{W}"><w:style w:styleId="Heading1"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style></w:styles>',
        'word/_rels/document.xml.rels':'''<Relationships><Relationship Id="icon" Type="image" Target="media/icon.emf"/><Relationship Id="object" Type="oleObject" Target="embeddings/object.xlsx"/><Relationship Id="image1" Type="image" Target="media/a.png"/><Relationship Id="image2" Type="image" Target="media/b.png"/></Relationships>''',
        'word/media/icon.emf':b'opaque icon fixture', 'word/media/a.png':img,'word/media/b.png':img,
        'word/embeddings/object.xlsx':tmp.read_bytes(),
        'word/comments.xml':f'<w:comments xmlns:w="{W}"><w:comment w:id="1"><w:p><w:r><w:t>Confirm with owner</w:t></w:r></w:p></w:comment></w:comments>'})
    tmp.unlink()


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def make(self,name='complex source with spaces.docx'):
        src=self.root/name;docx(src)
        pack=self.root/'pack'
        report=d.build([str(src)],pack,'Generic: technical [material]',renderer='none')
        self.assertTrue(report['pass'],report)
        return src,pack,d.read_json(pack/'manifest.json')

    def test_native_coverage_dedup_location_and_comments(self):
        src,pack,m=self.make()
        s=m['sources'][0]
        self.assertEqual(s['inventory']['media_parts'],3)
        self.assertEqual(s['inventory']['embedded_xlsx'],1)
        self.assertEqual(s['inventory']['icon_embedded_objects'],1)
        images=[a for a in m['assets'] if a['kind']=='image']
        self.assertEqual(len(images),1)
        self.assertEqual(len(images[0]['origins']),2)
        self.assertEqual(len(images[0]['occurrences']),2)
        icon=next(a for a in m['assets'] if a['kind']=='emf')
        self.assertEqual(icon['visual_status'],'icon_only')
        self.assertFalse(icon['reading_versions'])
        structure=d.read_json(pack/s['structure']['path'])
        self.assertEqual(len(structure['comments']),1)
        self.assertEqual(structure['comments'][0]['anchors'],['P0002'])
        self.assertEqual(len(structure['revisions']),1)
        self.assertEqual(s['inventory']['tables'],2)
        self.assertEqual(s['inventory']['physical_cells'],2)
        self.assertEqual((pack/s['reading']['path']).read_text().count('Inner cell'),1)

    def test_hidden_cells_formulas_and_missing_cache(self):
        _,pack,m=self.make()
        asset=next(a for a in m['assets'] if a['kind']=='xlsx')
        data=d.read_json(pack/asset['auxiliary']['path'])
        sheet=data['sheets'][0]
        self.assertEqual(sheet['state'],'hidden')
        self.assertEqual(sheet['hidden_rows'],['1'])
        self.assertEqual(sheet['cells'][1]['formula'],'2*3')
        self.assertIsNone(sheet['cells'][1]['value'])
        self.assertFalse(sheet['cells'][1]['cached_result_present'])

    def test_relocation_and_tamper_detection(self):
        _,pack,m=self.make()
        move=self.root/'moved';shutil.copytree(pack,move)
        self.assertTrue(d.verify(move)['pass'])
        original=move/m['assets'][0]['original']['path'];original.write_bytes(b'tampered')
        self.assertFalse(d.verify(move)['pass'])

    def test_plaintext_markdown_csv_and_unknown_formats(self):
        directory=self.root/'selected';directory.mkdir()
        (directory/'plain.txt').write_text('技术接口说明\nTimeout is unknown',encoding='utf-8')
        (directory/'design.md').write_text('# Design\n```text\n# not heading\n```\n![Topology](topology.png)',encoding='utf-8')
        (directory/'table.csv').write_text('Field,Required\nCode,Yes\n',encoding='utf-8')
        (directory/'unsupported.xyz').write_bytes(b'opaque source')
        (directory/'topology.png').write_bytes(png())
        pack=self.root/'mixed';d.build([str(directory)],pack,'General technical',doctype='technical')
        m=d.read_json(pack/'manifest.json')
        self.assertEqual(len(m['sources']),5)
        self.assertTrue(d.verify(pack)['pass'])
        self.assertGreater(d.query(pack,'Timeout')['total_hits'],0)
        md=next(s for s in m['sources'] if s['kind']=='markdown')
        struct=d.read_json(pack/md['structure']['path'])
        self.assertIsNone(struct['paragraphs'][2]['heading_level'])
        self.assertEqual(struct['visual_links'][0]['target'],'topology.png')
        self.assertEqual(struct['visual_links'][0]['status'],'resolved_to_selected_input')
        with self.assertRaises(ValueError):d.build([str(directory)],directory/'nested','Bad')

    def test_invalid_text_encoding_is_explicit(self):
        p=self.root/'text.txt';p.write_bytes(b'\xff\x10garbled')
        pack=self.root/'text';d.build([str(p)],pack,'Text')
        m=d.read_json(pack/'manifest.json')
        self.assertEqual(m['sources'][0]['status'],'partial')
        self.assertIsNone(m['sources'][0]['reading'])

    def test_scanned_pdf_vector_page_and_crop(self):
        fitz=d.fitz_module()
        p=self.root/'vector and scan.pdf';pdf=fitz.open()
        page=pdf.new_page(width=300,height=200)
        page.insert_text((20,30),'Generic architecture diagram')
        page.draw_rect(fitz.Rect(20,40,100,100),color=(1,0,0),fill=(1,0,0))
        pdf.new_page(width=200,height=200)
        pdf.save(p);pdf.close()
        pack=self.root/'pdf';d.build([str(p)],pack,'PDF')
        m=d.read_json(pack/'manifest.json');s=m['sources'][0]
        self.assertEqual(s['inventory']['pdf_pages'],2)
        self.assertEqual(s['inventory']['pages_without_extracted_text'],1)
        self.assertEqual(len(s['layout']),2)
        r=s['layout'][0]
        crop=d.crop_region(pack,s['id'],r['id'],[40,80,200,200])
        self.assertEqual(crop['parent_rendition_id'],r['id'])
        self.assertTrue(Path(crop['absolute_path']).is_file())
        self.assertTrue(d.verify(pack)['pass'])

    def test_interpretation_update_and_context_invalidation(self):
        src,pack,m=self.make()
        s=m['sources'][0];a=next(a for a in m['assets'] if a['kind']=='image');r=a['reading_versions'][0]
        obj={'question':'What is shown?','model':'fixture','observations':['Observed material'],
             'interpretation':'Not a semantic benchmark','unknowns':[],
             'dependencies':[{'id':s['id'],'sha256':s['original']['sha256']},{'id':a['id'],'sha256':a['original']['sha256']},{'id':r['id'],'sha256':r['sha256']}],
             'visual_reads':[{'rendition_id':r['id'],'sha256':r['sha256'],'tool':'synthetic fixture; no model claim'}],
             'review_status':'unreviewed'}
        f=self.root/'record.json';d.write_json(f,obj);d.record_interpretation(pack,f)
        self.assertTrue(d.verify(pack)['pass'])
        docx(src,word='Changed context')
        new=self.root/'updated';d.build([str(src)],new,'New context',previous=str(pack))
        nm=d.read_json(new/'manifest.json');note=d.read_json(new/nm['interpretations'][0]['path'])
        self.assertEqual(note['review_status'],'needs_revalidation')
        self.assertTrue(note['stale_reasons'])
        self.assertTrue(d.verify(new)['pass'])
        self.assertEqual(len(d.read_json(pack/'manifest.json')['interpretations']),1)

    def test_crop_outside_bounds_and_path_escape(self):
        _,pack,m=self.make()
        a=next(a for a in m['assets'] if a['kind']=='image');r=a['reading_versions'][0]
        with self.assertRaises(ValueError):d.crop_region(pack,a['id'],r['id'],[-1,0,10,10])
        with self.assertRaises(ValueError):d.safe_path(pack,'../outside')
        with self.assertRaises(ValueError):d.safe_path(pack,'/absolute')

    def test_unmodified_update_retains_valid_cache(self):
        src,pack,m=self.make()
        s=m['sources'][0]
        obj={'question':'Text scope','model':'fixture','observations':[],'interpretation':'draft',
             'unknowns':['unread images'],'dependencies':[{'id':s['id'],'sha256':s['original']['sha256']}],
             'visual_reads':[],'review_status':'unreviewed'}
        f=self.root/'record.json';d.write_json(f,obj);d.record_interpretation(pack,f)
        new=self.root/'same';d.build([str(src)],new,'Same',previous=str(pack))
        nm=d.read_json(new/'manifest.json');note=d.read_json(new/nm['interpretations'][0]['path'])
        self.assertEqual(note['review_status'],'unreviewed')
        self.assertFalse(note['stale_reasons'])

    def test_hidden_cell_derived_view(self):
        _,pack,m=self.make()
        a=next(a for a in m['assets'] if a['kind']=='xlsx')
        views=d.cell_view(pack,a['id'],'Matrix',['A1','B1'])
        self.assertTrue(views)
        updated=d.read_json(pack/'manifest.json')
        asset=next(x for x in updated['assets'] if x['id']==a['id'])
        self.assertEqual(asset['reading_versions'][0]['role'],'structured_cell_view')
        self.assertEqual(asset['reading_versions'][0]['native_cells']['addresses'],['A1','B1'])
        self.assertTrue(d.verify(pack)['pass'])

    def test_standalone_visio_geometry_remains_uninterpreted(self):
        p=self.root/'network.vsdx'
        archive(p,{'visio/pages/page1.xml':f'<PageContents xmlns="{d.V[1:-1]}"><Shapes><Shape ID="1"><Text>Service A</Text></Shape><Shape ID="2"><Text>Service B</Text></Shape></Shapes><Connects><Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/><Connect FromSheet="3" FromCell="EndX" ToSheet="2"/></Connects></PageContents>'})
        pack=self.root/'visio';d.build([str(p)],pack,'Technical topology')
        m=d.read_json(pack/'manifest.json');a=m['assets'][0]
        data=d.read_json(pack/a['auxiliary']['path'])
        self.assertEqual(len(data['pages'][0]['connections']),2)
        self.assertEqual(a['visual_status'],'pending')
        self.assertNotIn('business_direction',data['pages'][0]['connections'][0])
        self.assertTrue(d.verify(pack)['pass'])

    def test_unicode_units_in_cell_evidence(self):
        _,pack,m=self.make()
        a=next(a for a in m['assets'] if a['kind']=='xlsx')
        aux=d.read_json(pack/a['auxiliary']['path'])
        aux['sheets'][0]['cells'][0]['value']='技术说明: AED/m²/yr × 20% — no assumption'
        d.write_json(pack/a['auxiliary']['path'],aux)
        payload=(pack/a['auxiliary']['path']).read_bytes()
        a['auxiliary']['sha256']=d.digest(payload);a['auxiliary']['bytes']=len(payload)
        d.write_json(pack/'manifest.json',m)
        d.cell_view(pack,a['id'],'Matrix',['A1'])
        m=d.read_json(pack/'manifest.json');a=next(x for x in m['assets'] if x['id']==a['id'])
        with d.fitz_module().open(pack/a['auxiliary_views'][0]['path']) as doc:
            text=''.join(p.get_text() for p in doc)
        self.assertIn('m²',text)
        self.assertIn('技术说明',text)
        self.assertTrue(d.verify(pack)['pass'])

    def test_source_name_parentheses_and_no_overwrite(self):
        p=self.root/'unknown (draft).xyz';p.write_bytes(b'original')
        pack=self.root/'pack';d.build([str(p)],pack,'Doc: [draft]')
        self.assertTrue(d.verify(pack)['pass'])
        with self.assertRaises(ValueError):d.build([str(p)],pack,'Repeated')

    def test_stale_rendition_detected_without_source_change(self):
        _,pack,m=self.make()
        s=m['sources'][0];a=next(a for a in m['assets'] if a['kind']=='image');r=a['reading_versions'][0]
        note={'dependencies':[{'id':s['id'],'sha256':s['original']['sha256']},{'id':r['id'],'sha256':r['sha256']}]}
        self.assertFalse(d.freshness(m,note))
        a['reading_versions'][0]['sha256']='0'*64
        self.assertTrue(d.freshness(m,note))

    def test_peripheral_context_does_not_relabel_main_body(self):
        path = self.root / "peripheral.docx"
        docx(path)
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("word/header1.xml", f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>Controlled header</w:t></w:r></w:p></w:hdr>')
        pack = self.root / "peripheral"
        d.build([str(path)], pack, "Peripheral context")
        source = d.read_json(pack / "manifest.json")["sources"][0]
        reading = (pack / source["reading"]["path"]).read_text()
        self.assertNotIn("## word/header1.xml", reading)
        self.assertLess(reading.index("Generic technical workflow"), reading.index("页眉、页脚与注释正文"))
        structure = d.read_json(pack / source["structure"]["path"])
        self.assertTrue(any(p["part"] == "word/header1.xml" and p["text"] == "Controlled header" for p in structure["paragraphs"]))


if __name__=='__main__': unittest.main(verbosity=2)
