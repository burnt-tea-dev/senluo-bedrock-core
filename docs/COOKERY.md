# Local Cookery adapter

This tool builds a user-local Cookery archive from the clean Cookery 1.6.4
release and the pinned Grilling release. The release descriptor pins both
archives, the Grilling declaration and every SDK helper. The adapter reads the
hook instructions from that declaration; it does not publish author files.

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

The command also creates `OUTPUT.receipt.json`. Keep that receipt with the
local output: it records input and output hashes, pack identities, changed
paths, and SDK helper hashes. Treat adapted output as a local build, not an
official Cookery download. Installing it into a world or validating saved
world behavior is a separate step; a successful build does not prove client
gameplay.
