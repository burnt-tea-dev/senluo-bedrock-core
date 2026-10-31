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
