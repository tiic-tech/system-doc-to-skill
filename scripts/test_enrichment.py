"""Incremental evidence recovery; only fictional inputs and actual file behavior."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

import docpack as d
import enrichment as n
from test_v3 import document
from test_evidence import xlsx


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        child = self.root / 'annex.docx'
        document(child, 'Annex-only exception.')
        source = self.root / 'requirements.docx'
        document(source, 'An approval is required.', child.read_bytes())
        workbook = self.root / 'limits.xlsx'
        xlsx(workbook)
        self.pack = self.root / 'package'
        d.build([str(source), str(workbook)], self.pack, 'Fictional document set', renderer='none')

    def tearDown(self):
        self.temp.cleanup()

    def renderer(self, source, destination, executable, timeout=120):
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / (source.stem + '.pdf')
        pdf = d.fitz_module().open()
        pdf.new_page().insert_text((40, 40), 'Derived fictional layout')
        pdf.save(target)
        pdf.close()
        return target

    def run_enrich(self, **kwargs):
        kwargs.setdefault('expected_revision', d.knowledge.project(self.pack)['revision'])
        with patch.object(d.core, 'libreoffice_path', return_value='fixture-renderer'), \
             patch.object(d.core, 'render_office', side_effect=self.renderer):
            return d.enrich(self.pack, **kwargs)

    def commit_text(self):
        k = d.knowledge
        unit = next(u for u in k.project(self.pack)['units'].values()
                    if u['kind'] == 'clause' and u['text'] == 'An approval is required.')
        readable = [u['id'] for u in k.project(self.pack)['units'].values()
                    if u['required'] and not u.get('blocked_reason')]
        result = k.read_units(self.pack, readable)
        payload = {'expected_revision': 0, 'model': 'Fixture reader',
                   'receipt_ids': [result['receipt_id']],
                   'reads': [{'unit_ids': readable, 'stage': 'initial',
                              'status': 'read', 'notes': 'Read complete fixture text/native data'}],
                   'records': [{'kind': 'rule', 'name': 'Approval', 'scope': unit['owner_id'],
                                'review_status': 'unreviewed',
                                'claims': [{'content': unit['text'], 'authority': 'source_requirement',
                                            'evidence': [{'unit_id': unit['id'], 'start': 0,
                                                          'end': len(unit['text']), 'quote': unit['text']}]}]}]}
        committed = k.commit(self.pack, payload)
        deep = k.read_units(self.pack, [unit['id']])
        k.commit(self.pack, {'expected_revision': 1, 'model': 'Fixture reader',
                            'receipt_ids': [deep['receipt_id']], 'reads': [{
                                'unit_id': unit['id'], 'stage': 'deep', 'status': 'deep_read',
                                'notes': 'Fixture clause interpreted with recorded scope'}]})
        return unit, committed['records'][0]['id'], payload['records'][0]

    def test_same_package_preserves_originals_history_and_requeues_new_evidence(self):
        unit, kid, record = self.commit_text()
        original = {ref['path']: d.file_bytes(self.pack / ref['path'])
                    for owner in d.read_json(self.pack / 'manifest.json')['sources'] +
                    d.read_json(self.pack / 'manifest.json')['assets'] for ref in [owner['original']]}
        events = {p.name: p.read_bytes() for p in (self.pack / 'knowledge/events').glob('*.json')}
        result = self.run_enrich()
        self.assertTrue(result['pass'], result)
        self.assertTrue(result['changed'])
        self.assertEqual(result['package'], str(self.pack))
        self.assertEqual(result['revision'], 3)
        self.assertEqual(result['records_needing_revalidation'], 1)
        for name, raw in original.items(): self.assertEqual((self.pack / name).read_bytes(), raw)
        for name, raw in events.items(): self.assertEqual((self.pack / 'knowledge/events' / name).read_bytes(), raw)
        manifest = d.read_json(self.pack / 'manifest.json')
        for source in manifest['sources']:
            if source['kind'] == 'docx': self.assertEqual(len(source['layout']), 1)
        attachment = next(a for a in manifest['assets'] if a['kind'] == 'docx')
        child = next(s for s in manifest['sources'] if s['id'] == attachment['content_source_id'])
        self.assertEqual(child['layout'], attachment['reading_versions'])
        state = d.knowledge.project(self.pack)
        self.assertEqual(state['coverage'][unit['id']]['initial']['status'], 'read')
        self.assertEqual(state['coverage'][unit['id']]['deep']['status'], 'needs_revalidation')
        self.assertTrue(state['records'][kid]['stale_reasons'])
        self.assertTrue(all(state['coverage'][uid]['initial']['status'] == 'unread'
                            for uid,u in state['units'].items() if u['kind'] == 'visual'))
        self.assertTrue((self.pack / result['history'] / 'before/manifest.json').is_file())
        self.assertFalse((self.pack / n.PENDING).exists())
        # Rechecking creates a new explanation version, while preserving the old one.
        receipt = d.knowledge.read_units(self.pack, [unit['id']])
        record.update(id=kid, reason='Rechecked supplemental evidence scope')
        d.knowledge.commit(self.pack, {'expected_revision': 3, 'model': 'Fixture reader',
                                     'receipt_ids': [receipt['receipt_id']], 'records': [record]})
        revised = d.knowledge.project(self.pack)
        self.assertFalse(revised['records'][kid]['stale_reasons'])
        self.assertEqual(len(revised['history'][kid]), 1)

    def test_second_enrichment_is_noop_and_keeps_rendition_bytes(self):
        self.run_enrich()
        before = n.inventory(self.pack)
        with patch.object(d.core, 'libreoffice_path', return_value='fixture-renderer'), \
             patch.object(d.core, 'render_office', side_effect=AssertionError('Must not rerender')):
            result = d.enrich(self.pack, expected_revision=1)
        self.assertFalse(result['changed'], result)
        self.assertEqual(result['revision'], 1)
        self.assertEqual(before, n.inventory(self.pack))

    def test_revision_active_lock_and_contract_checks(self):
        with self.assertRaisesRegex(ValueError, 'requires'): d.enrich(self.pack)
        with self.assertRaisesRegex(ValueError, 'Revision changed'): d.enrich(self.pack, 99)
        with d.knowledge.writer(self.pack):
            with self.assertRaisesRegex(ValueError, 'locked'): d.enrich(self.pack, 0)
        m = d.read_json(self.pack / 'manifest.json')
        m['schema_version'] = 2
        d.write_json(self.pack / 'manifest.json', m)
        with self.assertRaisesRegex(ValueError, 'older package'): d.enrich(self.pack, 0)

    def test_staging_failure_leaves_original_package_unchanged(self):
        before = n.inventory(self.pack)
        def fail(stage, renderer, dpi):
            (stage / 'manifest.json').write_text('{}')
            raise OSError('Simulated candidate failure')
        with patch.object(d, 'supplement', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'candidate failure'): d.enrich(self.pack, 0)
        self.assertEqual(before, n.inventory(self.pack))
        self.assertFalse((self.pack / n.PENDING).exists())

    def interrupt_publication(self):
        original_copy = n.atomic_copy
        publications = []
        def interrupt(source, target):
            target = Path(target)
            relative = target.relative_to(self.pack) if target.is_relative_to(self.pack) else None
            if relative and (self.pack / n.PENDING / 'plan.json').exists() and \
                    relative.parts[0] not in (n.PENDING, 'history'):
                publications.append(str(relative))
                if len(publications) == 2:
                    raise OSError('Simulated interruption after first replacement')
            original_copy(source, target)
        with patch.object(n, 'atomic_copy', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'Simulated interruption'): self.run_enrich()
        self.assertTrue((self.pack / n.PENDING / 'plan.json').exists())

    def test_interruption_blocks_reads_and_writes_then_review_recovers(self):
        self.interrupt_publication()
        with self.assertRaisesRegex(ValueError, 'pending'): d.query(self.pack, 'approval')
        with self.assertRaisesRegex(ValueError, 'pending'): d.verify(self.pack)
        with self.assertRaisesRegex(ValueError, 'pending'): d.knowledge.commit(self.pack, {})
        result = d.knowledge.review(self.pack, recover=True)
        self.assertEqual(result['revision'], 1)
        self.assertTrue(d.verify(self.pack)['pass'])
        self.assertFalse((self.pack / n.PENDING).exists())
        self.assertTrue(d.query(self.pack, 'approval')['total_hits'])

    def test_pending_transaction_survives_directory_move(self):
        self.interrupt_publication()
        moved = self.root / 'moved-package'
        self.pack.rename(moved)
        self.pack = moved
        result = d.enrich(self.pack, recover=True)
        self.assertTrue(result['pass'], result)
        self.assertTrue(result['recovered'])
        self.assertEqual(result['revision'], 1)
        self.assertTrue(d.verify(self.pack)['pass'])

    def test_recovery_rejects_damaged_blob_without_applying_more_files(self):
        self.interrupt_publication()
        plan = d.read_json(self.pack / n.PENDING / 'plan.json')
        blob = self.pack / n.PENDING / 'after' / plan['changes'][-1]['path']
        blob.write_bytes(b'damaged payload')
        manifest = (self.pack / 'manifest.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'blob damaged'): d.enrich(self.pack, recover=True)
        self.assertEqual(manifest, (self.pack / 'manifest.json').read_bytes())
        self.assertTrue((self.pack / n.PENDING).exists())

    def test_tampered_source_is_rejected(self):
        m = d.read_json(self.pack / 'manifest.json')
        (self.pack / m['sources'][0]['original']['path']).write_bytes(b'changed original')
        with self.assertRaisesRegex(ValueError, 'integrity failed'): d.enrich(self.pack, 0)

    def test_renderer_none_does_not_export_and_gaps_remain(self):
        with patch.object(d.core, 'render_office', side_effect=AssertionError('Disabled')):
            result = d.enrich(self.pack, 0, renderer='none')
        self.assertTrue(result['pass'])
        m = d.read_json(self.pack / 'manifest.json')
        self.assertTrue(all(not s['layout'] for s in m['sources'] if s['kind']=='docx'))
        self.assertTrue(d.knowledge.review(self.pack)['gaps'])

    def test_buffered_reader_rejects_generation_change(self):
        @d.core.operation_scope
        def simulated_read(root):
            m = d.read_json(root / 'manifest.json')
            m['title'] += ' updated'
            d.write_json(root / 'manifest.json', m)
            return {'unsupported_mixed_generation': True}
        with self.assertRaisesRegex(ValueError, 'changed during reading'): simulated_read(self.pack)

    def test_embedded_content_missing_in_old_v3_is_expanded_without_manual_extraction(self):
        m = d.read_json(self.pack / 'manifest.json')
        a = next(a for a in m['assets'] if a['kind'] == 'docx')
        child_id = a.pop('content_source_id')
        m['sources'] = [s for s in m['sources'] if s['id'] != child_id]
        d.write_json(self.pack / 'manifest.json', m)
        d.knowledge.initialize(self.pack)
        d.project_entry(self.pack)
        self.assertTrue(d.verify(self.pack)['pass'])
        result = self.run_enrich()
        self.assertTrue(result['pass'], result)
        m = d.read_json(self.pack / 'manifest.json')
        a = next(a for a in m['assets'] if a['kind'] == 'docx')
        child = next(s for s in m['sources'] if s['id'] == a['content_source_id'])
        self.assertEqual(child['original']['sha256'], a['original']['sha256'])
        self.assertTrue(d.query(self.pack, 'Annex-only exception')['total_hits'])


if __name__ == '__main__': unittest.main()
