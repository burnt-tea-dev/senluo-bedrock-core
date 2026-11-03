"""Public-minimal build contract: exactly Grilling and adapted Cookery, no optional addons.

These tests exercise real CLI entry points, ZIP IO, manifests, receipts and
rollback on synthetic archives. They do not contain author assets or imply
Bedrock client acceptance.
"""
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import assemble_family
import build_owned_family_recipe as builder


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def zip_bytes(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)
    return buf.getvalue()


class PublicMinimalTests(unittest.TestCase):
    def fixture(self, root):
        descriptor = json.loads(builder.PUBLIC_MINIMAL_DESCRIPTOR.read_text())
        by_id = {p["id"]: p for p in descriptor["packs"]}
        entries = {"grilling": {}, "cookery": {}}
        for pack in descriptor["packs"]:
            dependencies = []
            if pack["id"] == "grilling-bp":
                dependencies = [
                    {"uuid": by_id["grilling-rp"]["uuid"], "version": [2, 8, 212]},
                    {"uuid": by_id["cookery-bp"]["uuid"], "version": [1, 6, 4]},
                    {"module_name": "@minecraft/server", "version": "2.12.0-beta"},
                ]
            elif pack["id"] == "grilling-rp":
                dependencies = [{"uuid": by_id["cookery-rp"]["uuid"], "version": [1, 6, 4]}]
            elif pack["id"] == "cookery-bp":
                dependencies = [{"uuid": by_id["cookery-rp"]["uuid"], "version": [1, 6, 20012]}]
            manifest = {
                "format_version": 2,
                "header": {"uuid": pack["uuid"], "version": pack["version"],
                           "min_engine_version": [1, 26, 60]},
                "modules": [{"uuid": m["uuid"], "version": m["version"], "type": "data"}
                            for m in pack["modules"]],
                "dependencies": dependencies,
            }
            prefix = pack["id"] + "/"
            entries[pack["input"]][prefix + "manifest.json"] = (
                json.dumps(manifest, indent=2) + "\n").encode()
            if pack["id"] == "grilling-bp":
                entries["grilling"][prefix + "entities/player.json"] = json.dumps({
                    "minecraft:entity": {"description": {"identifier": "minecraft:player",
                        "properties": {"kaleidoscope_grilling:held_frame": {
                            "type": "int", "range": [0, 1000000], "default": 0}}}}}).encode()
                entries["grilling"][prefix + "scripts/main.js"] = b"// G gameplay remains untouched\n"
            if pack["id"] == "grilling-rp":
                entries["grilling"][prefix + "textures/held.bin"] = b"G resource unchanged"
            if pack["id"] == "cookery-bp":
                entries["cookery"][prefix + "scripts/host.js"] = b"// locally adapted Cookery host\n"
            if pack["id"] == "cookery-rp":
                entries["cookery"][prefix + "textures/host.bin"] = b"Cookery resource unchanged"
        for input_id, source in entries.items():
            payload = zip_bytes(source)
            (root / descriptor["inputs"][input_id]["filename"]).write_bytes(payload)
            descriptor["inputs"][input_id]["sha256"] = digest(payload)
        return descriptor, entries

    def test_profile_cli_builds_four_paired_packs_from_only_two_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, originals = self.fixture(root)
            original_hashes = {key: digest((root / pin["filename"]).read_bytes())
                               for key, pin in descriptor["inputs"].items()}
            original_read = Path.read_text

            def read(path, *args, **kwargs):
                if path == builder.PUBLIC_MINIMAL_DESCRIPTOR:
                    return json.dumps(descriptor)
                return original_read(path, *args, **kwargs)

            recipe_path = root / "recipe.json"
            with patch.object(Path, "read_text", read), redirect_stdout(io.StringIO()):
                builder.main(["--profile", "public-minimal", "--inputs", str(root),
                              "--output", str(recipe_path)])
            recipe = json.loads(recipe_path.read_text())
            self.assertEqual(set(recipe["inputs"]), {"grilling", "cookery"})
            self.assertEqual({p["id"] for p in recipe["packs"]},
                             {"grilling-bp", "grilling-rp", "cookery-bp", "cookery-rp"})
            self.assertTrue(recipe["require_resolved_dependencies"])
            self.assertEqual({p["id"] for p in recipe["packs"] if p["files"]["manifest.json"].get("transforms")},
                             {"grilling-bp", "grilling-rp"})

            output = root / "minimal-output"
            with redirect_stdout(io.StringIO()):
                assemble_family.main(["--recipe", str(recipe_path), "--inputs",
                                      str(root), "--output", str(output)])
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(len(receipt["packs"]), 4)
            self.assertEqual(receipt["behavior_player_definition"]["pack_id"], "grilling-bp")
            self.assertEqual(len(json.loads((output / "world_behavior_packs.json").read_text())), 2)
            self.assertEqual(len(json.loads((output / "world_resource_packs.json").read_text())), 2)
            self.assertEqual(json.loads((output / "world_behavior_packs.json").read_text())[0]
                             ["pack_id"], next(p["uuid"] for p in descriptor["packs"] if p["id"] == "grilling-bp"))
            self.assertEqual(set(zipfile.ZipFile(output / "family.mcaddon").namelist()),
                             {p["id"] + ".mcpack" for p in descriptor["packs"]})
            for pack in descriptor["packs"]:
                with zipfile.ZipFile(output / (pack["id"] + ".mcpack")) as built:
                    original = {name[len(pack["id"]) + 1:]: raw
                                for name, raw in originals[pack["input"]].items()
                                if name.startswith(pack["id"] + "/")}
                    self.assertEqual(set(built.namelist()), set(original))
                    for name, raw in original.items():
                        if name != "manifest.json" or not pack["id"].startswith("grilling"):
                            self.assertEqual(built.read(name), raw)
                        else:
                            before, after = json.loads(raw), json.loads(built.read(name))
                            target_uuid = descriptor["manifest_dependency_updates"][pack["id"]]["uuid"]
                            source_dep = next(d for d in before["dependencies"] if d.get("uuid") == target_uuid)
                            new_dep = next(d for d in after["dependencies"] if d.get("uuid") == target_uuid)
                            self.assertEqual(source_dep["version"], [1, 6, 4])
                            self.assertEqual(new_dep["version"], [1, 6, 20012])
                            source_dep["version"] = [1, 6, 20012]
                            self.assertEqual(before, after)
            for key, expected in original_hashes.items():
                self.assertEqual(digest((root / descriptor["inputs"][key]["filename"]).read_bytes()), expected)

    def test_pinned_public_profile_matches_current_cookery_and_grilling_inputs(self):
        public = json.loads(builder.PUBLIC_MINIMAL_DESCRIPTOR.read_text())
        family = json.loads(builder.DEFAULT_DESCRIPTOR.read_text())
        cookery = json.loads((ROOT / "adapters/cookery-1.6.4-grilling-2.8.212-station-performance.json").read_text())
        self.assertEqual(set(public["inputs"]), {"grilling", "cookery"})
        self.assertEqual({key: public["inputs"][key]["sha256"] for key in public["inputs"]},
                         {key: family["inputs"][key]["sha256"] for key in public["inputs"]})
        self.assertEqual(public["inputs"]["grilling"]["sha256"], cookery["companion"]["archive_sha256"])
        self.assertEqual(public["source_descriptors"]["cookery_author_archive_sha256"],
                         cookery["archive_sha256"])
        self.assertEqual(public["manifest_dependency_updates"]["grilling-bp"]["after"],
                         cookery["output_version"])
        self.assertEqual(public["manifest_dependency_updates"]["grilling-rp"]["after"],
                         cookery["output_version"])
        self.assertEqual(public["manifest_dependency_updates"]["grilling-bp"]["before"],
                         cookery["author_version"])
        self.assertEqual({p["id"] for p in public["packs"]},
                         {"grilling-bp", "grilling-rp", "cookery-bp", "cookery-rp"})

    def test_manifest_preimage_mismatch_rejected_before_recipe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, _ = self.fixture(root)
            descriptor["manifest_dependency_updates"]["grilling-bp"]["before"] = [1, 6, 5]
            with self.assertRaisesRegex(ValueError, "manifest dependency preimage differs"):
                builder.build_recipe(descriptor, root)

    def test_extra_optional_inputs_and_wrong_pack_dependency_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, _ = self.fixture(root)
            extra = copy.deepcopy(descriptor)
            extra["inputs"]["immersive-eating"] = {"filename": "ie.mcaddon", "sha256": "0" * 64}
            with self.assertRaisesRegex(ValueError, "exactly its selected inputs"):
                builder.build_recipe(extra, root)
            bad = copy.deepcopy(descriptor)
            bad["manifest_dependency_updates"]["grilling-rp"]["uuid"] = "not-a-selected-pack"
            with self.assertRaisesRegex(ValueError, "does not match selected pack"):
                builder.build_recipe(bad, root)

    def test_corrupted_archive_and_recipe_hash_fail_without_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, _ = self.fixture(root)
            file = root / descriptor["inputs"]["grilling"]["filename"]
            original = file.read_bytes()
            file.write_bytes(original + b"corrupt")
            with self.assertRaisesRegex(ValueError, "input hash differs"):
                builder.build_recipe(descriptor, root)
            file.write_bytes(original)
            recipe = builder.build_recipe(descriptor, root)
            recipe["packs"][0]["files"]["manifest.json"]["output_sha256"] = "0" * 64
            path = root / "recipe.json"
            path.write_text(json.dumps(recipe))
            output = root / "not-published"
            with self.assertRaisesRegex(ValueError, "file output hash differs"):
                assemble_family.assemble(recipe, path, root, output)
            self.assertFalse(output.exists())

    def test_external_uuid_dependency_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            descriptor, originals = self.fixture(root)
            source = originals["cookery"]
            manifest_path = "cookery-bp/manifest.json"
            doc = json.loads(source[manifest_path])
            doc["dependencies"].append({"uuid": "unknown-addon-bp", "version": [1, 0, 0]})
            source[manifest_path] = json.dumps(doc).encode()
            new_raw = zip_bytes(source)
            source_file = root / descriptor["inputs"]["cookery"]["filename"]
            source_file.write_bytes(new_raw)
            descriptor["inputs"]["cookery"]["sha256"] = digest(new_raw)
            recipe = builder.build_recipe(descriptor, root)
            recipe_path = root / "recipe.json"
            recipe_path.write_text(json.dumps(recipe))
            output = root / "not-published"
            with self.assertRaisesRegex(ValueError, "unresolved pack dependency"):
                assemble_family.assemble(recipe, recipe_path, root, output)
            self.assertFalse(output.exists())

    def test_profile_descriptor_is_mutually_exclusive_with_history_selector(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(SystemExit) as raised:
                builder.main(["--profile", "public-minimal", "--descriptor",
                              "adapters/owned-t194-g203-w180.json",
                              "--inputs", str(root), "--output", str(root / "recipe.json")])
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
