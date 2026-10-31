import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from build_grilling_input import build as build_grilling_input
from export_ie_grilling_compat import export_controller
import install_cookery_from_descriptor as cookery_cli


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def make_zip(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)
    return output.getvalue()


class PortAdapterTests(unittest.TestCase):
    def test_grilling_exporter_uses_descriptor_specific_tree_pins(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source"
            bp = source / "projects/grilling/gameplay_core/behavior_pack"
            rp = source / "projects/grilling/gameplay_core/resource_pack"
            bp.mkdir(parents=True)
            rp.mkdir(parents=True)
            (bp / "manifest.json").write_bytes(b"bp manifest")
            (bp / "owned.js").write_bytes(b"owned bp")
            (rp / "manifest.json").write_bytes(b"rp manifest")
            bp_hashes = {p.relative_to(bp).as_posix(): digest(p.read_bytes()) for p in sorted(bp.rglob("*")) if p.is_file()}
            rp_hashes = {p.relative_to(rp).as_posix(): digest(p.read_bytes()) for p in sorted(rp.rglob("*")) if p.is_file()}
            tree = lambda files: {"sha256": digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()),
                                  "files": len(files)}
            descriptor = {"companion": {"runtime_trees": {"BP": tree(bp_hashes), "RP": tree(rp_hashes)}}}
            first = build_grilling_input(source, descriptor)
            self.assertEqual(first, build_grilling_input(source, descriptor))
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertEqual(archive.read("BP/owned.js"), b"owned bp")
                self.assertEqual(archive.read("RP/manifest.json"), b"rp manifest")
            (rp / "manifest.json").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "reviewed Grilling tree: RP"):
                build_grilling_input(source, descriptor)

    def test_descriptor_cli_calls_existing_cookery_installer(self):
        installer_tests_spec = importlib.util.spec_from_file_location(
            "test_install_cookery", Path(__file__).resolve().parent / "test_install_cookery.py")
        installer_tests = importlib.util.module_from_spec(installer_tests_spec)
        installer_tests_spec.loader.exec_module(installer_tests)
        data = installer_tests.InstallerTests().fixture()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cookery, grilling = root / "cookery.mcaddon", root / "grilling.mcaddon"
            cookery.write_bytes(data[0]); grilling.write_bytes(data[1])
            descriptor = root / "adapter.json"
            descriptor.write_text(json.dumps(data[2]), encoding="utf-8")
            output = root / "adapted.mcaddon"
            cookery_cli.main(["--cookery", str(cookery), "--grilling", str(grilling),
                              "--descriptor", str(descriptor), "--output", str(output)])
            receipt = json.loads(Path(str(output) + ".receipt.json").read_text())
            self.assertEqual(digest(output.read_bytes()), receipt["output_sha256"])
            self.assertEqual(receipt["version"], [1, 6, 20001])

    def test_ie_grilling_export_reproduces_reviewed_composition(self):
        player_path = "IE/RP/entity/player.entity.json"
        ie_controller_path = "IE/RP/render_controllers/kie_player_first_person.render_controllers.json"
        grilling_controller_path = "RP/render_controllers/java_eating_player.render_controllers.json"
        player = json.dumps({"minecraft:client_entity": {"description": {"scripts": {
            "pre_animation": ["variable.kie_eating_active=(query.is_first_person && query.main_hand_item_use_duration>0);"]}}}},
            separators=(",", ":")).encode()
        ie_controller = json.dumps({"render_controllers": {"controller.render.player.first_person": {
            "part_visibility": [{"*": False}, {"rightArm": "IE_RIGHT"}, {"rightSleeve": "IE_RIGHT"},
                                {"leftArm": "IE_LEFT"}, {"leftSleeve": "IE_LEFT"}]}}},
            separators=(",", ":")).encode()
        grilling_controller = json.dumps({"format_version": "1.8.0", "render_controllers": {
            "controller.render.player.first_person": {"part_visibility": [
                {"*": False}, {"rightArm": "GRILL_RIGHT"}, {"rightSleeve": "GRILL_RIGHT"},
                {"leftArm": "GRILL_LEFT"}, {"leftSleeve": "GRILL_LEFT"}]}}},
            separators=(",", ":")).encode()
        ie = make_zip({player_path: player, ie_controller_path: ie_controller})
        grilling = make_zip({grilling_controller_path: grilling_controller})
        descriptor = {
            "immersive_eating": {"archive_sha256": digest(ie), "player_entity_path": player_path,
                "player_entity_sha256": digest(player), "controller_path": ie_controller_path,
                "controller_sha256": digest(ie_controller)},
            "grilling": {"archive_sha256": digest(grilling), "controller_path": grilling_controller_path,
                "controller_sha256": digest(grilling_controller), "source": {"commit": "synthetic"}},
            "output_sha256": "d4af47c315c4e7ac64a3e9b7eb0fa086588b6d1d0303a02708c73e65942dcf28"}
        with tempfile.TemporaryDirectory() as td:
            ie_path, grilling_path = Path(td) / "ie.mcaddon", Path(td) / "grilling.zip"
            ie_path.write_bytes(ie); grilling_path.write_bytes(grilling)
            output, receipt = export_controller(ie_path, grilling_path, descriptor)
            self.assertEqual(digest(output), descriptor["output_sha256"])
            self.assertEqual(receipt["output_bytes"], len(output))
            with zipfile.ZipFile(io.BytesIO(grilling)) as original:
                source = json.loads(original.read(grilling_controller_path))
            generated = json.loads(output)
            self.assertEqual(source["render_controllers"]["controller.render.player.first_person"]["part_visibility"][1]["rightArm"],
                             "GRILL_RIGHT")
            self.assertEqual(generated["render_controllers"]["controller.render.player.first_person"]["part_visibility"][1]["rightArm"],
                             "((query.is_first_person && query.main_hand_item_use_duration>0)) ? (IE_RIGHT) : (GRILL_RIGHT)")


if __name__ == "__main__":
    unittest.main()
