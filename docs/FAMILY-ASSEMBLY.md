# Local family assembly

`tools/assemble_family.py` builds reviewed Bedrock pack archives from local,
hash-pinned inputs. It never downloads inputs or installs packs into a server.
The recipe is the reviewed allowlist: it names every input, source member,
output file, source hash, final hash, pack identity and load order.
The toolkit source release follows the independent `package.json` version;
the SDK version in `sdk.json` and its release history remain separate.
This repository does not currently include a formal family recipe. The
`families/current/recipe.json` path below is an example location only; a tool
or pack file alone does not prove that assembled downloads match LIVE gameplay.

## Run

```sh
python3 tools/assemble_family.py --recipe families/current/recipe.json \
  --inputs /path/to/local-inputs --output /path/to/new-output
```

Place each recipe input under its exact `filename` in the input directory.
The tool checks every whole-input hash before it creates output. The output
directory must not already exist. It contains one `.mcpack` per recipe pack,
one `family.mcaddon` that nests those exact `.mcpack` files, the two world
load-list JSON files, and `receipt.json`. The aggregate is a user-local
convenience output and is not a Core release asset. The world files are
metadata for review; they are not copied to a world.

## Recipe shape

The recipe uses `schema: 1`, an `id`, `version`, an `inputs` object, a `packs`
list, and `order` lists for `BP` and `RP`. Each input declares `filename` and
`sha256`. Each pack declares a unique `id`, pack `uuid`, three-part `version`,
`side` (`BP` or `RP`), `modules` (the expected module UUID and version list),
and `files`. The built `manifest.json` must match these identities and versions.

Each file maps its output-relative path to one source declaration:

- `archive`: `input`, a `members` list, and `sha256` of the selected file. The
  list may cross nested ZIP files, such as an outer release ZIP containing an
  `.mcaddon` and then an inner `.mcpack`.
- `input`: `input` and `sha256` for a whole raw input file already verified by
  the recipe's inputs table, such as an OGG audio file.
- `owned`: a repository-relative `path` and its `sha256`. The resolved file
  must remain below the recipe's directory.
- `generated`: UTF-8 `content` and its `sha256`.

Optional `transforms` run in order. `text_replace` replaces one exact UTF-8
string that must occur once. `json_replace` changes one existing JSON value
at a pointer such as `["header", "version"]`, after matching its exact old
value. When transforms are present, declare `output_sha256`; otherwise the
source and final hashes must match. No scripts, code expressions, or broad
patches run from a recipe.

Each pack may pin `expected_tree.files` as output-path-to-SHA256 values and
`expected_tree.sha256`, computed from the canonical sorted JSON map of those
paths and hashes. The receipt records source/final hashes, pack identities,
standalone archive hashes and sizes, aggregate hash and size, input hashes,
recipe hash and order. It contains no resolved source paths.

ZIP paths are checked for traversal, duplicates, and size limits on every
archive layer. Files are staged in a temporary sibling directory and renamed
into place only after all recipe checks pass. On failure, the tool removes
only its own temporary output.
