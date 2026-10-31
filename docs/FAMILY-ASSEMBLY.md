# Local family assembly

`tools/assemble_family.py` builds reviewed Bedrock pack archives from local,
hash-pinned inputs. It never downloads inputs or installs packs into a server.
The recipe is the reviewed allowlist: it names every input, source member,
output file, source hash, final hash, pack identity and load order.
The toolkit source release follows the independent `package.json` version;
the SDK version in `sdk.json` and its release history remain separate.
The owned-port descriptor in `adapters/owned-t194-g203-w180.json` retains the
Tavern 0.6.194, Grilling 2.8.203, World Liquor 0.1.180 and local Cookery
combination. `adapters/owned-t194-g205-w180.json` records a separate G205 source
candidate from the pinned public-source commit. It is not a public Release or
full-family admission. Both descriptors cover only these three owned ports and
the required Cookery API; other third-party gameplay and optional Immersive
Eating are outside this set. A tool or pack file alone does not prove rendered
gameplay matches LIVE.

## Owned-port input recipe

Obtain the three exact port archives named in the descriptor. Build
`cookery-g203.mcaddon` locally from your own Cookery 1.6.4 archive, following
[the G203 adapter instructions](PORT-ADAPTERS.md). Do not distribute that
adapted author archive. Put all four files in one input directory, then run:

```sh
python3 tools/build_owned_family_recipe.py --inputs /path/to/local-inputs \
  --output /path/to/new-owned-recipe.json
python3 tools/assemble_family.py --recipe /path/to/new-owned-recipe.json \
  --inputs /path/to/local-inputs --output /path/to/new-owned-output
```

The first command verifies whole-archive hashes, selects the pinned pack and
module identities, and records every original file hash in a local recipe.
The second command uses the existing assembler to preserve those exact files
and the declared BP/RP order. Neither step changes gameplay or pack versions.
Both outputs must be new paths. No downloads, server operations or save-data
migrations run. The generated aggregate includes your local author content;
it stays local and is not a Core release asset.

This combination requires Beta APIs for the ports' declared server modules
(including `2.12.0-beta`). BDS 1.26.60.6 accepted the exact G203 and adapted
Cookery pair during saved-data/restart/rollback checks. Full three-port native,
multiplayer and client acceptance are separate checks and remain pending.
Port artifacts may be built from their canonical public sources while their
matching Releases await admission; the descriptor does not claim publication.

## G205 source-candidate recipe

The G205 descriptor pins Grilling source commit `83026c0bb41fa6574e50a9b5a61cfb3b473bc59c`,
Git tree `482a11c348d87c0963a7df8500d2bbeb9c33b1d4`, both runtime trees, the
board API declaration and all copied Core helper hashes. Build its local input
from that clean source checkout with the G205 adapter descriptor:

```sh
python3 tools/build_grilling_input.py \
  --source /path/to/grilling-guide-perf-source-r1 \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.205.json \
  --output /path/to/local-inputs/Kaleidoscope_Grilling_Unofficial_2.8.205_baseline1.mcaddon
python3 tools/install_cookery_from_descriptor.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/local-inputs/Kaleidoscope_Grilling_Unofficial_2.8.205_baseline1.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.205.json \
  --output /path/to/local-inputs/cookery-g205.mcaddon
python3 tools/build_owned_family_recipe.py \
  --descriptor adapters/owned-t194-g205-w180.json \
  --inputs /path/to/local-inputs --output /path/to/new-owned-recipe.json
```

The current source reproduces the pinned G205 archive. Every copied Core helper
matches G203, so rebuilding Cookery produces the exact same archive hash and
keeps version `[1, 6, 20002]`; no manifest-only version bump is made. The
descriptor is a source-rebuild record, not a claim that G205 has a public
Release, full-family admission, BDS acceptance, or client acceptance. Keep the
local Cookery archive and assembled family output out of this repository.

## Run

```sh
python3 tools/assemble_family.py --recipe /path/to/reviewed-recipe.json \
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
