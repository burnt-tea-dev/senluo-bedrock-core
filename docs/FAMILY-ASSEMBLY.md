# Local assembly: public first, family opt-in

Core is a build-time tool, not another gameplay pack. The existing
`build_owned_family_recipe.py` and `assemble_family.py` serve both public and
optional family installations. They do not deploy a server or change a world.

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

**Unreleased source candidate, not a ready-made public Release or client PASS.**
The current `--profile public-minimal` selects exactly two addons: Grilling
BP/RP and locally adapted original-author Cookery 1.6.4 BP/RP. Tavern,
世界名酒, Immersive Eating, TACZ, private repair packs and server family locks
are neither inputs nor prerequisites. Unrelated addons are not required to be
on a Senluo combination whitelist; actual player-definition conflicts need
separate, explicit integration rather than silent replacement.

### What was missing, and what this route changes

The historical G213 package-only four-pack output assembled successfully but contained **no
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

The source input is now canonical G234, but the local output has a **new paired
Grilling identity 2.8.235 (G235)**. Both existing Grilling UUIDs, module UUIDs,
item/entity IDs, gameplay scripts and save owners remain. Owning manifests and
mutual dependency versions advance together; Cookery dependencies are rebound
from original `[1,6,4]` to the locally adapted `[1,6,20012]`. The original
archives and all historical output identities are never overwritten.

Canonical G234 from Grilling #360 and the older Core G233 → local G234
recipe have the same Grilling UUID/version but different bytes. The current
route therefore uses a new local G235 identity, not a rewritten G234 output.
This is a source/package identity conflict; no installed-world incident was
observed. The old G233 descriptor, input/output hashes and source references
remain frozen for historical reproduction with explicit selection.

### Build references and genuine addon inputs

Use a clean Grilling source checkout at
`e9d495816dc8961fd86071016a797185f55c7473` (tree
`67288d46f7458406a6f0f6f7f6edd0799861a8d8`). Its original input archive hash is
`c6f153b2ed4596b272524e7ba1c6504f7b76f64ea18f609911ac841a576b0f4d`.

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
**Grilling G234** archive, the existing builder can perform the Cookery local
adaptation, exact two-input recipe, complete G235 player-RP composition and
four-pack assembly **in one command**:

```sh
python tools/build_owned_family_recipe.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/grilling-2.8.234.mcaddon \
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
git -C grilling checkout e9d495816dc8961fd86071016a797185f55c7473
git clone https://github.com/Mojang/bedrock-samples.git vanilla
git -C vanilla checkout 15701fa9c13923f12662984c32c124327e40e3d3
mkdir -p local-inputs

python tools/build_grilling_input.py \
  --source ./grilling \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.234-station-performance.json \
  --output ./local-inputs/grilling-2.8.234.mcaddon

python tools/install_cookery_from_descriptor.py \
  --cookery /path/to/clean-original-Cookery-1.6.4.mcaddon \
  --grilling ./local-inputs/grilling-2.8.234.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.234-station-performance.json \
  --output ./local-inputs/cookery-g234.mcaddon

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

The G234 input and all 16 copied host helpers were checked against the new
exact-source descriptor. The adapted Cookery20012 archive remains byte-identical:
`a13cf4e8f48308c73c0e9acf72352026a0bd0becc9a5c89fff1670e7d9e3c144`.
A real clean-author local run passed Node 19/19 and Python 75/78, with three
explicit skips (historical G213 and two optional TACZ input cases). The public
recipe and direct installer tests actually ran, including consecutive builds,
four-pack identity/dependency closure, unique BP/RP player ownership, unchanged
original inputs and rejected altered inputs. The local G235 aggregate is
`ade40b13dc27bd5f8096dfbe7d1fca638b9599c72a3de0a3aef268f0ed91a3c7`.

Before this candidate, 59 accessible Core and 495 accessible Grilling
branch/tag refs were checked in their adapter descriptors, release histories
and canonical pack manifests; none claimed G235. Organization issue, commit
and default-branch code searches also found no G235 allocation. This is a
bounded reservation check, not proof about unshared private work. G235 is
selected provisionally for this local recipe, not externally reserved by
a global registry. Future canonical or local producers must coordinate
instead of reusing it for different bytes. No
published toolkit/package hashes were regenerated, and no Release was made.
The existing Toolkit 0.33.0 history describes its original source only; a
future toolkit publication must allocate a new identity for changed sources.

Keep `receipt.json`: it distinguishes source inputs, transformed manifests,
new output identities, behavior-player owner and resource-player owner.
The public route does not download IE, TACZ, Tavern or 世界名酒.
The G213/G218 reproduction report remains historical evidence only.
**Actual client rendering, audio, normal gameplay, BDS, upgrade/restart and
multiplayer remain NOT-RUN for this candidate.** Test a disposable world, not
LIVE; retain a stopped-world backup before any later upgrade.

### Historical G233 → local G234 evidence

The following original evidence belongs only to the superseded G233
descriptor. It is not evidence for canonical G234 or local G235. Its recorded
G234 aggregate was also rebuilt with this change and matched the original
`7d578a39a1759a60fae6f53e91b4982b2f01d6b556d3e9ee40393b2cf175f48b`
exactly, using the unchanged explicit descriptor and original source pin.

The G233 input is checked against the new descriptor. The local output is
G234; its hash is recorded by the actual assembler receipt, not inherited from
the historical G218 result. The unchanged Cookery20012 adapter bytes are
retained because the exact host declaration and all 16 copied helpers match.
Real-author reconstruction was executed on this G233/G234 candidate using the
clean author archive above: Node 19/19 passed; Python 77 discovered, 74 passed,
3 explicitly skipped (historical G213 and two optional TACZ real-input cases).
The real direct one-command build ran twice with byte-identical output. A new
real-input regression verifies the four pack identities, closed dependencies,
unique Grilling BP/RP player owners, unchanged original inputs, and rejection
of modified Grilling or Cookery archive bytes without leaving an installation.
The local G234 aggregate SHA256 is
`7d578a39a1759a60fae6f53e91b4982b2f01d6b556d3e9ee40393b2cf175f48b`.
The G219 descriptors are retained byte-for-byte, and their historical G220
aggregate was actually reconstructed with the updated tools, reproducing
`2d4b4d35607fb22f1c9c46b81ab2031196b56b0d7b54bc6cfe9268637dade678`.
These are local package/build results, not a new public Release or engine test.

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

`public-minimal-player.json` preserves the previous G213 → G218 player-complete
recipe. Select it explicitly with the original source references; the new
default is `public-minimal-g234-player.json`. Old descriptors and all previously
published identities remain unchanged. The G219 → local G220 and G233 → local
G234 descriptors also remain byte-for-byte selectable by their explicit paths;
never relabel either historical output as the current source.


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
