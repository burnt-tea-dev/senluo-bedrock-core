#!/usr/bin/env python3
"""Build a user-local Cookery archive through the reviewed Core installer."""
import argparse
import json
from pathlib import Path

from install_cookery import _atomic_new, apply_archive, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESCRIPTOR = ROOT / "adapters/cookery-1.6.4-grilling-2.8.203.json"


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
    _atomic_new(args.output, output)
    _atomic_new(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"output": str(args.output), "output_sha256": sha256(output),
                      "receipt": str(receipt_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
