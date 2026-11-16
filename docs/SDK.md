# SDK 0.1.2 source candidate

`sdk.json` is the export and provenance authority. Its two modules originated in
the owned Grilling runtime at the recorded commit. Core maintains them now;
0.1.1 changes event routing while the public food module retains its original bytes.
This candidate pairs that router with the owned food locale carrier.
Consumers pin the Core commit, manifest hash and each exported file hash. Update
Core first, then regenerate consumers; never edit a generated consumer directly.

`host_api/event_router.js` accepts the consumer's native `world` or `system`.
It shares one subscription per event inside that JavaScript module instance.
Interaction owners run in priority order, respect cancellation and can be
followed by observers. Removing a route releases its subscription when empty.
Separate behavior packs still have separate JavaScript buses. The optional
`playerCraftRecipe` signal is accessed only when that route is requested.

Route arrays are replaced when a subscription is added or removed. Each native
event uses the current array directly; an in-flight callback retains its original
snapshot when routes change, and a nested or later event sees the new array.
Priority, cancellation, observers, lazy optional signals and independent pack
buses keep the same behavior. Interaction target filtering still takes its own
snapshot before invoking owners, so an owner cannot change the later targets by
changing the event's block type.

## 2026-11-16 implementation and performance review

At main `0fe3f59f85b30da2426078680d0e6ea8908386c8`, the SDK copied its complete
route array for every delivered native event, including channels whose subscribers
never changed after startup. This was an implementation cost, not a missing Java
feature or a Bedrock API restriction. The 0.1.1 source candidate moves that copy
to subscription changes. It does not change event frequency or add a tick loop.

The existing `node --test tests/sdk.test.mjs` passes all four checks before and
after the change, including self removal during dispatch, priority/cancellation,
observers, independent buses, optional crafting and unchanged food metadata.
A temporary run of the actual old and new exports with eight subscribers and
100,000 script events confirms 800,000 callbacks in each version. Source-level
instrumentation counts 100,000 per-event route-array copies before and zero after.
Registration/removal still allocate replacement arrays; interaction filtering,
engine event objects and other allocations are outside that count. This is not
a device memory, tick-time or FPS measurement. No new test, fixture or workflow
is introduced.

The native subscription APIs are unchanged. Microsoft's
[script performance guidance](https://learn.microsoft.com/en-us/minecraft/creator/documents/scripting/script-performance?view=minecraft-bedrock-stable)
also recommends filtering supported signals at subscription. A generic router
cannot silently adopt a different native filter for a caller: future filtering
must preserve the union of all routes and the exact supported API version.

Other Core audit boundaries:

- The two exported SDK modules own routing and public food metadata, not Java
  recipes, renderer behavior, machines or persistence. Addon parity stays with
  the corresponding consumer.
- Cookery guide/recipe helpers already use native jobs or bounded tick work.
  FIFO ordering, complete-chapter visibility and synchronous registration
  contracts must remain intact; scheduling changes cannot promise identical
  completion ticks across devices.
- The station helper already avoids equal pose/item/state writes and periodically
  reconciles live entities. A cache must not become the machine's saved-data owner.
- Historical descriptors are explicit build inputs, not simultaneous runtime
  copies. Removing them alone does not establish a gameplay memory reduction.

Consumers adopt 0.1.1 by pinning this candidate's exact committed SDK manifest
and source hashes, then running their existing SDK generator. Unchanged consumers
remain on their recorded 0.1.0 input until separately updated. This source PR
does not publish an SDK/toolkit Release or change immutable release-history
payloads. A later toolkit publication needs its own complete release identity.

`host_api/food_api_core.js` owns the existing `senluo.public.food.v1` lore carrier.
It validates and reads existing absolute heat deadlines without rounding them.
New deadlines use the existing 100-tick bucket. Public food data can carry heat,
seasoning, a native variant and cuisine quality, while preserving custom lore.
Core does not read another pack's private dynamic properties.

The carrier's client text is owned by
[`resources/texts/food_api.lang`](../resources/texts/food_api.lang). Its nonempty
`§r` value is a native formatting reset with no visible glyphs; do not replace it
with an empty translation value. The V1 key and JSON in `with` are unchanged.
An installation using a food writer must provide this entry in its resource
locales, including the `en_US` fallback. The Core Cookery installer
and Grilling's SDK synchronization use `merge_food_locale()` from
`tools/install_cookery.py` for this merge. The SDK archive includes the resource
fragment; the toolkit includes its merge function. Read-only consumers such as
OTC retain the existing codec and do not need a second writer or a new carrier.
These source changes require a fresh release before distribution; they do not
retroactively alter the recorded SDK 0.1.0 release.

The cross-pack client and gameplay APIs remain in
[Grilling's integration contract](https://github.com/burnt-tea-dev/kaleidoscope-grilling-unofficial/blob/main/docs/BEDROCK-INTEGRATION-API.md).
Crafting, chopping boards, oil, pots, recipes, rewards and persistent gameplay
data remain addon responsibilities. Core is not a Java JAR or a Bedrock port of
the Java Kaleidoscope Lib API.

## Native block shape compaction

`tools/block_shapes.py::compact_block()` compacts explicitly selected block
bounds into containing boxes. The caller owns input provenance and the decision
to compact each block. With no new options, the existing behavior is unchanged:
collision and selection bounds are processed independently. Switching solidity
is still rejected unless the caller selects the existing `allow_empty` handling
for mixtures of `false` and boxes.

Use `compact_block(definition, non_solid=True)` when the owner's source confirms
that the block should allow entities to pass through in every state. This sets
the base `minecraft:collision_box` to `false` and removes collision overrides
from every permutation before compaction. It does not infer solidity from a
model, a selection box or an addon name. The input is copied; block identity,
state values and other component data retain their existing ownership.

Selection still follows the existing compaction algorithm. This option does not
turn off cursor selection, and it is not a standalone transformation that
preserves arbitrary state-specific selection boxes. Review those bounds before
selecting a block for compaction. Permutations emptied by compaction continue to
be removed by the existing cleanup.

For a collision decision that must preserve every existing selection box, use
`with_collision(definition, collision)` instead. It copies the definition, sets
the supplied native collision value at the base, and removes only collision
overrides from permutations. Selection bounds, mixed selectable/non-selectable
states, permutation order and all other data stay intact. The collision value
is copied too; neither caller-owned argument is mutated. This operation does
not compact boxes or remove empty permutations. `with_collision(definition,
False)` therefore supports pass-through multipart decorations whose helper
cells deliberately have `selection_box:false` without expanding their targets.
The caller must verify the supplied boolean, box or box array against the
selected engine/format and the physical behavior of the original source; an
interaction actor's dimensions are not evidence of physical collision.

For reviewed state-dependent physical shapes, the optional `permutations`
mapping assigns collision values to exact, already-existing condition strings.
For example, a furniture block's existing height state can retain distinct short
and tall collision boxes without changing its visual or selection permutations.
An unknown condition raises `ValueError`; the helper does not add a state or
guess an expression. Unspecified permutation collisions are removed, so the
base and supplied overrides form the complete new physical definition.

Bedrock supports [disabling native block collision](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/blockreference/examples/blockcomponents/minecraftblock_collision_box?view=minecraft-bedrock-stable)
without disabling the independent [cursor selection box](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/blockreference/examples/blockcomponents/minecraftblock_selection_box?view=minecraft-bedrock-stable).
This build-time option adds no script callback, tick loop or helper entity.
Consumers must pin the committed source and hash, then regenerate their copies
and addon outputs through their existing build. This source capability does not
publish a toolkit release or modify a generated consumer.

## Save compatibility

No pack UUID, module UUID, persisted key, item ID, block ID or state value is
removed or renamed. Host helpers still execute in Cookery's original script
module. Existing dynamic properties therefore keep their original owner.
The installer changes only reviewed hooks/helpers plus the paired manifest
release identity. It never reads or rewrites a world database.
