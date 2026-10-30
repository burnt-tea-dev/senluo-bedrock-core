# Validation 0.1.0

The SDK/local-adapter release checks passed on BDS 1.26.60.6. The [machine-readable summary](validation-0.1.0.json) pins inputs, outputs, module hashes and the scope of each check.

- SDK behavior and six Python installer tests passed in CI. The public Grilling source reproduces the exact pinned Grilling archive; clean author Cookery plus that input reproduce the exact adapted archive. All 3,443 unchanged author files retain their bytes. The ten reviewed host files and sixteen owned helpers match the public declaration. Pack and module UUIDs remain unchanged.
- Native startup/restart accepted Cookery 1.6.20001 with Grilling 2.8.201. A separate original-UUID compatibility fixture passed old Cookery readback, candidate first load, candidate restart, and original Cookery rollback on the same existing QA database. It preserved world/item dynamic properties and a real chest ItemStack with name, lore, public heat/quality/seasoning, enchantment, durability and block permissions.
- The compatibility fixture adds QA-only diagnostic code in the original Cookery script module. Its SDK helper copies match the published bytes. It uses the native on_area_loaded callback before reading a chest; a fixed two-second delay produced earlier false missing-item results. Earlier harness failures and raw logs remain preserved separately.

Startup watchdog spikes were observed and are retained in the summary. This is SDK and host-namespace evidence; it does not establish full-family saved-world admission, multiplayer performance, rendered gameplay, sound, complete Java parity or real-player acceptance. Client and production-ready status remain false. No LIVE world was changed for these checks.
