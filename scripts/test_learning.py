"""Behavior/integrity tests, not model-understanding or actual-vision claims."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("docpack_v2", Path(__file__).with_name("docpack.py"))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
k = d.knowledge


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "requirements.md"
        self.source.write_text("# 审批限制\nBids are visible only after publishing ends. Exceptions require approval.\nFAR applies.\nPricing Farmwork is unrelated.\n", encoding="utf-8")
        self.pack = self.root / "pack"
        d.build([str(self.source)], self.pack, "Generic technical requirements", doctype="technical")

    def tearDown(self):
        self.temp.cleanup()

    def units(self):
        return k.project(self.pack)["units"]

    def find(self, needle):
        return next(u for u in self.units().values() if u["required"] and needle in u["text"])

    def payload(self, **kw):
        return {"expected_revision": k.project(self.pack)["revision"],
            "model": "synthetic behavioral fixture; no semantic/vision assertion", **kw}

    def ref(self, unit):
        return {"unit_id": unit["id"], "quote": unit["text"]}

    def record(self, unit=None, **kw):
        unit = unit or self.find("FAR")
        return {"kind": "term", "name": "FAR", "scope": "Local source",
            "claims": [{"content": "Scoped test explanation", "authority": "interpretation",
                        "evidence": [self.ref(unit)]}], "review_status": "unreviewed", **kw}

    def mark_initial(self):
        ids = [u["id"] for u in self.units().values() if u["required"] and not u.get("blocked_reason")]
        read = k.read_units(self.pack, ids)
        k.commit(self.pack, self.payload(receipt_ids=[read["receipt_id"]], reads=[
            {"unit_ids": ids, "stage": "initial", "status": "read", "notes": "Synthetic protocol validation; not model understanding."}]))

    def test_receipt_is_not_reading_and_stage_gating(self):
        u = self.find("Bids")
        before = k.review(self.pack)
        read = k.read_units(self.pack, [u["id"]])
        self.assertEqual(before["stages"], k.review(self.pack)["stages"])
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(receipt_ids=[read["receipt_id"]], reads=[
                {"unit_id": u["id"], "stage": "deep", "status": "deep_read", "notes": "Premature"}]))
        self.mark_initial()
        self.assertEqual(k.review(self.pack)["current_stage"], "deep")
        self.assertEqual(k.review(self.pack)["qa_readiness"], "not_ready")

    def test_full_two_stages_and_unknowns(self):
        self.mark_initial()
        ids = list(k.project(self.pack)["coverage"])
        read = k.read_units(self.pack, ids)
        record = self.record(unknowns=["Source does not define an exceptional permission"])
        k.commit(self.pack, self.payload(receipt_ids=[read["receipt_id"]], records=[record],
            reads=[{"unit_id": uid, "stage": "deep", "status": "deep_read",
                    "notes": "Synthetic per-unit protocol assertion, not semantic accuracy."} for uid in ids]))
        report = k.review(self.pack)
        self.assertEqual(report["qa_readiness"], "ready")
        self.assertEqual(report["unknowns"], 1)
        self.assertIsNone(report["semantic_accuracy"])

    def test_word_boundaries_chinese_alias_and_inflection(self):
        self.assertGreater(d.query(self.pack, "bid")["total_hits"], 0)
        far = d.query(self.pack, "FAR")
        self.assertTrue(far["results"])
        self.assertFalse(any("Farmwork" in x["text"] for x in far["results"]))
        self.assertGreater(d.query(self.pack, "审批")["total_hits"], 0)
        k.commit(self.pack, self.payload(records=[self.record(aliases=["容积率"])]))
        results = d.query(self.pack, "容积率")
        self.assertGreater(results["total_hits"], 1)
        self.assertTrue(results["alias_expansions"])
        self.assertFalse(any("Farmwork" in x["text"] for x in results["results"]))

    def test_pagination_and_filters(self):
        first = d.query(self.pack, "FAR", limit=1)
        self.assertIsNotNone(first["next_offset"])
        second = d.query(self.pack, "FAR", limit=1, offset=first["next_offset"])
        self.assertNotEqual(first["results"][0]["id"], second["results"][0]["id"])
        source_id = d.read_json(self.pack / "manifest.json")["sources"][0]["id"]
        self.assertGreater(d.query(self.pack, "Bids", source=source_id, section="审批")["total_hits"], 0)
        self.assertEqual(d.query(self.pack, "Bids", source="missing")["total_hits"], 0)

    def test_long_text_requires_all_receipt_ranges(self):
        path = self.root / "long.txt"
        path.write_text("x" * 9000)
        pack = self.root / "long"
        d.build([str(path)], pack, "Long input")
        uid = next(u["id"] for u in k.project(pack)["units"].values() if u["required"])
        a = k.read_units(pack, [uid], max_chars=2000)
        payload = {"expected_revision": 0, "model": "fixture", "receipt_ids": [a["receipt_id"]],
            "reads": [{"unit_id": uid, "stage": "initial", "status": "read", "notes": "Long text"}]}
        with self.assertRaises(ValueError):
            k.commit(pack, payload)
        b = k.read_units(pack, [uid], offset=2000, max_chars=7000)
        payload["receipt_ids"].append(b["receipt_id"])
        k.commit(pack, payload)
        self.assertEqual(k.review(pack)["stages"]["initial"]["actually_read"], 1)

    def test_invalid_quotes_and_missing_ids_rejected_atomically(self):
        bad = self.record()
        bad["claims"][0]["evidence"][0]["quote"] = "Not in original"
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[bad]))
        bad = self.record()
        bad["claims"][0]["evidence"][0]["unit_id"] = "missing"
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[bad]))
        self.assertEqual(k.project(self.pack)["revision"], 0)

    def test_reviewed_claim_needs_receipt_and_review_notes(self):
        unit = self.find("FAR")
        record = self.record(review_status="source_checked", review_notes="Fixture checks reference protocol, not entailment.")
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[record]))
        read = k.read_units(self.pack, [unit["id"]])
        k.commit(self.pack, self.payload(records=[record], receipt_ids=[read["receipt_id"]]))
        self.assertTrue(d.verify(self.pack)["pass"])
        human = self.record(review_status="human_reviewed", review_notes="Test")
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[human]))

    def test_optimistic_conflict_and_live_writer_lock(self):
        payload = self.payload(records=[self.record()])
        k.commit(self.pack, payload)
        with self.assertRaises(ValueError):
            k.commit(self.pack, payload)
        with k.writer(self.pack):
            with self.assertRaises(ValueError):
                k.commit(self.pack, self.payload(records=[self.record()]))
            with self.assertRaises(ValueError):
                k.recover_lock(self.pack)

    def test_revision_history_and_transitive_invalidation(self):
        result = k.commit(self.pack, self.payload(records=[self.record(id="Kterm")]))
        child = self.record(id="Kdependent", name="DownstreamMeaning",
            knowledge_dependencies=[{"id": "Kterm", "version": 1}])
        k.commit(self.pack, self.payload(records=[child]))
        update = self.record(id="Kterm", reason="New detail found", aliases=["新的术语"])
        k.commit(self.pack, self.payload(records=[update]))
        state = k.project(self.pack)
        self.assertEqual(state["records"]["Kterm"]["version"], 2)
        self.assertEqual(len(state["history"]["Kterm"]), 1)
        self.assertTrue(state["records"]["Kdependent"]["stale_reasons"])
        self.assertEqual(d.query(self.pack, "DownstreamMeaning", kind="term")["total_hits"], 0)
        self.assertEqual(k.read_units(self.pack, ["Kterm"])["items"][0]["history"][0]["version"], 1)

    def test_bound_deep_read_reopens_after_knowledge_revision(self):
        self.mark_initial()
        u = self.find("FAR")
        r = k.read_units(self.pack, [u["id"]])
        k.commit(self.pack, self.payload(records=[self.record(id="Kterm")], receipt_ids=[r["receipt_id"]],
            reads=[{"unit_id": u["id"], "stage": "deep", "status": "deep_read", "notes": "Bound interpretation",
                    "knowledge_dependencies": [{"id": "Kterm", "version": 1}]}]))
        k.commit(self.pack, self.payload(records=[self.record(id="Kterm", reason="Revised meaning")]))
        self.assertEqual(k.project(self.pack)["coverage"][u["id"]]["deep"]["status"], "needs_revalidation")

    def test_relations_and_conflicts_keep_real_sources(self):
        bad = self.record(relations=[{"kind": "defines", "target_id": "missing"}])
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[bad]))
        conflict = self.record(kind="conflict")
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[conflict]))
        conflict["claims"].append({"content": "Second side", "authority": "interpretation",
                                  "evidence": [self.ref(self.find("Exceptions"))]})
        k.commit(self.pack, self.payload(records=[conflict]))
        self.assertEqual(k.review(self.pack)["knowledge_records"], 1)

    def test_projection_failure_replay_and_corrupt_index_fallback(self):
        with patch.object(k, "rebuild", side_effect=OSError("Interrupted after journal commit")):
            result = k.commit(self.pack, self.payload(records=[self.record(name="UniqueNewMeaning")]))
        self.assertEqual(result["projection_status"], "journal_committed_projection_rebuild_needed")
        self.assertGreater(d.query(self.pack, "UniqueNewMeaning")["total_hits"], 0)
        index = self.pack / "knowledge/index.json"
        index.write_text("invalid JSON")
        self.assertGreater(d.query(self.pack, "UniqueNewMeaning")["total_hits"], 0)
        k.review(self.pack, recover=True)
        self.assertTrue(d.verify(self.pack)["pass"])

    def test_journal_and_source_tampering_are_detected(self):
        k.commit(self.pack, self.payload(records=[self.record()]))
        event = self.pack / "knowledge/events/00000001.json"
        data = json.loads(event.read_text())
        data["records"][0]["claims"][0]["content"] = "Unauthorized alteration"
        event.write_text(json.dumps(data))
        self.assertFalse(d.verify(self.pack)["pass"])
        with self.assertRaises(ValueError):
            d.query(self.pack, "FAR")

    def test_original_tamper_blocks_read_and_update(self):
        source = d.read_json(self.pack / "manifest.json")["sources"][0]
        uid = self.find("FAR")["id"]
        (self.pack / source["original"]["path"]).write_bytes(b"changed original")
        with self.assertRaises(ValueError):
            k.read_units(self.pack, [uid])
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[]))

    def test_updated_source_preserves_history_but_not_old_truth(self):
        k.commit(self.pack, self.payload(records=[self.record(id="Kold", name="OldMeaning")]))
        self.mark_initial()
        self.source.write_text("# 新版本\nChanged interpretation and limits.")
        new = self.root / "new"
        d.build([str(self.source)], new, "Updated", previous=str(self.pack))
        state = k.project(new)
        self.assertTrue(state["records"]["Kold"]["stale_reasons"])
        self.assertEqual(d.query(new, "OldMeaning")["total_hits"], 0)
        self.assertEqual(k.review(new)["current_stage"], "initial")
        self.assertTrue(d.verify(new)["pass"])
        self.assertEqual(k.project(self.pack)["records"]["Kold"]["version"], 1)

    def test_segmentation_repair_does_not_omit_original(self):
        clause = self.find("Bids")
        parent = self.units()[clause["parent_id"]]
        k.commit(self.pack, self.payload(records=[self.record(clause, id="Kscope")]))
        payload = self.payload(replace_units=[{"parent_id": parent["id"], "reason": "Repair sentence boundaries",
            "spans": [[0, len(parent["text"])-1]]}])
        with self.assertRaises(ValueError):
            k.commit(self.pack, payload)
        payload["replace_units"][0]["spans"] = [[0, len(parent["text"])]]
        k.commit(self.pack, payload)
        state = k.project(self.pack)
        self.assertTrue(state["records"]["Kscope"]["stale_reasons"])
        active = [u for u in state["units"].values() if u.get("parent_id") == parent["id"] and not u.get("retired")]
        self.assertEqual("".join(u["text"] for u in active), parent["text"])

    def test_visual_path_is_not_viewing(self):
        fitz = d.fitz_module()
        img = self.root / "figure.png"
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 40))
        pix.clear_with(200)
        pix.save(img)
        pack = self.root / "visual"
        d.build([str(img)], pack, "Visual fixture")
        unit = next(u for u in k.project(pack)["units"].values() if u["kind"] == "visual")
        read = k.read_units(pack, [unit["id"]])
        payload = {"expected_revision": 0, "model": "synthetic tool-contract fixture", "receipt_ids": [read["receipt_id"]],
            "reads": [{"unit_id": unit["id"], "stage": "initial", "status": "read", "notes": "Fixture protocol only"}]}
        with self.assertRaises(ValueError):
            k.commit(pack, payload)
        rendition = unit["rendition"]
        payload["visual_reads"] = [{"rendition_id": rendition["id"], "sha256": rendition["sha256"],
            "tool": "synthetic fixture; no actual-view assertion", "observation": "Protocol validation only"}]
        k.commit(pack, payload)
        self.assertEqual(k.review(pack)["stages"]["initial"]["actually_read"], 1)

    def test_explicit_gaps_do_not_count_as_reads(self):
        unit = self.find("Bids")
        k.commit(self.pack, self.payload(reads=[{"unit_id": unit["id"], "stage": "initial",
            "status": "gap", "notes": "Unavailable host capacity in this fixture"}]))
        report = k.review(self.pack)
        self.assertEqual(report["stages"]["initial"]["gap"], 1)
        self.assertEqual(report["stages"]["initial"]["actually_read"], 0)
        self.assertEqual(report["qa_readiness"], "not_ready")

    def test_relocation_and_self_contained_cli(self):
        import subprocess, sys
        k.commit(self.pack, self.payload(records=[self.record(aliases=["容积率"])]))
        moved = self.root / "moved"
        shutil.copytree(self.pack, moved)
        result = subprocess.run([sys.executable, "-B", str(moved / "scripts/docpack.py"),
            "query", "--package", str(moved), "--term", "容积率"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(json.loads(result.stdout)["total_hits"], 0)
        self.assertTrue(d.verify(moved)["pass"])

    def test_multiline_csv_is_not_silently_flattened(self):
        csv = self.root / "fields.csv"
        csv.write_text('Name,Rule\nCode,"First line\nSecond line"\n')
        pack = self.root / "csv"
        d.build([str(csv)], pack, "CSV")
        cells = [u for u in k.project(pack)["units"].values() if u["kind"] == "csv_cell"]
        self.assertTrue(any(u["text"] == "First line\nSecond line" for u in cells))

    def test_unicode_json_line_separators_in_native_data(self):
        import zipfile
        p = self.root / "units.xlsx"
        ns = d.S[1:-1]
        with zipfile.ZipFile(p, "w") as archive:
            archive.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{d.R[1:-1]}"><sheets><sheet name="Units" sheetId="1" r:id="r1"/></sheets></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>AED\u2028per area\u0085year</t></is></c><c r="B1"><f>2*3</f><v/></c><c r="C1" s="1"/></row></sheetData></worksheet>')
        pack = self.root / "unicode"
        d.build([str(p)], pack, "Unicode native data")
        state = k.project(pack)
        cell = next(u for u in state["units"].values() if u["kind"] == "native_cell" and u["locator"]["cell"] == "A1")
        self.assertEqual(cell["text"], "AED\u2028per area\u0085year")
        formula = next(u for u in state["units"].values() if u["kind"] == "native_cell" and u["locator"]["cell"] == "B1")
        self.assertFalse(formula["native_metadata"]["cached_result_present"])
        self.assertTrue(formula["native_metadata"]["value_element_present"])
        k.validate_reference({"unit_id": formula["id"], "field": "formula", "value": "2*3"}, state)
        with self.assertRaises(ValueError):
            k.validate_reference({"unit_id": formula["id"], "field": "formula", "value": "3*3"}, state)
        blank = next(u for u in state["units"].values() if u["kind"] == "native_cell" and u["locator"]["cell"] == "C1")
        self.assertTrue(blank["native_metadata"]["serialized_empty"])

    def test_upgrade_preserves_cell_view_input_snapshot(self):
        import test_evidence
        x = self.root / "history.xlsx"
        test_evidence.xlsx(x)
        old = self.root / "old"
        d.core.build([str(x)], old, "History")
        manifest = d.read_json(old / "manifest.json")
        a = manifest["assets"][0]
        sidecar = d.read_json(old / a["auxiliary"]["path"])
        sidecar.pop("native_schema_version")
        d.write_json(old / a["auxiliary"]["path"], sidecar)
        a["auxiliary"]["sha256"] = d.digest((old / a["auxiliary"]["path"]).read_bytes())
        d.write_json(old / "manifest.json", manifest)
        d.core.cell_view(old, a["id"], "Matrix", ["A1", "B1"])
        original = (old / a["auxiliary"]["path"]).read_bytes()
        new = self.root / "upgraded"
        result = d.upgrade(old, new)
        self.assertTrue(result["pass"], result)
        view = next(r for r in d.read_json(new / "manifest.json")["assets"][0]["reading_versions"] if r["role"] == "structured_cell_view")
        self.assertEqual((new / view["auxiliary_snapshot"]["path"]).read_bytes(), original)
        self.assertEqual((old / a["auxiliary"]["path"]).read_bytes(), original)
        (new / view["auxiliary_snapshot"]["path"]).write_text("tampered")
        self.assertFalse(d.verify(new)["pass"])

    def test_unparsed_native_objects_are_explicit_gaps(self):
        import zipfile, test_evidence
        path = self.root / "annotated.xlsx"
        test_evidence.xlsx(path)
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("xl/comments/comment1.xml", "<comments>Unreviewed cell note</comments>")
            archive.writestr("xl/media/image1.png", test_evidence.png())
        pack = self.root / "annotated"
        d.build([str(path)], pack, "Additional native objects")
        gaps = [u for u in k.project(pack)["units"].values() if u.get("locator", {}).get("native_part")]
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all(u["required"] and u["blocked_reason"] for u in gaps))
        self.assertTrue(all(u["native_metadata"]["retained_in_original"] for u in gaps))

    def test_empty_quote_boolean_offsets_and_revision_are_rejected(self):
        unit = self.find("Bids")
        for reference in [{"unit_id":unit["id"], "start":0, "end":0, "quote":""},
                          {"unit_id":unit["id"], "start":False, "end":True, "quote":"B"}]:
            bad = self.record(unit)
            bad["claims"][0]["evidence"] = [reference]
            with self.assertRaises(ValueError):
                k.commit(self.pack, self.payload(records=[bad]))
        payload = self.payload(records=[self.record()])
        payload["expected_revision"] = False
        with self.assertRaises(ValueError):
            k.commit(self.pack, payload)
        self.assertEqual(k.project(self.pack)["revision"], 0)

    def test_unreadable_native_archive_is_preserved_as_gap(self):
        source = self.root / "unreadable.xlsx"
        source.write_bytes(b"Unreadable native-format fixture")
        pack = self.root / "unreadable"
        report = d.build([str(source)], pack, "Unreadable attachment")
        self.assertTrue(report["pass"], report)
        state = k.project(pack)
        self.assertTrue(any(u.get("locator", {}).get("native_archive") == "unreadable" for u in state["units"].values()))
        original = d.read_json(pack / "manifest.json")["assets"][0]["original"]["path"]
        self.assertEqual((pack / original).read_bytes(), source.read_bytes())

    def test_recover_lock_checks_os_and_real_process_exit(self):
        import subprocess, sys, os
        lock = self.pack / ".knowledge-write-lock"
        lock.mkdir()
        k.atomic_json(lock / "owner.json", {"pid":os.getpid(),"os_name":"nt" if os.name != "nt" else "posix"})
        with self.assertRaises(ValueError):
            k.recover_lock(self.pack)
        self.assertTrue(lock.exists())
        child = subprocess.Popen([sys.executable, "-B", "-c", "pass"])
        child.wait()
        k.atomic_json(lock / "owner.json", {"pid":child.pid,"os_name":os.name})
        k.recover_lock(self.pack)
        self.assertFalse(lock.exists())

    def test_unicode_terms_and_chinese_queries_do_not_match_only_one_character(self):
        source = self.root / "unicode-terms.md"
        source.write_text("# 检索样例\nDébit αβ µs 配额。\n审批需要批准。\n这段只记录评审。\n", encoding="utf-8")
        pack = self.root / "unicode-terms"
        d.build([str(source)], pack, "Unicode terms")
        for term in ["débit", "αβ", "µs", "配额"]:
            self.assertTrue(d.query(pack, term)["results"], term)
        matches = d.query(pack, "审批")["results"]
        self.assertTrue(matches)
        self.assertFalse(any("只记录评审" in x["text"] for x in matches))

    def test_read_knowledge_expands_source_context_without_marking_read(self):
        unit = self.find("Bids")
        with self.assertRaises(ValueError):
            k.commit(self.pack, self.payload(records=[self.record(unit, id=unit["id"])]))
        k.commit(self.pack, self.payload(records=[self.record(unit, id="Ksource")]))
        result = k.read_units(self.pack, ["Ksource"])
        card, evidence = result["items"]
        self.assertEqual(card["expanded_evidence_unit_ids"], [unit["id"]])
        self.assertEqual(evidence["text"], unit["text"])
        self.assertTrue(evidence["context"]["neighbours"])
        self.assertEqual(k.review(self.pack)["stages"]["initial"]["actually_read"], 0)
        changed = self.root / "changed.md"
        changed.write_text("# Replacement\nNew material only.")
        new = self.root / "changed"
        d.build([str(changed)], new, "Source update", previous=str(self.pack))
        historical = k.read_units(new, ["Ksource"])["items"][0]
        self.assertTrue(historical["unavailable_or_changed_evidence_unit_ids"])
        self.assertFalse(historical["expanded_evidence_unit_ids"])


if __name__ == "__main__":
    unittest.main()
