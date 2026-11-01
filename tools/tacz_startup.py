"""Precompute the pinned TACZ string-table rotations without running gameplay.

javascript-obfuscator documents stringArrayRotate as a fixed table shift. The
reviewed offsets reproduce its final table; only that table and its pure
bootstrap are changed. Original decoders, imports, events and timing stay byte
identical. No author script is stored in this repository.
"""
import hashlib
import json
from pathlib import Path
import re

DEFAULT_RECIPE = Path(__file__).resolve().parents[1] / 'adapters/tacz-1.0.3-startup.json'
STRING = re.compile(rb"'(?:\\.|[^'\\])*'")


def prepare_script(raw, row):
    if hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('TACZ startup script differs from reviewed preimage')
    start, end = row['table_span']
    table = raw[start:end]
    literals = STRING.findall(table[1:-1])
    if (table[:1] != b'[' or table[-1:] != b']'
            or b','.join(literals) != table[1:-1]
            or len(literals) != row['strings']):
        raise ValueError('TACZ startup table is not the reviewed literal array')
    offset = row['offset']
    rotated = b'[' + b','.join(literals[offset:] + literals[:offset]) + b']'
    edits = [(start, end, rotated), (*row['rotate_span'], b'')]
    result = raw
    for first, last, replacement in sorted(edits, reverse=True):
        result = result[:first] + replacement + result[last:]
    if hashlib.sha256(result).hexdigest() != row['output_sha256']:
        raise ValueError('TACZ startup result differs from reviewed postimage')
    return result


def prepare_scripts(originals, recipe=None):
    recipe = recipe if recipe is not None else json.loads(DEFAULT_RECIPE.read_bytes())
    return {row['path']: prepare_script(originals[row['path']], row)
            for row in recipe['scripts']}
