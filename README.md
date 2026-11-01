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
Liquor 0.1.180. Toolkit 0.12.1 contains the unchanged 0.12.0 adapters: local
Cookery 1.6.20007 and Immersive Eating 1.1.20002. It preserves welcome chat
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
helper intentionally rejects those immutable older helper pins. The optional
TACZ route uses local 1.0.20004, retains 24 gun properties alongside Grilling's
four, and has its own client acceptance. It is not selected for LIVE merely
because its local archive can be built.
