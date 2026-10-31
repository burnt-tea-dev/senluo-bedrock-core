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
