import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/install_cookery.py"
spec = importlib.util.spec_from_file_location("install_cookery", MODULE_PATH)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def make_zip(entries, infos=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = (infos or {}).get(name, zipfile.ZipInfo(name))
            archive.writestr(info, data)
    return out.getvalue()


class InstallerTests(unittest.TestCase):
    def fixture(self, bad_anchor=False, preimage_override=None, bad_position=False, invalid_json_update=False):
        bp, rp, gbp = "Cookery BP/", "Cookery RP/", "GrillingPack/"
        target = "scripts/worker.js"
        source = b"export const marker = 1;\n"
        anchor = "export const marker = 1;"
        replacement = "const hostHook = true;\n"
        manifest_bp = {"header": {"uuid": "bp-uuid", "version": [1, 6, 4]},
                       "modules": [{"uuid": "bp-module", "version": [1, 6, 4], "type": "data"}],
                       "dependencies": [{"uuid": "rp-uuid", "version": [1, 6, 4]},
                                       {"uuid": "engine", "version": "1.21.0"}]}
        manifest_rp = {"header": {"uuid": "rp-uuid", "version": [1, 6, 4]}, "modules": []}
        bp_manifest = json.dumps(manifest_bp, indent=2).encode()
        rp_manifest = json.dumps(manifest_rp, indent=2).encode()
        untouched_info = zipfile.ZipInfo(bp + "unrelated.bin", (2020, 2, 3, 4, 5, 6))
        untouched_info.external_attr = 0o100640 << 16
        updates = {bp + "manifest.json": bp_manifest, rp + "manifest.json": rp_manifest,
                   bp + target: source, bp + "unrelated.bin": b"keep these bytes\x00",
                   gbp + "scripts/core/helper.js": b"export const sdk=1;\n"}
        cookery_bytes = make_zip({k: v for k, v in updates.items() if not k.startswith(gbp)},
                                 {bp + "unrelated.bin": untouched_info})
        spec_doc = {"schema": 1, "archive_sha256": digest(cookery_bytes), "host_uuid": "bp-uuid",
                    "original_files": {target: digest(preimage_override or source)},
                    "patched_files": {target: digest((replacement + source.decode()).encode())},
                    "imports": {},
                    "insertions": [{"path": target, "anchor": anchor if not bad_anchor else "missing anchor",
                                    "position": "sideways" if bad_position else "before", "text": replacement}],
                    "json_updates": [],
                    "copies": {"scripts/core/helper.js": "scripts/api/helper.js"},
                    "owned_helpers": {"scripts/core/helper.js": digest(b"export const sdk=1;\n")}}
        spec_bytes = json.dumps(spec_doc, sort_keys=True).encode()
        g_manifest = json.dumps({"header": {"uuid": "gbp-uuid", "version": [2, 8, 201]}}).encode()
        if invalid_json_update:
            spec_doc["json_updates"] = [{"path": target, "pointer": ["arbitrary", "path"], "value": True}]
            spec_bytes = json.dumps(spec_doc, sort_keys=True).encode()
        grilling_entries = {gbp + "manifest.json": g_manifest,
                            gbp + "host-extensions/board-api.json": spec_bytes,
                            gbp + "scripts/core/helper.js": b"export const sdk=1;\n"}
        grilling_bytes = make_zip(grilling_entries)
        descriptor = {"schema": 1, "id": "test:adapter", "version": "0.1.0",
                      "archive_sha256": digest(cookery_bytes), "host_uuid": "bp-uuid",
                      "resource_uuid": "rp-uuid", "author_version": [1, 6, 4],
                      "output_version": [1, 6, 20001],
                      "companion": {"archive_sha256": digest(grilling_bytes), "bp_uuid": "gbp-uuid",
                                    "version": [2, 8, 201], "spec_path": "host-extensions/board-api.json",
                                    "spec_sha256": digest(spec_bytes)},
                      "owned_helpers": spec_doc["owned_helpers"],
                      "prefixes": {"BP": bp, "RP": rp}}
        return cookery_bytes, grilling_bytes, descriptor, target, bp, rp, gbp

    def paths(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        c, g = root / "cookery.mcaddon", root / "grilling.mcaddon"
        c.write_bytes(data[0]); g.write_bytes(data[1])
        return c, g

    def test_apply_rewrites_only_reviewed_paths_and_preserves_sdk_bytes(self):
        data = self.fixture()
        cookery, grilling = self.paths(data)
        output, receipt = installer.apply_archive(cookery, grilling, data[2])
        self.assertEqual(receipt["version"], [1, 6, 20001])
        self.assertEqual(receipt["input_file_count"], 4)
        self.assertEqual(receipt["output_file_count"], 5)
        self.assertEqual(receipt["unmodified_input_tree"]["file_count"], 1)
        self.assertEqual(receipt["output_tree"]["file_count"], 5)
        self.assertEqual(receipt["manifest_identities"][data[4] + "manifest.json"]["dependencies"],
                         [{"uuid": "rp-uuid", "version": [1, 6, 20001]},
                          {"uuid": "engine", "version": "1.21.0"}])
        with zipfile.ZipFile(io.BytesIO(output)) as adapted:
            names = adapted.namelist()
            self.assertEqual(adapted.read(data[4] + data[3]), b"const hostHook = true;\nexport const marker = 1;\n")
            self.assertEqual(adapted.read(data[4] + "scripts/api/helper.js"), b"export const sdk=1;\n")
            self.assertEqual(adapted.read(data[4] + "unrelated.bin"), b"keep these bytes\x00")
            preserved_info = adapted.getinfo(data[4] + "unrelated.bin")
            self.assertEqual(preserved_info.date_time, (2020, 2, 3, 4, 5, 6))
            self.assertEqual(preserved_info.external_attr, 0o100640 << 16)
            manifest = json.loads(adapted.read(data[4] + "manifest.json"))
            self.assertEqual(manifest["modules"][0]["uuid"], "bp-module")
            self.assertEqual(manifest["modules"][0]["version"], [1, 6, 20001])
            self.assertEqual(json.loads(adapted.read(data[5] + "manifest.json"))["header"]["version"], [1, 6, 20001])

    def test_rejects_preimage_and_anchor_mismatch(self):
        for fixture in (self.fixture(preimage_override=b"changed"), self.fixture(bad_anchor=True)):
            cookery, grilling = self.paths(fixture)
            with self.assertRaises(ValueError):
                installer.apply_archive(cookery, grilling, fixture[2])

    def test_rejects_malformed_insertion_position(self):
        data = self.fixture(bad_position=True)
        cookery, grilling = self.paths(data)
        with self.assertRaisesRegex(ValueError, "invalid insertion"):
            installer.apply_archive(cookery, grilling, data[2])

    def test_rejects_json_updates_outside_fixed_capability(self):
        data = self.fixture(invalid_json_update=True)
        cookery, grilling = self.paths(data)
        with self.assertRaisesRegex(ValueError, "reviewed allow_off_hand"):
            installer.apply_archive(cookery, grilling, data[2])

    def test_rejects_duplicate_and_traversal_zip_names(self):
        for raw in (make_zip({"../escape": b"x"}),):
            tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
            path = Path(tmp.name) / "bad.zip"; path.write_bytes(raw)
            with self.assertRaises(ValueError):
                installer._read_zip(path)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("same", b"a"); archive.writestr("same", b"b")
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "duplicate.zip"; path.write_bytes(out.getvalue())
        with self.assertRaises(ValueError):
            installer._read_zip(path)

    def test_refuses_changed_input_hash(self):
        data = self.fixture()
        cookery, grilling = self.paths(data)
        cookery.write_bytes(cookery.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "Cookery archive hash"):
            installer.apply_archive(cookery, grilling, data[2])


if __name__ == "__main__":
    unittest.main()
