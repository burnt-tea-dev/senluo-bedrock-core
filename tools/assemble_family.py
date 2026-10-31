#!/usr/bin/env python3
"""Build reviewed local Bedrock packs from hash-pinned recipe inputs.

This tool assembles files only. It does not download inputs or install packs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from install_cookery import MAX_ENTRIES, MAX_MEMBER, MAX_TOTAL, _atomic_new, _safe_name


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pointer_parent(doc, pointer):
    if not isinstance(pointer, list) or not pointer or any(not isinstance(p, str) for p in pointer):
        raise ValueError("invalid JSON pointer")
    node = doc
    for part in pointer[:-1]:
        if not isinstance(node, dict) or part not in node:
            raise ValueError("JSON pointer parent missing")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError("JSON pointer parent is not an object")
    return node, pointer[-1]


def _transform(raw: bytes, operations: list, label: str) -> bytes:
    for operation in operations:
        kind = operation.get("kind")
        if kind == "text_replace":
            before, after = operation.get("before"), operation.get("after")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("text transform target is not UTF-8: " + label) from exc
            if not isinstance(before, str) or not before or text.count(before) != 1 or not isinstance(after, str):
                raise ValueError("text transform must match one exact source string: " + label)
            raw = text.replace(before, after, 1).encode("utf-8")
        elif kind == "json_replace":
            try:
                doc = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("JSON transform target is invalid: " + label) from exc
            parent, leaf = _pointer_parent(doc, operation.get("pointer"))
            if leaf not in parent or parent[leaf] != operation.get("before"):
                raise ValueError("JSON transform preimage differs: " + label)
            parent[leaf] = operation.get("after")
            raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        else:
            raise ValueError("unsupported transform kind: " + str(kind))
    return raw


def _validate_zip(zf: zipfile.ZipFile):
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ValueError("archive contains too many entries")
    names = set()
    total = 0
    for info in infos:
        name = info.filename
        if not _safe_name(name):
            raise ValueError("unsafe ZIP path")
        if name in names:
            raise ValueError("duplicate ZIP path")
        names.add(name)
        if info.file_size > MAX_MEMBER:
            raise ValueError("ZIP member exceeds size limit")
        total += info.file_size
        if total > MAX_TOTAL:
            raise ValueError("archive exceeds uncompressed size limit")
    return {info.filename: info for info in infos}


class _PackArchiveReader:
    """Reuse ZIP indexes and one bounded nested pack while processing a pack."""

    def __init__(self):
        self.outer_path = None
        self.outer = None
        self.outer_entries = None
        self.nested_key = None
        self.nested_buffer = None
        self.nested = None
        self.nested_entries = None

    def close(self):
        self._close_nested()
        if self.outer is not None:
            self.outer.close()
            self.outer = None
            self.outer_entries = None
            self.outer_path = None

    def _close_nested(self):
        if self.nested is not None:
            self.nested.close()
            self.nested = None
        if self.nested_buffer is not None:
            self.nested_buffer.close()
            self.nested_buffer = None
        self.nested_entries = None
        self.nested_key = None

    def _open_outer(self, path: Path):
        resolved = path.resolve()
        if self.outer_path == resolved:
            return
        self.close()
        self.outer = zipfile.ZipFile(path, "r")
        self.outer_entries = _validate_zip(self.outer)
        self.outer_path = resolved

    def read(self, path: Path, members: list[str]) -> bytes:
        if not isinstance(members, list) or not members:
            raise ValueError("archive source requires a nonempty members chain")
        for member in members:
            if not isinstance(member, str) or not _safe_name(member):
                raise ValueError("unsafe archive member path")
        self._open_outer(path)
        current_zip, entries = self.outer, self.outer_entries
        selected_prefix = []
        for index, member in enumerate(members):
            info = entries.get(member)
            if info is None or info.is_dir():
                raise ValueError("archive member missing: " + member)
            if index == len(members) - 1:
                return current_zip.read(info)
            selected_prefix.append(member)
            nested_key = (self.outer_path, tuple(selected_prefix))
            if self.nested_key == nested_key:
                current_zip, entries = self.nested, self.nested_entries
                continue
            raw = current_zip.read(info)
            if len(raw) > MAX_MEMBER:
                raise ValueError("selected archive member exceeds size limit")
            self._close_nested()
            try:
                self.nested_buffer = io.BytesIO(raw)
                self.nested = zipfile.ZipFile(self.nested_buffer, "r")
                self.nested_entries = _validate_zip(self.nested)
            except zipfile.BadZipFile as exc:
                self._close_nested()
                raise ValueError("input is not a valid nested ZIP archive") from exc
            self.nested_key = nested_key
            current_zip, entries = self.nested, self.nested_entries
        raise ValueError("archive member chain did not select a file")


def _read_archive_source(path: Path, members: list[str]) -> bytes:
    reader = _PackArchiveReader()
    try:
        return reader.read(path, members)
    finally:
        reader.close()


def _safe_output_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not _safe_name(relative):
        raise ValueError("unsafe output path")
    path = root.joinpath(*PurePosixPath(relative).parts)
    return path


def _load_and_verify_inputs(recipe: dict, inputs_dir: Path):
    inputs = recipe.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("recipe inputs must be a nonempty object")
    verified = {}
    for key, spec in inputs.items():
        if not isinstance(key, str) or not isinstance(spec, dict):
            raise ValueError("invalid input declaration")
        filename = spec.get("filename")
        if not isinstance(filename, str) or not _safe_name(filename) or "/" in filename:
            raise ValueError("input filename must be a plain filename")
        path = inputs_dir / filename
        if not path.is_file():
            raise ValueError("input file missing: " + filename)
        actual = file_sha256(path)
        if actual != spec.get("sha256"):
            raise ValueError("input hash differs: " + filename)
        verified[key] = {"path": path, "sha256": actual, "filename": filename}
    return verified


def _tree_fingerprint(files: dict[str, str]) -> str:
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(canonical)


def assemble(recipe: dict, recipe_path: Path, inputs_dir: Path, output: Path) -> dict:
    if recipe.get("schema") != 1:
        raise ValueError("unsupported recipe schema")
    packs = recipe.get("packs")
    if not isinstance(packs, list) or not packs:
        raise ValueError("recipe packs must be a nonempty list")
    output = output.absolute()
    if output.exists():
        raise ValueError("refusing to replace existing output directory")
    verified = _load_and_verify_inputs(recipe, inputs_dir)

    # All source files are hash-checked before creating any output directory.
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="." + output.name + ".", dir=output.parent))
    pack_receipts = []
    world_lists = {"BP": [], "RP": []}
    archive_reader = None
    try:
        pack_ids = set()
        for pack in packs:
            if archive_reader is not None:
                archive_reader.close()
            archive_reader = _PackArchiveReader()
            pack_id, side = pack.get("id"), pack.get("side")
            version, pack_uuid = pack.get("version"), pack.get("uuid")
            if not isinstance(pack_id, str) or not pack_id or not _safe_name(pack_id) or "/" in pack_id or pack_id in pack_ids:
                raise ValueError("pack ids must be unique nonempty strings")
            pack_ids.add(pack_id)
            if side not in ("BP", "RP") or not isinstance(pack_uuid, str):
                raise ValueError("pack requires a UUID and BP or RP side")
            if not (isinstance(version, list) and len(version) == 3 and all(type(n) is int and n >= 0 for n in version)):
                raise ValueError("pack version must have three nonnegative integers")
            files = pack.get("files")
            if not isinstance(files, dict) or not files:
                raise ValueError("pack files must be a nonempty object")
            pack_root = stage / "payload" / pack_id
            source_hashes = {}
            for relative, spec in files.items():
                if not isinstance(spec, dict):
                    raise ValueError("invalid file source declaration")
                target = _safe_output_path(pack_root, relative)
                if relative in source_hashes:
                    raise ValueError("duplicate output path")
                kind = spec.get("kind")
                if kind == "input":
                    key = spec.get("input")
                    if key not in verified:
                        raise ValueError("raw file refers to undeclared input")
                    raw = verified[key]["path"].read_bytes()
                elif kind == "archive":
                    key = spec.get("input")
                    if key not in verified:
                        raise ValueError("archive refers to undeclared input")
                    raw = archive_reader.read(verified[key]["path"], spec.get("members"))
                elif kind == "owned":
                    source = spec.get("path")
                    if not isinstance(source, str) or not _safe_name(source):
                        raise ValueError("unsafe owned source path")
                    src = (recipe_path.parent / source).resolve()
                    if recipe_path.parent.resolve() not in src.parents:
                        raise ValueError("owned source escapes recipe directory")
                    if not src.is_file():
                        raise ValueError("owned source file missing: " + source)
                    raw = src.read_bytes()
                elif kind == "generated":
                    raw = spec.get("content")
                    if not isinstance(raw, str):
                        raise ValueError("generated content must be UTF-8 text")
                    raw = raw.encode("utf-8")
                else:
                    raise ValueError("unsupported file source kind")
                source_hash = sha256(raw)
                if source_hash != spec.get("sha256"):
                    raise ValueError("file source hash differs: " + relative)
                raw = _transform(raw, spec.get("transforms", []), relative)
                if sha256(raw) != spec.get("output_sha256", spec.get("sha256")):
                    raise ValueError("file output hash differs: " + relative)
                source_hashes[relative] = {"source_sha256": source_hash, "output_sha256": sha256(raw)}
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomic_new(target, raw)
            fingerprint = _tree_fingerprint({p: h["output_sha256"] for p, h in source_hashes.items()})
            manifest_paths = [p for p in source_hashes if PurePosixPath(p).name == "manifest.json"]
            if len(manifest_paths) != 1:
                raise ValueError("each pack must contain exactly one manifest.json: " + pack_id)
            try:
                manifest = json.loads(_safe_output_path(pack_root, manifest_paths[0]).read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("invalid pack manifest: " + pack_id) from exc
            header = manifest.get("header", {})
            if header.get("uuid") != pack_uuid or header.get("version") != version:
                raise ValueError("pack manifest UUID or version differs from recipe: " + pack_id)
            expected_modules = pack.get("modules")
            modules = manifest.get("modules", [])
            if not isinstance(expected_modules, list) or not expected_modules:
                raise ValueError("recipe pack must pin its modules: " + pack_id)
            actual_modules = [{"uuid": module.get("uuid"), "version": module.get("version")}
                              for module in modules]
            if actual_modules != expected_modules:
                raise ValueError("pack manifest module UUIDs or versions differ from recipe: " + pack_id)
            expected = pack.get("expected_tree", {})
            expected_files = expected.get("files") if isinstance(expected, dict) else None
            if expected_files is not None and expected_files != {p: h["output_sha256"] for p, h in source_hashes.items()}:
                raise ValueError("pack expected file tree differs: " + pack_id)
            if isinstance(expected, dict) and expected.get("sha256") and expected["sha256"] != fingerprint:
                raise ValueError("pack expected tree hash differs: " + pack_id)
            output_name = pack_id + ".mcpack"
            archive = stage / output_name
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                for relative in sorted(source_hashes):
                    target = _safe_output_path(pack_root, relative)
                    if file_sha256(target) != source_hashes[relative]["output_sha256"]:
                        raise ValueError("staged output hash differs: " + relative)
                    zf.write(target, relative)
            with zipfile.ZipFile(archive, "r") as zf:
                members = _validate_zip(zf)
                if set(members) != set(source_hashes):
                    raise ValueError("built pack file list differs from recipe: " + pack_id)
                archived_hashes = {relative: sha256(zf.read(members[relative])) for relative in members}
            if archived_hashes != {p: h["output_sha256"] for p, h in source_hashes.items()}:
                raise ValueError("built pack contents differ from recipe: " + pack_id)
            world_lists[side].append({"pack_id": pack_uuid, "version": version})
            pack_receipts.append({"id": pack_id, "uuid": pack_uuid, "version": version,
                                  "side": side, "archive": output_name, "tree_sha256": fingerprint,
                                  "files": source_hashes})

        if archive_reader is not None:
            archive_reader.close()
            archive_reader = None
        order = recipe.get("order", {})
        for side, key in (("BP", "BP"), ("RP", "RP")):
            desired = order.get(key)
            if desired is not None:
                by_id = {p["id"]: {"pack_id": p["uuid"], "version": p["version"]}
                         for p in pack_receipts if p["side"] == side}
                if not isinstance(desired, list) or set(desired) != set(by_id) or len(desired) != len(by_id):
                    raise ValueError("order must list each pack id once for " + side)
                world_lists[side] = [by_id[item] for item in desired]
        for name, key in (("world_behavior_packs.json", "BP"), ("world_resource_packs.json", "RP")):
            _atomic_new(stage / name, (json.dumps(world_lists[key], ensure_ascii=False, indent=2) + "\n").encode())
        aggregate_name = "family.mcaddon"
        aggregate_path = stage / aggregate_name
        aggregate_members = {}
        with zipfile.ZipFile(aggregate_path, "w", zipfile.ZIP_DEFLATED) as aggregate:
            for pack_receipt in pack_receipts:
                standalone = stage / pack_receipt["archive"]
                aggregate_member = pack_receipt["archive"]
                raw = standalone.read_bytes()
                aggregate.writestr(aggregate_member, raw)
                member_info = {"path": aggregate_member, "sha256": sha256(raw), "bytes": len(raw)}
                pack_receipt["archive_sha256"] = member_info["sha256"]
                pack_receipt["archive_bytes"] = member_info["bytes"]
                aggregate_members[aggregate_member] = member_info
        aggregate_sha256 = file_sha256(aggregate_path)
        aggregate_bytes = aggregate_path.stat().st_size
        with zipfile.ZipFile(aggregate_path, "r") as aggregate:
            if set(aggregate.namelist()) != set(aggregate_members):
                raise ValueError("aggregate file list differs from standalone pack list")
            for member, info in aggregate_members.items():
                raw = aggregate.read(member)
                if len(raw) != info["bytes"] or sha256(raw) != info["sha256"]:
                    raise ValueError("aggregate pack bytes differ from standalone output: " + member)
        shutil.rmtree(stage / "payload")
        receipt = {"schema": 1, "recipe_id": recipe.get("id"), "recipe_version": recipe.get("version"),
                   "recipe_sha256": file_sha256(recipe_path),
                   "inputs": {key: {"filename": v["filename"], "sha256": v["sha256"]} for key, v in verified.items()},
                   "packs": pack_receipts, "aggregate": {"filename": aggregate_name,
                       "sha256": aggregate_sha256, "bytes": aggregate_bytes,
                       "members": aggregate_members}, "order": order}
        _atomic_new(stage / "receipt.json", (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
        output.parent.mkdir(parents=True, exist_ok=True)
        os.rename(stage, output)
        return receipt
    except Exception:
        if archive_reader is not None:
            archive_reader.close()
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, default=Path(__file__).resolve().parents[1] / "families/current/recipe.json")
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    receipt = assemble(recipe, args.recipe.resolve(), args.inputs.resolve(), args.output)
    print(json.dumps({"output": str(args.output), "packs": len(receipt["packs"]),
                      "receipt": str(args.output / "receipt.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
