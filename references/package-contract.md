# Document package contract v3 (v2 compatible)

## Files and evidence

`manifest.json` stores sources, assets, occurrences, renditions, limitations, and historical interpretation indexes. `knowledge/` stores full-document reading units, navigation, journal events, and rebuildable indexes/coverage. `SKILL.md` is the project entry point; `visual-index.md` is the visual inventory. Working references are package-relative; `show` returns absolute paths for host tools.

A source `original` is the complete file; an asset `original` is a byte-preserved embedded member or independent material. IDs derive from content hashes. Paragraph numbers are valid only within the same source hash; `xml_para_id` provides additional native localization without guaranteed permanence across versions.

Assets are content-deduplicated. `origins` retains source members and `occurrences` retains repeated appearances. Identical embedded Excel content is not independent evidence. Adjacent Visio and JPEG content remains `candidate_not_verified_equivalent`.

## Location precision

- DOCX: `part`, `paragraph`, `relationship_id`, `target_part`, and `shape_id` provide native locations for text and auxiliary anchors.
- Rendered DOCX: pages/pixels belong to derived layout, not original Microsoft Word pagination. Record tool, resolution, and hashes; automatic XML-to-page coordinate mapping is not implemented.
- PDF: file page order starts at 1 and differs from printed page numbers. Record page dimensions, rotation, and rendition pixel dimensions.
- Model visual localization: estimated positions need an explicit pixel coordinate system and verification. Crops record parent image, region, offset, and scale.

## States and auxiliary data

`readable_unreviewed` / `rendered_unreviewed` means images exist but their semantics remain unreviewed. `pending` means originals are preserved while content renditions await generation. `icon_only` is never content evidence. Rendition `role` distinguishes `original_image`, `page_content`, `region_content`, and `icon`. Derived images never overwrite originals.

Excel sidecars preserve sheets, hidden states, cells, raw values, types, style indexes, formulas, caches, merged ranges, and style XML. They do not calculate formulas or automatically convert dates. Print exports can omit hidden rows/columns and content outside print areas; check originals and sidecars.

Visio sidecars preserve pages, shape text, parent shapes, native properties, geometry cells, and connections. `BeginX`/`EndX` do not automatically imply business direction. Visually verify swimlanes, inheritance, and hidden layers. Exported-page to native page-part mapping is not automatically certified.

DOCX sidecars preserve paragraphs, numbering properties, directly nested tables, merged/nested relationships, comments, and revisions. They do not repair inconsistent source styles or reconstruct every displayed number/page.

## Updating and verification

Generate a new package for new versions and retain the old package. Check interpretation `dependencies` during migration. Changed/missing source or rendition hashes trigger `needs_revalidation`. Even unchanged images can become stale when body context changes; records must also bind sources.

`verify` checks actual file hashes, member inventories, locations, and references. `freshness` checks manifest dependencies only and cannot replace `verify`. Historical manifests snapshot prior state; they do not promise every old file exists in the new package.

```text
docpack.py check
docpack.py build --input FILE_OR_DIRECTORY ... --output NEW --doctype BRD --renderer auto
docpack.py list --package PACK
docpack.py query --package PACK --term "Commercial" --limit 12
docpack.py show --package PACK --asset ASSET_ID
docpack.py crop --package PACK --asset ASSET_ID --rendition RENDITION_ID --bbox X1 Y1 X2 Y2
docpack.py record --package PACK --file INTERPRETATION_JSON
docpack.py cellview --package PACK --asset ASSET_ID --sheet SHEET --cells A1 D4
docpack.py verify --package PACK
docpack.py freshness --package PACK
docpack.py build --input UPDATED ... --output NEW --previous OLD --renderer auto
```

Package-local `scripts/docpack.py` continues independently without global installation. `none` captures sources and creates PDF/original-image reading versions, without Office layout export. LibreOffice uses a short isolated profile in the renderer OS's temporary workspace rather than a user's running session or a deep package directory. Copy inputs byte-for-byte to staging, validate generated PDFs, then atomically copy outputs back. This also supports Windows renderers when WSL inputs/packages are on the Linux filesystem. Preserve originals and record export timeouts/failures as limitations. Diagnostics record the failure stage, original/staged hashes, profile length, command, version, and PDF validation result. Temporary paths in diagnostics describe past operations and are not persistent evidence paths.

Updating the global skill alone does not update embedded runtimes. For v3 packages with unchanged originals, use the updated skill's `enrich --package PACK --expected-revision REV`: supplement the same package and update its runtime. Use `upgrade --package OLD --output NEW` for older contracts or a separate migration. Preserve history, revalidate affected explanations, and inspect coverage rather than assuming old declarations cover new pages. New packages include `VERSION`; capabilities report `runtime_version` (older copies may report `unknown`).

Excel export uses `SinglePageSheets` to export whole sheets without print-area slicing, but hidden rows/columns may still be invisible. `cellview` renders native cells at selected coordinates as `structured_cell_view`: auxiliary evidence, not the author's original visible layout, with no formula calculation. LibreOffice itself may recalculate on opening/export; compare original caches and exports if numbers differ rather than automatically accepting recalculated values.

Initial large-page previews are capped at 4096 pixels per edge / 16 million pixels; record actual DPI. Preserve vector PDFs and rerender regions at high DPI rather than merely enlarging low-resolution previews. Preview/search limits do not discard source content.

## v2 compatibility and quality

Retain old packages. `upgrade --package OLD --output NEW` migrates originals, renditions, and interpretation history into a new directory without inferring reading status. `build` creates both reading queues; the host follows `reading-workflow.md`. Legacy interpretation input remains supported without automatically creating atomic knowledge or reading coverage. New transactions use `expected_revision`.

`query` returns `total_hits`, `next_offset`, and match reasons. Snippets support navigation only. `read` exposes complete paginated text, context, native data, and image input paths. A read receipt proves returned materials, not understanding. Visual/source-check attestations are traceable declarations; scripts cannot audit host tool history or automatically prove semantic entailment.

Events are the commit point for knowledge updates; indexes and coverage are rebuildable. `verify` separates evidence and learning results. `review` separates `pending`/`completed_with_gaps` from `actually_read`. There is no omission cap on text, short clauses, or knowledge records.

When upgrading native indexes, preserve the `auxiliary_snapshot` (relative path/hash) used to create old cell renditions. Do not silently bind an old image to a new index. `cached_result_present` means an actual value was stored; `value_element_present` separately records XML value-element existence, including empty `<v/>`. Preserve every serialized blank cell; do not invent evidence for coordinates absent from XML.

Uninterpreted native XLSX parts (comments, shapes/media, embedded objects, external links, pivot/structured tables) and VSDX master parts retain ZIP member locations/hashes and explicit gaps. Readable pages do not prove all hidden/inherited content has been read. Continue processing through preserved original members rather than bypassing gaps to claim completeness.

Reading a knowledge ID expands currently valid evidence units, context, and image paths, deduplicating without marking them read. Explicitly list missing, replaced, or changed historical units rather than rebinding old citations. Follow `next_text_offset` to continue expanded original text.

## v3 contract and performance

New packages use `schema_version=3` and `learning.version=3`. v3 also reads v2 packages and replays legacy events. `build` defaults to `renderer=auto`; `none` skips layout export, and unrendered DOCX pages remain visual gaps. `check` detects existing tools without installing them.

An embedded DOCX asset's `content_source_id` points to its byte-identical content source. Source `parent_assets` retains parent assets and occurrence IDs. The content source provides the single text/page reading queue; assets share its renditions without double-counting reading. Attachment evidence also depends on parent source context. Content deduplication does not make occurrence contexts equivalent.

`query --expand related` follows recorded knowledge relations, evidence, and nearby attachment occurrences for one hop. `related_via` explains navigation; `total_hits` and `next_offset` include expanded candidates. This is not proof of semantic equivalence. Retrieval invents neither synonyms nor source precedence.

`journal_schema_version=2` stores `visual_reads` once per transaction. Knowledge/reading records reference relevant `visual_read_ids`; replay uses transaction-versioned V identifiers. `record` still accepts the original input arrays. Legacy event bytes remain unchanged.

Checkpoints, inverted indexes, and coverage are rebuildable projections. Cache validity binds manifest, units, navigation, and every event's content hash/version, not modification times or sizes. Damaged caches replay and rebuild; source/journal tampering is rejected. Writes remain serialized, revision-checked, and atomic.

`upgrade` writes only a new directory, preserves old manifests/unit snapshots, and expands embedded DOCX from old packages without rewriting old journals. Retain historical citations invalidated by new formatting/context/units; do not silently rebind them or upgrade unread materials to read.


## Recoverable enrichment (3.1.0)

`enrich` supplements a v3 package in place, preserving its identity, originals, existing renditions, and old event bytes. `manifest.enrichment` identifies the latest evidence-update revision and relative history path. A new journal event may contain `evidence_update`, `revalidate_records=[{id,version,reason}]`, and `revalidate_reads=[{unit_id,stage,reason}]`. These are deterministic invalidations, not reading attestations. Revising an affected record clears that version's enrichment invalidation; actual new reads clear the corresponding progress invalidation. Other dependency checks remain active.

`.evidence-update` is a pending commit marker with a hashed plan and before/after blobs. Publication is per-file atomic with a recoverable multi-file transaction; readers must reject a pending marker or changed manifest generation. History preserves replaced-file snapshots, including old manifest/unit/runtime versions, in `history/enrichment/ID/before/`. Indexes/checkpoints are disposable projections. See [dynamic-updates.md](dynamic-updates.md) for recovery and conservative revalidation scope.
