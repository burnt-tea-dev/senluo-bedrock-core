# Senluo Bedrock Core

Unofficial shared SDK and local integration tools for the Senluo Bedrock addon family.

Core is a build-time SDK. Its code is copied into each consuming pack; it does
not add a behavior pack, a global tick loop or a new save-data owner.

```text
Core SDK ──→ Grilling (event routing and public food metadata)
        └──→ Cookery's original host (through Grilling's reviewed adapter)
Local installer + your original Cookery archive ──→ your adapted local archive
```

The original G203 adapter targets Cookery 1.6.4 and Grilling 2.8.203. It
preserves pack and module UUIDs, item/block IDs, existing dynamic-property
keys and payloads. Its user-local Cookery pair uses version 1.6.20002; it is
not an official author release. Keep a complete stopped-world backup before
upgrading.

- [SDK contract and source ownership](docs/SDK.md)
- [Cookery local installation](docs/COOKERY.md)
- [Local family assembly tool](docs/FAMILY-ASSEMBLY.md)
- [Owned-port adapters](docs/PORT-ADAPTERS.md)
- [Validation limits](docs/VALIDATION.md)

The family assembler retains the pinned G203 recipe and adds a source-candidate
recipe for Tavern 0.6.194, Grilling 2.8.205 and World Liquor 0.1.180 plus the
local Cookery adapter. G205 is reproducible from a pinned public source commit,
but is not a public Release or full-family admission. The G205 Cookery adapter
reuses the reviewed helpers; its output stays at 1.6.20002 because rebuilding
it produced the same archive bytes as G203. Full-family and client acceptance
for G205 remain pending; see the assembly instructions.

Author archives, complete author modules, worlds, private integration history,
server configuration and credentials are not distributed here. Obtain Cookery
from its [author's project](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial).
This unofficial project is not affiliated with Mojang or the original authors.

The SDK and newly written tools are BSD-3-Clause; see [LICENSE](LICENSE).
Gameplay helpers supplied by the separate Grilling addon retain that project's
notices. Locally adapted author content retains its original license and credits.
