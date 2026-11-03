# Local family assembly

`tools/assemble_family.py` builds reviewed Bedrock pack archives from local,
hash-pinned inputs. It never downloads inputs or installs packs into a server.
The recipe is the reviewed allowlist: it names every input, source member,
output file, source hash, final hash, pack identity and load order.
The toolkit source release follows the independent `package.json` version;
the SDK version in `sdk.json` and its release history remain separate.
<a id="current-g206-installation"></a>
<a id="current-g208-installation"></a>

## Public-minimal installation (Grilling + Cookery only)

This public-first profile selects exactly Grilling 2.8.212 BP/RP and
locally adapted original-author Cookery 1.6.4 BP/RP. **Tavern, 世界名酒,
Immersive Eating, TACZ, the private repair pack and server family lock are not
inputs or dependencies.** It uses the same `build_owned_family_recipe.py` and
`assemble_family.py` as the full-family and historical workflows.

**Why local assembly?** Grilling requires Cookery's host-extension interface.
The original Grilling G212 BP/RP manifest dependencies name Cookery
`[1,6,4]`, while the reviewed local host adapter produces `[1,6,20012]`.
This recipe checks the exact manifest dependency preimages and updates **only
the two dependencies in the generated Grilling copies** to Cookery
`[1,6,20012]`. It never changes the source archives, drops a dependency,
or reads optional third-party resources. The assembler checks pack-dependency
closure and that Grilling is the sole behavior `minecraft:player` owner.

Download clean Cookery 1.6.4 from
[the original author's project](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial)
(file 9317031, SHA256
`aa760058f43dce462778a3ac570ba5c1af629cb3b60fdc31bf457e589822eb83`).
The reviewed G212 Grilling source candidate is pinned to commit
`aa8a07ad223c993c05b0d356615d38e990148588`. Until a matching
public Grilling Release exists, use that clean public checkout; source
trees and generated archive are also pinned and checked.

```sh
git clone https://github.com/burnt-tea-dev/kaleidoscope-grilling-unofficial.git grilling
git -C grilling checkout aa8a07ad223c993c05b0d356615d38e990148588

python3 tools/build_grilling_input.py \
  --source ./grilling \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.212-station-performance.json \
  --output ./local-inputs/Kaleidoscope_Grilling_Unofficial_2.8.212_baseline1.mcaddon

python3 tools/install_cookery_from_descriptor.py \
  --cookery /path/to/clean-original-Cookery-1.6.4.mcaddon \
  --grilling ./local-inputs/Kaleidoscope_Grilling_Unofficial_2.8.212_baseline1.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.212-station-performance.json \
  --output ./local-inputs/cookery-station-performance-20012.mcaddon

python3 tools/build_owned_family_recipe.py \
  --profile public-minimal --inputs ./local-inputs \
  --output ./public-minimal.recipe.json

python3 tools/assemble_family.py \
  --recipe ./public-minimal.recipe.json --inputs ./local-inputs \
  --output ./public-minimal-output
```

Import `./public-minimal-output/family.mcaddon` into a **fresh test world**:
it nests four `.mcpack` files (2 BP and 2 RP) and writes source,
manifest, output SHA256, UUID/version and player-owner evidence to
`./public-minimal-output/receipt.json`. Enable both pairs in the world.
The G212 manifests require Bedrock compatible with
`min_engine_version [1,26,60]`, `@minecraft/server 2.12.0-beta`,
`@minecraft/server-ui 2.2.0`, Beta APIs and Points of Interest
experiments.

This is **not** a freely redistributable modified Cookery archive: download
the original author content independently, then retain generated Cookery
and the paired archive locally. Keep the receipts and a stopped-world
backup; UUIDs and save ownership are unchanged, but real client gameplay,
rendering, saved-world reopening, BDS and rollback remain separate acceptance
gates. Do not describe a synthetic fixture test as original-author or
client PASS. For IE/TACZ, deliberately use their separate optional installers
and matching reviewed inputs. Do not use them for this profile.

The existing complete family remains selectable by omitting `--profile`
or providing `--profile full-family`. Explicit historical
`--descriptor` paths are unchanged.

## Current G212 installation

**Optional full-family assembly; not a public-minimal prerequisite.**

Use the owned Tavern 0.6.194, Grilling 2.8.212 and World Liquor 0.1.180
archives named by
[`owned-t194-g212-w180-cookery-station-performance.json`](../adapters/owned-t194-g212-w180-cookery-station-performance.json).
Obtain clean Cookery 1.6.4 (file 9317031) and Immersive Eating 1.1.0 from
their authors. Keep original and locally adapted author files private.
Toolkit 0.25.0 selects G212 and the Cookery20012 station adapter by default.
SDK0.1.0 and historical explicit recipes remain unchanged. Omitting `--descriptor`
selects the current recipe; the explicit arguments below identify the inputs.

Build from a clean Grilling checkout at
`aa8a07ad223c993c05b0d356615d38e990148588`. Use the published Grilling archive
as the input when available; this source command reproduces its pinned bytes:

```sh
python3 tools/build_grilling_input.py \
  --source /path/to/grilling \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.212-station-performance.json \
  --output /path/to/local-inputs/Kaleidoscope_Grilling_Unofficial_2.8.212_baseline1.mcaddon
python3 tools/install_cookery_from_descriptor.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/local-inputs/Kaleidoscope_Grilling_Unofficial_2.8.212_baseline1.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.212-station-performance.json \
  --output /path/to/local-inputs/cookery-station-performance-20012.mcaddon
python3 tools/install_player_presentation.py \
  --ie /path/to/original-immersive-eating-1.1.0.mcaddon \
  --grilling /path/to/local-inputs/Kaleidoscope_Grilling_Unofficial_2.8.212_baseline1.mcaddon \
  --grilling-source /path/to/grilling \
  --descriptor adapters/ie-grilling-2.8.212.json \
  --output /path/to/local-inputs/ie-g212-r1.mcaddon
python3 tools/build_owned_family_recipe.py \
  --descriptor adapters/owned-t194-g212-w180-cookery-station-performance.json \
  --inputs /path/to/local-inputs --output /path/to/new-recipe.json
python3 tools/assemble_family.py \
  --recipe /path/to/new-recipe.json --inputs /path/to/local-inputs \
  --output /path/to/new-family-output
```

Put the exact Tavern and World Liquor archives into that same input directory.
The descriptor verifies all five complete input hashes. Cookery becomes local
1.6.20012 and IE becomes local 1.1.20005; these are not author releases. Select
both sides of all five pairs in the generated load order. BDS 1.26.60.6 and
the Beta APIs and Points of Interest experiments are required. The three owned ports and their required
glue define public parity; other LIVE addons are outside this download.

Back up the stopped world and validate a separate save copy before installation.
Keep the generated receipts. Never copy a diagnostic database into LIVE.
Native/save checks and real client acceptance remain separate.

## Historical recipes

The G203/G205 examples below reproduce older pinned combinations. Use their
original toolkit source, rather than the current helper with an older identity.

## Owned-port input recipe

Obtain the three exact port archives named in the descriptor. Build
`cookery-g203.mcaddon` locally from your own Cookery 1.6.4 archive, following
[the G203 adapter instructions](PORT-ADAPTERS.md). Do not distribute that
adapted author archive. Put all four files in one input directory, then run:

```sh
python3 tools/build_owned_family_recipe.py --inputs /path/to/local-inputs \
  --descriptor adapters/owned-t194-g203-w180.json \
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

The legacy G205 descriptor keeps producing Cookery `[1, 6, 20002]` unchanged.
For the separate startup adapter candidate, build Cookery with
`adapters/cookery-1.6.4-grilling-2.8.205-guide-startup.json` instead, producing
local `[1, 6, 20003]`. Then use
`adapters/owned-t194-g205-w180-cookery-startup.json` with that new archive to
build the corresponding eight-pack family recipe. The new descriptor pins
Cookery archive SHA256
`1e9b308445119be3d2b56adf26cf292a639b490d6e1bb2047ebbd2d779b9ae6b`. Both descriptors preserve the same
author UUIDs; only the new descriptor selects the receiver repair. The recipe
pins the exact local Cookery archive hash. Neither descriptor is a claim that G205 has a public
Release, full-family admission, BDS acceptance, or client acceptance. Keep the
local Cookery archive and assembled family output out of this repository.

For the historical 0.7.0 incremental-decoding source candidate, build the user-local
Cookery input with
`adapters/cookery-1.6.4-grilling-2.8.205-guide-decoding.json`. It produces local
Cookery `[1, 6, 20004]`. Keep the 0.6 startup archive and recipe above intact.
Use the exact Tavern 0.6.194, Grilling 2.8.205 and World Liquor 0.1.180
archives named by the family descriptor and the generated Cookery archive
named `cookery-g205-decoding.mcaddon`. Then use the public family descriptor;
it pins these input hashes, the Cookery pair and `toolkit_version` 0.7.0:

```sh
python3 tools/build_owned_family_recipe.py \
  --descriptor adapters/owned-t194-g205-w180-cookery-decoding.json \
  --inputs /path/to/local-inputs \
  --output /path/to/private-owned-t194-g205-w180-cookery-decoding.recipe.json
```

The generated eight-pack recipe records `toolkit_version` 0.7.0 and the exact
local Cookery archive hash. Keep the recipe and Cookery archive with the local
build inputs; they are not Core publication files. This is still a source
candidate, not full-family, BDS or client acceptance.

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
