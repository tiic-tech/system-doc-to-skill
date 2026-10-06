# Continuing multimodal interpretation

## Retrieval and actual viewing

1. Check `verify` and source versions. On first use, inspect the visual index for undescribed images and `pending` objects.
2. Locate candidates by section, caption, context, and native text. A search miss does not establish that a diagram contains no rule.
3. `show` returns absolute image paths. Send actual pixels to the model using an available host image tool. Codex may offer `view_image`; Claude/other hosts use their own image or attachment mechanism. Do not invent tool names.
4. Inspect the whole image for boundaries, roles, direction, and notes, then `crop` small text as needed. For cross-region arrows, inspect both endpoints and the complete connecting line.
5. Cross-check body text, comments, and native sidecars. Preserve qualifications on approvals, permissions, amounts, deadlines, and loop limits.
6. Report observations, business interpretations, unknowns, and locations separately. Acceptance/design suggestions are not source requirements.

Without an image tool, list questions, rendition paths, auxiliary data, and unchecked boundaries. Do not claim visual verification. Do not add a paid API chain or automatically upload the package.

## Persistent records

Use transactions from the [dynamic update protocol](dynamic-updates.md), rather than relying on chat history. Each `visual_reads` item needs `rendition_id`, `sha256`, the actual `tool`, and a concrete `observation`. Bind important observations individually to visual units, optionally including a bounding box in original image pixels. Read receipts prove returned materials, not image viewing.

~~~json
{
  "expected_revision": 0,
  "model": "Actual host/model; state when the exact version is unknown",
  "receipt_ids": ["Q..."],
  "visual_reads": [{"rendition_id": "R...", "sha256": "ACTUAL_HASH", "tool": "ACTUAL_TOOL", "observation": "Nodes, arrows, notes, and boundaries actually observed"}],
  "records": [{
    "kind": "process", "name": "Process name", "scope": "Specific source and scope",
    "claims": [{"content": "Scoped observation", "authority": "visual_observation", "evidence": [{"unit_id": "U..."}]}],
    "review_status": "source_checked", "review_notes": "Images and text actually checked; list unchecked parts separately", "unknowns": []
  }]
}
~~~

Example IDs are not valid submission data. `unreviewed` denotes a candidate. `source_checked` declares host checks of decisive sources, conditions, and counterevidence. `human_reviewed` needs an actual human `reviewer`; `needs_revalidation` cannot serve as a current verified conclusion. Source checking is not business approval, and model agreement does not prove truth.

Bind contextual source, asset, and image dependencies so unchanged images are not incorrectly reused after context changes. Legacy `question`/`interpretation`/`dependencies` records remain compatible without automatically increasing atomic knowledge or reading coverage. Scripts cannot audit host tool history or prove interpretations correct.

## Visual boundaries

For illegible small text, compression, clipped screenshots, crossing arrows, line/color conventions, font substitution, or hidden layers, preserve originals and unknowns, then re-export or crop. A model cannot recover details absent from the supplied original. PDF server scaling does not guarantee coordinate precision; use package images with explicit dimensions for localization.

A cropped screenshot does not replace evidence from native Excel cells, hidden data, or other Visio pages.

Official capability boundaries:

- [OpenAI file inputs](https://developers.openai.com/api/docs/guides/file-inputs): embedded images in non-PDF files do not automatically enter image context.
- [Claude file uploads](https://support.claude.com/en/articles/8241126-upload-files-to-claude): ordinary text extraction is insufficient for embedded non-PDF images.
- [Claude vision coordinates](https://platform.claude.com/docs/en/build-with-claude/vision-coordinates): scaling and estimated coordinates require mapping and verification.
