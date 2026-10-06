# Dynamic expansion and knowledge updates

Keywords: record, expected_revision, claims, evidence, revisions, conflicts, dependencies, replace_units.

Text, tables, and native auxiliary data are source evidence; knowledge is revisable interpretation. Do not edit `units.jsonl`, journal events, or source files directly. Update through `record`. Add explicitly selected sources or updated originals with `build --previous OLD --output NEW`; retain the old package.

## Minimal transaction

~~~json
{
  "expected_revision": 0,
  "model": "Actual host/model; state when the exact version is unknown",
  "receipt_ids": ["Q... returned by read"],
  "visual_reads": [],
  "reads": [
    {"unit_id": "U...", "stage": "initial", "status": "read", "notes": "Content actually read and its boundaries"}
  ],
  "records": [
    {
      "kind": "term",
      "name": "Term from the source",
      "scope": "Explicit project/source/section or object scope",
      "aliases": [],
      "claims": [
        {"content": "Scoped interpretation", "authority": "interpretation",
         "evidence": [{"unit_id": "U...", "start": 0, "end": 4, "quote": "EXACT_SOURCE_TEXT"}]}
      ],
      "unknowns": [],
      "review_status": "unreviewed"
    }
  ]
}
~~~

Replace IDs, character ranges, and quotes with actual results from this reading; the example cannot be submitted as-is. Submit a JSON transaction with `record --file FILE`. Use the revision from the latest `review`/`read`/`query`. On conflict, reread and merge rather than forcing an overwrite.

`reads` may use `unit_ids` for a group actually read. Deep reading uses `stage=deep`, `status=deep_read`; `gap` needs a reason. For long text, receipts must cover every character. Reading records may bind `knowledge_dependencies` to specific knowledge versions; revision requeues affected deep reading.

Each `visual_reads` entry requires `rendition_id`, `sha256`, the actual `tool`, and a concrete `observation`. Visual claims bind evidence to visual units. Optional `bbox` uses original rendition pixels within `dimensions_px`; convert scaled coordinates. Attestations remain declarations, and scripts cannot audit host tool history. Never fabricate them.

## Knowledge records

Use `kind` values such as overview, term, concept, object, rule, process, interface, decision, conflict, issue, navigation, or another type required by the content. Claim `authority` must be one of `source_requirement`, `visual_observation`, `interpretation`, `background`, or `suggestion`.

- Bind each source-derived claim separately to evidence. Quotes must exactly match the unit character range. Scripts add the unit fingerprint and source/asset/image dependencies.
- Native fields may use `{unit_id, field, value}`, such as `formula`, `hidden_row`, or `hidden_sheet`; `value` must exactly match `native_metadata`. Separate formulas from cached values; an uncached formula is not a computed result.
- `background` and `suggestion` may lack document references but cannot masquerade as source requirements. External materials must be explicitly selected as independent sources; do not crawl automatically.
- Evidence-bind `aliases`. Candidate translations/acronym expansions remain `interpretation`/`unreviewed`; retrieval expansion does not prove source-defined equivalence.
- `source_checked` requires `review_notes` explaining qualifications and counterevidence checks, complete read receipts for text, and current viewing attestations for visuals. It is not human business approval.
- Set `human_reviewed` and `reviewer` only after actual human review. Keep unconfirmed scores `unknown`, rather than defaulting to `medium`.

## Addition, revision, relations, and conflicts

Omit `id` to generate a new record ID. To revise, specify the existing ID, the complete replacement record, and `reason`. Versions increase and `supersedes_version` preserves history. Do not omit `kind`/`name`/`scope`/`claims`: updating only aliases must not accidentally erase rules.

Relations use `kind` and `target_id`; targets must exist or be created in the same batch. Examples: `defines`, `applies_to`, `depends_on`, `contradicts`. Also bind reasoning prerequisites through `knowledge_dependencies=[{id,version}]` to invalidate dependent conclusions on revision. Naming a relation does not prove it.

A `conflict` needs evidence from at least two different reading units and `unknowns`. Deduplicated copies of the same source/content are not independent corroboration. Do not resolve conflicts by newer dates, body position, or model consensus. Record governing evidence and business decisions separately.

## Revising sentence segmentation

Each `replace_units` item specifies `parent_id` (paragraph/page_text), `reason`, and `spans=[[start,end],...]`. Spans must continuously cover the complete original text without overlap or omission. Segmentation changes requeue affected references or reading records. Use `records` for interpretation; never edit original text to remove contradictions.

## Commit, recovery, and Q&A loop

Each transaction commits one hash-chained event; success requires atomic persistence. Indexes and coverage can be rebuilt from events. After interruption, `read`/`review` replay the journal; `review --recover` rebuilds caches. Serialize writes to each package; never force-remove an active writer lock.

Check `verify`, `freshness`, and `review` before Q&A; stale records are excluded from valid knowledge retrieval. Write back new definitions, boundaries, exceptions, visual rules, relationships, or corrections with `record`, then confirm discoverability through `query`/`read`. Do not copy entire conversations when there is no new finding. Chat history is not the sole memory.

Legacy `interpretation` records remain readable/appendable as scoped history. They do not automatically create atomic knowledge, reading coverage, or exhaustive review declarations.

## v3 input compatibility

Transaction input retains the format above. Scripts store `visual_reads` once per event; reading and knowledge records reference only relevant images, rather than copying every attestation to every text unit. Returned `visual_read_ids` can be checked in `knowledge/checkpoint.json` under `visual_attestations`; historical declarations do not authorize fabricated current viewing.

Base new relationships on source checks. Use `query --expand related` to revisit attachment evidence. Invented relationships, model-generated keywords, and candidate translations are not source evidence. Separate business unknowns from technical gaps; retain both sides and impact of conflicts without automatic resolution by date or location.
