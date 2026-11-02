# Senluo Bedrock Core

Unofficial shared SDK and local integration tools for the Senluo Bedrock addon family.

Core is a build-time SDK. Its code is copied into each consuming pack; it does
not add a behavior pack, a global tick loop or a new save-data owner.

```text
Core SDK ──→ Grilling (event routing and public food metadata)
        └──→ Cookery's original host (through Grilling's reviewed adapter)
Local installer + your original Cookery archive ──→ your adapted local archive
```

The current installation uses Tavern 0.6.194, Grilling 2.8.206 and World
Liquor 0.1.180. Toolkit 0.16.0 retains the current G206 and Immersive Eating adapters: local
Cookery 1.6.20008 and Immersive Eating 1.1.20002. It preserves welcome chat
and native recipe ordering while avoiding repeated full recipe sorts.
Start with [the current family installation](docs/FAMILY-ASSEMBLY.md#current-g206-installation).
Pack/module UUIDs, item IDs and save ownership are retained. Back up a stopped
world and test a copy before upgrading.

- [SDK contract and source ownership](docs/SDK.md)
- [Cookery local installation](docs/COOKERY.md)
- [Local family assembly tool](docs/FAMILY-ASSEMBLY.md)
- [Owned-port adapters](docs/PORT-ADAPTERS.md)
- [Validation limits](docs/VALIDATION.md)

Public and server integration use the same canonical Grilling player composer
and Core guide helper. The three owned ports and required glue are the public
parity scope; unrelated third-party addons are separate downloads. Native and
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
helper intentionally rejects those immutable older helper pins. The optional TACZ route now builds local 1.0.20007 with the resource stack PBR
capability, while retaining 24 gun properties alongside Grilling's four. Use
[the current TACZ family recipe](adapters/owned-t194-g206-w180-recipe-ingress-tacz.json). It requires
its own full-family, saved-world, rollback and client evidence. Toolkit 0.12
releases and their TACZ20004 recipes remain historical outputs.

Cookery recipe registration now processes at most four incoming messages per tick, with a one-millisecond target. Original registration validation, FIFO replacement order, every recipe and welcome chat remain. The synchronous exported registration function is unchanged. Use [the current Cookery descriptor](adapters/cookery-1.6.4-grilling-2.8.206-recipe-ingress.json) and [optional TACZ family descriptor](adapters/owned-t194-g206-w180-recipe-ingress-tacz.json). Native and client acceptance remain separate from installer verification.

The source and family builder defaults select the current G206/Cookery20008 installation. Historical G201/G203 and prior Cookery recipes remain available through an explicit `--descriptor`.

Archive writers use canonical ZIP metadata on both Windows and Linux. The G206, Cookery20008, IE20002 and SDK0.1.0 archive bytes remain unchanged. The current TACZ output is pinned by its descriptor; older TACZ20005 recipes remain historical.

Toolkit 0.17 fixes TACZ client resource errors. Use the exact `composer_source` commit
in [the current TACZ descriptor](adapters/tacz-1.0.3-grilling-2.8.206.json) as
`install_tacz.py --grilling-source`. This is the animation tool source; the separately
pinned Grilling 2.8.206 archive and its runtime source remain unchanged.
Left-arm curves retain constant keyframes and use a separate animation weight.
The four pistol walk aliases use the author's existing common pistol pose;
casing and smoke aliases resolve to existing author particles. The dead G36
third-person slide reference is removed: no missing sliding pose is invented.
The current family recipe uses TACZ 1.0.20009; explicit historical recipes retain
their recorded older outputs. Client rendering/audio and complete saved-world
validation must still pass before use; a successful local build is not acceptance.

Toolkit 0.19 retains the TACZ HUD/form controls and keeps oil-pot
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
