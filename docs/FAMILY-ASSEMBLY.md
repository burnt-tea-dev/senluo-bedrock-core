# Local assembly: public first, family opt-in

Core is a build-time tool, not another gameplay pack. The existing
`build_owned_family_recipe.py` and `assemble_family.py` serve both public and
optional family installations. They do not deploy a server or change a world.

## Optional shared still-water renderer data

[`resources/textures/terrain_texture.json`](../resources/textures/terrain_texture.json)
contains only the two vanilla still-water atlas entries with `quad: 1`.
It references built-in textures and includes no images, author addon data or
player definitions. Four mip levels and padding eight are retained; flowing
water, lava and other atlas entries are not supplied by this file.

An existing resource-pack producer can copy this file to
`textures/terrain_texture.json` through its normal owned/generated input route.
Keep the selected Core commit and file hash in that producer's source lock.
Do not replace another addon's atlas or create another Core gameplay pack.
If the destination pack already owns an atlas, its producer must preserve that
content explicitly; this file is not a JSON merger.

This is an optional candidate for Fancy still-water rendering. Successful file
assembly does not establish the engine's effective atlas merge or a client
fix. Check the actual world's resource selection and compare near/far water,
movement, flowing water, color and animation on the affected client. Keep
that observation separate from JSON, server-loading and save checks.

## Paired manifest releases

An owned-port descriptor can advance a selected pair without composing a
player. Use `paired_releases` to name the existing BP/RP pack IDs, a fresh
`version`, and exact `dependency_rewrites` (`uuid`, `before`, `after`). The
shared planner also serves the player installer and public-player recipe.
It preserves pack/module UUIDs and every non-manifest byte. Both pack versions,
module versions and reciprocal dependencies advance together; external
dependencies change only when their exact input version matches the rule.
An unused rule or reused output version is rejected. Original archives remain
unchanged, and the existing recipe records the input, transformations and
complete output trees. This source capability does not declare a new ready-made
addon combination or certify native/client behavior.

```json
"paired_releases": [{
  "packs": {"BP": "example-bp", "RP": "example-rp"},
  "version": [1, 0, 2],
  "dependency_rewrites": [{"uuid": "host-pack-uuid", "before": [2, 0, 0], "after": [2, 0, 1]}]
}]
```

## Public-minimal installation (Grilling + Cookery only)

<a id="public-player-presentation"></a>

This route installs exactly **Grilling BP/RP + locally adapted Cookery BP/RP**.
Tavern, World Liquor, IE, TACZ, private repair packs and a particular server
family are not inputs or prerequisites. Core remains a build-time tool, not a
fifth gameplay addon. Genuine conflicting player definitions need explicit
integration; unrelated addons do not need to be on a Senluo whitelist.

### Reviewed source and output ownership

The current reviewed source and the two input archive hashes are maintained in
[the public descriptor](../adapters/public-minimal.json); the original
Cookery archive, host edits and companion declarations belong to
[the public Cookery adapter](../adapters/cookery-public-minimal.json).
The existing builder, installer, player composer and assembler are reused.
New reviews update this one active profile instead of introducing another
version-specific gameplay branch.

The active profile selects the reviewed source declared above. The output advances both
existing Grilling pack/module versions and rebinds the exact Cookery pair.
It preserves gameplay bytes and save ownership. The selected source supplies
the same sixteen reviewed host helpers and board declaration as the former
G213 route; author originals remain unchanged. Original/adapted Cookery
archives are user-local inputs and are not public release assets.

Grilling's canonical composer merges the exact official vanilla player into
**Grilling's existing RP**. IE/TACZ routes are not executed. The assembler
requires one Grilling behavior-player owner and one complete Grilling resource
player, including its public variables and animation aliases. It retains
vanilla materials, textures, geometry, render controllers, attachables and the
Mojang license. Another player definition is not silently overwritten.

The 2026-11-03 package-only failure and repaired G218 structural result remain
[historical evidence](validation-public-player-20261103.json). They do not
certify this updated input or its native gameplay. Engine, save/rollback and
client evidence must be read at their actual tested scope.

### Native and saved-world scope

[Current validation](validation-public-minimal.json) records real input
reconstruction and attributes retained engine evidence to its tested source.
Warmth timing and persistence retain the canonical native timing/restart result;
the only change in that effect module is an Ordinary damage explanation comment.
The new Heavy Metal priority has a separate native observation: eligible held
totems run first, and confirmed native healing clears effects. Forced-damage
controls and remaining absorption limits stay explicit in the validation.
Held-snapshot recovery has production-publisher fault-model regressions; this
does not establish spontaneous engine API failure or rendered recovery.

The previous public candidate's one-QA original-pack load, upgrade, saved restart
and rollback covered native grill/chest metadata and a partially cut Cookery
board completing its original outputs plus Grilling skin. These storage/board
paths and save owners remain unchanged. That result is retained at its original
candidate identity, with no additional world cycle for unchanged persisted
behavior. The explicit observer overlays are test-only; the distributed four
archives contain none of them.

This is not a human-click, rendering/audio, arbitrary-NBT or multiplayer PASS.
Earlier mismatched QA setups remain failures; successful unchanged stages were
reused. See [the isolated observer](../tests/native/public-minimal.js) when
reproducing those cases in a disposable, network-isolated test world.

### Local build

Use Python 3 and Node.js. Obtain clean Cookery 1.6.4 from
[the original author](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial),
file 9317031. Its verified archive hash is in the adapter descriptor; do not
substitute a server-patched archive.

From this Core checkout, clone the reviewed references into new local folders:

```sh
git clone https://github.com/burnt-tea-dev/kaleidoscope-grilling-unofficial.git grilling
git -C grilling checkout "$(python3 -c 'import json; print(json.load(open("adapters/public-minimal.json"))["player_presentation"]["source"]["commit"])')"
git clone https://github.com/Mojang/bedrock-samples.git vanilla
git -C vanilla checkout "$(python3 -c 'import json; print(json.load(open("adapters/public-minimal.json"))["player_presentation"]["vanilla"]["commit"])')"

python3 tools/build_grilling_input.py \
  --source ./grilling --descriptor adapters/cookery-public-minimal.json \
  --output ./grilling-source.mcaddon

python3 tools/build_owned_family_recipe.py \
  --cookery /path/to/clean-original-Cookery-1.6.4.mcaddon \
  --grilling ./grilling-source.mcaddon \
  --grilling-source ./grilling --vanilla-source ./vanilla \
  --output ./public-minimal-output
```

The two source folders are build references, not extra enabled addons. The
vanilla input must contain the complete pinned `resource_pack/entity/player.entity.json`
and `LICENSE.md`; the descriptor verifies their exact Git blob identities.
A verified extraction of those official files is also accepted.

Enable all four packs inside `public-minimal-output/public-minimal.mcaddon`.
The output also contains the per-pack archives, selected pack lists, recipe,
installation metadata and receipt. Keep those records when diagnosing the
installed version. The output is a local adaptation, not an official author
release or a claim that every possible Grilling archive is interchangeable.

Use an engine compatible with the selected manifests. The current Grilling
source requires **Beta APIs (`gametest`) and Points of Interest (`poi`)**;
missing a required experiment is a configuration mismatch. The selected
manifest is authoritative for server/UI module versions. A diagnostic-only
GameTest observer is not installed in the four-pack production output.

For step-by-step reconstruction, the existing `install_cookery_from_descriptor.py`,
`build_owned_family_recipe.py --profile public-minimal` and `assemble_family.py`
commands remain available. Use the active descriptor's filenames and hashes;
older explicit descriptors retain their own historical inputs.

<a id="current-g212-installation"></a>

## Historical G212 installation

<a id="current-g206-installation"></a>
<a id="current-g208-installation"></a>

**Optional full-family reproduction, not the public installation requirement.**
The unchanged historical default (no `--profile`) and `--profile full-family`
select `owned-t194-g212-w180-cookery-station-performance.json` for callers
already using that workflow. This selects T194/G212/W180 and the prescribed
local Cookery/IE integrations. Do not substitute newer main versions.

The exact original inputs, commands, order and boundaries remain in
[the immutable full-family instructions](https://github.com/burnt-tea-dev/senluo-bedrock-core/blob/7f015e92ed7536e5ed64317338eda55968e0c4ae/docs/FAMILY-ASSEMBLY.md#current-g212-installation).
The original descriptors and installers remain unchanged. Adding IE/TACZ is
an explicit optional integration, not a way to repair the public base profile.
Those profiles have their own exact output identities and acceptance scope;
they do not establish compatibility with every third-party player override.

## Historical recipes and package-only probes

`public-minimal-player.json` preserves the previous G213 → G218 player-complete
recipe. Select it explicitly with the original source references; the new
active default is `public-minimal.json`; `public-minimal-g219-player.json` and
`public-minimal-g233-player.json` remain explicit historical inputs. Old descriptors and all previously
published identities remain unchanged.


Historical G203/G205 startup/decoding/family instructions are preserved at
[the fixed earlier source](https://github.com/burnt-tea-dev/senluo-bedrock-core/blob/7f015e92ed7536e5ed64317338eda55968e0c4ae/docs/FAMILY-ASSEMBLY.md#historical-recipes).
Use their explicit descriptors and original toolchain. No old archive, SHA,
source history, UUID or save migration is removed by this documentation change.

`public-minimal-grilling-g212-cookery20012.json` and
`public-minimal-grilling-g213-cookery20012.json` remain explicitly selectable
**package-only historical candidates**. Their success does not establish a
complete resource-player route. G213's unchanged four-pack aggregate
`96856304f186320014636d3cca81f2e8429edee433780c761de82bb1b029423e`
is the retained failing structural control, not the newly presented G218 pack.

## Recipe and publication boundaries

Recipes retain schema 1: pinned `inputs`, selected `packs`, `order`, file
sources (`archive`, `input`, `owned`, `generated`) and exact transforms. The
assembler verifies input hashes, source/output file hashes, UUID/module
identities, manifests, expected trees and closed pack dependencies. Output
paths must be new. It stages locally and cleans only its own failed output;
it never writes a world, deploys LIVE or changes the input archives.

Public recipes additionally declare one behavior-player owner and the required
resource-player capability. Generated resource-player content stays in the
user-local recipe/output; its official reference license is retained. This
record is not renderer or native gameplay acceptance.

Toolkit and SDK identities are separate from generated game-pack identities.
The existing immutable toolkit history is not rewritten to bless these newer
source bytes. Toolkit 0.30.0's source allowlist now includes the public player descriptor
and its review evidence, with pinned content hashes. This PR prepares those
release inputs; it does not create a Release or ship any author archive.
