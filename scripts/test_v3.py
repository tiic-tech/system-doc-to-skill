"""v3 behavioral regressions: no real project names or expected business answers."""
from pathlib import Path
import copy,json,os,sys,tempfile,unittest,zipfile
from unittest.mock import patch
import docpack as d
import formatting
import xml.etree.ElementTree as ET

W=d.W;R=d.R;O=d.O
def archive(path,parts):
    with zipfile.ZipFile(path,'w') as z:
        for name,data in parts.items():z.writestr(name,data)

def document(path,text,child=None,repeated=False):
    body=f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
    parts={}
    if child:
        obj='<w:p><w:r><w:object><o:OLEObject r:id="attachment" DrawAspect="Icon"/></w:object></w:r></w:p>'
        body+=obj*(2 if repeated else 1)
        parts['word/embeddings/attachment.docx']=child
        parts['word/_rels/document.xml.rels']='<Relationships><Relationship Id="attachment" Target="embeddings/attachment.docx"/></Relationships>'
    parts['word/document.xml']=f'<w:document xmlns:w="{W[1:-1]}" xmlns:r="{R[1:-1]}" xmlns:o="{O[1:-1]}"><w:body>{body}</w:body></w:document>'
    archive(path,parts)

class V3Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def textpack(self):
        src=self.root/'requirements.md';src.write_text('# Rules\nBids need approval.\nFAR applies.\nFarmwork is separate.\n')
        pack=self.root/'pack';d.build([str(src)],pack,'Generic requirements',renderer='none');return pack
    def test_nested_attachment_dedup_parent_and_queue(self):
        leaf=self.root/'leaf.docx';document(leaf,'Unique exception in deepest attachment.')
        child=self.root/'child.docx';document(child,'Nested annex.',leaf.read_bytes())
        main=self.root/'main.docx';document(main,'Main requirement.',child.read_bytes(),True)
        pack=self.root/'pack';report=d.build([str(main)],pack,'Nested documents',renderer='none')
        self.assertTrue(report['pass'],report)
        m=d.read_json(pack/'manifest.json');self.assertEqual(len(m['sources']),3)
        self.assertEqual(len(m['assets']),2)
        for a in m['assets']:
            content=next(s for s in m['sources'] if s['id']==a['content_source_id'])
            self.assertEqual(content['original']['sha256'],a['original']['sha256'])
            self.assertEqual(content['parent_assets'][0]['occurrence_ids'],[o['id'] for o in a['occurrences']])
        units=d.knowledge.project(pack)['units']
        self.assertEqual(sum(u['kind']=='clause' and 'Unique exception' in u['text'] for u in units.values()),1)
        q=d.query(pack,'Main requirement',limit=100,expand='related')
        self.assertTrue(any('Nested annex' in x['text'] and x['related_via'] for x in q['results']))
    def test_style_inheritance_direct_off_hidden_and_unknown(self):
        styles=ET.fromstring(f'<w:styles xmlns:w="{W[1:-1]}"><w:style w:styleId="Base"><w:rPr><w:strike/><w:highlight w:val="yellow"/></w:rPr></w:style><w:style w:styleId="Derived"><w:basedOn w:val="Base"/></w:style></w:styles>')
        node=ET.fromstring(f'<w:p xmlns:w="{W[1:-1]}"><w:pPr><w:pStyle w:val="Derived"/></w:pPr><w:r><w:t>A</w:t></w:r><w:r><w:rPr><w:strike w:val="0"/><w:vanish/></w:rPr><w:t>B</w:t></w:r></w:p>')
        spans,err=formatting.spans_for({'text':'AB'},node,styles,d.paragraph_text)
        self.assertFalse(err);self.assertTrue(spans[0]['format']['strike']);self.assertFalse(spans[1]['format']['strike'])
        self.assertTrue(spans[1]['format']['vanish']);self.assertEqual(spans[0]['format']['highlight'],'yellow')
        node.find(W+'pPr/'+W+'pStyle').set(W+'val','Missing')
        spans,err=formatting.spans_for({'text':'AB'},node,styles,d.paragraph_text)
        self.assertTrue(spans[0]['requires_visual_check'])
    def test_format_read_query_preserve_original_offsets(self):
        src=self.root/'formatted.docx'
        archive(src,{'word/document.xml':f'<w:document xmlns:w="{W[1:-1]}"><w:body><w:p><w:r><w:rPr><w:dstrike/></w:rPr><w:t>Service shall register.</w:t></w:r></w:p></w:body></w:document>'})
        pack=self.root/'pack';d.build([str(src)],pack,'Formatting',renderer='none')
        unit=next(u for u in d.knowledge.project(pack)['units'].values() if u['kind']=='clause')
        r=d.knowledge.read_units(pack,[unit['id']]);self.assertEqual(r['items'][0]['text'],'Service shall register.')
        self.assertTrue(r['items'][0]['interpretation_annotations'])
        q=d.query(pack,'register');self.assertTrue(any(x.get('interpretation_annotations') for x in q['results']))
        md=next((pack/'text').glob('*.md')).read_text();self.assertIn('不属于原文',md)
        d.knowledge.validate_reference({'unit_id':unit['id'],'quote':unit['text']},d.knowledge.project(pack))
    def test_checkpoint_same_size_and_mtime_journal_tamper_rejected(self):
        pack=self.textpack();k=d.knowledge;u=next(u for u in k.project(pack)['units'].values() if u['required'])
        r=k.read_units(pack,[u['id']]);k.commit(pack,{'expected_revision':0,'model':'Fixture model','receipt_ids':[r['receipt_id']],
            'reads':[{'unit_id':u['id'],'stage':'initial','status':'read','notes':'Fixture note'}]})
        d.query(pack,'FAR')
        event=next((pack/'knowledge/events').glob('*.json'));stat=event.stat()
        event.write_bytes(event.read_bytes().replace(b'Fixture note',b'Changed note'))
        os.utime(event,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        with self.assertRaises(ValueError):d.query(pack,'FAR')
    def test_corrupt_checkpoint_falls_back_to_journal(self):
        pack=self.textpack();before=d.knowledge.project(pack)
        (pack/'knowledge/checkpoint.json').write_text('{broken')
        self.assertEqual(d.knowledge.project(pack),before)
        d.knowledge.review(pack,recover=True);self.assertTrue(d.verify(pack)['pass'])
    def test_view_payload_stored_once_and_only_related_ids(self):
        pack=self.textpack();image=self.root/'image.png'
        pix=d.fitz_module().Pixmap(d.fitz_module().csRGB,d.fitz_module().IRect(0,0,12,12));pix.clear_with(200);image.write_bytes(pix.tobytes('png'))
        other=self.root/'images';d.build([str(image)],other,'Image',renderer='none')
        k=d.knowledge;state=k.project(other);u=next(u for u in state['units'].values() if u['kind']=='visual');r=k.read_units(other,[u['id']])
        views=[{'rendition_id':u['rendition']['id'],'sha256':u['rendition']['sha256'],'tool':'fixture attestation only','observation':'Synthetic grey square; test is not actual model vision.'}]
        k.commit(other,{'expected_revision':0,'model':'Fixture','receipt_ids':[r['receipt_id']],'visual_reads':views,
            'reads':[{'unit_id':u['id'],'stage':'initial','status':'read','notes':'Protocol fixture'}]})
        event=d.read_json(next((other/'knowledge/events').glob('*.json')))
        self.assertEqual(event['visual_reads'],views);self.assertNotIn('visual_reads',event['reads'][0]);self.assertEqual(len(event['reads'][0]['visual_read_ids']),1)
        projected=k.project(other);self.assertEqual(len(projected['visual_attestations']),1)
    def test_business_unknowns_separate_from_capture_gaps(self):
        pack=self.textpack();k=d.knowledge;u=next(u for u in k.project(pack)['units'].values() if u['required'])
        k.commit(pack,{'expected_revision':0,'model':'Fixture','records':[{'id':'Kunknown','kind':'issue','name':'Unspecified role','scope':'Selected text',
            'claims':[{'content':'Role not resolved','authority':'interpretation','evidence':[{'unit_id':u['id'],'quote':u['text']}]}],'unknowns':['Which role?']}]})
        review=k.review(pack);self.assertEqual(review['business_unresolved'][0]['knowledge_id'],'Kunknown');self.assertFalse(review['needs_revalidation_records'])
    def test_related_results_paginate_and_respect_filters(self):
        pack=self.textpack();k=d.knowledge;s=k.project(pack);units=[u for u in s['units'].values() if u['required']]
        def record(id,u,name,relations=[]):return {'id':id,'kind':'rule','name':name,'scope':'Selected text','relations':relations,
            'claims':[{'content':name,'authority':'interpretation','evidence':[{'unit_id':u['id'],'quote':u['text']}]}]}
        k.commit(pack,{'expected_revision':0,'model':'Fixture','records':[record('Kalpha',units[0],'Extension', [{'kind':'related_notice','target_id':'Kbeta'}]),record('Kbeta',units[-1],'Submission retained')]})
        q=d.query(pack,'Extension',expand='related',limit=1);ids=[]
        while True:
            ids.extend(x['id'] for x in q['results'])
            if q['next_offset'] is None:break
            q=d.query(pack,'Extension',expand='related',limit=1,offset=q['next_offset'])
        self.assertIn('Kbeta',ids);self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(d.query(pack,'Extension',source='missing',expand='related')['total_hits'],0)
    def test_operation_scope_symlink_escape_checked_each_call(self):
        outside=self.root/'outside';outside.mkdir();(outside/'secret').write_text('outside')
        pack=self.root/'pack';pack.mkdir();(pack/'link').symlink_to(outside,target_is_directory=True)
        @d.core.operation_scope
        def locate():return d.safe_path(pack,'link/secret')
        with self.assertRaises(ValueError):locate()
        (pack/'link').unlink();(pack/'link').mkdir();(pack/'link/secret').write_text('inside')
        self.assertEqual(locate().read_text(),'inside')
        (pack/'link/secret').unlink();(pack/'link').rmdir();(pack/'link').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):locate()
    def test_pdf_crop_is_optional_and_parent_dependency_checked(self):
        source=self.root/'diagram.pdf';fitz=d.fitz_module();doc=fitz.open();p=doc.new_page();p.insert_text((72,72),'A flow diagram');doc.save(source);doc.close()
        pack=self.root/'pack';d.build([str(source)],pack,'PDF diagram',renderer='none')
        before=d.knowledge.summarize(d.knowledge.project(pack))['stages']['initial']['total_required_units']
        m=d.read_json(pack/'manifest.json');owner=m['sources'][0];r=owner['layout'][0]
        d.crop_region(pack,owner['id'],r['id'],[0,0,200,200],288)
        after=d.knowledge.summarize(d.knowledge.project(pack))['stages']['initial']['total_required_units']
        self.assertEqual(before,after)
        m=d.read_json(pack/'manifest.json');m['sources'][0]['layout'][-1]['parent_sha256']='changed';d.write_json(pack/'manifest.json',m)
        self.assertFalse(d.verify(pack)['pass'])
    def test_relative_path_recovery_preserves_commits(self):
        pack=self.textpack();k=d.knowledge;u=next(u for u in k.project(pack)['units'].values() if u['required'])
        r=k.read_units(pack,[u['id']]);k.commit(pack,{'expected_revision':0,'model':'Fixture','receipt_ids':[r['receipt_id']],
            'reads':[{'unit_id':u['id'],'stage':'initial','status':'read','notes':'Actually inspected fixture'}]})
        for path in ('knowledge/index.json','knowledge/checkpoint.json','knowledge/coverage.json'):(pack/path).unlink()
        old=os.getcwd()
        try:
            os.chdir(self.root);self.assertEqual(k.review(Path('pack'),recover=True)['revision'],1)
        finally:os.chdir(old)
    def test_attachment_visual_depends_on_parent_context(self):
        child=self.root/'child.docx';document(child,'Annex rule.')
        main=self.root/'main.docx';document(main,'Main scope.',child.read_bytes())
        pack=self.root/'pack';d.build([str(main)],pack,'Attachments',renderer='none')
        m=d.read_json(pack/'manifest.json');source=next(s for s in m['sources'] if s.get('parent_assets'))
        source['layout']=[{'id':'Rfixture','role':'page_content','method':'fixture','sha256':'fixture','path':'unused.png'}]
        units,_=d.knowledge.create_units(pack,m)
        visual=next(u for u in units if u['kind']=='visual')
        self.assertEqual(set(visual['source_ids']),{s['id'] for s in m['sources']})
    def test_export_failure_has_exit_diagnostic_and_preserves_input(self):
        source=self.root/'file.docx';source.write_bytes(b'original fixture')
        completed=type('Result',(),{'returncode':9,'stdout':b'','stderr':b'filter unavailable'})()
        with patch.object(d.core.subprocess,'run',return_value=completed):
            with self.assertRaises(RuntimeError):d.core.render_office(source,self.root/'render','libreoffice')
        diagnostic=d.read_json(self.root/'render/export-diagnostic.json');self.assertEqual(diagnostic['returncode'],9)
        self.assertIn('filter unavailable',diagnostic['stderr']);self.assertEqual(source.read_bytes(),b'original fixture')

if __name__=='__main__':unittest.main()
