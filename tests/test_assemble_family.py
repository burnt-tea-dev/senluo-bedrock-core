import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("assemble_family", TOOLS / "assemble_family.py")
assembler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembler)
release_spec = importlib.util.spec_from_file_location("build_release", TOOLS / "build_release.py")
build_release = importlib.util.module_from_spec(release_spec)
release_spec.loader.exec_module(build_release)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def make_zip(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)
    return out.getvalue()


class AssembleFamilyTests(unittest.TestCase):
    def fixture(self):
        manifest = json.dumps({"header": {"uuid": "bp-uuid", "version": [1, 2, 3]},
                               "modules": [{"uuid": "module-uuid", "version": [1, 2, 3]}]},
                              indent=2).encode()
        rp_manifest = json.dumps({"header": {"uuid": "rp-uuid", "version": [1, 2, 3]},
                                  "modules": [{"uuid": "rp-module-uuid", "version": [1, 2, 3]}]},
                                 indent=2).encode()
        config = b'{"enabled":false}\n'
        script = b"const label = 'old';\n"
        bp = make_zip({"BP/manifest.json": manifest, "BP/config.json": config,
                       "BP/scripts/main.js": script})
        rp = make_zip({"RP/manifest.json": rp_manifest, "RP/textures/readme.txt": b"texture payload"})
        outer = make_zip({"release/family.mcpack": bp, "release/family-rp.mcpack": rp})
        return outer, manifest, rp_manifest, config, script

    def setup_case(self, root, bad=None):
        outer, manifest, rp_manifest, config, script = self.fixture()
        inputs = root / "inputs"
        inputs.mkdir()
        (inputs / "family.zip").write_bytes(outer)
        raw_audio = b"OggS\x00synthetic-input-bytes"
        (inputs / "raw.ogg").write_bytes(raw_audio)
        recipe_dir = root / "repo" / "families" / "current"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "helpers.js").write_bytes(b"export const helper = 1;\n")
        before_json = config
        after_json = b'{\n  "enabled": true\n}\n'
        before_text = script.decode()
        after_text = "const label = 'new';\n"
        files = {
            "manifest.json": {"kind": "archive", "input": "family",
                              "members": ["release/family.mcpack", "BP/manifest.json"],
                              "sha256": digest(manifest)},
            "config.json": {"kind": "archive", "input": "family",
                            "members": ["release/family.mcpack", "BP/config.json"],
                            "sha256": digest(before_json),
                            "output_sha256": digest(after_json),
                            "transforms": [{"kind": "json_replace", "pointer": ["enabled"],
                                            "before": False, "after": True}]},
            "scripts/main.js": {"kind": "archive", "input": "family",
                                "members": ["release/family.mcpack", "BP/scripts/main.js"],
                                "sha256": digest(script), "output_sha256": digest(after_text.encode()),
                                "transforms": [{"kind": "text_replace", "before": "old", "after": "new"}]},
            "scripts/helper.js": {"kind": "owned", "path": "helpers.js",
                                  "sha256": digest(b"export const helper = 1;\n")},
            "sounds/example.ogg": {"kind": "input", "input": "raw-audio",
                                   "sha256": digest(raw_audio)},
        }
        if bad == "source_hash":
            files["scripts/main.js"]["sha256"] = "0" * 64
        if bad == "post_hash":
            files["scripts/main.js"]["output_sha256"] = "0" * 64
        if bad == "missing_owned":
            files["scripts/helper.js"]["path"] = "absent.js"
        if bad == "unsafe_member":
            files["scripts/main.js"]["members"] = ["release/family.mcpack", "../escape"]
        all_hashes = {p: spec["output_sha256"] if "output_sha256" in spec else spec["sha256"]
                      for p, spec in files.items()}
        rp_files = {
            "manifest.json": {"kind": "archive", "input": "family",
                              "members": ["release/family-rp.mcpack", "RP/manifest.json"],
                              "sha256": digest(rp_manifest)},
            "textures/readme.txt": {"kind": "archive", "input": "family",
                                     "members": ["release/family-rp.mcpack", "RP/textures/readme.txt"],
                                     "sha256": digest(b"texture payload")},
        }
        rp_hashes = {p: spec["sha256"] for p, spec in rp_files.items()}
        recipe = {"schema": 1, "id": "test:family", "version": "1",
                  "inputs": {"family": {"filename": "family.zip", "sha256": digest(outer)},
                             "raw-audio": {"filename": "raw.ogg", "sha256": digest(raw_audio)}},
                  "packs": [{"id": "test-family-bp", "uuid": "bp-uuid", "version": [1, 2, 3],
                             "side": "BP", "modules": [{"uuid": "module-uuid", "version": [1, 2, 3]}],
                             "files": files,
                             "expected_tree": {"sha256": assembler._tree_fingerprint(all_hashes),
                                               "files": all_hashes}},
                            {"id": "test-family-rp", "uuid": "rp-uuid", "version": [1, 2, 3],
                             "side": "RP", "modules": [{"uuid": "rp-module-uuid", "version": [1, 2, 3]}],
                             "files": rp_files,
                             "expected_tree": {"sha256": assembler._tree_fingerprint(rp_hashes),
                                               "files": rp_hashes}}],
                  "order": {"BP": ["test-family-bp"], "RP": ["test-family-rp"]}}
        recipe_path = recipe_dir / "recipe.json"
        recipe_path.write_text(json.dumps(recipe, indent=2), encoding="utf-8")
        return recipe, recipe_path, inputs, root / "output"

    def test_assembles_nested_archive_owned_file_transforms_and_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            recipe, recipe_path, inputs, output = self.setup_case(Path(td))
            receipt = assembler.assemble(recipe, recipe_path, inputs, output)
            self.assertEqual(receipt["packs"][0]["tree_sha256"], recipe["packs"][0]["expected_tree"]["sha256"])
            self.assertTrue((output / "test-family-bp.mcpack").is_file())
            self.assertEqual(json.loads((output / "world_behavior_packs.json").read_text())[0]["pack_id"], "bp-uuid")
            with zipfile.ZipFile(output / "test-family-bp.mcpack") as pack:
                self.assertEqual(json.loads(pack.read("config.json")), {"enabled": True})
                self.assertIn(b"label = 'new'", pack.read("scripts/main.js"))
                self.assertEqual(pack.read("scripts/helper.js"), b"export const helper = 1;\n")
                self.assertEqual(pack.read("sounds/example.ogg"), b"OggS\x00synthetic-input-bytes")
            aggregate_path = output / "family.mcaddon"
            aggregate_raw = aggregate_path.read_bytes()
            self.assertEqual(receipt["aggregate"]["bytes"], len(aggregate_raw))
            self.assertEqual(receipt["aggregate"]["sha256"], digest(aggregate_raw))
            with zipfile.ZipFile(aggregate_path) as aggregate:
                self.assertEqual(set(aggregate.namelist()), {"test-family-bp.mcpack", "test-family-rp.mcpack"})
                for filename in aggregate.namelist():
                    standalone = (output / filename).read_bytes()
                    self.assertEqual(aggregate.read(filename), standalone)
                    with zipfile.ZipFile(io.BytesIO(aggregate.read(filename))) as nested:
                        manifest = json.loads(nested.read("manifest.json"))
                        self.assertEqual(manifest["header"]["uuid"], "bp-uuid" if "-bp." in filename else "rp-uuid")

    def test_pack_reader_reuses_outer_index_and_one_nested_archive(self):
        outer, _, _, config, script = self.fixture()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "outer.mcaddon"
            path.write_bytes(outer)
            reader = assembler._PackArchiveReader()
            original_zipfile = zipfile.ZipFile
            try:
                with mock.patch.object(assembler.zipfile, "ZipFile", wraps=original_zipfile) as open_zip:
                    self.assertEqual(reader.read(path, ["release/family.mcpack", "BP/config.json"]), config)
                    self.assertEqual(reader.read(path, ["release/family.mcpack", "BP/scripts/main.js"]), script)
                    self.assertEqual(open_zip.call_count, 2)
            finally:
                reader.close()

    def test_rejects_hash_mismatches_unsafe_members_and_dangling_sources_without_output(self):
        for bad in ("source_hash", "post_hash", "missing_owned", "unsafe_member"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as td:
                recipe, recipe_path, inputs, output = self.setup_case(Path(td), bad)
                with self.assertRaises(ValueError):
                    assembler.assemble(recipe, recipe_path, inputs, output)
                self.assertFalse(output.exists())

    def test_rejects_changed_input_before_creating_output(self):
        with tempfile.TemporaryDirectory() as td:
            recipe, recipe_path, inputs, output = self.setup_case(Path(td))
            (inputs / "family.zip").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "input hash differs"):
                assembler.assemble(recipe, recipe_path, inputs, output)
            self.assertFalse(output.exists())

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as td:
            recipe, recipe_path, inputs, output = self.setup_case(Path(td))
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                assembler.assemble(recipe, recipe_path, inputs, output)

    def test_release_builder_keeps_toolkit_and_sdk_versions_independent_and_zips_only_allowlist(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "source"
            files = {
                "LICENSE": "license text",
                "PUBLICATION.json": "",
                "README.md": "toolkit source, no family recipe",
                "package.json": json.dumps({"name": "senluo-bedrock-core", "version": "0.2.0"}),
                "sdk.json": json.dumps({"schema": 1, "version": "0.1.0", "files": {}}),
                "release-history.json": "",
                "tools/build_release.py": "public release tool",
                "tools/assemble_family.py": "public generic assembler",
                "tests/test_assemble_family.py": "synthetic tests only",
                "docs/FAMILY-ASSEMBLY.md": "example recipe path only",
            }
            names = sorted(files)
            files["PUBLICATION.json"] = json.dumps({"schema": 1, "files": names})
            toolkit_payloads = {name: digest(files[name].encode()) for name in (
                "PUBLICATION.json", "README.md", "package.json", "tools/build_release.py",
                "tools/assemble_family.py", "tests/test_assemble_family.py", "docs/FAMILY-ASSEMBLY.md")}
            files["release-history.json"] = json.dumps({"schema": 1,
                "0.1.0": {"payloads": {}, "cookery_version": [1, 6, 4]},
                "0.2.0": {"sdk_version": "0.1.0", "toolkit_version": "0.2.0",
                           "payloads": toolkit_payloads}})
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            stray = root / "incoming/private-author-sound.ogg"
            stray.parent.mkdir(parents=True)
            stray.write_bytes(b"must not ship")
            output = Path(td) / "release-output"
            git_names = ("\0".join(names) + "\0").encode()
            with mock.patch.object(build_release, "ROOT", root), \
                    mock.patch.object(build_release.subprocess, "check_output", return_value=git_names), \
                    mock.patch.object(sys, "argv", ["build_release.py", "--output", str(output)]):
                build_release.main()
            self.assertTrue((output / "senluo-core-toolkit-0.2.0-source.zip").is_file())
            self.assertTrue((output / "senluo-core-0.1.0-sdk.zip").is_file())
            self.assertFalse((output / "senluo-core-0.1.0-source.zip").exists())
            with zipfile.ZipFile(output / "senluo-core-toolkit-0.2.0-source.zip") as toolkit:
                self.assertEqual(set(toolkit.namelist()), set(names))
                self.assertNotIn("incoming/private-author-sound.ogg", toolkit.namelist())
            (root / "tools/assemble_family.py").write_text("tampered", encoding="utf-8")
            with mock.patch.object(build_release, "ROOT", root), \
                    mock.patch.object(build_release.subprocess, "check_output", return_value=git_names):
                with self.assertRaisesRegex(ValueError, "Toolkit release payload changed"):
                    build_release.validate()


if __name__ == "__main__":
    unittest.main()
