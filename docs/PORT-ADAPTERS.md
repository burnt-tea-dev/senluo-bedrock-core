# Owned-port adapters

These tools join our Grilling port to separately downloaded author inputs.
They create user-local files. They do not modify a server or publish author
archives.

## Cookery 1.6.4 with Grilling 2.8.203

The G203 descriptor pins Grilling source commit `c879943b`, both runtime tree
hashes, the board API declaration, and each copied helper hash. Build the G203
input from that reviewed public Grilling checkout:

```sh
python3 tools/build_grilling_input.py \
  --source /path/to/kaleidoscope-grilling-unofficial \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.203.json \
  --output /path/to/local-inputs/grilling-2.8.203.zip
```

Then provide the original Cookery 1.6.4 `.mcaddon` as a separate local input:

```sh
python3 tools/install_cookery_from_descriptor.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/local-inputs/grilling-2.8.203.zip \
  --output /path/to/local-output/cookery-g203.mcaddon
```

The adapter preserves Cookery's existing pack UUIDs and raises both pack
versions to `[1, 6, 20002]`. Its code calls the existing Core installer. The
output archive and receipt are local build products, not a public Cookery
release.

## Cookery 1.6.4 with the G205 source candidate

The G205 descriptor pins Grilling source commit
`83026c0bb41fa6574e50a9b5a61cfb3b473bc59c`, its Git and runtime tree hashes,
the board API declaration, and every copied Core helper hash. Rebuild the
Grilling input from that clean checkout:

```sh
python3 tools/build_grilling_input.py \
  --source /path/to/grilling-guide-perf-source-r1 \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.205.json \
  --output /path/to/local-inputs/grilling-2.8.205.mcaddon
```

Then use the original Cookery 1.6.4 archive and the G205 descriptor:

```sh
python3 tools/install_cookery_from_descriptor.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/local-inputs/grilling-2.8.205.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.205.json \
  --output /path/to/local-output/cookery-g205.mcaddon
```

This source candidate has not been admitted as a public Grilling Release or as
a full-family/client-tested combination. Its reviewed Core helper files match
G203 byte-for-byte, and the current local rebuild has the same Cookery archive
hash; it therefore remains version `[1, 6, 20002]` rather than receiving a
version-only bump.

## Immersive Eating first-person compatibility

For users who also install Immersive Eating 1.1.0, the optional compatibility
export reads that author archive's player definition and first-person
controller, plus the current Grilling controller. It writes only a composed
controller file and receipt:

```sh
python3 tools/export_ie_grilling_compat.py \
  --ie /path/to/original-immersive-eating-1.1.0.mcaddon \
  --grilling /path/to/local-inputs/grilling-2.8.203.zip \
  --output /path/to/local-output/ie_grilling_first_person.render_controllers.json
```

The generated file is checked against the reviewed output hash. It is not a
standalone pack; include it only in a local compatibility build that also
contains the original Immersive Eating pack. The tool does not redistribute
Immersive Eating files.

These source and hash checks prove that the local transformations match the
pinned inputs. They do not prove Bedrock engine behavior, rendered client
results, or full-family parity with LIVE.

The G205 source-candidate first-person descriptor is
`adapters/ie-grilling-2.8.205.json`. It is included because the pinned G205
Grilling controller bytes match G203 exactly; its generated controller hash is
therefore unchanged. It adds no Grilling or Immersive Eating gameplay change.
Use it only with the matching original Immersive Eating archive and G205
Grilling input. This is still a local source candidate, not client acceptance.

## Cookery guide startup receiver (G205, toolkit 0.6.0)

Use `adapters/cookery-1.6.4-grilling-2.8.205-guide-startup.json` with the normal installer command and `tools/install_cookery_from_descriptor.py` to reproduce the earlier local version 1.6.20003. This runs the G205 adapter first, then applies the Core-owned startup stage. Its original helper hash, receiver operations and output remain unchanged.

## Cookery incremental guide decoding (G205, toolkit 0.7.0)

The current local source candidate uses
`adapters/cookery-1.6.4-grilling-2.8.205-guide-decoding.json`. It repeats the
same G205 and receiver operations, but copies the new Core-owned incremental
decoder into the existing helper destination. Cookery BP/RP and their modules
become `[1, 6, 20004]`; the author pack UUIDs and existing save keys stay the
same. The descriptor's receiver preimages, postimages and operations match the
0.6 startup descriptor exactly. The SDK remains 0.1.0.

```sh
python3 tools/install_cookery_from_descriptor.py \
  --cookery /path/to/original-cookery-1.6.4.mcaddon \
  --grilling /path/to/pinned-grilling-2.8.205.mcaddon \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.205-guide-decoding.json \
  --output /path/to/private-output/cookery-g205-decoding.mcaddon
```

Keep the generated archive and receipt outside this repository. This source
build does not prove full-family, saved-world or client acceptance.

## G206 selected player presentation

G206 transports both hands through four player properties and public player
variables. The selected complete player must apply its presentation extension;
replacing only the Grilling archive leaves the new attachables without readers.

Use the exact public Grilling source checkout pinned in
[`ie-grilling-2.8.206.json`](../adapters/ie-grilling-2.8.206.json), and obtain the
original IE1.1.0 archive separately. The local tool calls Grilling's canonical
`tools/compose_held_player.py`; the server integration uses the same composer.

```sh
python tools/build_grilling_input.py --source /path/to/grilling-source \
  --descriptor adapters/cookery-1.6.4-grilling-2.8.206-command-context.json \
  --output /new/Grilling-2.8.206.mcaddon
python tools/install_player_presentation.py --ie /inputs/original-ie.mcaddon \
  --grilling /new/Grilling-2.8.206.mcaddon \
  --grilling-source /path/to/grilling-source --output /new/ie-g206.mcaddon
```

The output is a user-local IE1.1.20002 pair. It retains the author's pack and
module UUIDs, scripts, assets and save ownership. Grilling remains the sole BP player owner. It
extends the original RP player, combines the existing first-person arm
controller in place, advances both manifest/module versions and pins Grilling.
Only the BP minimum engine context advances to1.26.60. Select this IE pair above
Grilling in both pack lists; retain the other required original inputs.

The canonical Grilling composer can produce a28-property TACZ source preview.
This installer currently supports the selected LIVE combination without TACZ.
A complete TACZ installation also needs one behavior-player owner and verified
left-arm animation routing; these are separate from merging the two player JSON
files. The optional TACZ source preview is not admitted by this descriptor.
Original and generated author archives never belong in public Releases.
Source checks do not establish real first-person, food, sound or multiplayer
acceptance.

## Optional TACZ test profile

Toolkit0.10 adds a separate local installer for the reviewed TACZ1.0.3 input.
It uses the original author archive and the same G206 source pinned by the IE
adapter. Obtain the original TACZ archive from its author; it is never a public
Core release asset.

```sh
python tools/install_tacz.py --tacz /inputs/original-tacz.mcaddon \
  --ie /inputs/original-ie.mcaddon --grilling /new/Grilling-2.8.206.mcaddon \
  --grilling-source /path/to/grilling-source --output /new/tacz-g206.mcaddon
```

The local output is a paired TACZ1.0.20004 with original UUIDs and script APIs.
It contains the complete28-property player, Grilling's public held variables,
85 left-arm animation repairs, the repaired original53-bone model, the shared
IE/G first-person controller and a normal-skeleton offhand route. The legacy
push flags become the equivalent modern block-only push component; two AWP
`panel` typos become `pane`. Original scripts, textures, other bones and metadata
are retained. Source tests are separate from real gun, hand, sound and eating
acceptance.

Use [`owned-t194-g206-w180-tacz-test.json`](../adapters/owned-t194-g206-w180-tacz-test.json)
only as an optional isolated test profile. Disable the raw TACZ pair; place the
adapted pair above Grilling and IE. The assembler checks the exact hashes of
both BP player definitions and refuses an unreviewed duplicate or reversed
priority. The composed TACZ player is the selected effective owner; unchanged
G206 supplies the lower-priority four-property definition. Private full-family
testing must also put the adapted TACZ RP above its private player overlay.
This profile does not automatically enable TACZ on LIVE.

The minimum engine for the adapted TACZ pair is1.26.60. Its original
`@minecraft/server`1.18.0 and `@minecraft/server-ui`1.3.0 requirements remain;
the GameTest module used by isolated validation is not part of the output.
Keep a complete stopped-world backup before switching player definitions.

## TACZ startup table preparation

Toolkit0.11 prepares13 fixed string-table rotations from the exact author input
before writing the local pair. The [obfuscator documentation](https://github.com/javascript-obfuscator/javascript-obfuscator#stringarrayrotate)
describes this as a fixed generated shift; its RC4 decoders otherwise repeat
substantial startup work. The recipe pins each script preimage, both changed
byte spans, rotation, table count and exact output hash. The tool never executes
author scripts. Original decoders, imports, event subscriptions and gameplay
code outside those two spans remain byte identical.

The reviewed preparation preserves6016 encoded table entries and all5673
unique literal decoder calls checked against the original post-bootstrap
state. This equivalence check does not replace the actual engine performance
gate, saved-world checks or client gun/eating evidence. The failed20003
performance record remains [unchanged](validation-0.10.0.json).
