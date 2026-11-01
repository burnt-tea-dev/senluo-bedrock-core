# Local Cookery adapter

For the current G206 / Cookery 1.6.20007 installation, follow the
[current family commands](FAMILY-ASSEMBLY.md#current-g206-installation).
That route keeps the welcome message and both startup repairs.
The examples below document earlier pinned adapters; use their matching
original toolkit source to reproduce them.

## Historical SDK and G201 installation

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

## G205 guide-decoding source candidate (0.7.0)

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

## G205 command-context source candidate (0.8.0)

Use `adapters/cookery-1.6.4-grilling-2.8.205-command-context.json` with the
same clean author and G205 inputs. It builds the fresh local BP/RP pair
`[1, 6, 20005]`. The BP minimum engine becomes `[1, 26, 60]`; the RP's
author requirement stays unchanged. Older clients cannot use this route.
The welcome script, other gameplay files, UUIDs and save keys are preserved.
The installer refuses to lower an author's engine requirement.

On isolated BDS 1.26.60.6, changing only the diagnostic BP engine declaration
from 1.26.1 to 1.26.60 reduced its first network Player message from 155 ms
to 1 ms, with both messages received. The same declaration change in Cookery
made the unchanged welcome call take less than 1 ms in both the eight-side
public fixture and the full family fixture. No warm-up message or forwarding
pack was used. This supports an engine command-context initialization cause;
the stripped engine does not provide a confirmed internal function name.

These focused measurements do not establish full-family admission. The
full-family fixture still reported other Cookery startup Slowdowns. Saved-world
first load/restart, rollback, real client and normal multiplayer checks remain
separate. See [the validation record](validation-0.8.0.json).

The G206 source route is pinned by
[`cookery-1.6.4-grilling-2.8.206-command-context.json`](../adapters/cookery-1.6.4-grilling-2.8.206-command-context.json).
It retains the0.8 receiver/decoder and original welcome, uses the reviewed
G206 helpers, and advances the paired local Cookery identity to1.6.20006.
Use the selected-player adapter alongside it; see [port adapters](PORT-ADAPTERS.md).
