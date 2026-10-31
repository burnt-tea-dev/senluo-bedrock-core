# Senluo Bedrock Core

Unofficial shared SDK and local integration tools for the Senluo Bedrock addon family.

Core is a build-time SDK. Its code is copied into each consuming pack; it does
not add a behavior pack, a global tick loop or a new save-data owner.

```text
Core SDK ──→ Grilling (event routing and public food metadata)
        └──→ Cookery's original host (through Grilling's reviewed adapter)
Local installer + your original Cookery archive ──→ your adapted local archive
```

The first adapter targets Cookery 1.6.4 and Grilling 2.8.201. It preserves pack
and module UUIDs, item/block IDs, existing dynamic-property keys and payloads.
The adapted Cookery pair gets its own local version, 1.6.20001. It is not an
official author release. Keep a complete stopped-world backup before upgrading.

- [SDK contract and source ownership](docs/SDK.md)
- [Cookery local installation](docs/COOKERY.md)
- [Local family assembly tool](docs/FAMILY-ASSEMBLY.md)
- [Validation limits](docs/VALIDATION.md)

The generic family assembler is available as local tooling, but this release
does not include a reviewed family recipe. Its output does not establish that
the public downloads have the same gameplay as the live server.

Author archives, complete author modules, worlds, private integration history,
server configuration and credentials are not distributed here. Obtain Cookery
from its [author's project](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial).
This unofficial project is not affiliated with Mojang or the original authors.

The SDK and newly written tools are BSD-3-Clause; see [LICENSE](LICENSE).
Gameplay helpers supplied by the separate Grilling addon retain that project's
notices. Locally adapted author content retains its original license and credits.
