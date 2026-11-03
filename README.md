# Senluo Bedrock Core

Unofficial shared SDK and local integration tools for the Senluo Bedrock addon family.

Core is a build-time SDK. Its code is copied into each consuming pack; it does
not add a behavior pack, a global tick loop or a new save-data owner.

```text
Core SDK ──→ Grilling (event routing and public food metadata)
        └──→ Cookery's original host (through Grilling's reviewed adapter)
Local installer + your original Cookery archive ──→ your adapted local archive
```

**Public Grilling installation (no family required):** select
`build_owned_family_recipe.py --profile public-minimal` following the
[Grilling + Cookery 1.6.4 local-install instructions](docs/FAMILY-ASSEMBLY.md#public-minimal-grilling--cookery-only-opt-in).
This uses the same pinned Cookery host installer and family assembler, but
requires only the Grilling and locally adapted Cookery BP/RP pairs. IE, TACZ,
Tavern, World Liquor and private packs are **not required**.

The [complete G212 family installation](docs/FAMILY-ASSEMBLY.md#current-g212-installation)
and older exact-version IE/TACZ recipes remain available by explicit selection.
Pack/module UUIDs, item IDs and save ownership are retained. Back up a stopped
world and test a copy before upgrading. Builds are not client gameplay PASS.

- [SDK contract and source ownership](docs/SDK.md)
- [Cookery local installation](docs/COOKERY.md)
- [Local family assembly tool](docs/FAMILY-ASSEMBLY.md)
- [Owned-port adapters](docs/PORT-ADAPTERS.md)
- [Validation limits](docs/VALIDATION.md)

Public and server integration use the same canonical Grilling player composer
and Core guide helper. The public-minimal entry covers Grilling + the real Cookery host dependency;
the other owned ports and third-party compatibility are separate, opt-in
profiles rather than required downloads. Native and
save evidence do not establish rendered client acceptance. Get published
assets from [Releases](https://github.com/burnt-tea-dev/senluo-bedrock-core/releases).

Author archives, complete author modules, worlds, private integration history,
server configuration and credentials are not distributed here. Obtain Cookery
from its [author's project](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial).
This unofficial project is not affiliated with Mojang or the original authors.

The SDK and newly written tools are BSD-3-Clause; see [LICENSE](LICENSE).
Gameplay helpers supplied by the separate Grilling addon retain that project's
notices. Locally adapted author content retains its original license and credits.

Earlier descriptors and their validation records remain as history. Reproduce
older Cookery decoding outputs with their original toolkit source; the 0.12
helper intentionally rejects those immutable older helper pins. The optional TACZ route now builds local 1.0.20014 with the resource stack PBR
capability, while retaining 24 gun properties alongside Grilling's four. Use
[the current TACZ family recipe](adapters/owned-t194-g212-w180-station-performance-tacz.json). It requires
its own full-family, saved-world, rollback and client evidence. Toolkit 0.12
releases and their TACZ20004 recipes remain historical outputs.

Cookery recipe registration now processes at most four incoming messages per tick, with a one-millisecond target. Original registration validation, FIFO replacement order, every recipe and welcome chat remain. The synchronous exported registration function is unchanged. Use [the current Cookery descriptor](adapters/cookery-1.6.4-grilling-2.8.212-station-performance.json) and [optional TACZ family descriptor](adapters/owned-t194-g212-w180-station-performance-tacz.json). Native and client acceptance remain separate from installer verification.

The source and family builder defaults select the current G212/Cookery20012 installation. Historical G201/G203 and prior Cookery recipes remain available through an explicit `--descriptor`.

Archive writers use canonical ZIP metadata on both Windows and Linux.
SDK0.1.0 retains its archive bytes. The current descriptors pin fresh paired
identities; older recipes retain their recorded outputs.

Toolkit 0.17 fixes TACZ client resource errors. Use the exact `composer_source` commit
in [the current TACZ descriptor](adapters/tacz-1.0.3-grilling-2.8.212.json) as
`install_tacz.py --grilling-source`. This is the animation tool source; the separately
pinned Grilling archive retains its reviewed gameplay bytes.
Left-arm curves retain constant keyframes and use a separate animation weight.
The four pistol walk aliases use the author's existing common pistol pose;
casing and smoke aliases resolve to existing author particles. The dead G36
third-person slide reference is removed: no missing sliding pose is invented.
The current family recipe uses TACZ 1.0.20014; explicit historical recipes retain
their recorded older outputs. Client rendering/audio and complete saved-world
validation must still pass before use; a successful local build is not acceptance.

Toolkit 0.20 retains the TACZ HUD/form controls and keeps oil-pot
animation weights free of actor queries during skin previews. The current local
TACZ installer requires `--source-assets /path/to/source-assets` (the existing
`--source-sounds` flag is also accepted). The current descriptor pins the seven
source sounds plus four pre-SkinPack gun textures and three matching cosmetic
models. The pinned CI workflow shows the separate downloads and exact archive
and file verification. The cosmetic source is a mirror of the removed Bedrock
1.0.2 translation, not a currently verified official author download. Only those
seven cosmetic files are selected; its code is not installed. The 1.0.3 scripts,
IDs and mechanics remain, with a target-validity repair before native hit queries.
Public source/SDK archives contain no author audio, textures or models.

Sound path spelling is corrected against the existing author assets. Broken
CAR15/PKM/Tabukar sound registrations with no corresponding item definitions are
retired; no replacement gun, sound stub or new gameplay is introduced. Original
source audio was restored for the supported AKM, MP5, G3, P90 and minigun cues.
Native rendering, listening, complete-family saves and rollback remain separate.

TACZ20010 also corrects the missing `textures/nothing` reference in82 held-item
attachables to the author-shipped `textures/ikon/empty` transparent pixel. The
existing gun geometry, render controllers, animation and pixel files are retained.

The portable station helper avoids rewriting unchanged native displays and
saved JSON. Cooking still advances every original loaded tick. It rechecks
loaded or removed replicas and reads actual saved properties before writes.
Cookery-only lantern/tray geometry, basin and ChineseFood mold repairs are
outside the three-port integration scope. No author files are published here.

Toolkit0.23 completes the oil-preview guard in `pre_animation`, which skin
previews can also execute without a gameplay actor. UI models keep native arm
poses; world first/third-person rendering retains the prior held-data predicate.
Use the current G207 source pin for both local IE and TACZ composition. G207
changes the G206 package manifests and adds license notices; gameplay payloads
are unchanged. Source tests cover UI entry/exit; real client preview acceptance
remains required. Earlier complete archive identities remain in explicit recipes.

Toolkit0.25 pairs the merged native-oil-POI Grilling source with the current
local installers. Original gun appearance, UI-safe composition, shared station
behavior, all UUIDs and save owners are preserved. No new rendered-client or
multiplayer acceptance is implied.
