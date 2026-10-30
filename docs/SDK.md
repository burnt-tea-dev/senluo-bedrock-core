# SDK 0.1.0

`sdk.json` is the export and provenance authority. Its two modules originate in
the owned Grilling runtime at the recorded commit, with their bytes unchanged.
The Core repository is their maintenance source from this release onward.
Consumers pin the Core commit, manifest hash and each exported file hash. Update
Core first, then regenerate consumers; never edit a generated consumer directly.

`host_api/event_router.js` accepts the consumer's native `world` or `system`.
It shares one subscription per event inside that JavaScript module instance.
Interaction owners run in priority order, respect cancellation and can be
followed by observers. Removing a route releases its subscription when empty.
Separate behavior packs still have separate JavaScript buses. The optional
`playerCraftRecipe` signal is accessed only when that route is requested.

`host_api/food_api_core.js` owns the existing `senluo.public.food.v1` lore carrier.
It validates and reads existing absolute heat deadlines without rounding them.
New deadlines use the existing 100-tick bucket. Public food data can carry heat,
seasoning, a native variant and cuisine quality, while preserving custom lore.
Core does not read another pack's private dynamic properties.

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
