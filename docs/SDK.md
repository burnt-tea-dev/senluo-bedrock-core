# SDK 0.1.1 source candidate

`sdk.json` is the export and provenance authority. Its two modules originated in
the owned Grilling runtime at the recorded commit. Core maintains them now;
0.1.1 changes event routing while the public food module retains its original bytes.
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

## Save compatibility

No pack UUID, module UUID, persisted key, item ID, block ID or state value is
removed or renamed. Host helpers still execute in Cookery's original script
module. Existing dynamic properties therefore keep their original owner.
The installer changes only reviewed hooks/helpers plus the paired manifest
release identity. It never reads or rewrites a world database.
