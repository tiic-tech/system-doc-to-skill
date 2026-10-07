# Dynamic expansion and knowledge updates

Keywords: enrich, recovery, record, expected_revision, claims, evidence, revisions, conflicts, dependencies, replace_units.

Text, tables, and native auxiliary data are source evidence; knowledge is revisable interpretation. Do not edit `units.jsonl`, journal events, or source files directly. Update through `record`. Add explicitly selected sources or updated originals with `build --previous OLD --output NEW`; retain the old package.

## Same-package evidence enrichment

Use the updated global skill's `enrich --package PACK --expected-revision REV --renderer auto` for missing reading representations of already captured materials. Obtain `REV` from the latest `review`. A v3 contract is required; older contracts use new-directory `upgrade`. This entry point retains the package directory/identity and originals, automatically expands unlinked embedded DOCX and missing native sidecars, and retries absent Office layouts. It does not replace existing renditions, edit source files, add external sources, or certify model reading. `none` retains Office page gaps.

Preparation uses a temporary full package copy; ensure spare disk capacity. Candidate evidence, journals, references, and old originals/renditions are verified before publication. The package writer lock serializes the operation; revision and content hashes detect conflicts. Finish old-runtime reading batches and stop other writers first. Existing scripts already running before the runtime update cannot acquire new behavior retroactively.

Publication uses `.evidence-update/plan.json`, hashed before/after blobs, per-file atomic replacements, and a pending marker. **This is a recoverable multi-file transaction, not a filesystem-wide atomic rename.** Updated readers refuse pending updates and discard buffered results if the manifest generation changes. Completed replacements are archived in `history/enrichment/UPDATE_ID/before/`; the transaction retains hashes and paths. Historical knowledge events remain byte-identical; one new hash-chained deterministic event records changed units and revalidation. Rebuildable checkpoints/indexes are refreshed after publication. No model reading is inferred.

New units begin unread. Changed fingerprints invalidate references as usual. Supplemental evidence also queues source-scoped existing knowledge and prior deep-reading declarations for rechecks, even when original hashes are unchanged; this conservative scope can overqueue. Initial text coverage survives when unchanged. Revise knowledge with `record` and explain the recheck; do not erase old versions. Review new pages and any affected context before confirming explanations. Knowledge remains stored while stale entries are excluded from valid retrieval.

After interruption, run the updated CLI's `enrich --package PACK --recover` or `review --recover`. Recovery checks that a writer exited, validates the plan and all blobs, rejects independently changed targets, and rolls forward the prepared transaction. Interrupted preparation without a durable plan is discarded because it has not replaced package files. Relative paths permit relocation before recovery. Rebuildable indexes are recovered from evidence and events. Active or cross-OS locks are not force-removed; integrity failures require investigation. An unchanged repeat produces no new update event.

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
