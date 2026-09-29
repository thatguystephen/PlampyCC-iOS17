# Theme catalog (M0 manifest + generated stock catalog)

The theme catalog is the single canonical Module Identity / Capability vocabulary for iPhone15,2 / iOS 17.3 / 21D50. A checked-in TypeScript manifest declares 30 Module identities and 32 capabilities (13 catalog-eligible CAML routes, 19 explicit stock-only dispositions); a Bun generator validates it against the closed census and emits an immutable Objective-C++ stock catalog plus an evidence sidecar. Generation is deterministic, byte-identical on regen, and the selected stage (Q0, empty activation) pins the artifact. No runtime hook, session, device, package, or theme-substitution behavior changes.

Sources: `manifest/theme-manifest.ts`, `manifest/21d50-canonical-manifest-seed.json`, `tools/theme-catalog/validate.ts`, `tools/theme-catalog/generate.ts`, `src/generated/PlampyCCThemeCatalog.hpp`, `src/generated/PlampyCCThemeCatalog.json`.

## Sub-features

- `manifest-parity` pins the seed SHA-256 (`63252e…`) and source SHA-256 (`d1d990…`) and preserves every seed record, disposition, name, asset path, and stock default in the TypeScript model.
- `catalog-generation` validates the manifest and emits the immutable catalog deterministically; checked-in output is byte-identical on regen (stale-generation gate via `--check`).
- `catalog-validation` fails generation on invalid counts, IDs, ownership, dispositions, aliases, assets, family adapters, target metadata, stage names, duplicate active IDs, and wrong stage shapes.
- `catalog-stage` pins Q0 as the sole selected stage with an empty activation set; activation of an eligible capability requires complete direct 21D50 lifecycle evidence.
- `catalog-extension` proves an existing-family module can be added by changing manifest/asset/generated inputs without editing hook source; the rendered extended header is compiled AND run under its extended census (31 modules / 33 capabilities / 14 eligible), proving the generated static_asserts come from the validated contract rather than hardcoded 30/32/13 literals.

## How to get to it (user POV)

- Maintainers add or correct a Module Identity / Capability by editing `manifest/theme-manifest.ts`, then regenerating and committing both generated outputs.
- Verifiers confirm the catalog is current and valid before any handoff or acceptance run.

## Driving it with the Bun theme-catalog harness

Preconditions:

- Repo root as CWD on the Linux host (python3, g++, bun).
- `git status --porcelain` shows exactly the intended diff.

- **Strict TypeScript.** Run `./node_modules/.bin/tsc --noEmit` (after `bun install --frozen-lockfile`). Exit 0, no output. The pinned TypeScript dev dependency type-checks the manifest, validator, generator, and every catalog test under a strict `tsconfig` — no `@ts-nocheck`, no `bunx`/`bun run`, and no `as unknown as ThemeManifest` cast anywhere in the catalog surface.
- **Regeneration / stale-generation.** Run `bun tools/theme-catalog/generate.ts --check`. One PASS line, exit 0; nonzero means the checked-in Objective-C++ and JSON outputs are stale and must be regenerated with `bun tools/theme-catalog/generate.ts`.
- **Parity.** Run `bun tests/theme-manifest-parity.ts`. One PASS line, exit 0. Pins both input digests, preserves all 30/32 records field-for-field, and verifies the 13/19 eligible/stock-only split and the six disposition classes.
- **Generation + native compile.** Run `bun tests/theme-catalog-generation.ts`. One PASS line, exit 0. Determinism, byte-identity, digest recomputation, `--check` green, and compiles `tests/native-theme-catalog.cpp` (`g++ -std=c++17 -Wall -Wextra -Werror`) against the generated header, asserting census counts, the immutable `ModuleEntry` table (all 30 identities, safe defaults, and module→capability ownership edges), unique precomputed tags, constant-time ID lookup, and the empty Q0 bitset.
- **Validation fixtures.** Run `bun tests/theme-catalog-validation.ts`. One PASS line, exit 0. Exercises every generation-failure mode plus the stage-shape rules and the existing-family extension fixture.

## Gotchas

- The catalog digest hashes the manifest model (records, routes, dispositions, lifecycle-evidence records, and renderer-adapter declarations) — NOT the selected stage or the activation set. The activation-set digest hashes only the selected stage name and its active capabilities. Changing activation changes activation identity only; changing catalog, evidence, or adapter data changes catalog identity.
- Catalog eligibility never requires lifecycle evidence: an eligible capability may stay inactive with `lifecycleEvidence: null`. Only activation requires a complete direct 21D50 evidence record. Selecting any stage beyond Q0 fails generation until its capabilities' evidence closes.
- Lifecycle evidence is structural: each record couples its bind/close/detach/reuse selector or signal to its form, encoding, and 21D50 call-site source, and each Issue #9 fact (invalidation, producer tag, capture/adoption/restoration/teardown, fail-open) to its statement and source. `synthetic-fixture` records prove schema shape only and can never close activation.
- `kTagIndex` is a sorted index for cross-TU identity checks, NOT a constant-time tag→capability map — constant-time lookup remains the typed `CapabilityId` ordinal into `kCapabilities`. The false "constant-time tag lookup" comment was removed.
- The generator emits constant C++17 data only — no strings that would require setter-time parsing, and the shipping dylib still contains no manifest parser. Manifest strings containing newline/control characters are rejected before they reach a C++ literal.
- The generated header compiles on the host (g++); it is not yet wired into the tweak build — M2a integrates it.

## Observable proof

Non-device boundary (what one verification run must reach): the five commands above, each with one PASS line and exit 0, plus `python3 -B tests/manifest-contract.py` and `bun tests/static-check.ts` still green (existing gates unweakened), captured under `evidence/verify-<YYYYMMDD-HHMM>/` at a repo state whose `git status --porcelain` matches the change under review.

Device-only gap (separate authorized task): Q0 exercises the catalog with all 32 capabilities stock on iPhone15,2 / 17.3 / 21D50 (D0–D6); the device test vectors emitted per capability are host-authored declarations confirmed only at the device stage.