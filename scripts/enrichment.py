"""Same-package evidence enrichment with a durable, recoverable file transaction."""
from pathlib import Path
import os
import shutil
import tempfile
import uuid

import evidence as e
import learning as k

PENDING = '.evidence-update'
PROJECTIONS = {'knowledge/checkpoint.json', 'knowledge/index.json',
               'knowledge/coverage.json', 'verification.json'}


def inventory(root):
    """Content hashes, not timestamps; disposable runtime state is excluded."""
    result = {}
    for path in Path(root).rglob('*'):
        relative = path.relative_to(root).as_posix()
        parts = Path(relative).parts
        if any(p in {PENDING, '.knowledge-write-lock', '__pycache__', '.git'} or
               p.startswith('.evidence-update-done-') for p in parts):
            continue
        if relative.startswith('knowledge/receipts/') or relative in PROJECTIONS:
            continue
        if path.is_symlink():
            raise ValueError('Enrichment requires ordinary package files; symlink: ' + relative)
        if path.is_file():
            result[relative] = e.digest(e.file_bytes(path))
    return result


def atomic_copy(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.enrich-copy-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(e.file_bytes(source))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def preserve_existing(old, stage):
    manifest = e.read_json(old / 'manifest.json')
    immutable = [x['original'] for x in manifest['sources'] + manifest['assets']]
    immutable += [r for x in manifest['sources'] + manifest['assets']
                  for r in x.get('layout', x.get('reading_versions', []))]
    for ref in immutable:
        if e.digest(e.file_bytes(e.safe_path(stage, ref['path']))) != ref['sha256']:
            raise ValueError('Existing original/rendition would change: ' + ref['path'])
    for event in (old / 'knowledge/events').glob('*.json'):
        if event.read_bytes() != (stage / 'knowledge/events' / event.name).read_bytes():
            raise ValueError('Historical journal would change: ' + event.name)


def enrichment_event(stage, before, after, update_id):
    """Add deterministic progress, never a model reading declaration."""
    previous, current = before['units'], after['units']
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(uid for uid in set(previous) & set(current)
                     if previous[uid]['fingerprint'] != current[uid]['fingerprint'])
    affected = set()
    for uid in added + removed + changed:
        unit = current.get(uid, previous.get(uid))
        affected.add(unit['owner_id'])
        affected.update(unit['source_ids'])
    reason = 'Supplemental evidence requires source checks: ' + update_id
    records = [{'id': r['id'], 'version': r['version'], 'reason': reason}
               for r in before['records'].values()
               if affected.intersection(r.get('source_ids', [])) or
               affected.intersection(d['id'] for d in r.get('dependencies', []))]
    readings = [{'unit_id': uid, 'stage': 'deep', 'reason': reason}
                for uid, rows in before['coverage'].items()
                if uid in current and rows['deep']['status'] in ('read', 'deep_read') and
                (current[uid]['owner_id'] in affected or
                 affected.intersection(current[uid]['source_ids']))]
    event = {'revision': before['revision'] + 1,
             'previous_event_sha256': before['event_sha256'], 'created_at': e.now(),
             'model': 'deterministic evidence enrichment (no model reading)',
             'journal_schema_version': 2, 'visual_reads': [], 'records': [],
             'reads': [], 'replace_units': [], 'revalidate_records': records,
             'revalidate_reads': readings,
             'evidence_update': {'id': update_id, 'added_units': added,
                                 'changed_units': changed, 'removed_units': removed,
                                 'affected_owners': sorted(affected)}}
    event['event_sha256'] = k.sha(event)
    k.atomic_json(stage / 'knowledge/events' / f"{event['revision']:08d}.json", event)
    k.rebuild(stage)
    return event


def recover_locked(root):
    """Roll forward a validated transaction; never overwrite unrelated newer data."""
    root = Path(root)
    pending = root / PENDING
    if not pending.exists():
        return {'recovered': False}
    plan_path = pending / 'plan.json'
    if not plan_path.exists():
        # Preparation never changes package files before the durable plan exists.
        shutil.rmtree(pending)
        return {'recovered': False, 'discarded_uncommitted_preparation': True}
    plan = e.read_json(plan_path)
    checksum = plan.pop('sha256', None)
    if k.sha(plan) != checksum:
        raise ValueError('Evidence update plan checksum mismatch; retain for inspection')
    # Validate every blob and target before any replacement, including recovery.
    for change in plan['changes']:
        relative = change['path']
        target = e.safe_path(root, relative)
        current = e.digest(e.file_bytes(target)) if target.is_file() else None
        if current not in (change['before'], change['after']):
            raise ValueError('Evidence recovery target changed independently: ' + relative)
        for area, expected in (('after', change['after']), ('before', change['before'])):
            if expected is not None:
                blob = e.safe_path(pending / area, relative)
                if e.digest(e.file_bytes(blob)) != expected:
                    raise ValueError('Evidence recovery blob damaged: ' + area + '/' + relative)
    history = e.safe_path(root, plan['history'])
    history.mkdir(parents=True, exist_ok=True)
    for change in plan['changes']:
        if change['before'] is not None:
            target = e.safe_path(history / 'before', change['path'])
            atomic_copy(e.safe_path(pending / 'before', change['path']), target)
    k.atomic_json(history / 'transaction.json', {**plan, 'sha256': checksum})
    # Replace manifest last. Pending marker blocks readers throughout publication.
    ordered = sorted(plan['changes'], key=lambda c: (c['path'] == 'manifest.json', c['path']))
    for change in ordered:
        target = e.safe_path(root, change['path'])
        atomic_copy(e.safe_path(pending / 'after', change['path']), target)
    # Retire the marker atomically before cleanup: directory deletion is not atomic.
    retired = root / ('.evidence-update-done-' + plan['id'])
    os.replace(pending, retired)
    shutil.rmtree(retired, ignore_errors=True)
    k._PROJECT_CACHE.pop(str(root.resolve()), None)
    return {'recovered': True, 'update_id': plan['id'], 'history': plan['history'],
            'revision': plan['revision'], 'files_published': len(plan['changes'])}


def publish(root, stage, before_hashes, update_id, revision):
    after_hashes = inventory(stage)
    if set(before_hashes) - set(after_hashes):
        raise ValueError('Enrichment must not delete existing package files')
    changes = [{'path': name, 'before': before_hashes.get(name), 'after': checksum}
               for name, checksum in sorted(after_hashes.items())
               if before_hashes.get(name) != checksum]
    pending = root / PENDING
    pending.mkdir()
    for change in changes:
        relative = change['path']
        atomic_copy(e.safe_path(stage, relative), e.safe_path(pending / 'after', relative))
        if change['before'] is not None:
            atomic_copy(e.safe_path(root, relative), e.safe_path(pending / 'before', relative))
    plan = {'version': 1, 'id': update_id, 'revision': revision,
            'history': 'history/enrichment/' + update_id, 'created_at': e.now(),
            'changes': changes}
    plan['sha256'] = k.sha(plan)
    k.atomic_json(pending / 'plan.json', plan)
    return recover_locked(root)


def enrich(root, expected_revision, renderer, dpi, prepare, verify, recover=False):
    root = Path(root).resolve()
    if renderer not in ('auto', 'none', 'libreoffice') or dpi < 1:
        raise ValueError('Invalid renderer or DPI')
    if recover:
        k.recover_lock(root)
        with k.writer(root, allow_pending=True):
            recovery = recover_locked(root)
            k.rebuild(root)
            report = verify(root)
            return {**report, 'operation': 'enrich_recovery', **recovery}
    if type(expected_revision) is not int:
        raise ValueError('enrich requires --expected-revision from the latest review')
    with k.writer(root):
        report = verify(root)
        if not report['pass']:
            raise ValueError('Package integrity failed; enrichment cannot repair tampered evidence')
        manifest = e.read_json(root / 'manifest.json')
        if manifest.get('schema_version') != 3:
            raise ValueError('Use upgrade to a new directory for older package contracts')
        before = k.project(root)
        if before['revision'] != expected_revision:
            raise ValueError('Revision changed; review the current package and retry')
        original_hashes = inventory(root)
        update_id = 'E' + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix='docpack-enrich-') as temporary:
            stage = Path(temporary) / 'package'
            shutil.copytree(root, stage, ignore=shutil.ignore_patterns(
                '.knowledge-write-lock', PENDING, '.evidence-update-done-*', 'receipts', '__pycache__'))
            prepare(stage, renderer, dpi)
            preserve_existing(root, stage)
            candidate = verify(stage)
            if not candidate['pass']:
                raise ValueError('Enrichment candidate failed verification: ' + '; '.join(candidate['errors']))
            if inventory(stage) == original_hashes:
                return {**report, 'operation': 'enrich', 'changed': False,
                        'revision': before['revision'], 'package': str(root)}
            after = k.project(stage)
            event = enrichment_event(stage, before, after, update_id)
            updated = e.read_json(stage / 'manifest.json')
            updated['enrichment'] = {'last_update_id': update_id,
                                     'revision': event['revision'],
                                     'history': 'history/enrichment/' + update_id}
            k.atomic_json(stage / 'manifest.json', updated)
            k.rebuild(stage)
            candidate = verify(stage)
            if not candidate['pass']:
                raise ValueError('Final enrichment candidate failed verification')
            if inventory(root) != original_hashes:
                raise ValueError('Package changed during staging; no evidence was committed')
            result = publish(root, stage, original_hashes, update_id, event['revision'])
        k.rebuild(root)
        report = verify(root)
        k.atomic_json(root / 'verification.json', report)
        return {**report, **result, 'operation': 'enrich', 'changed': True,
                'package': str(root), 'recovered': False,
                'added_units': len(event['evidence_update']['added_units']),
                'changed_units': len(event['evidence_update']['changed_units']),
                'retired_units': len(event['evidence_update']['removed_units']),
                'records_needing_revalidation': len(event['revalidate_records']),
                'deep_reads_needing_revalidation': len(event['revalidate_reads'])}
