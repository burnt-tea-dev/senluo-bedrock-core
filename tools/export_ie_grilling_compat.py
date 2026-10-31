#!/usr/bin/env python3
"""Create a local IE + Grilling first-person controller from original inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from install_cookery import _atomic_new, _safe_name, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / "adapters/ie-grilling-2.8.203.json"
ARM_PARTS = (("rightArm", 1), ("rightSleeve", 2), ("leftArm", 3), ("leftSleeve", 4))


def _member(path: Path, name: str) -> bytes:
    if not _safe_name(name):
        raise ValueError("unsafe ZIP member path")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = [item for item in archive.infolist() if item.filename == name]
            if len(infos) != 1 or infos[0].is_dir():
                raise ValueError("ZIP member must occur exactly once: " + name)
            if infos[0].file_size > 64 * 1024 * 1024:
                raise ValueError("ZIP member exceeds size limit: " + name)
            return archive.read(infos[0])
    except zipfile.BadZipFile as exc:
        raise ValueError("input is not a valid ZIP archive") from exc


def _json(raw: bytes, label: str):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON input: " + label) from exc


def _player_parts(doc: dict, controller: dict):
    description = doc.get("minecraft:client_entity", {}).get("description", {})
    expressions = description.get("scripts", {}).get("pre_animation", [])
    assignments = [item for item in expressions if isinstance(item, str)
                   and item.startswith("variable.kie_eating_active=")]
    if len(assignments) != 1:
        raise ValueError("IE player must declare its eating-active expression once")
    gate = assignments[0].partition("=")[2]
    if gate.endswith(";"):
        gate = gate[:-1]
    part_visibility = controller.get("render_controllers", {}).get(
        "controller.render.player.first_person", {}).get("part_visibility", [])
    if len(part_visibility) <= 4:
        raise ValueError("IE first-person controller is incomplete")
    return gate, part_visibility


def _controller(doc: dict):
    controllers = doc.get("render_controllers", {})
    result = controllers.get("controller.render.player.first_person")
    if not isinstance(result, dict) or not isinstance(result.get("part_visibility"), list):
        raise ValueError("first-person controller is missing")
    return result


def export_controller(ie_archive: Path, grilling_archive: Path, descriptor: dict):
    ie = descriptor["immersive_eating"]
    grill = descriptor["grilling"]
    if hashlib.sha256(ie_archive.read_bytes()).hexdigest() != ie["archive_sha256"]:
        raise ValueError("Immersive Eating archive hash differs from reviewed input")
    if hashlib.sha256(grilling_archive.read_bytes()).hexdigest() != grill["archive_sha256"]:
        raise ValueError("Grilling archive hash differs from reviewed input")

    player_raw = _member(ie_archive, ie["player_entity_path"])
    ie_controller_raw = _member(ie_archive, ie["controller_path"])
    grilling_raw = _member(grilling_archive, grill["controller_path"])
    if (sha256(player_raw) != ie["player_entity_sha256"]
            or sha256(ie_controller_raw) != ie["controller_sha256"]
            or sha256(grilling_raw) != grill["controller_sha256"]):
        raise ValueError("first-person source file hash differs from reviewed inputs")

    gate, ie_parts = _player_parts(_json(player_raw, ie["player_entity_path"]),
                                   _json(ie_controller_raw, ie["controller_path"]))
    grilling_doc = _json(grilling_raw, grill["controller_path"])
    gr_parts = _controller(grilling_doc)["part_visibility"]
    output_text = grilling_raw.decode("utf-8")
    replacements = {}
    for name, index in ARM_PARTS:
        before = gr_parts[index].get(name)
        ie_value = ie_parts[index].get(name)
        if not isinstance(before, str) or not isinstance(ie_value, str):
            raise ValueError("arm visibility source is missing: " + name)
        source_token = json.dumps(before, ensure_ascii=False, separators=(",", ":"))
        output_token = json.dumps(f"({gate}) ? ({ie_value}) : ({before})",
                                  ensure_ascii=False, separators=(",", ":"))
        if source_token in replacements:
            if replacements[source_token][0] != output_token:
                raise ValueError("arm and sleeve source expressions differ: " + name)
            replacements[source_token][1] += 1
        else:
            replacements[source_token] = [output_token, 1]
    for source_token, (output_token, expected_count) in replacements.items():
        if output_text.count(source_token) != expected_count:
            raise ValueError("Grilling arm source occurrence count differs")
        output_text = output_text.replace(source_token, output_token)

    output = output_text.encode("utf-8")
    result = _json(output, grill["controller_path"])
    generated_parts = _controller(result)["part_visibility"]
    if any(generated_parts[index].get(name) !=
           f"({gate}) ? ({ie_parts[index].get(name)}) : ({gr_parts[index].get(name)})"
           for name, index in ARM_PARTS):
        raise ValueError("generated arm conditions do not match the pinned source inputs")
    expected = descriptor["output_sha256"]
    actual = sha256(output)
    if actual != expected:
        raise ValueError("generated compatibility controller hash differs: " + actual)
    receipt = {
        "schema": 1,
        "output_sha256": actual,
        "output_bytes": len(output),
        "inputs": {"immersive_eating": ie["archive_sha256"], "grilling": grill["archive_sha256"]},
        "source_files": {ie["player_entity_path"]: ie["player_entity_sha256"],
                         ie["controller_path"]: ie["controller_sha256"],
                         grill["controller_path"]: grill["controller_sha256"]},
        "grilling_source": grill["source"],
        "distribution": "user-local output only",
    }
    return output, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ie", required=True, type=Path)
    parser.add_argument("--grilling", required=True, type=Path)
    parser.add_argument("--descriptor", type=Path, default=DEFAULT_DESCRIPTOR)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    receipt_path = Path(str(args.output) + ".receipt.json")
    if args.output.exists() or receipt_path.exists() or args.output.resolve() in {
            args.ie.resolve(), args.grilling.resolve()}:
        raise SystemExit("refusing to overwrite an existing file or an input")
    descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
    output, receipt = export_controller(args.ie, args.grilling, descriptor)
    _atomic_new(args.output, output)
    _atomic_new(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"output": str(args.output), "output_sha256": receipt["output_sha256"],
                      "receipt": str(receipt_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
