#!/usr/bin/env python3
"""Build a user-local Cookery archive through the reviewed Core installer."""
import argparse
import io
import json
from pathlib import Path
import zipfile

from install_cookery import _atomic_new, _safe_name, _tree_fingerprint, apply_archive, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / "adapters/cookery-1.6.4-grilling-2.8.206-recipe-index.json"


def apply_post_adapter(output, descriptor):
    """Apply an independently Core-pinned adapter stage to the built archive."""
    post = descriptor.get("post_adapter")
    if post is None:
        return output
    helper_path = post["helper_path"]
    if not _safe_name(helper_path):
        raise ValueError("unsafe post-adapter helper path")
    helper_file = ROOT / helper_path
    if helper_file.is_symlink() or not helper_file.is_file() or not helper_file.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("post-adapter helper must be a regular Core-relative file")
    helper = helper_file.read_bytes()
    if sha256(helper) != post["helper_sha256"]:
        raise ValueError("post-adapter helper hash differs")
    with zipfile.ZipFile(io.BytesIO(output)) as source:
        files = {name: (info, source.read(info)) for info in source.infolist() for name in [info.filename]}
    prefix = descriptor["prefixes"]["BP"]
    if set(post["preimages"]) != set(post["postimages"]):
        raise ValueError("post-adapter preimages and postimages differ")
    allowed = set(post["preimages"])
    if not allowed:
        raise ValueError("post-adapter path allowlist is empty")
    for path in post.get("imports", {}):
        if path not in allowed:
            raise ValueError("post-adapter import outside path allowlist")
    for collection in ("text_replacements", "insertions"):
        if not isinstance(post.get(collection, []), list) or any(op.get("path") not in allowed for op in post.get(collection, [])):
            raise ValueError("post-adapter operation outside path allowlist")
    for path, expected in post["preimages"].items():
        if not _safe_name(path):
            raise ValueError("unsafe post-adapter path")
        member = prefix + path
        if member not in files or sha256(files[member][1]) != expected:
            raise ValueError("post-adapter preimage differs: " + path)
        text = post.get("imports", {}).get(path, "") + files[member][1].decode("utf-8")
        for op in post.get("text_replacements", []):
            if op["path"] != path: continue
            if not isinstance(op.get("before"), str) or not op["before"] or text.count(op["before"]) != 1 or not isinstance(op.get("after"), str):
                raise ValueError("invalid post-adapter replacement: " + path)
            text = text.replace(op["before"], op["after"], 1)
        for op in post.get("insertions", []):
            if op["path"] != path: continue
            anchor = op["anchor"]
            if not isinstance(anchor, str) or not anchor or text.count(anchor) != 1 or op["position"] not in ("before", "after") or not isinstance(op.get("text"), str):
                raise ValueError("invalid post-adapter insertion: " + path)
            text = text.replace(anchor, op["text"] + anchor if op["position"] == "before" else anchor + op["text"], 1)
        raw = text.encode()
        if sha256(raw) != post["postimages"][path]:
            raise ValueError("post-adapter postimage differs: " + path)
        files[member] = (files[member][0], raw)
    destination = prefix + post["helper_destination"]
    if not _safe_name(destination) or destination in files:
        raise ValueError("unsafe or existing post-adapter helper destination")
    files[destination] = (zipfile.ZipInfo(destination), helper)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for name, (info, raw) in files.items(): target.writestr(info, raw)
    return out.getvalue(), {path: post["postimages"][path] for path in allowed}, sha256(helper)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cookery", required=True, type=Path)
    parser.add_argument("--grilling", required=True, type=Path)
    parser.add_argument("--descriptor", type=Path, default=DEFAULT_DESCRIPTOR)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    receipt_path = Path(str(args.output) + ".receipt.json")
    inputs = {args.cookery.resolve(), args.grilling.resolve()}
    if args.output.exists() or receipt_path.exists() or args.output.resolve() in inputs:
        raise SystemExit("refusing to overwrite an existing file or an input")
    descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
    output, receipt = apply_archive(args.cookery, args.grilling, descriptor)
    stage1_output_sha256 = sha256(output)
    post = descriptor.get("post_adapter")
    if post is not None:
        output, final_changed, helper_sha256 = apply_post_adapter(output, descriptor)
        receipt["stage1_changed_paths"] = receipt.pop("changed_paths", {})
        receipt["stage1_output_tree"] = receipt["output_tree"]
        receipt["stage1_output_file_count"] = receipt["output_file_count"]
        with zipfile.ZipFile(io.BytesIO(output)) as archive:
            final_files = {info.filename: archive.read(info) for info in archive.infolist()}
        receipt["output_tree"] = _tree_fingerprint(final_files)
        receipt["output_file_count"] = len(final_files)
        receipt["post_adapter"] = {
            "descriptor_sha256": sha256(json.dumps(post, sort_keys=True, separators=(",", ":")).encode()),
            "helper_path": post["helper_path"], "helper_sha256": helper_sha256,
            "helper_destination": post["helper_destination"],
            "preimages": post["preimages"], "postimages": final_changed,
            "changed_paths": {path: {"sha256": digest} for path, digest in final_changed.items()}}
        receipt["final_changed_paths"] = dict(receipt["stage1_changed_paths"])
        receipt["final_changed_paths"].update(receipt["post_adapter"]["changed_paths"])
        receipt["final_changed_paths"][post["helper_destination"]] = {"sha256": helper_sha256}
    else:
        receipt["post_adapter"] = None
    receipt["output_sha256"] = sha256(output)
    receipt["final_stage1_output_sha256"] = stage1_output_sha256
    _atomic_new(args.output, output)
    _atomic_new(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"output": str(args.output), "output_sha256": sha256(output),
                      "receipt": str(receipt_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
