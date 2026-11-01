# Local Cookery adapter

This tool builds a user-local Cookery archive from the clean Cookery 1.6.4
release and the pinned Grilling release. The release descriptor pins both
archives, the Grilling declaration and every SDK helper. The adapter reads the
hook instructions from that declaration; it does not publish author files.

The Grilling input for this first SDK release is exactly 2.8.201, SHA256
`5cef5795b5ef40a800d8ac5592419dbcca40eeb7b2e036ed5c3c8c2bd7901fe4`.
It is a development companion, not a claim that the full server family or client
has been accepted. If that archive is not available as a separate Grilling
Release, reproduce it from its public source without any private integration:

```sh
git clone https://github.com/burnt-tea-dev/kaleidoscope-grilling-unofficial.git grilling
git -C grilling checkout 61864d017a1e4e9847325cd7313098b4379dc2e9
python3 tools/build_grilling_input.py --source grilling --output Grilling-2.8.201.mcaddon
```

The builder validates both complete runtime trees and the final archive hash.
It refuses changed source bytes. It does not download anything or publish the
generated archive. Use this local archive as the `--grilling` input below.

```sh
python3 tools/install_cookery.py \
  --cookery /path/to/clean-cookery.mcaddon \
  --grilling /path/to/pinned-grilling.mcaddon \
  --output /path/to/Cookery-local-adapted.mcaddon
```

Download clean inputs from their maintainers. The command checks archive
hashes, ZIP paths and sizes, author preimages, unique insertion anchors, SDK
helper hashes and patched file hashes. It updates the pinned local BP/RP pack
version while preserving pack and module UUIDs and unrelated dependencies.
It copies only files listed by the Grilling declaration. No archive is
extracted to disk. It refuses to overwrite the inputs or an existing output.

Use the original Cookery 1.6.4 download (file 9317031), SHA256
`aa760058f43dce462778a3ac570ba5c1af629cb3b60fdc31bf457e589822eb83`.
Enable both generated Cookery sides and both Grilling sides in the test world.
Native validation uses BDS 1.26.60.6; Grilling requires `@minecraft/server`
2.12.0-beta and the Beta APIs experiment. Core itself adds no runtime pack.
Keep a complete stopped-world backup and test the old save on a copy before
updating a server. Never overwrite a world database with a diagnostic world.

The command also creates `OUTPUT.receipt.json`. Keep that receipt with the
local output: it records input and output hashes, pack identities, changed
paths, and SDK helper hashes. Treat adapted output as a local build, not an
official Cookery download. Installing it into a world or validating saved
world behavior is a separate step; a successful build does not prove client
gameplay.

## Current G205 guide-decoding candidate

For the reviewed G205 source candidate, use the
`adapters/cookery-1.6.4-grilling-2.8.205-guide-decoding.json` descriptor with
the same installer. It keeps the receiver's startup patch and adds a pinned
Core helper that scans large guide JSON in small slices. Both Cookery pack
versions become `[1, 6, 20004]`; pack and module UUIDs stay with the author.
Toolkit 0.7.0 and SDK 0.1.0 are separate versions. The 0.6.0
`guide-startup` descriptor remains available to reproduce local version
`[1, 6, 20003]`.

```sh
python3 tools/install_cookery_from_descriptor.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/pinned-grilling-2.8.205.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.205-guide-decoding.json \
  --output /path/to/private-output/cookery-g205-decoding.mcaddon
```

Keep the generated archive and receipt outside this repository. This is a
local source build; it does not establish full-family, saved-world or client
acceptance.
