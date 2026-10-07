# system-doc-to-skill

Turn complex system-development documents into portable local packages that preserve originals, trace claims to evidence, and support continuing Q&A and knowledge updates.

Supports RFP, TP (technical proposal for a tender), BRD, PRD, architecture, interfaces, design, implementation, and operations materials. The skill acts as a Requirements Engineer and Multimodal Document Architect. Scripts capture, locate, version, and index; the host model reads and interprets. This independent implementation has no runtime dependency on book-to-skill, PaperIndex, vector databases, or model APIs.

Version **3.1.0** adds same-package `enrich`: fill missing captured attachment content and Office pages, update navigation/indexes, preserve originals and existing journals, and queue new evidence and affected explanations for reading/revalidation. English guidance and verbatim source text remain supported, including Chinese/Unicode retrieval. The v3 contract and new-directory `upgrade` remain compatible.

## Acknowledgements and architectural inspiration

This project draws on two open-source projects:

- [book-to-skill](https://github.com/virgiliojr94/book-to-skill): document-to-skill packaging, a project skill entry point, on-demand reading, and continuing reuse and updates.
- [PaperIndex](https://github.com/Biajin-PKU/PaperIndex): section navigation, layered knowledge units, scoped evidence references, and returning to source passages during interpretation.

These ideas are adapted for system-development documents with immutable originals, native and visual evidence, full reading coverage, claim-level citations, and versioned knowledge updates. This repository implements its own scripts and protocols; it does not bundle either project's code or require either project at runtime.

## Use the skill

Install the repository root as one complete Codex skill. [SKILL.md](SKILL.md) is the entry point; [agents/openai.yaml](agents/openai.yaml) provides UI metadata. With a host supporting local files and image tools, invoke:

```text
$system-doc-to-skill Package the documents I explicitly selected, complete full initial and deep reading, preserve evidence and unresolved issues, and support continuing Q&A and updates.
```

In the desktop skill picker, select `system-doc-to-skill` using `@`. The invocation example above uses the CLI/IDE `$` form. See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills) for host-specific controls.

Each document package includes its own scripts and project skill and can be moved as a whole. Registering every project package is unnecessary. Claude and other hosts can follow the same file protocol using their actual file/image tools; compatibility does not certify semantic correctness.

## CLI quick start

Requires Python 3.10+. Text/OOXML capture, retrieval, and journals use the standard library. PDF reading, images, and crops require existing PyMuPDF; Office page export requires existing LibreOffice. Missing capabilities become explicit technical gaps. Scripts do not install software. Run `check` to inspect available capabilities.

```bash
python -B scripts/docpack.py check
python -B scripts/docpack.py build --input examples/requirements.md --output work/example-docpack --title "Synthetic requirements" --doctype BRD
python -B scripts/docpack.py verify --package work/example-docpack
python -B scripts/docpack.py review --package work/example-docpack --next --limit 8
python -B scripts/docpack.py query --package work/example-docpack --term "approval" --expand related --limit 10
python -B scripts/docpack.py read --package work/example-docpack --unit UNIT_ID_FROM_RESULTS
python -B scripts/docpack.py record --package work/example-docpack --file FINDINGS_TRANSACTION.json
```

Returning materials through `read` does not mark them read. After actual initial/deep reading, the host submits status and claim-level evidence with `record`; see the [transaction protocol](references/dynamic-updates.md). Q&A checks versions, retrieves candidates, expands related text/tables/attachments, verifies decisive evidence, and writes new discoveries back.

`build --renderer auto` probes existing tools by default; `none` and `libreoffice` are also available. `none` does not generate Office pages and retains the corresponding gaps. Update sources with `build --input UPDATED_MATERIALS --previous OLD_PACKAGE --output NEW_PACKAGE`; preserve history without directly editing originals or journal events.

Office conversion runs in a separate temporary workspace accessible to the renderer's OS, using short input/profile/output paths. It copies the input byte-for-byte, verifies the generated PDF, then atomically copies it into the package. Windows rendering from WSL uses the existing Windows temp directory, including when the package is on the Linux filesystem. Export diagnostics include the failure stage, tool version, arguments, source hashes, profile path, exit code, and output. Discovery is not proof of successful rendering. Pages remain derived LibreOffice layouts.

Existing packages contain runtime copies. Updating the global skill alone does not add missing pages. For a v3 package with unchanged originals, run the updated global skill's CLI:

```bash
python -B /absolute/updated-skill/scripts/docpack.py review --package PACKAGE
python -B /absolute/updated-skill/scripts/docpack.py enrich --package PACKAGE --expected-revision CURRENT_REVISION --renderer auto
python -B PACKAGE/scripts/docpack.py verify --package PACKAGE
python -B PACKAGE/scripts/docpack.py review --package PACKAGE --next
```

`enrich` keeps the same directory and package identity. It replaces the package runtime with the current skill runtime, fills missing reading representations, and commits a deterministic evidence-update event; it does not reread materials or regenerate existing visual evidence. New pages are unread. Affected knowledge and previously deep-read units need revalidation; unaffected progress remains. Retry against the latest `review` revision after a conflict. A repeat with unchanged evidence/runtime/capabilities is a no-op.

Stop other package-writing processes before enrichment; finish reading batches running an older runtime before publication. An active writer lock is rejected. Staging uses a temporary full copy, requiring spare disk space; the durable transaction and replaced-file snapshots live inside the package. Reads detect pending/changed evidence generations. After interruption use the updated CLI's `enrich --package PACKAGE --recover`, or `review --recover`. Recovery validates blobs and existing targets, then finishes the prepared transaction; it cannot repair arbitrary tampering. See the [dynamic update protocol](references/dynamic-updates.md).

Use `upgrade --package OLD_PACKAGE --output NEW_PACKAGE` for older contracts or an explicit separate migration. New/changed source files still use `build --previous OLD --output NEW`, preserving the old version. Enrichment processes only already captured materials; it does not widen the selected source scope. New packages carry `VERSION`; `check` reports `runtime_version`.

## Capabilities and boundaries

- Recursively expands embedded DOCX, deduplicates by content hash, and preserves every occurrence and parent context. An icon is not attachment content evidence.
- Separates original text and character ranges from formatting annotations. Preserves tables, comments, revisions, strikethrough, highlighting, hidden text, and style provenance. Formatting does not automatically mean business approval or cancellation.
- Supports Chinese/Unicode, English word boundaries, and basic inflection. Aliases and one-hop relationships require recorded evidence. A search miss does not prove a rule is absent.
- Shares visual attestations within each transaction. Validates rebuildable indexes and checkpoints by content hashes; recovers from a serialized, atomic, revision-checked, hash-chained journal.
- Accepts TXT, Markdown, CSV/TSV, DOCX, PDF, XLSX, VSDX, PNG, JPEG, and WebP. Unreadable native parts remain explicit gaps; arbitrary complexity is not claimed to have been exhaustively validated.

Report capture completeness, actual reading coverage, and interpretation review separately. `source_checked` is a host source-check declaration, not expert approval. Scripts cannot prove an image tool was actually used or that an interpretation follows from evidence. Scoped Q&A may proceed with explicit gaps; distinguish conflicts, undefined terms, placeholders, and derived calculations.

## Synthetic examples and validation

[requirements.md](examples/requirements.md) is fictional material written from scratch, not adapted from a customer document. Generate complex Office fixtures using the standard library:

```bash
python -B examples/generate_office.py --output work/synthetic-inputs
python -B scripts/docpack.py build --input work/synthetic-inputs/requirements.docx --output work/office-docpack --renderer none --title "Synthetic office materials"
```

The generator demonstrates repeated embedded Word documents, merged/nested tables, inherited strikethrough and explicit overrides, hidden text, and an embedded Excel workbook with a hidden row and an uncached formula. `none` retains visual gaps. Fixtures and generated packages do not prove that host-model deep reading has occurred.

The suite contains 43 original program tests, 19 v3 regression/compatibility tests, and 11 enrichment tests (73 total). Full testing requires existing PyMuPDF. These validate deterministic behavior, not business semantic accuracy:

```bash
python -B -m unittest discover -s scripts -p 'test*.py' -v
```

The public repository contains generic implementation and fictional fixtures only: no real project packages, business answers, internal attachments, or local acceptance logs. See the [package contract](references/package-contract.md), [two-stage reading workflow](references/reading-workflow.md), and [multimodal protocol](references/multimodal-protocol.md).
