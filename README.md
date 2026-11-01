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

The family assembler retains the pinned G203 and G205 recipes. The G205 inputs
are Tavern 0.6.194, Grilling 2.8.205 and World Liquor 0.1.180. The newest local
Cookery route is the 0.8.0 command-context descriptor, which builds Cookery
1.6.20005 and requires Bedrock 1.26.60 for its behavior pack. It retains the
guide decoder, original welcome and author pack IDs. The 0.7.0 descriptor
still reproduces Cookery 1.6.20004.
The 0.6.0 startup descriptor remains available and reproduces Cookery
1.6.20003. These local archives are source candidates, not public Releases or
full-family/client acceptance; see the adapter and assembly instructions.

Author archives, complete author modules, worlds, private integration history,
server configuration and credentials are not distributed here. Obtain Cookery
from its [author's project](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial).
This unofficial project is not affiliated with Mojang or the original authors.

The SDK and newly written tools are BSD-3-Clause; see [LICENSE](LICENSE).
Gameplay helpers supplied by the separate Grilling addon retain that project's
notices. Locally adapted author content retains its original license and credits.

The guide-decoding descriptor applies the same Core-owned receiver repair and
copies a separately versioned incremental JSON decoder. It builds local
Cookery 1.6.20004 and leaves the G205 input unchanged. Its output is user-local
only.
