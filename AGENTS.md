# Senluo Bedrock Core

Use the shared [pstack agent workflow](https://github.com/burnt-tea-dev/kaleidoscope-tavern-unofficial/blob/5bc82d3d60e1837306eeb3f0ae4da64c7df4b392/family/UPDATE-WORKFLOW.md#pstack-代理入口) for task routing, host adaptation, scoped verification and Draft PR delivery. Its project constraints override upstream defaults; retain the repository-specific contracts below.

- This repository owns the shared SDK and generic local adapter tooling. Gameplay belongs to its addon repository; host storage retains its existing pack UUID and data format.
- Never commit author addon archives, complete author scripts, private integration source, host configuration, worlds or credentials. Public release inputs are an explicit allowlist.
- Read `.repo-target.json` and verify remote repository name, numeric ID, owner and visibility before remote writes. Changes go through PR, required CI and merge.
- Keep source and generated SDK exports in one direction. Consumers pin the exact committed SDK version and hashes; update the canonical source and regenerate consumers.
- Verify actual exported behavior and clean-author integration. Do not replace engine or client acceptance with mocks. Preserve original failed evidence and existing save keys/IDs/UUID ownership.
- Release only after appropriate SDK, original-author input, isolated BDS, saved-world and rollback checks. Record remaining client limitations honestly.
- Ordinary PR CI tests source behavior only. Tests and workflow files are not public toolkit inputs; change them freely without bumping the toolkit version. Validate exact published files and SDK hashes when preparing an actual release.
