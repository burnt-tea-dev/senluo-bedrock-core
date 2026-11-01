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

The current toolkit source candidate adds G206's selected-player presentation
adapter. It builds user-local Cookery1.6.20006 and IE1.1.20002 using original
author inputs; the original welcome remains. Public and server integration call
the same canonical Grilling player composer. See [owned-port adapters](docs/PORT-ADAPTERS.md).
The G203 and G205 descriptors remain immutable for reproducing earlier local
outputs. Current source candidates are not a public Release or rendered/client
acceptance. See each pinned descriptor and validation record.

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

The0.10.0 source candidate adds a separately generated optional TACZ test
profile. Its28-field native player and six saved-world flows pass, but the
TACZ script performance gate currently fails; it is not approved for LIVE or a
public Release. The standard no-TACZ route remains the0.9.0 validated assembly.
See [the0.10 validation record](docs/validation-0.10.0.json).
