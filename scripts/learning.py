"""Local navigation, reading coverage and versioned knowledge. No model/API calls."""
from __future__ import annotations
from collections import Counter, defaultdict
from contextlib import contextmanager
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
import uuid
import zipfile
import xml.etree.ElementTree as ET

import evidence as e
import formatting
import search_index

STAGES = ("initial", "deep")
REVIEW_STATES = {"unreviewed", "source_checked", "human_reviewed"}
AUTHORITIES = {"source_requirement", "visual_observation", "interpretation", "background", "suggestion"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=None if path.name in ("checkpoint.json", "index.json", "coverage.json") else 2, separators=(",", ":") if path.name in ("checkpoint.json", "index.json", "coverage.json") else None)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def writer(root):
    """An interrupted lock is released only explicitly after checking its PID."""
    lock = Path(root) / ".knowledge-write-lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("Package writer locked; review --recover checks whether its owner exited")
    try:
        atomic_json(lock / "owner.json", {"pid": os.getpid(), "os_name": os.name, "created_at": e.now()})
        yield
    finally:
        shutil.rmtree(lock, ignore_errors=True)


def recover_lock(root):
    lock = Path(root) / ".knowledge-write-lock"
    if not lock.exists():
        return
    owner = e.read_json(lock / "owner.json") if (lock / "owner.json").exists() else None
    if not owner:
        raise ValueError("Lock owner unknown; inspect it before removal")
    if owner.get("os_name", os.name) != os.name:
        raise ValueError("Lock belongs to another OS; inspect ownership instead of interpreting its PID locally")
    if type(owner.get("pid")) is not int or owner["pid"] <= 0:
        raise ValueError("Invalid writer PID; inspect the lock")
    if pid_alive(owner["pid"]):
        raise ValueError("Writer PID is still running; recovery must not remove its lock")
    shutil.rmtree(lock)


def pid_alive(pid):
    # Windows kill(pid, 0) terminates a process; use read-only process queries.
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return False
            raise ValueError("Cannot inspect writer PID safely; Windows error " + str(error))
        try:
            status = ctypes.c_uint32()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(status)):
                raise ValueError("Cannot read writer process state")
            return status.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    else:
        return True


def identity(kind, owner, locator):
    return "U" + sha([kind, owner, locator])[:24]


def sentence_spans(text, indivisible=False):
    """Candidates, not a claim that punctuation perfectly represents sentences."""
    if not text.strip():
        return []
    if indivisible:
        return [(0, len(text))]
    spans, start = [], 0
    for match in re.finditer(r"[。！？]+|[.!?]+(?=\s|$)|\n+", text):
        end = match.end()
        if text[start:end].strip():
            spans.append((start, end))
        start = end
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def enhance_docx(root, source):
    """Retain formatting, numbering definitions, fields and unresolved math."""
    if source["kind"] != "docx" or not source.get("structure"):
        return
    path = e.safe_path(root, source["structure"]["path"])
    data = e.read_json(path)
    with zipfile.ZipFile(e.safe_path(root, source["original"]["path"])) as archive:
        names = set(archive.namelist())
        data["numbering_xml"] = archive.read("word/numbering.xml").decode("utf-8") if "word/numbering.xml" in names else None
        styles_root=ET.fromstring(archive.read("word/styles.xml")) if "word/styles.xml" in names else None
        by_part = defaultdict(list)
        for paragraph in data["paragraphs"]:
            by_part[paragraph["part"]].append(paragraph)
        for part, paragraphs in by_part.items():
            if part not in names:
                continue
            tree = ET.fromstring(archive.read(part))
            nodes = list(tree.iter(e.W + "p"))
            relationships = e.xml_relationships(archive, part)
            for item, node in zip(paragraphs, nodes):
                offset, runs = 0, []
                # Only the nearest paragraph's runs; nested text boxes have own anchors.
                parents = {id(c): p for p in node.iter() for c in p}
                for run in node.iter(e.W + "r"):
                    ancestor = parents.get(id(run))
                    while ancestor is not None and ancestor.tag != e.W + "p":
                        ancestor = parents.get(id(ancestor))
                    if ancestor is not node:
                        continue
                    text = e.paragraph_text(run)
                    props = run.find(e.W + "rPr")
                    runs.append({"start": offset, "end": offset + len(text), "text": text,
                                 "properties_xml": ET.tostring(props, encoding="unicode") if props is not None else None})
                    offset += len(text)
                item["formatted_spans"],item["format_uncertainties"]=formatting.spans_for(item,node,styles_root,e.paragraph_text)
                item["comment_ids"]=[c["id"] for c in data.get("comments",[]) if item["id"] in c["anchors"] and part=="word/document.xml"]
                item["runs"] = runs
                item["run_offsets_match_text"] = "".join(r["text"] for r in runs) == item["text"]
                item["bookmarks"] = [dict(n.attrib) for n in node.iter(e.W + "bookmarkStart")]
                item["fields"] = [{"instruction": n.text or ""} for n in node.iter(e.W + "instrText")]
                item["hyperlinks"] = [{"anchor": n.get(e.W + "anchor"),
                    "relationship_id": n.get(e.R + "id"), "relationship": relationships.get(n.get(e.R + "id")),
                    "text": e.paragraph_text(n)} for n in node.iter(e.W + "hyperlink")]
                math_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
                item["math_objects"] = [{"xml": ET.tostring(n, encoding="unicode"),
                    "text": "".join(t.text or "" for t in n.iter(math_ns + "t"))}
                    for n in node.iter(math_ns + "oMath")]
    atomic_json(path, data)
    payload = path.read_bytes()
    source["structure"].update(sha256=e.digest(payload), bytes=len(payload))
    if source.get("reading"):
        reading=e.safe_path(root,source["reading"]["path"])
        raw=reading.read_text(encoding="utf-8")
        # Reinitialization replaces annotation projection rather than accumulating it.
        raw=re.sub(r"\n\n> (?:Formatting/interpretation annotations \(not source text\): |\u683c\u5f0f/\u89e3\u91ca\u63d0\u793a\uff08\u4e0d\u5c5e\u4e8e\u539f\u6587\uff09\uff1a)[^\n]*\n", "", raw)
        for paragraph in data["paragraphs"]:
            if paragraph["part"]=="word/document.xml":
                anchor="<div id=\""+paragraph["id"]+"\">"
                at=raw.find(anchor)
                if at>=0:
                    end=raw.find("</div>",at)+len("</div>")
                    raw=raw[:end]+formatting.markdown_note(paragraph)+raw[end:]
                else:
                    anchor='<a id="'+paragraph['id']+'"></a>'
                    at=raw.find(anchor)
                    if at>=0:
                        end=at+len(anchor)
                        raw=raw[:end]+formatting.markdown_note(paragraph)+raw[end:]
        reading.write_text(raw,encoding="utf-8")
        source["reading"].update(sha256=e.digest(reading.read_bytes()),bytes=reading.stat().st_size)


def create_units(root, manifest):
    units, navigation, by_id = [], [], {}
    sources = {s["id"]: s for s in manifest["sources"]}
    assets={a['id']:a for a in manifest['assets']}
    def context_sources(owner,seen=None):
        seen=set() if seen is None else seen
        if owner in seen:return set()
        seen.add(owner);result={owner} if owner in sources else set()
        for parent in sources.get(owner,{}).get('parent_assets',[]):
            for origin in assets[parent['asset_id']]['origins']:
                result.update(context_sources(origin['source_id'],seen))
        return result

    def add(kind, owner, locator, text="", required=True, **extra):
        uid = identity(kind, owner, locator)
        source_ids = extra.pop("source_ids", list(context_sources(owner)))
        unit = {"id": uid, "kind": kind, "owner_id": owner, "locator": locator,
                "source_ids": sorted(set(source_ids)), "text": text, "required": required,
                "section_path": extra.pop("section_path", []), **extra}
        unit["fingerprint"] = sha(unit)
        units.append(unit)
        by_id[uid] = unit
        return unit

    for source in manifest["sources"]:
        sid = source["id"]
        structure = e.read_json(e.safe_path(root, source["structure"]["path"])) if source.get("structure") else {}
        table_map = {t["id"]: t for t in structure.get("tables", [])}
        cell_by_paragraph = {}
        for table in table_map.values():
            for row in table["rows"]:
                for cell in row["cells"]:
                    for pid in cell["paragraphs"]:
                        cell_by_paragraph[pid] = {"table": table["id"], "row": row["id"], "cell": cell["id"],
                            "grid_column": cell["grid_column"], "grid_span": cell["grid_span"],
                            "vertical_merge": cell["vertical_merge"], "inherited_from": cell["inherited_from"],
                            "parent_table": table["parent_table"]}
        paragraph_units = {}
        for paragraph in structure.get("paragraphs", []) if source["kind"] != "csv" else []:
            locator = {"part": paragraph["part"], "paragraph": paragraph["id"]}
            context = cell_by_paragraph.get(paragraph["id"]) if paragraph["part"] == "word/document.xml" else None
            parent = add("paragraph", sid, locator, paragraph["text"], False,
                section_path=paragraph.get("section_path", []), table_context=context,
                native_metadata={k: paragraph[k] for k in ("style", "numbering", "runs", "run_offsets_match_text",
                    "fields", "hyperlinks", "bookmarks", "math_objects", "revisions", "kind", "formatted_spans", "format_uncertainties", "comment_ids") if k in paragraph},
                visual_occurrences=paragraph.get("visual_occurrences", []))
            paragraph_units[(paragraph["part"], paragraph["id"])] = parent["id"]
            if paragraph.get("heading_level"):
                navigation.append({"unit_id": parent["id"], "source_id": sid, "title": paragraph["text"],
                    "path": paragraph.get("section_path", []), "level": paragraph["heading_level"],
                    "origin": "source_structure", "locator": locator})
            spans = sentence_spans(paragraph["text"], bool(paragraph.get("heading_level") or paragraph.get("kind") == "code"))
            for start, end in spans:
                add("clause", sid, {**locator, "start": start, "end": end},
                    paragraph["text"][start:end], parent_id=parent["id"],
                    section_path=parent["section_path"], table_context=context, segmentation="candidate",
                    visual_occurrences=paragraph.get("visual_occurrences", []),
                    interpretation_annotations=formatting.visible_annotations(paragraph))
            for index, math_object in enumerate(paragraph.get("math_objects", [])):
                add("native_math", sid, {**locator, "math_index": index}, math_object["text"],
                    parent_id=parent["id"], native_metadata=math_object,
                    limitations=["Native math XML retained; mathematical layout requires page inspection."])
        for table in structure.get("tables", []):
            add("table", sid, {"table": table["id"]}, "", False, native_metadata=table)
            for row in table["rows"]:
                for cell in row["cells"]:
                    text_paragraphs = [by_id[paragraph_units[("word/document.xml", pid)]]
                                       for pid in cell["paragraphs"] if ("word/document.xml", pid) in paragraph_units]
                    if not any(p["text"].strip() for p in text_paragraphs):
                        add("empty_cell", sid, {"table": table["id"], "row": row["id"], "cell": cell["id"]},
                            "", native_metadata=cell,
                            limitations=["Empty is not zero, No, or a confirmed missing requirement."])
        for comment in structure.get("comments", []):
            add("comment", sid, {"comment_id": comment["id"]}, comment["text"], native_metadata=comment,
                limitations=["Comment is not an accepted requirement."])
        for row in structure.get("rows", []):
            for cell in row["cells"]:
                add("csv_cell", sid, {"row": row["row"], "column": cell["column"]}, cell["value"])
        for page in structure.get("pages", []):
            parent = add("page_text", sid, {"page": page["page"]}, page["text"], False,
                native_metadata={"text_blocks": page.get("text_blocks", [])},
                limitations=["Extracted PDF order may differ from visual reading order."])
            for start, end in sentence_spans(page["text"]):
                add("clause", sid, {"page": page["page"], "start": start, "end": end},
                    page["text"][start:end], parent_id=parent["id"], segmentation="candidate")
        for ref_index, ref in enumerate(structure.get("visual_links", [])):
            if ref.get("status") != "resolved_to_selected_input":
                add("external_reference", sid, {"visual_link": ref_index}, ref["target"], native_metadata=ref,
                    limitations=["Reference is retained; external target was not fetched or silently added."])
        for ref_index, ref in enumerate(structure.get("external_references", [])):
            add("external_reference", sid, {"external_relationship": ref_index}, str(ref.get("target", ref)),
                native_metadata=ref, limitations=["External linked material is outside the selected input scope."])
        for ref_index, ref in enumerate(structure.get("unresolved_internal_references", [])):
            add("gap", sid, {"unresolved_relationship": ref_index}, str(ref.get("target", ref)),
                native_metadata=ref, blocked_reason="Internal relationship has no supported captured reading representation")
        if source.get("status") == "partial":
            add("gap", sid, {"capture_status": "partial"}, "", blocked_reason="Partial source capture: " +
                "; ".join(source.get("limitations", [])) + "; inspect manifest issues and preserved original")
        if not structure and not source.get("asset_id"):
            add("gap", sid, {"file": source["name"]}, "", blocked_reason="Source has no supported reading representation")
        if source["kind"]=="docx" and not source.get("layout"):
            add("gap",sid,{"layout":"pending"},"",blocked_reason="Document text captured; visual layout unavailable. Check export diagnostics and source limitations.")
        for rendition in source.get("layout", []):
            if rendition.get("role") != "page_content":
                continue
            add("visual", sid, {"rendition": rendition["id"]}, "",
                rendition=rendition, source_ids=context_sources(sid), page_origin="derived_layout" if rendition["method"] == "libreoffice" else "source_pdf")
        pdfs = sorted({r.get("pdf_path") for r in source.get("layout", []) if r.get("pdf_path")})
        fitz = e.fitz_module()
        if fitz:
            for pdf in pdfs:
                try:
                    with fitz.open(e.safe_path(root, pdf)) as doc:
                        for level, title, page in doc.get_toc():
                            navigation.append({"source_id": sid, "title": title, "level": level, "page": page,
                                "origin": "pdf_outline_candidate", "pdf_path": pdf, "hierarchy_verified": False,
                                "page_origin": "source_pdf" if source["kind"] == "pdf" else "derived_layout"})
                except Exception as exc:
                    navigation.append({"source_id": sid, "origin": "outline_unavailable", "reason": str(exc)})
    for asset in manifest["assets"]:
        aid = asset["id"]
        if asset.get("content_source_id"):
            # Its canonical source owns text and visuals; no second coverage queue.
            continue
        source_ids = sorted({sid for o in asset["origins"] for sid in context_sources(o['source_id'])})
        auxiliary = e.read_json(e.safe_path(root, asset["auxiliary"]["path"])) if asset.get("auxiliary") else {}
        occurrences = asset.get("occurrences", [])
        sections = next((o.get("section_path", []) for o in occurrences if o.get("section_path")), [])
        if asset["kind"] in ("xlsx", "vsdx"):
            # A readable printout does not establish coverage of unparsed native parts.
            try:
                with zipfile.ZipFile(e.safe_path(root, asset["original"]["path"])) as archive:
                    for part in archive.namelist():
                        extra = (asset["kind"] == "xlsx" and part.startswith(("xl/comments", "xl/threadedComments", "xl/drawings/", "xl/media/", "xl/embeddings/", "xl/externalLinks/", "xl/pivot", "xl/tables/"))) or (
                            asset["kind"] == "vsdx" and re.fullmatch(r"visio/masters/master\d+\.xml", part))
                        if extra and not part.endswith("/"):
                            add("gap", aid, {"native_part": part}, "", source_ids=source_ids,
                                native_metadata={"retained_in_original": True, "member_sha256": e.digest(archive.read(part))},
                                blocked_reason="Native part preserved in original but not separately interpreted: " + part)
            except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
                add("gap", aid, {"native_archive": "unreadable"}, "", source_ids=source_ids,
                    blocked_reason="Original native archive retained; member inventory unavailable: " + str(exc))
        for sheet in auxiliary.get("sheets", []):
            for cell in sheet["cells"]:
                add("native_cell", aid, {"sheet": sheet["name"], "cell": cell["address"]},
                    "" if cell["value"] is None else str(cell["value"]), source_ids=source_ids,
                    section_path=sections, native_metadata={**cell, "sheet_state": sheet["state"],
                        "hidden_row": re.sub(r"\D", "", cell["address"]) in sheet["hidden_rows"],
                        "column_settings": sheet["column_settings"], "merged_ranges": sheet["merged_ranges"]},
                    occurrences=occurrences)
        for page in auxiliary.get("pages", []):
            for shape in page["shapes"]:
                add("native_shape", aid, {"part": page["part"], "shape_id": shape["id"]}, shape["text"],
                    source_ids=source_ids, section_path=sections, native_metadata=shape, occurrences=occurrences)
            for index, connection in enumerate(page["connections"]):
                add("native_connection", aid, {"part": page["part"], "connection_index": index},
                    json.dumps(connection, ensure_ascii=False), source_ids=source_ids, section_path=sections,
                    native_metadata=connection, occurrences=occurrences,
                    limitations=["Geometric endpoint is not certified business direction."])
        for index, chart in enumerate(auxiliary.get("chart_parts", [])):
            add("gap", aid, {"chart_part": chart}, chart, source_ids=source_ids,
                blocked_reason="Native chart part retained in original; semantic chart coverage not certified")
        primary = [r for r in asset["reading_versions"] if r["role"] in ("original_image", "page_content")]
        for rendition in primary:
            add("visual", aid, {"rendition": rendition["id"]}, "", source_ids=source_ids,
                section_path=sections, rendition=rendition, occurrences=occurrences,
                alternative_views=[r for r in asset["reading_versions"] if r["id"] != rendition["id"]])
        if asset["visual_status"] == "pending":
            add("gap", aid, {"asset": aid}, "", source_ids=source_ids, occurrences=occurrences,
                blocked_reason="; ".join(asset["limitations"]) or "Content rendition unavailable")
        if not auxiliary and not primary and asset["visual_status"] != "pending":
            # Explicit inventory metadata; icons are never promoted to content.
            add("artifact_metadata", aid, {"asset": aid}, "", False, source_ids=source_ids,
                native_metadata={"role": asset["visual_status"], "occurrences": occurrences})
    return units, navigation


def initialize(root, previous=None):
    root = Path(root).resolve()
    manifest = e.read_json(root / "manifest.json")
    for source in manifest["sources"]:
        enhance_docx(root, source)
    for asset in manifest["assets"]:
        if asset["kind"] == "xlsx" and asset.get("auxiliary") and e.read_json(e.safe_path(root, asset["auxiliary"]["path"])).get("native_schema_version", 1) < 2:
            # Historical cell views must keep their exact input snapshot.
            old = dict(asset["auxiliary"])
            bound = [r for r in asset["reading_versions"] if r.get("native_cells", {}).get("auxiliary_sha256") == old["sha256"]]
            if bound:
                snapshot = root / "history" / "auxiliary" / (old["sha256"] + ".json")
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(e.safe_path(root, old["path"]), snapshot)
                for rendition in bound:
                    rendition["auxiliary_snapshot"] = {**old, "path": snapshot.relative_to(root).as_posix()}
                    rendition["historical_input_snapshot"] = True
            data = e.native_xlsx(e.safe_path(root, asset["original"]["path"]))
            path = e.safe_path(root, asset["auxiliary"]["path"])
            atomic_json(path, data)
            asset["auxiliary"].update(sha256=e.digest(path.read_bytes()), bytes=path.stat().st_size)
    units, navigation = create_units(root, manifest)
    directory = root / "knowledge"
    directory.mkdir(exist_ok=True)
    raw = b"".join(canonical(unit) + b"\n" for unit in units)
    (directory / "units.jsonl").write_bytes(raw)
    atomic_json(directory / "navigation.json", navigation)
    manifest["schema_version"] = 3
    manifest["learning"] = {"version": 3, "units": {"path": "knowledge/units.jsonl", "sha256": e.digest(raw)},
        "navigation": {"path": "knowledge/navigation.json", "sha256": e.digest((directory / "navigation.json").read_bytes())},
        "journal": "knowledge/events", "readiness_policy": "explicit_gaps_allowed"}
    atomic_json(root / "manifest.json", manifest)
    if previous and (Path(previous) / "knowledge/events").exists():
        # Journal is portable; outdated unit/fact references are invalidated on projection.
        shutil.copytree(Path(previous) / "knowledge/events", directory / "events", dirs_exist_ok=True)
        snapshots=root/"history"/"previous-learning";snapshots.mkdir(parents=True,exist_ok=True)
        for name in ("units.jsonl","navigation.json"):
            path=Path(previous)/"knowledge"/name
            if path.exists():shutil.copyfile(path,snapshots/name)
    rebuild(root)
    return project(root)


def base_units(root, manifest):
    ref = manifest.get("learning", {}).get("units")
    if not ref:
        raise ValueError("Version 1 package: upgrade to a NEW output before learning")
    path = e.safe_path(root, ref["path"])
    if e.digest(path.read_bytes()) != ref["sha256"]:
        raise ValueError("Reading units changed outside the update protocol")
    # JSON Lines are delimited only by LF. U+2028/U+0085 may be inside JSON strings.
    units = [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]
    for unit in units:
        fingerprint = unit.pop("fingerprint")
        if sha(unit) != fingerprint:
            raise ValueError("Unit fingerprint mismatch: " + unit["id"])
        unit["fingerprint"] = fingerprint
    return {u["id"]: u for u in units}


def evidence_hashes(manifest):
    current = {s["id"]: s["original"]["sha256"] for s in manifest["sources"]}
    current.update({a["id"]: a["original"]["sha256"] for a in manifest["assets"]})
    for owner in manifest["sources"] + manifest["assets"]:
        current.update({r["id"]: r["sha256"] for r in owner.get("layout", owner.get("reading_versions", []))})
    return current


def replay(root):
    root = Path(root).resolve()
    manifest = e.read_json(root / "manifest.json")
    units = base_units(root, manifest)
    records, history, reads, revision, previous_hash = {}, {}, {}, 0, None
    views={}
    for path in sorted((root / "knowledge/events").glob("*.json")):
        event = e.read_json(path)
        event_hash = event.pop("event_sha256", None)
        if sha(event) != event_hash or event["revision"] != revision + 1 or event["previous_event_sha256"] != previous_hash:
            raise ValueError("Knowledge journal checksum/order mismatch: " + path.name)
        revision, previous_hash = event["revision"], event_hash
        for replacement in event.get("replace_units", []):
            for uid in replacement["retired"]:
                if uid in units:
                    units[uid] = {**units[uid], "retired": True}
            for unit in replacement["children"]:
                units[unit["id"]] = unit
        event_views={v["rendition_id"]:v for v in event.get("visual_reads",[])}
        def compact(item):
            item=copy.deepcopy(item)
            supplied=item.pop("visual_reads",None)
            required=item.pop("visual_read_ids",[])
            if supplied is not None:
                ids={units.get(ref["unit_id"],{}).get("rendition",{}).get("id") for c in item.get("claims",[]) for ref in c.get("evidence",[])}
                own=units.get(item.get("unit_id"),{}).get("rendition",{}).get("id")
                if own:ids.add(own)
                chosen=[v for v in supplied if v["rendition_id"] in ids]
            else:chosen=[event_views[rid] for rid in required if rid in event_views]
            item["visual_read_ids"]=[]
            for v in chosen:
                vid="V"+sha([revision,v])[:24];views[vid]={**v,"revision":revision}
                item["visual_read_ids"].append(vid)
            return item
        for raw_record in event.get("records", []):
            record=compact(raw_record)
            if record.get("id") in records:
                history.setdefault(record["id"], []).append(records[record["id"]])
            records[record["id"]] = copy.deepcopy(record)
        for raw_reading in event.get("reads", []):
            reading=compact(raw_reading)
            reads.setdefault(reading["unit_id"], {})[reading["stage"]] = reading
    current_hashes = evidence_hashes(manifest)
    for record in records.values():
        reasons = []
        for dependency in record.get("dependencies", []):
            if current_hashes.get(dependency["id"]) != dependency["sha256"]:
                reasons.append("Changed/missing source or rendition: " + dependency["id"])
        for claim in record.get("claims", []):
            for reference in claim.get("evidence", []):
                unit = units.get(reference.get("unit_id"))
                if not unit or unit.get("retired") or unit["fingerprint"] != reference.get("unit_fingerprint"):
                    reasons.append("Changed/missing reading unit: " + str(reference.get("unit_id")))
        for dependency in record.get("knowledge_dependencies", []):
            target = records.get(dependency["id"])
            if not target or target["version"] != dependency["version"]:
                reasons.append("Knowledge dependency revised: " + dependency["id"])
        record["stale_reasons"] = sorted(set(reasons))
    # Transitive invalidation, including cycles, terminates at a fixed point.
    changed = True
    while changed:
        changed = False
        for record in records.values():
            for dependency in record.get("knowledge_dependencies", []):
                target = records.get(dependency["id"])
                reason = "Knowledge dependency needs revalidation: " + dependency["id"]
                if target and target["stale_reasons"] and reason not in record["stale_reasons"]:
                    record["stale_reasons"].append(reason)
                    changed = True
    coverage = {}
    for uid, unit in units.items():
        if not unit["required"] or unit.get("retired"):
            continue
        coverage[uid] = {}
        for stage in STAGES:
            reading = reads.get(uid, {}).get(stage)
            if reading and reading["unit_fingerprint"] == unit["fingerprint"]:
                coverage[uid][stage] = {**reading}
                for dependency in reading.get("knowledge_dependencies", []):
                    target = records.get(dependency["id"])
                    if not target or target["version"] != dependency["version"] or target["stale_reasons"]:
                        coverage[uid][stage] = {**reading, "status": "needs_revalidation",
                            "invalidation_reason": "Bound knowledge revised or stale: " + dependency["id"]}
            elif unit.get("blocked_reason"):
                coverage[uid][stage] = {"status": "gap", "notes": unit["blocked_reason"], "automatic_capture_gap": True}
            else:
                coverage[uid][stage] = {"status": "needs_revalidation" if reading else "unread"}
    return {"revision": revision, "event_sha256": previous_hash, "units": units,
        "records": records, "history": history, "coverage": coverage,"visual_attestations":views}


_PROJECT_CACHE={}

def cache_signature(root):
    root=e._scoped_resolve(root)
    manifest=e.read_json(root/'manifest.json')
    paths=[root/'manifest.json']+[e.safe_path(root,manifest['learning'][key]['path']) for key in ('units','navigation')]
    paths+=sorted((root/'knowledge/events').glob('*.json'))
    return {'algorithm':3,'files':{str(p.relative_to(root)):e.digest(e.file_bytes(p)) for p in paths}}


def project(root, copy_result=True):
    root=e._scoped_resolve(root);signature=cache_signature(root)
    checkpoint=root/'knowledge/checkpoint.json'
    try:
        checkpoint_bytes=e.file_bytes(checkpoint)
    except FileNotFoundError:
        checkpoint_bytes=None
    checkpoint_hash=e.digest(checkpoint_bytes) if checkpoint_bytes is not None else None
    key=sha([signature,checkpoint_hash]);cached=_PROJECT_CACHE.get(str(root))
    if cached and cached[0]==key:return copy.deepcopy(cached[1]) if copy_result else cached[1]
    state=None
    if checkpoint_bytes is not None:
        try:
            value=json.loads(checkpoint_bytes)
            if value['signature']==signature and value['state_sha256']==sha(value['state']):state=value['state']
        except (KeyError,ValueError,OSError):pass
    if state is None:state=replay(root)
    _PROJECT_CACHE[str(root)]=(key,state)
    return copy.deepcopy(state) if copy_result else state


def tokens(text, for_query=False):
    result = []
    normalized = unicodedata.normalize("NFKC", str(text))
    # Unicode words; separate Chinese runs from adjacent Latin/Greek identifiers.
    pattern = r"[\u3400-\u9fff]+|[^\W_\u3400-\u9fff]+(?:[_.:/+\-][^\W_\u3400-\u9fff]+)*"
    for value in re.findall(pattern, normalized):
        if re.fullmatch(r"[\u3400-\u9fff]+", value):
            result.append(value)
            result.extend(value[i:i+2] for i in range(max(0, len(value)-1)))
            if not for_query or len(value) == 1:
                result.extend(value)
        else:
            value = value.casefold()
            result.append(value)
            if len(value) > 3 and value.endswith("s") and not value.endswith(("ss", "us", "is")):
                result.append(value[:-1])
    return result


def index_documents(state):
    docs = []
    for unit in state["units"].values():
        if unit.get("retired"):
            continue
        docs.append({"id": unit["id"], "type": "unit", "kind": unit["kind"],
            "source_ids": unit["source_ids"], "section": " > ".join(unit["section_path"]),
            "fields": {"name": "", "body": unit["text"], "section": " ".join(unit["section_path"]),
                "metadata": json.dumps(unit.get("native_metadata", {}), ensure_ascii=False)},
            "locator": unit["locator"],"interpretation_annotations":unit.get("interpretation_annotations",[])})
    for record in state["records"].values():
        if record["stale_reasons"]:
            continue
        docs.append({"id": record["id"], "type": "knowledge", "kind": record["kind"],
            "source_ids": record.get("source_ids", []), "section": record.get("scope", ""),
            "fields": {"name": " ".join([record["name"]] + record.get("aliases", [])),
                "body": " ".join(claim["content"] for claim in record["claims"]),
                "section": record.get("scope", ""), "metadata": " ".join(record.get("unknowns", []))},
            "review_status": record["review_status"]})
    return docs



def make_index(state,manifest):
    docs=index_documents(state)
    return {'revision':state['revision'],'event_sha256':state['event_sha256'],
            'capture_sha256':manifest['learning']['units']['sha256'],
            'documents_sha256':sha(docs),'documents':docs,
            'prepared':search_index.prepare(docs,tokens),'relationships':search_index.graph(state,manifest)}


def rebuild(root):
    root=Path(root);state=replay(root);manifest=e.read_json(root/'manifest.json')
    index=make_index(state,manifest);index['projection_sha256']=sha(index)
    atomic_json(root/'knowledge/index.json',index)
    atomic_json(root/'knowledge/coverage.json',{'revision':state['revision'],'units':state['coverage']})
    atomic_json(root/'knowledge/checkpoint.json',{'signature':cache_signature(root),'state':state,'state_sha256':sha(state)})
    _PROJECT_CACHE.pop(str(root.resolve()),None)
    return state


@e.operation_scope
def query(root,term,limit=12,offset=0,source=None,section=None,kind=None,expand='none'):
    if limit<1 or offset<0:raise ValueError('limit must be positive and offset nonnegative')
    if expand not in ('none','related'):raise ValueError('Unknown query expansion')
    guard(root);state=project(root,copy_result=False);manifest=e.read_json(Path(root)/'manifest.json')
    try:
        index=e.read_json(Path(root)/'knowledge/index.json');checksum=index.pop('projection_sha256')
        valid=(checksum==sha(index) and index['revision']==state['revision'] and
               index['event_sha256']==state['event_sha256'] and index['capture_sha256']==manifest['learning']['units']['sha256'])
    except (KeyError,ValueError,OSError):valid=False
    if not valid:index=make_index(state,manifest)
    return search_index.search(index,state,term,tokens,limit,offset,source,section,kind,expand)


def guard(root):
    report = e.verify(root)
    if not report["pass"]:
        raise ValueError("Evidence integrity failed: " + "; ".join(report["errors"]))
    manifest = e.read_json(Path(root) / "manifest.json")
    if "learning" in manifest:
        for key in ("units", "navigation"):
            ref = manifest["learning"][key]
            if e.digest(e.file_bytes(e.safe_path(root, ref["path"]))) != ref["sha256"]:
                raise ValueError(key + " altered outside update protocol")
    return report


def unit_context(root, manifest, state, unit):
    context = {}
    context["related_attachments"]=[{"asset_id":a["id"],"content_source_id":a.get("content_source_id"),"occurrences":a["occurrences"],"reading_versions":a["reading_versions"]} for a in manifest["assets"] if a.get("content_source_id") and (unit["owner_id"]==a["content_source_id"] or any(o["source_id"] in unit["source_ids"] and (o.get("section_path")==unit.get("section_path") or o.get("locator",{}).get("paragraph")==unit["locator"].get("paragraph")) for o in a["occurrences"]))]
    parent = state["units"].get(unit.get("parent_id"))
    if parent:
        context["parent"] = {"id": parent["id"], "text": parent["text"],
            "locator": parent["locator"], "native_metadata": parent.get("native_metadata", {})}
    for sid in unit["source_ids"]:
        if unit['owner_id'] in {s['id'] for s in manifest['sources']} and sid!=unit['owner_id']:
            continue
        source = next(s for s in manifest["sources"] if s["id"] == sid)
        if not source.get("structure"):
            continue
        data = state.setdefault("_context_cache",{}).setdefault(source["id"],None)
        if data is None:
            data=e.read_json(e.safe_path(root, source["structure"]["path"]));state["_context_cache"][source["id"]]=data
        paragraphs = data.get("paragraphs", [])
        locator = unit["locator"]
        position = next((i for i, p in enumerate(paragraphs) if
            p.get("id") == locator.get("paragraph") and p.get("part") == locator.get("part")), None)
        if position is not None:
            context.setdefault("neighbours", []).extend(paragraphs[max(0, position-2):position+3])
            context.setdefault("comments", []).extend(c for c in data.get("comments", []) if locator["paragraph"] in c["anchors"])
        table_info = unit.get("table_context")
        table_id = table_info.get("table") if table_info else locator.get("table")
        table = next((t for t in data.get("tables", []) if t["id"] == table_id), None)
        if table:
            paragraph_map = {p["id"]: p for p in paragraphs if p["part"] == "word/document.xml"}
            row_id = table_info.get("row") if table_info else locator.get("row")
            selected = [r for i, r in enumerate(table["rows"]) if i < 2 or r["id"] == row_id]
            cells_by_id = {c["id"]: (r, c) for r in table["rows"] for c in r["cells"]}
            inherited = []
            for row in selected:
                for cell in row["cells"]:
                    if cell.get("inherited_from") in cells_by_id:
                        inherited.append(cells_by_id[cell["inherited_from"]][0])
            selected = list({r["id"]: r for r in selected + inherited}.values())
            context["table"] = {"id": table_id, "parent_table": table["parent_table"],
                "rows": [{"id": row["id"], "cells": [{**c,
                    "paragraph_text": [{"id": pid, "text": paragraph_map[pid]["text"]} for pid in c["paragraphs"]]}
                    for c in row["cells"]]} for row in selected],
                "notice": "First two rows are header candidates, not certified headers. Read the table unit and paragraph IDs for all other rows/nested tables."}
    owner = next((a for a in manifest["assets"] if a["id"] == unit["owner_id"]), None)
    if owner and unit["kind"] == "native_cell":
        native = e.read_json(e.safe_path(root, owner["auxiliary"]["path"]))
        sheet = next(s for s in native["sheets"] if s["name"] == unit["locator"]["sheet"])
        row = re.sub(r"\D", "", unit["locator"]["cell"])
        context["sheet"] = {k: v for k, v in sheet.items() if k != "cells"}
        context["sheet"]["row_and_header_candidates"] = [c for c in sheet["cells"] if re.sub(r"\D", "", c["address"]) in ("1", "2", row)]
        context["sheet"]["notice"] = "Rows 1 and 2 are candidates; hidden and multi-row headers require verification."
    if owner:
        context["occurrences"] = owner["occurrences"]
        context["visual_materials"] = [{"rendition_id": r["id"], "path": str(e.safe_path(root, r["path"])),
            "role": r["role"], "sha256": r["sha256"]} for r in owner["reading_versions"]]
    elif unit.get("visual_occurrences"):
        aids = {v["asset_id"] for v in unit["visual_occurrences"]}
        context["visual_materials"] = [{"asset_id": a["id"], "visual_status": a["visual_status"],
            "occurrences": a["occurrences"], "images": [{"rendition_id": r["id"], "path": str(e.safe_path(root, r["path"])),
                "sha256": r["sha256"], "role": r["role"]} for r in a["reading_versions"]]}
            for a in manifest["assets"] if a["id"] in aids]
    return context


@e.operation_scope
def read_units(root, ids, offset=0, max_chars=6000, with_context=True):
    root = Path(root).resolve()
    if offset < 0 or max_chars < 1:
        raise ValueError("Invalid text pagination")
    guard(root)
    state, manifest = project(root), e.read_json(root / "manifest.json")
    result, ranges = [], []
    expanded_ids = list(dict.fromkeys(ids))
    links = {}
    for uid in list(expanded_ids):
        if uid not in state["records"]:
            continue
        available, unavailable = [], []
        for claim in state["records"][uid]["claims"]:
            for ref in claim["evidence"]:
                target = state["units"].get(ref["unit_id"])
                if not target or target.get("retired") or target["fingerprint"] != ref["unit_fingerprint"]:
                    unavailable.append(ref["unit_id"])
                elif target["id"] not in available:
                    available.append(target["id"])
        links[uid] = {"expanded_evidence_unit_ids": available,
                      "unavailable_or_changed_evidence_unit_ids": sorted(set(unavailable))}
        expanded_ids.extend(item for item in available if item not in expanded_ids)
    for uid in expanded_ids:
        if uid in state["records"]:
            result.append({"type": "knowledge", **state["records"][uid],
                "history": state["history"].get(uid, []), **links[uid],
                "notice": "Current source units follow this record; unavailable historical evidence is not rebound to a new source."})
            continue
        if uid not in state["units"]:
            legacy = next((i for i in manifest.get("interpretations", []) if i["id"] == uid), None)
            if legacy:
                result.append({"type": "legacy_interpretation", "content": e.read_json(e.safe_path(root, legacy["path"])),
                    "notice": "Historical scoped interpretation; not atomically reviewed knowledge or evidence of full-document reading."})
                continue
            raise ValueError("Unknown reading/knowledge ID: " + uid)
        unit = state["units"][uid]
        if unit.get("retired"):
            raise ValueError("Reading unit retired; follow replacement records")
        text = unit["text"]
        if offset > len(text):
            raise ValueError("Text offset is outside the unit")
        end = min(len(text), offset + max_chars)
        item = {**unit, "text": text[offset:end], "text_range": [offset, end], "total_chars": len(text),
            "next_text_offset": end if end < len(text) else None}
        if with_context:
            item["context"] = unit_context(root, manifest, state, unit)
        if unit.get("rendition"):
            item["image_input"] = {"path": str(e.safe_path(root, unit["rendition"]["path"])),
                "rendition_id": unit["rendition"]["id"], "sha256": unit["rendition"]["sha256"],
                "notice": "Open this image with the actual host image tool; returning this path is not viewing it."}
        result.append(item)
        ranges.append({"unit_id": uid, "unit_fingerprint": unit["fingerprint"], "start": offset, "end": end})
    receipt = {"id": "Q" + uuid.uuid4().hex, "created_at": e.now(), "revision": state["revision"],
        "ranges": ranges, "notice": "Attests delivered material, not model cognition or image-tool invocation."}
    receipt["sha256"] = sha(receipt)
    atomic_json(root / "knowledge/receipts" / (receipt["id"] + ".json"), receipt)
    return {"revision": state["revision"], "receipt_id": receipt["id"], "items": result}


def summarize(state):
    summaries = {}
    for stage in STAGES:
        counts = Counter(row[stage]["status"] for row in state["coverage"].values())
        unread = counts["unread"] + counts["needs_revalidation"]
        summaries[stage] = {"total_required_units": len(state["coverage"]), **dict(counts),
            "unread_or_stale": unread, "accounted_for": len(state["coverage"]) - unread,
            "actually_read": counts["read"] + counts["deep_read"],
            "complete": not unread and not counts["gap"],
            "state": "pending" if unread else ("completed_with_gaps" if counts["gap"] else "completed")}
    initial_ready = summaries["initial"]["unread_or_stale"] == 0
    deep_ready = initial_ready and summaries["deep"]["unread_or_stale"] == 0
    return {"revision": state["revision"], "stages": summaries,
        "current_stage": "initial" if not initial_ready else ("deep" if not deep_ready else "qa"),
        "qa_readiness": "not_ready" if not deep_ready else (
            "ready_with_gaps" if summaries["deep"].get("gap") else "ready"),
        "knowledge_records": len(state["records"]),
        "stale_knowledge": sum(bool(r["stale_reasons"]) for r in state["records"].values()),
        "unknowns": sum(len(r.get("unknowns", [])) for r in state["records"].values()),
        "semantic_accuracy": None,
        "notice": "Reading states and source_checked are host attestations; quality checks do not prove semantic truth."}


def review(root, stage="auto", next_batch=False, limit=8, recover=False):
    if limit < 1:
        raise ValueError("Review batch limit must be positive")
    if recover:
        recover_lock(root)
        with writer(root):
            rebuild(root)
    integrity = guard(root)
    state = project(root)
    summary = summarize(state)
    selected_stage = summary["current_stage"] if stage == "auto" else stage
    summary["capture_pass"] = integrity["pass"]
    summary["business_unresolved"]=[{"knowledge_id":r["id"],"unknowns":r.get("unknowns",[]),"stale_reasons":r["stale_reasons"]} for r in state["records"].values() if r.get("unknowns")]
    summary["needs_revalidation_records"]=[r["id"] for r in state["records"].values() if r["stale_reasons"]]
    summary["gaps"] = [{"unit_id": uid, "kind": state["units"][uid]["kind"], "locator": state["units"][uid]["locator"],
        "initial": rows["initial"], "deep": rows["deep"]}
        for uid, rows in state["coverage"].items() if any(r["status"] == "gap" for r in rows.values())]
    if next_batch and selected_stage in STAGES:
        if selected_stage == "deep" and summary["stages"]["initial"]["unread_or_stale"]:
            raise ValueError("Finish/account for initial reading before deep reading")
        pending = [uid for uid, rows in state["coverage"].items() if rows[selected_stage]["status"] in ("unread", "needs_revalidation")]
        summary["selected_stage"] = selected_stage
        summary["next"] = read_units(root, pending[:limit]) if pending else {"items": []}
        summary["remaining_after_batch"] = max(0, len(pending) - limit)
    return summary


def receipt_ranges(root, receipt_ids, state):
    found = defaultdict(list)
    for rid in receipt_ids:
        if not re.fullmatch(r"Q[0-9a-f]{32}", rid):
            raise ValueError("Invalid receipt ID")
        receipt = e.read_json(Path(root) / "knowledge/receipts" / (rid + ".json"))
        checksum = receipt.pop("sha256")
        if sha(receipt) != checksum:
            raise ValueError("Receipt checksum mismatch")
        for item in receipt["ranges"]:
            unit = state["units"].get(item["unit_id"])
            if not unit or unit.get("retired") or unit["fingerprint"] != item["unit_fingerprint"]:
                raise ValueError("Receipt references changed/retired units")
            found[item["unit_id"]].append((item["start"], item["end"]))
    return found


def covered(ranges, length):
    cursor = 0
    for start, end in sorted(ranges):
        if start > cursor:
            return False
        cursor = max(cursor, end)
    return bool(ranges) and cursor >= length


def validate_visual_views(manifest, views):
    renditions = {r["id"]: r for owner in manifest["sources"] + manifest["assets"]
                  for r in owner.get("layout", owner.get("reading_versions", []))}
    valid = set()
    for view in views:
        rendition = renditions.get(view.get("rendition_id"))
        if not rendition or rendition["role"] == "icon" or rendition["sha256"] != view.get("sha256") or not view.get("tool"):
            raise ValueError("Visual view needs an existing content rendition, its current hash and actual tool")
        if not view.get("observation", "").strip():
            raise ValueError("Visual view needs observed content; a file path is insufficient")
        valid.add(rendition["id"])
    return valid


def validate_reference(reference, state):
    unit = state["units"].get(reference.get("unit_id"))
    if not unit or unit.get("retired"):
        raise ValueError("Unknown or retired evidence unit")
    reference = copy.deepcopy(reference)
    fingerprint = reference.get("unit_fingerprint", unit["fingerprint"])
    if fingerprint != unit["fingerprint"]:
        raise ValueError("Evidence unit changed")
    reference["unit_fingerprint"] = fingerprint
    if unit["kind"] == "visual":
        reference["rendition_id"] = unit["rendition"]["id"]
        if "bbox" in reference:
            bbox, dims = reference["bbox"], unit["rendition"].get("dimensions_px")
            if not dims or len(bbox) != 4 or not (0 <= bbox[0] < bbox[2] <= dims[0] and 0 <= bbox[1] < bbox[3] <= dims[1]):
                raise ValueError("Visual region outside its original pixel frame")
    elif "field" in reference:
        metadata = unit.get("native_metadata", {})
        field = reference["field"]
        if field not in metadata or reference.get("value") != metadata[field]:
            raise ValueError("Native evidence field/value does not match the captured original")
    else:
        quote = reference.get("quote")
        start, end = reference.get("start", 0), reference.get("end", len(unit["text"]))
        if type(start) is not int or type(end) is not int or not (0 <= start <= end <= len(unit["text"])):
            raise ValueError("Invalid original text range")
        if unit["text"] and start == end:
            raise ValueError("Empty quote cannot support a claim about nonempty source text")
        if quote is None or unit["text"][start:end] != quote:
            raise ValueError("Evidence quote does not match exact original text range")
        reference.update(start=start, end=end)
    return reference


def commit(root, payload):
    """One journal file is the commit. Index/coverage are recoverable projections."""
    root = Path(root).resolve()
    guard(root)
    with writer(root):
        state, manifest = project(root), e.read_json(root / "manifest.json")
        if type(payload.get("expected_revision")) is not int or payload["expected_revision"] != state["revision"]:
            raise ValueError("Revision changed or absent; read current state, merge and retry")
        model = payload.get("model", "")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Name the host/model honestly; use 'exact version unavailable' when needed")
        ranges = receipt_ranges(root, payload.get("receipt_ids", []), state)
        valid_views = validate_visual_views(manifest, payload.get("visual_reads", []))
        records, readings, replacements = [], [], []
        now = e.now()
        # Assign IDs before validating references between records in one batch.
        proposals = copy.deepcopy(payload.get("records", []))
        for item in proposals:
            item.setdefault("id", "K" + uuid.uuid4().hex[:24])
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,80}", item["id"]):
                raise ValueError("Invalid knowledge ID")
            if item["id"] in state["units"]:
                raise ValueError("Knowledge ID collides with a source reading unit")
        if len({r["id"] for r in proposals}) != len(proposals):
            raise ValueError("Duplicate record ID within transaction")
        future_versions = {uid: r["version"] for uid, r in state["records"].items()}
        for item in proposals:
            future_versions[item["id"]] = future_versions.get(item["id"], 0) + 1
        for item in proposals:
            old = state["records"].get(item["id"])
            if old and not item.get("reason", "").strip():
                raise ValueError("Revising knowledge requires a reason")
            if not all(item.get(key) for key in ("kind", "name", "scope", "claims")):
                raise ValueError("Knowledge requires kind, name, scope and claim-level content")
            review_status = item.get("review_status", "unreviewed")
            if review_status not in REVIEW_STATES:
                raise ValueError("Invalid review state")
            if review_status == "human_reviewed" and not item.get("reviewer"):
                raise ValueError("Human review requires an actual named reviewer")
            if review_status != "unreviewed" and not item.get("review_notes", "").strip():
                raise ValueError("Reviewed claims require source/counterevidence check notes")
            refs, claims = [], []
            for claim in item["claims"]:
                if not claim.get("content", "").strip() or claim.get("authority") not in AUTHORITIES:
                    raise ValueError("Every claim requires content and an explicit authority type")
                evidence = [validate_reference(ref, state) for ref in claim.get("evidence", [])]
                if not evidence and claim["authority"] not in ("background", "suggestion"):
                    raise ValueError("Source-derived claims require exact evidence")
                for ref in evidence:
                    unit = state["units"][ref["unit_id"]]
                    if review_status != "unreviewed":
                        if unit["kind"] == "visual":
                            if unit["rendition"]["id"] not in valid_views:
                                raise ValueError("Reviewed visual claim needs an actual viewing attestation")
                        elif not covered(ranges[unit["id"]], len(unit["text"])):
                            raise ValueError("Reviewed claim evidence must be fully delivered via read receipts")
                    refs.append(ref)
                claims.append({**claim, "evidence": evidence})
            if item["kind"] == "conflict" and len({r["unit_id"] for r in refs}) < 2:
                raise ValueError("Conflict must retain at least two distinct evidence units")
            if item.get("aliases") and not refs:
                raise ValueError("Aliases need bound evidence; they cannot be an ungrounded term map")
            hashes, source_ids = evidence_hashes(manifest), set()
            dependency_ids = set()
            for ref in refs:
                unit = state["units"][ref["unit_id"]]
                source_ids.update(unit["source_ids"])
                dependency_ids.update(unit["source_ids"])
                if unit["owner_id"] in hashes:
                    dependency_ids.add(unit["owner_id"])
                if unit.get("rendition"):
                    dependency_ids.add(unit["rendition"]["id"])
            dependencies = [{"id": uid, "sha256": hashes[uid]} for uid in sorted(dependency_ids)]
            for dependency in item.get("knowledge_dependencies", []):
                if future_versions.get(dependency["id"]) != dependency["version"]:
                    raise ValueError("Knowledge dependency missing or wrong version")
            for relation in item.get("relations", []):
                if relation.get("target_id") not in future_versions or not relation.get("kind"):
                    raise ValueError("Relation needs an existing/batch target and kind")
            record = {**item, "claims": claims, "version": future_versions[item["id"]],
                "supersedes_version": old["version"] if old else None, "created_at": now, "model": model,
                "review_status": review_status, "dependencies": dependencies, "source_ids": sorted(source_ids),
                "aliases": item.get("aliases", []), "unknowns": item.get("unknowns", []),
                "visual_read_ids": [v["rendition_id"] for v in payload.get("visual_reads",[]) if v["rendition_id"] in {state["units"][r["unit_id"]].get("rendition",{}).get("id") for r in refs}], "stale_reasons": [],
                "review_scope": "Source-checked attestation, not business approval or automatic entailment verification"}
            records.append(record)
        current_summary = summarize(state)
        for item in payload.get("reads", []):
            if item.get("stage") not in STAGES:
                raise ValueError("Reading stage must be initial or deep")
            stage, status = item["stage"], item["status"]
            if stage == "deep" and current_summary["stages"]["initial"]["unread_or_stale"]:
                raise ValueError("Initial stage is not accounted for; deep stage cannot start")
            if status not in (("read", "gap") if stage == "initial" else ("deep_read", "gap")):
                raise ValueError("Stage/read status mismatch")
            if not item.get("notes", "").strip():
                raise ValueError("Reading needs observations/explanation or a concrete gap reason")
            ids = item.get("unit_ids", [item.get("unit_id")])
            for uid in ids:
                unit = state["units"].get(uid)
                if not unit or not unit["required"] or unit.get("retired"):
                    raise ValueError("Reading coverage needs active required units")
                if status != "gap":
                    if unit.get("blocked_reason"):
                        raise ValueError("Unrendered/unsupported material cannot be marked read")
                    if not covered(ranges[uid], len(unit["text"])):
                        raise ValueError("Reading receipts do not cover the complete unit")
                    if unit["kind"] == "visual" and unit["rendition"]["id"] not in valid_views:
                        raise ValueError("Visual reading needs current actual-tool viewing attestation")
                for dependency in item.get("knowledge_dependencies", []):
                    if future_versions.get(dependency["id"]) != dependency["version"]:
                        raise ValueError("Reading refers to absent/revised knowledge")
                readings.append({"unit_id": uid, "unit_fingerprint": unit["fingerprint"], "stage": stage,
                    "status": status, "notes": item["notes"], "model": model, "created_at": now,
                    "receipt_ids": payload.get("receipt_ids", []), "visual_read_ids": [unit["rendition"]["id"]] if unit["kind"]=="visual" and status!="gap" else [],
                    "knowledge_dependencies": item.get("knowledge_dependencies", [])})
        for item in payload.get("replace_units", []):
            parent = state["units"].get(item.get("parent_id"))
            if not parent or parent["kind"] not in ("paragraph", "page_text"):
                raise ValueError("Segmentation repair requires a raw paragraph/page-text parent")
            if not item.get("reason", "").strip():
                raise ValueError("Segmentation repair needs a reason")
            cursor, children = 0, []
            for start, end in item["spans"]:
                if not (isinstance(start, int) and isinstance(end, int) and cursor == start < end <= len(parent["text"])):
                    raise ValueError("Replacement spans must cover raw text contiguously without overlap")
                locator = {**parent["locator"], "start": start, "end": end}
                child = {**parent, "id": identity("clause", parent["owner_id"], locator), "kind": "clause",
                    "locator": locator, "text": parent["text"][start:end], "required": True,
                    "parent_id": parent["id"], "segmentation": "host_revised"}
                child.pop("fingerprint")
                child["fingerprint"] = sha(child)
                children.append(child)
                cursor = end
            if cursor != len(parent["text"]):
                raise ValueError("Segmentation repair must not omit any raw characters")
            retired = [u["id"] for u in state["units"].values() if u.get("parent_id") == parent["id"] and u["kind"] == "clause" and not u.get("retired")]
            replacements.append({**item, "retired": retired, "children": children})
        if not (records or readings or replacements):
            raise ValueError("Empty update")
        event = {"revision": state["revision"] + 1, "previous_event_sha256": state["event_sha256"],
            "created_at": now, "model": model, "records": records, "reads": readings, "replace_units": replacements,
            "journal_schema_version":2,"visual_reads":payload.get("visual_reads",[])}
        event["event_sha256"] = sha(event)
        atomic_json(root / "knowledge/events" / f'{event["revision"]:08d}.json', event)
        # If interrupted here, the journal is committed; read/review replay it.
        try:
            rebuild(root)
            projection_status = "current"
        except OSError:
            projection_status = "journal_committed_projection_rebuild_needed"
        return {"revision": event["revision"], "records": [{"id": r["id"], "version": r["version"]} for r in records],
            "read_updates": len(readings), "projection_status": projection_status}


@e.operation_scope
def verify_learning(root):
    errors, warnings = [], []
    try:
        state = project(root)
        manifest = e.read_json(Path(root) / "manifest.json")
        nav = manifest["learning"]["navigation"]
        if e.digest(e.safe_path(root, nav["path"]).read_bytes()) != nav["sha256"]:
            errors.append("Navigation altered outside protocol")
        for record in state["records"].values():
            if record["stale_reasons"]:
                warnings.append(record["id"] + ": needs_revalidation")
                continue
            for claim in record["claims"]:
                for reference in claim["evidence"]:
                    validate_reference(reference, state)
        return {"pass": not errors, "errors": errors, "warnings": warnings,
            "reading": summarize(state), "provenance": "Visual-tool use and semantic checks are attestations; no automated truth guarantee."}
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
        return {"pass": False, "errors": [str(exc)], "warnings": warnings}
