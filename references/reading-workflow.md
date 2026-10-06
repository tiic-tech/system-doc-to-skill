# Two-stage reading and acceptance

Keywords: review, receipt, coverage, Stage 1, Stage 2, resume.

Scripts create materials and candidate segmentation; the host model understands them. Run both stages by default and commit each completed batch without additional approval. Reading scope is limited to the explicitly selected sources in the manifest.

## Working loop

1. Run `verify` to check actual files, native members, source locations, and knowledge references. `review` returns current stages and gaps.
2. `review --next --limit 8` returns the next unread batch and read receipts. Stage `auto` switches from `initial` to `deep` when initial reading has been accounted for.
3. Actually read complete `text` and `context`. When `next_text_offset` is non-null, continue with `read --unit ID --offset OFFSET`; combine receipts covering all characters before marking a unit read. Paginate search with `next_offset`. If host tool output is truncated, do not declare complete reading; continue with smaller batches or character windows.
4. Open every `visual` unit's `image_input.path` using an actual host image tool. A returned path or receipt does not prove viewing. Save concrete observations, the tool, `rendition_id`, and hash. Use `crop` for small text, rendering preserved PDFs at higher resolution. Label `cellview` views of hidden cells as derived evidence.
5. Submit `record` with `expected_revision`, `model`, `receipt_ids`, `reads`, and discovered knowledge `records`. Initial reading uses `read`; deep reading uses `deep_read`. Use `gap` with a specific reason for material that cannot be read or understood.
6. Continue `review --next` until no unit awaits processing in the stage; proceed directly from initial to deep reading. Resume from committed progress after interruption. `review --recover` only reclaims locks from exited writers and rebuilds derived indexes.

## Stage 1: full initial reading

Visit every required unit, including short clauses, blank cells, code, comments, hidden data, native shapes/connections, and visual content pages. Preserve context at every occurrence of a repeated image. Establish an overview, term/alias candidates, objects, candidate relationships, and questions. Distinguish source content, layout, and structural inference; native table-of-contents hierarchy is not automatically business hierarchy.

A paragraph is a context container; a `clause` is a candidate sentence/provision that may be resegmented. The first two table rows are only header candidates. The table context returned by `read` also includes rows, merge inheritance, and parent tables. Read full table units and their paragraph IDs when necessary, rather than only a matching sentence. Preserve CSV multiline cells. An Excel blank is not zero or "No".

## Stage 2: full deep reading

Explain each sentence/provision's nature, references, roles, actions, objects, preconditions, negation, quantities, units, exceptions, and consequences. Explain heading/label scope and interpretive boundaries imposed by layout or blanks. Check hidden states, formulas, and cached values in native data without automatically calculating them. Native connection endpoints do not automatically establish business direction.

For complex terms/concepts, record definitions, scope, aliases, usage, relationships, and unknowns. For objects, record identity, fields, roles, states, and constraints without automatically treating them as database entities. Select knowledge types by actual content; do not create a card for every word. Bind each important conclusion to specific evidence and seek related passages, attachments, and counterevidence.

Every unit needs an actual deep-reading result or an explicit gap. One initial-reading entry may cover multiple units actually read. Share a deep interpretation only across semantically equivalent units, explaining their common meaning and occurrence/context differences in `notes`. A generic "all read" declaration cannot substitute for understanding a whole document.

## Acceptance states

- `completed`: every required unit in the stage has an actual reading record, with no gaps.
- `completed_with_gaps`: every unit is accounted for, but some are unreadable/incomplete; gaps are excluded from `actually_read`.
- `pending`: unread or `needs_revalidation` units remain; do not claim the stage is finished.
- `ready` / `ready_with_gaps`: both stages are accounted for and evidence integrity checks pass; scoped Q&A can proceed.

Missing definitions and conflicts can remain `unknowns` in read units; do not fabricate answers. Record technical failures, unsupported materials, and absent image capability as gaps. Check completeness and correct interpretation separately; never assign `semantic_accuracy` automatically. Reading declarations do not prove understanding; use actual sampling, counterexamples, and business review.

## v3 detail checks

`read` exposes `interpretation_annotations` for strikethrough, explicit overrides, hidden text, style provenance, unresolved revisions, fields, and comments. These annotations are separate from source text; cite `text_range`. Verify pages when formatting is uncertain, struck through, or visibly inconsistent. Do not automatically interpret it as approval, cancellation, or deletion of requirements.

Check applicable roles/actions/objects/scope, conditions, negation, exceptions, quantities, units, deadlines, outputs, and counterevidence. Avoid mechanically filling irrelevant template fields. Jointly inspect headers/merged cells, attachments, diagrams, and comments for important rules; record decisive evidence and unchecked boundaries. Context explanations suffice for headings, labels, and blanks.

Commit both stages in small batches; text and visuals may be read separately to avoid output truncation. Each deep-read unit needs an interpretation or gap, rather than a bulk generic declaration. Image-tool records remain host attestations; script acceptance does not prove actual viewing.

`review` separates `business_unresolved` from technical `gaps` and `needs_revalidation_records`. Unknowns may remain in read units. Do not fill undefined source content merely to obtain `ready`.
