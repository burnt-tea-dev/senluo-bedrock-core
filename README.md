# Senluo Bedrock Core

Unofficial shared build-time SDK and local integration tools for Minecraft
Bedrock addons. Core does **not** add a gameplay pack, global tick loop or new
save-data owner. Each addon owns its gameplay and saved data.

## Public Grilling: only Grilling and Cookery

Start with the [public-minimal installation guide](docs/FAMILY-ASSEMBLY.md#public-minimal-installation-grilling--cookery-only).
It selects **Grilling BP/RP + locally adapted Cookery 1.6.4 BP/RP**, using the
existing recipe builder and assembler. Tavern, 世界名酒, Immersive Eating,
TACZ, private repair packs and a particular server family are **not required**.
Cookery's gameplay/host interface remains a genuine dependency, not something
the installer pretends to remove.

The reviewed two-archive local route now runs through the existing
`build_owned_family_recipe.py --cookery ... --grilling ... --grilling-source ...
--vanilla-source ... --output ...` command. The two source directories are
build references (canonical Grilling composer and official vanilla player),
not extra installed addons. It produces the same four-pack local candidate,
not a generic promise for arbitrary Grilling or author archive versions.

The current source candidate also composes Grilling's player display into its
own RP using the existing canonical composer and a pinned official vanilla
reference. That reference is a **build input**, not a third addon installed in
the world. The output still has four packs, with no fifth compatibility layer.
IE/TACZ-specific player routes are not executed in the public profile.

**Status: current reviewed four-pack source route; no author archive is published.**
The active profile follows [reviewed G242](adapters/public-minimal.json), including
per-stack skewer icon sources, cold-dish transaction/oil-pot data fixes, plate
pose sources and Ordinary's native totem bypass. Earlier profiles remain
explicit historical inputs. Real original-author reconstruction, unique player
ownership and repeatability passed. Canonical native observations retain their
own tested source and scope, including GUI item data/restart, cold-dish/oil data
and the new Ordinary route. The prior public candidate's grill/chest/board
upgrade, restart and rollback is historical evidence, not a new world run.
See the [current validation and exact limits](docs/validation-public-minimal.json).

The prior public observer invokes production handlers with real native
players/inventories; simulated clicks did not emit the expected global events
in this configuration. Human input, rendering/audio and multiplayer remain
unobserved. No client acceptance gate is added. The old G218 structural result
remains dated history, not proof of this candidate's gameplay.

Local adaptation is still needed because the original Cookery archive lacks
this port's host-extension interface. The source workflow is documented;
removing unrelated family dependencies does not mean that this remaining
installation burden has already disappeared. Author originals stay unchanged.

## Optional integrations are separate

[Historical full-family assembly](docs/FAMILY-ASSEMBLY.md#current-g212-installation),
[owned-port adapters](docs/PORT-ADAPTERS.md), IE and TACZ integration are explicit
choices, not prerequisites for public Grilling. An actual third-party player
override may need an adapter. This does not justify a whitelist that excludes
otherwise unrelated addons, nor a claim of compatibility with every unknown
player definition. Never silently replace another addon's player or weapons.

For backward compatibility, the existing recipe builder's no-profile default
still selects the historical full family; the public commands explicitly use
`--profile public-minimal`. Historical descriptors and their exact source
instructions remain available. They do not establish present-day client or
LIVE status, and their identities are not reused for new output bytes.

## Creative inventory assembly

`tools/creative_catalog.py::regroup_creative(bp_files, rules)` reorganizes one
local BP through its native `menu_category` and crafting-item catalog. It returns
only changed BP file bytes, RP locale labels, and a report of unmapped or
unparsed entries. The caller applies these through its existing assembly path
and gives changed output a fresh paired identity; this tool never installs packs.

Rules contain `groups` (alias to `category`, `name`, vanilla `icon`, and locale
`labels`), exact `group_moves` and `items` mappings, and optional `components`
or exact `tags` mappings for ungrouped items. Component roles are `food`, `drink`,
`tool`, `weapon`, `ranged`, `projectile` and `wearable`. Existing meaningful
subgroups remain unless explicitly mapped. Zero-nutrition food input hooks are
not guessed to be meals. Hidden definitions stay hidden, duplicate block/item
IDs receive one catalog entry, and unknown entries retain their classification.
Author archives, scripts and resources remain caller-supplied local inputs.

## Development and publication

- [SDK contracts and ownership](docs/SDK.md)
- [Cookery local installation](docs/COOKERY.md)
- [Public/family assembly and reproduction](docs/FAMILY-ASSEMBLY.md)
- [Validation boundaries](docs/VALIDATION.md)
- [Published source/SDK assets](https://github.com/burnt-tea-dev/senluo-bedrock-core/releases)

Ordinary PR CI tests the current SDK and adapters without rebuilding historical
releases or downloading optional third-party packs. Real-author input checks
are separate. Publication validates its actual source allowlist and immutable
SDK/toolkit identities. A successful source PR does not publish a Release or
deploy a server. The new source must receive its own publication identity
before distribution as a toolkit release; old payload hashes remain untouched.

## Rights and privacy

Obtain Cookery from [its author's project](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial).
Complete author archives/scripts, generated author packs, worlds, private
server configuration and credentials are not distributed here. Local composed
vanilla player data retains Mojang's reference license in the generated RP.

The SDK and newly written tools are BSD-3-Clause; see [LICENSE](LICENSE).
Grilling helpers retain that project's notices; locally adapted author content
retains its original terms and credits. This unofficial project is not
associated with Mojang or the addon authors.

Earlier toolkit-specific repair descriptions remain in the
[immutable previous README](https://github.com/burnt-tea-dev/senluo-bedrock-core/blob/7f015e92ed7536e5ed64317338eda55968e0c4ae/README.md).
They are history, not public installation prerequisites.
