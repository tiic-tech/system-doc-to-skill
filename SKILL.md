---
name: system-doc-to-skill
description: Build traceable, continuously maintainable document packages from complex system-development materials. Use for full-document reading, terms, tables, visual attachments, and evidence-backed Q&A across requirements, proposals, and technical specifications.
---

# System documents: package, read deeply, and maintain knowledge

Role: Requirements Engineer and Multimodal Document Architect. Knowledge background: requirements analysis, tender responses, domain modeling, system and product design, document object structures, visual presentation, and evidence provenance.

Use for RFP, TP (technical proposal for a tender), BRD, PRD, architecture, interfaces, design, implementation, and operations materials. Apply [document-type rules](references/document-types.md) by actual content when materials are mixed. This independent implementation draws on document packages, navigation, and knowledge units without upstream runtime dependencies. Instructions and generated guidance are in English; preserve source text verbatim and respond in the user's requested language.

## Default: two reading stages, then continuing Q&A

1. Inventory explicitly selected materials and run `check`. `build` defaults to `--renderer auto` using existing tools and recursively expands embedded DOCX. Write to a new directory; use `upgrade` for existing v1/v2 packages. Preserve originals. Do not install dependencies, register global skills, or expand external sources automatically.
2. Run `verify`, inspect the visual index, and read the [package contract](references/package-contract.md). Successful capture does not mean the model has read the materials.
3. Follow the [two-stage reading workflow](references/reading-workflow.md) with `review --next`, `read`, and `record`: full initial reading, then full deep reading. Commit discoveries and reading status after each batch. Continue to deep reading automatically after initial reading, without another confirmation.
4. Actually open every visual reading unit with an available host image tool. Inspect the whole image, then details; check hidden content, arrows, captions, and text/diagram conflicts using the [multimodal protocol](references/multimodal-protocol.md). An object icon is not its contents.
5. Check coverage and references before Q&A. `ready_with_gaps` is acceptable when unread or unreadable materials, source conflicts, and unknowns are explicit. Do not claim they have been fully read or definitively interpreted.

Scripts capture, locate, index, and validate references and versions. The host model performs actual reading, semantic interpretation, and counterevidence checks. Scripts do not call model APIs or automatically understand the document. Without image capability, retain the visual gap; a text summary cannot substitute for viewing an image.

When Office layout export fails, inspect the corresponding `renders/ID/export-diagnostic.json` and report its failure stage, exit code, and reason. Tool discovery alone does not verify conversion. Existing packages carry their own runtime copies: updating this global skill does not repair them. Use `upgrade --package OLD --output NEW` to regenerate missing renditions in a new package while preserving history and revalidating affected evidence; never patch an actively used package in place.

## Expand the package through every Q&A session

Check `verify`, `freshness`, and `review`; retrieve paginated candidates with `query` (use `--expand related` for cross-object or attachment questions), then `read` original text, neighbors, tables, comments, and visual attachments. A search miss does not prove a rule is absent. For permissions, approvals, amounts, deadlines, or process boundaries, inspect related diagrams and attachments.

Persist useful discoveries, evidenced aliases, relationships, revisions, and conflicts through the [dynamic update protocol](references/dynamic-updates.md). Bind each important claim to specific evidence. Separate source requirements, observations, interpretations, background knowledge, and suggestions. Keep formatting annotations separate from original text; strikethrough, highlighting, or comments do not automatically mean business cancellation or approval. Preserve revision history, leave unknowns unresolved, and revalidate dependencies when sources change.

If asked a question before both stages finish, answer within the verified scope and continue the reading queue. Resume interrupted work from `review`; a chat summary or returned file path is not a reading record.

CLI: `python -B /absolute/skill/scripts/docpack.py --help`. Pass paths as separate arguments. Supported inputs: TXT, Markdown, CSV/TSV, DOCX, PDF, XLSX, VSDX, PNG, JPEG, and WebP. Preserve other formats as originals with explicit gaps. Use batches and pagination for complete processing; impose no omission limit on chapters or knowledge units.

Report material completeness, actual reading coverage, interpretation review, and unresolved issues separately. `source_checked` is a host declaration of source checks, not business approval or proof of semantic correctness. Record `human_reviewed` only after actual human review.
