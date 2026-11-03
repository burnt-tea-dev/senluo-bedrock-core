# Local assembly: public first, family opt-in

Core is a build-time tool, not another gameplay pack. The existing
`build_owned_family_recipe.py` and `assemble_family.py` serve both public and
optional family installations. They do not deploy a server or change a world.

## Public-minimal installation (Grilling + Cookery only)

<a id="public-player-presentation"></a>

**Unreleased source candidate, not a ready-made public Release or client PASS.**
The current `--profile public-minimal` selects exactly two addons: Grilling
BP/RP and locally adapted original-author Cookery 1.6.4 BP/RP. Tavern,
世界名酒, Immersive Eating, TACZ, private repair packs and server family locks
are neither inputs nor prerequisites. Unrelated addons are not required to be
on a Senluo combination whitelist; actual player-definition conflicts need
separate, explicit integration rather than silent replacement.

### What was missing, and what this route changes

The previous G213 four-pack output assembled successfully but contained **no
resource `minecraft:player` definition**. Its behavior-player ownership and
manifest closure checks could not prove that held food, plates and oil had the
required public variables and animation aliases. The original failure and the
repaired source evidence are recorded in
[the fixed-input report](validation-public-player-20261103.json).

This profile uses the existing `install_player_presentation.compose_players`
entry and Grilling's canonical `compose_held_player.py`, without its IE/TACZ
branches. A complete official vanilla player reference is composed into
**Grilling's existing RP**, not a fifth patch pack. Vanilla materials, textures,
geometry, render controllers and attachables are retained. The assembler
requires exactly one resource-player owner with the declared public variables
and animation aliases; a competing player is not silently overwritten.

The source input remains G213, but the local output has a **new paired
Grilling identity 2.8.218 (G218)**. Both existing Grilling UUIDs, module UUIDs,
item/entity IDs, gameplay scripts and save owners remain. Owning manifests and
mutual dependency versions advance together; Cookery dependencies are rebound
from original `[1,6,4]` to the locally adapted `[1,6,20012]`. The original
archives and old G212/G213 output identities are never overwritten.

### Build references and genuine addon inputs

Use a clean Grilling source checkout at
`6ea3fa5222c56d8ee2451c7c2d51e7d1dc5894e3` (tree
`9b7cd7c6e6be0a8a808fb73c27c67af9c3a1b224`). Its original input archive hash is
`ba073d40ad2bbf3ef8f68ea1121c3f9d9d81dd10acdb4085eb2bf15b0c000643`.

Obtain clean Cookery 1.6.4 from
[the author's project](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial),
file 9317031, SHA256
`aa760058f43dce462778a3ac570ba5c1af629cb3b60fdc31bf457e589822eb83`.
Grilling currently needs Cookery's host-extension interface, so local adaptation
is still necessary. **This is a remaining installation burden; the family has
been removed, not magically replaced by an already-published one-click pack.**
Do not redistribute the original or adapted Cookery archive through this repo.

The official Mojang reference is
[bedrock-samples 15701fa9](https://github.com/Mojang/bedrock-samples/tree/15701fa9c13923f12662984c32c124327e40e3d3),
whose `version.json` identifies 1.26.60.5. It is **a build reference, not an
additional addon to enable in the world**. The descriptor verifies the exact
player and license Git blob identities. The original Mojang license accompanies
the local composed RP; no author archive, vanilla sample, or generated complete
player definition is published in Core's source repository.

### Commands

### Direct local build (recommended)

Once you have the **clean original Cookery 1.6.4 archive** and the reviewed
**Grilling G213** archive, the existing builder can perform the Cookery local
adaptation, exact two-input recipe, complete G218 player-RP composition and
four-pack assembly **in one command**:

```sh
python tools/build_owned_family_recipe.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/grilling-2.8.213.mcaddon \
  --grilling-source ./grilling --vanilla-source ./vanilla \
  --output ./public-minimal-output
```

The `grilling-source` and `vanilla-source` directories are the exact clean
build references already identified above; they are **not** additional addons
for players to install. The output remains `public-minimal.mcaddon` with four
packs and the completed resource player, plus receipt and installation metadata.
It does not call the IE/TACZ player adapter, depend on the private family, or
accept unrelated Grilling builds with unreviewed manifests or changed helpers.
This is a convenience entry into the **same existing installer and assembler**;
the separate commands below remain available for reproducing each step.


From this candidate's Core source checkout (Python 3 and Node.js available):

```sh
git clone https://github.com/burnt-tea-dev/kaleidoscope-grilling-unofficial.git grilling
git -C grilling checkout 6ea3fa5222c56d8ee2451c7c2d51e7d1dc5894e3
git clone https://github.com/Mojang/bedrock-samples.git vanilla
git -C vanilla checkout 15701fa9c13923f12662984c32c124327e40e3d3
mkdir -p local-inputs

python tools/build_grilling_input.py \
  --source ./grilling \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.213-station-performance.json \
  --output ./local-inputs/grilling-2.8.213.mcaddon

python tools/install_cookery_from_descriptor.py \
  --cookery /path/to/clean-original-Cookery-1.6.4.mcaddon \
  --grilling ./local-inputs/grilling-2.8.213.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.213-station-performance.json \
  --output ./local-inputs/cookery-g213.mcaddon

python tools/build_owned_family_recipe.py \
  --profile public-minimal --grilling-source ./grilling --vanilla-source ./vanilla \
  --inputs ./local-inputs --output ./public-minimal.recipe.json

python tools/assemble_family.py \
  --recipe ./public-minimal.recipe.json --inputs ./local-inputs \
  --output ./public-minimal-output
```

The two recipe inputs are still only Grilling and adapted Cookery. The aggregate
`public-minimal-output/public-minimal.mcaddon` contains exactly four `.mcpack`
files; enable both BP/RP pairs. Use the descriptor's order, Beta APIs and Points
of Interest requirements. Grilling declares minimum engine `[1,26,60]`,
`@minecraft/server 2.12.0-beta` and `@minecraft/server-ui 2.2.0`.

The fixed-input assembled output SHA256 is
`9dca47ba396ede83a6dfd8146cef58474aa77555de154a400fe28289496ee822`.
Keep `receipt.json`: it distinguishes source inputs, transformed manifests,
new output identities, behavior-player owner and resource-player owner.
Reproduction succeeded without downloading IE, TACZ, Tavern or 世界名酒.
**Actual client rendering, audio, normal gameplay, BDS, upgrade/restart and
multiplayer remain NOT-RUN for this candidate.** Test a disposable world, not
LIVE; retain a stopped-world backup before any later upgrade.

## Current G212 installation

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
