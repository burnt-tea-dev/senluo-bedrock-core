# Reviewed dependency-only diagnostics

`tools/install_player_presentation.py::advance_reviewed_dependencies` is an
opt-in manifest owner operation for a **new** diagnostic adapter identity.
It does not change default descriptors, regenerate player semantics, edit an
installed pack, or establish client acceptance.

Use it only after a reviewed recipe has pinned the complete historical input
archive, every non-manifest byte, and the exact source producer. The caller must
also read the current identity registry and supply its maximum allocated
version as `latest_version`. A stale caller-side registry is not safe: recheck
allocation before committing the paired recipe or emitting an immutable output.

The operation requires an exact SHA-256 of the original manifest, its expected
version, exactly two existing paired UUIDs, and an explicit list of old/new
external dependency edges. Both the adapter version and each changed external
version must increase. The existing paired edge must match the old version.
Missing or duplicate edges, changed UUIDs, ambiguous JSON, malformed versions,
and unreviewed companion additions are rejected. Header/module UUIDs, engine
requirements, metadata and unrelated dependencies remain unchanged.

The ordinary `advance_manifest` entry still rejects a conflicting Grilling
dependency. Callers must not strip an old edge to bypass that guard. The new
entry validates each exact preimage before delegating pair-version advancement
to that same owner.

Before building a complete diagnostic family, verify every affected BP/RP pair,
the closed dependency graph, package order, effective player property count,
and all conserved body hashes. Use newly allocated immutable versions and
append-only receipts/history. Do not replace a historical result or mix a
new pose into an old candidate's evidence. Model appearance, gameplay, audio,
save/re-entry and multiplayer remain separate native-client checks.

No complete third-party archives, private host source or world data belong in
this public repository. This change exports tooling only; no adapter candidate
or production-ready claim is included.
