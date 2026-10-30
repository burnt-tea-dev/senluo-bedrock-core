#!/usr/bin/env python3
"""Apply a pinned local Cookery adapter without extracting either archive.

The descriptor is a reviewed lock file. This program never changes author
identities and writes only a user-local adapted archive and its receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

MAX_ENTRIES = 20_000
MAX_MEMBER = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_name(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name:
        return False
    if PurePosixPath(name).is_absolute():
        return False
    body = name[:-1] if name.endswith("/") else name
    return all(part not in ("", ".", "..") for part in body.split("/"))


def _read_zip(path: Path) -> tuple[zipfile.ZipFile, dict[str, tuple[zipfile.ZipInfo, bytes]]]:
    archive = zipfile.ZipFile(path, "r")
    result: dict[str, tuple[zipfile.ZipInfo, bytes]] = {}
    total = 0
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        archive.close()
        raise ValueError("archive contains too many entries")
    try:
        for info in infos:
            if not _safe_name(info.filename):
                raise ValueError("unsafe ZIP path")
            if info.filename in result:
                raise ValueError("duplicate ZIP path")
            if info.file_size > MAX_MEMBER:
                raise ValueError("ZIP member exceeds size limit")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError("archive exceeds uncompressed size limit")
            result[info.filename] = (info, archive.read(info))
    except Exception:
        archive.close()
        raise
    return archive, result


def _required(desc: dict, key: str):
    if key not in desc:
        raise ValueError("descriptor missing " + key)
    return desc[key]


def _json_bytes(raw: bytes, label: str) -> dict:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON: " + label) from exc


def _pointer_parent(doc: dict, pointer: list[str]):
    if not pointer or any(not isinstance(p, str) for p in pointer):
        raise ValueError("invalid JSON pointer")
    node = doc
    for part in pointer[:-1]:
        if not isinstance(node, dict) or part not in node:
            raise ValueError("JSON pointer parent missing")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError("JSON pointer parent is not an object")
    return node, pointer[-1]


def apply_archive(cookery: Path, grilling: Path, descriptor: dict) -> tuple[bytes, dict]:
    """Return adapted ZIP bytes plus a machine-readable evidence receipt."""
    cookery_raw, grilling_raw = cookery.read_bytes(), grilling.read_bytes()
    if sha256(cookery_raw) != _required(descriptor, "archive_sha256"):
        raise ValueError("Cookery archive hash does not match reviewed lock")
    companion = _required(descriptor, "companion")
    if sha256(grilling_raw) != companion["archive_sha256"]:
        raise ValueError("Grilling archive hash does not match reviewed lock")

    ca, files = _read_zip(cookery)
    ga, gfiles = _read_zip(grilling)
    try:
        baseline_files = {name: raw for name, (_, raw) in files.items()}
        grilling_roots = []
        for name, (_, raw) in gfiles.items():
            if not name.endswith("manifest.json"):
                continue
            candidate = _json_bytes(raw, name)
            header = candidate.get("header", {})
            if header.get("uuid") == companion["bp_uuid"] and header.get("version") == companion["version"]:
                grilling_roots.append(name[:-len("manifest.json")])
        if len(grilling_roots) != 1:
            raise ValueError("Grilling BP identity must occur exactly once")
        prefixes = {"cookery_bp": descriptor["prefixes"]["BP"],
                    "cookery_rp": descriptor["prefixes"]["RP"],
                    "grilling_bp": grilling_roots[0]}
        spec_path = prefixes["grilling_bp"] + companion["spec_path"]
        if spec_path not in gfiles or sha256(gfiles[spec_path][1]) != companion["spec_sha256"]:
            raise ValueError("Grilling API declaration hash differs")
        spec = _json_bytes(gfiles[spec_path][1], spec_path)
        if spec.get("archive_sha256") != descriptor["archive_sha256"] or spec.get("host_uuid") != descriptor["host_uuid"]:
            raise ValueError("Grilling declaration does not identify the pinned Cookery archive")
        sdk_files = _required(descriptor, "owned_helpers")
        sdk_map = spec.get("copies", {})
        if set(sdk_files) != set(sdk_map):
            raise ValueError("pinned SDK helper keys must exactly match declared copies")
        sdk_additions = {}
        for source, expected in sdk_files.items():
            if not _safe_name(source):
                raise ValueError("SDK source path is unsafe")
            source_member = prefixes["grilling_bp"] + source
            if source not in sdk_map or source_member not in gfiles:
                raise ValueError("owned SDK helper differs from pinned declaration: " + source)
            if sha256(gfiles[source_member][1]) != expected:
                raise ValueError("owned SDK helper bytes differ from reviewed hash: " + source)
            sdk_additions[source] = gfiles[source_member][1]

        version = _required(descriptor, "output_version")
        if not (isinstance(version, list) and len(version) == 3 and all(type(v) is int and v >= 0 for v in version)):
            raise ValueError("descriptor output version must be a three-part version")
        author_version = _required(descriptor, "author_version")
        if version <= author_version:
            raise ValueError("local output version must be newer than the author version")
        manifest_paths = [prefixes["cookery_bp"] + "manifest.json", prefixes["cookery_rp"] + "manifest.json"]
        owned_pack_uuids = {descriptor["host_uuid"], descriptor["resource_uuid"]}
        manifest_receipt = {}
        for path in manifest_paths:
            if path not in files:
                raise ValueError("manifest missing: " + path)
            old = files[path][1]
            doc = _json_bytes(old, path)
            header = doc.get("header", {})
            expected_uuid = descriptor["host_uuid"] if path == manifest_paths[0] else descriptor["resource_uuid"]
            if header.get("version") != author_version:
                raise ValueError("unexpected author manifest version: " + path)
            if header.get("uuid") != expected_uuid:
                raise ValueError("author manifest UUID differs: " + path)
            for module in doc.get("modules", []):
                if "version" in module:
                    if module["version"] != author_version:
                        raise ValueError("unexpected author module version: " + path)
                    module["version"] = version
            deps = doc.get("dependencies", [])
            for dep in deps:
                if isinstance(dep, dict) and dep.get("uuid") in owned_pack_uuids:
                    if dep.get("version") != author_version:
                        raise ValueError("unexpected owned-pack dependency version: " + path)
                    dep["version"] = version
            doc["header"]["version"] = version
            encoded = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
            files[path] = (files[path][0], encoded)
            manifest_receipt[path] = {"before": sha256(old), "after": sha256(encoded)}

        original_files = _required(spec, "original_files")
        patched_files = _required(spec, "patched_files")
        if (not isinstance(original_files, dict) or not original_files
                or any(not _safe_name(path) for path in original_files)):
            raise ValueError("original file paths must be a nonempty safe allowlist")
        if set(original_files) != set(patched_files):
            raise ValueError("original_files and patched_files must cover the same paths")
        for path in set(spec.get("imports", {})):
            if path not in original_files:
                raise ValueError("import target is outside original_files allowlist")
        for operation in spec.get("insertions", []):
            if operation.get("path") not in original_files:
                raise ValueError("insertion target is outside original_files allowlist")
        json_updates = spec.get("json_updates", [])
        if not isinstance(json_updates, list):
            raise ValueError("json_updates must be a list")
        for operation in json_updates:
            if (operation.get("path") not in original_files
                    or operation.get("pointer") != ["minecraft:item", "components", "minecraft:allow_off_hand"]
                    or operation.get("value") is not True):
                raise ValueError("JSON updates must use the reviewed allow_off_hand capability")
        changed = {}
        for path, expected in original_files.items():
            member = prefixes["cookery_bp"] + path
            if member not in files or sha256(files[member][1]) != expected:
                raise ValueError("author preimage differs: " + path)
            original = files[member][1]
            try:
                text = original.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("hook target is not UTF-8: " + path) from exc
            text = spec.get("imports", {}).get(path, "") + text
            for operation in spec.get("insertions", []):
                if operation.get("path") != path:
                    continue
                anchor, pos, addition = operation.get("anchor"), operation.get("position"), operation.get("text")
                if not isinstance(anchor, str) or not anchor or text.count(anchor) != 1:
                    raise ValueError("insertion anchor must occur exactly once: " + path)
                if pos not in ("before", "after") or not isinstance(addition, str):
                    raise ValueError("invalid insertion operation: " + path)
                text = text.replace(anchor, addition + anchor if pos == "before" else anchor + addition, 1)
            raw = text.encode()
            files[member] = (files[member][0], raw)
            changed[path] = raw

        for operation in json_updates:
            path = operation.get("path")
            member = prefixes["cookery_bp"] + path
            if path not in original_files or member not in files:
                raise ValueError("JSON update is outside original_files allowlist")
            doc = _json_bytes(files[member][1], path)
            parent, leaf = _pointer_parent(doc, operation.get("pointer", []))
            if leaf in parent:
                raise ValueError("JSON update target already exists: " + path)
            parent[leaf] = operation.get("value")
            raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
            files[member] = (files[member][0], raw)
            changed[path] = raw

        for path, raw in changed.items():
            if sha256(raw) != patched_files[path]:
                raise ValueError("patched postimage differs: " + path + " actual=" + sha256(raw) + " expected=" + patched_files[path])

        copies = _required(spec, "copies")
        for source, dest in copies.items():
            if not _safe_name(source) or not _safe_name(dest):
                raise ValueError("SDK copy paths must be safe relative paths")
            dest_member = prefixes["cookery_bp"] + dest
            if source not in sdk_additions or dest_member in files:
                raise ValueError("SDK copy is not allowlisted or destination already exists: " + dest)
            files[dest_member] = (zipfile.ZipInfo(dest_member), sdk_additions[source])

        input_tree = _tree_fingerprint(baseline_files,
                                       exclude=set(manifest_paths) | {prefixes["cookery_bp"] + p for p in changed})
        out = __import__("io").BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as writer:
            for name, (info, raw) in files.items():
                writer.writestr(info, raw)
        output = out.getvalue()
        output_files = {name: raw for name, (_, raw) in files.items()}
        output_tree = _tree_fingerprint(output_files)
        receipt = {
            "schema": 1, "input_sha256": sha256(cookery_raw), "grilling_sha256": sha256(grilling_raw),
            "descriptor_sha256": sha256(json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()),
            "grilling_spec_sha256": companion["spec_sha256"],
            "output_sha256": sha256(output), "version": version,
            "unmodified_input_tree": input_tree, "output_tree": output_tree,
            "input_file_count": len(baseline_files), "output_file_count": len(files),
            "host_uuid": descriptor["host_uuid"], "manifest_hashes": manifest_receipt,
            "manifest_identities": _manifest_identities(files, manifest_paths),
            "changed_paths": {path: {"before": original_files[path], "after": sha256(raw)} for path, raw in changed.items()},
            "sdk_helpers": {src: sha256(raw) for src, raw in sdk_additions.items()},
            "sdk_copies": {prefixes["grilling_bp"] + src: prefixes["cookery_bp"] + dst for src, dst in copies.items()},
        }
        return output, receipt
    finally:
        ca.close()
        ga.close()


def _manifest_identities(files, paths):
    result = {}
    for path in paths:
        doc = _json_bytes(files[path][1], path)
        result[path] = {
            "uuid": doc.get("header", {}).get("uuid"),
            "header_version": doc.get("header", {}).get("version"),
            "modules": [{"uuid": module.get("uuid"), "type": module.get("type"),
                         "version": module.get("version")} for module in doc.get("modules", [])],
            "dependencies": doc.get("dependencies", []),
        }
    return result


def _tree_fingerprint(files, exclude=frozenset()):
    entries = [{"path": path, "sha256": sha256(raw)} for path, raw in sorted(files.items()) if path not in exclude]
    canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": sha256(canonical), "file_count": len(entries)}


def _atomic_new(path: Path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cookery", required=True, type=Path)
    parser.add_argument("--grilling", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    receipt_path = Path(str(args.output) + ".receipt.json")
    if (args.output.exists() or receipt_path.exists()
            or args.output.resolve() in (args.cookery.resolve(), args.grilling.resolve())):
        raise SystemExit("refusing to overwrite an existing file or an input")
    descriptor = json.loads((Path(__file__).resolve().parents[1] / "adapters/cookery-1.6.4.json").read_text(encoding="utf-8"))
    output, receipt = apply_archive(args.cookery, args.grilling, descriptor)
    _atomic_new(args.output, output)
    _atomic_new(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"output": str(args.output), "output_sha256": receipt["output_sha256"], "receipt": str(receipt_path)}))


if __name__ == "__main__":
    main()
