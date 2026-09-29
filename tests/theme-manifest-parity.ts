// Parity gate: the checked-in TypeScript manifest preserves the immutable
// canonical seed (30 Module records / 32 capability records) field-for-field.
// The issue appendix, its two digests, and this parity test are the immutable
// input reference (see manifest/theme-manifest.ts).

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { modules, capabilities, target, seed } from "../manifest/theme-manifest.ts";
import { expectedDisposition } from "../tools/theme-catalog/validate.ts";

const seedBytes = readFileSync(
  new URL("../manifest/21d50-canonical-manifest-seed.json", import.meta.url),
  "utf8",
);

type SeedCapability = {
  disposition: string;
  names: string[];
  asset_paths: string[];
  evidence_type: string;
};
type SeedModule = {
  identity: string;
  renderer_evidence_status: string;
  capabilities: SeedCapability[];
};
type Seed = {
  source_sha256: string;
  target: { device: string; os_version: string; build: string };
  modules: SeedModule[];
};

const seedData: Seed = JSON.parse(seedBytes);

const fail = (message: string): never => {
  throw new Error(message);
};
function assert(condition: unknown, message: string): asserts condition {
  if (!condition) fail(message);
}
const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex");

// ---- immutable digests ----
const SEED_SHA256 = "63252e96ade77361484a75eade500bc7a653965ead644f11eaffe02cc2a7ef99";
const SOURCE_SHA256 = "d1d990e14cbbb683cfd5a42a924ec1839303e1cc4499bf0c976e89c9aabd9919";
assert(sha256(seedBytes) === SEED_SHA256, `seed SHA-256 drifted: ${sha256(seedBytes)}`);
assert(seedData.source_sha256 === SOURCE_SHA256, "seed source_sha256 drifted");
assert(seed.sha256 === SEED_SHA256, "manifest seed.sha256 does not match the input reference");
assert(seed.sourceSha256 === SOURCE_SHA256, "manifest seed.sourceSha256 does not match the input reference");

// ---- seed target / manifest target ----
assert(seedData.target.device === "iPhone15,2", "seed device mismatch");
assert(seedData.target.os_version === "iOS 17.3", "seed os_version mismatch");
assert(seedData.target.build === "21D50", "seed build mismatch");
assert(
  target.productType === "iPhone15,2" &&
    target.productVersion === "17.3" &&
    target.build === "21D50",
  "manifest target metadata is not exactly iPhone15,2 / 17.3 / 21D50",
);

// ---- cardinality ----
assert(seedData.modules.length === 30, `seed has ${seedData.modules.length} modules, expected 30`);
assert(
  seedData.modules.reduce((sum, module) => sum + module.capabilities.length, 0) === 32,
  "seed capability total is not 32",
);
assert(modules.length === 30, "manifest Module records not 30");
assert(capabilities.length === 32, "manifest Capability records not 32");

// ---- per-seed-module parity ----
const moduleById = new Map<string, (typeof modules)[number]>(modules.map((module) => [module.id, module]));
const capabilityByKey = new Map<string, (typeof capabilities)[number]>(
  capabilities.map((capability) => [`${capability.module}#${capability.localIndex}`, capability]),
);

for (const seedModule of seedData.modules) {
  const record = moduleById.get(seedModule.identity);
  assert(record !== undefined, `module omitted from manifest: ${seedModule.identity}`);
  assert(record.safeDefault === "stock", `module ${record.id} stock default not preserved`);
  assert(
    record.seedRendererEvidenceStatus === seedModule.renderer_evidence_status,
    `module ${record.id} renderer evidence status not preserved`,
  );
  assert(
    record.capabilities.length === seedModule.capabilities.length,
    `module ${record.id} capability count mismatch`,
  );
  seedModule.capabilities.forEach((seedCapability, local) => {
    const capability = capabilityByKey.get(`${seedModule.identity}#${local}`);
    assert(capability !== undefined, `capability omitted: ${seedModule.identity}#${local}`);
    assert(
      capability.seedDisposition === seedCapability.disposition,
      `capability ${capability.id} disposition not preserved (${capability.seedDisposition} != ${seedCapability.disposition})`,
    );
    assert(
      JSON.stringify(capability.stockAliases) === JSON.stringify(seedCapability.names),
      `capability ${capability.id} names not preserved`,
    );
    assert(
      JSON.stringify(capability.stockAssets) === JSON.stringify(seedCapability.asset_paths),
      `capability ${capability.id} asset paths not preserved`,
    );
    assert(
      capability.seedEvidenceType === seedCapability.evidence_type,
      `capability ${capability.id} evidence type not preserved`,
    );
    const mapped = expectedDisposition(
      capability.seedDisposition,
      capability.seedEvidenceType,
      record.seedRendererEvidenceStatus,
    );
    assert(capability.disposition === mapped, "disposition mapping violated");
  });
}

// ---- eligible / stock-only split ----
const eligible = capabilities.filter((capability) => capability.disposition === "eligible");
const stockOnly = capabilities.filter((capability) => capability.disposition !== "eligible");
assert(eligible.length === 13, `expected 13 eligible, found ${eligible.length}`);
assert(stockOnly.length === 19, `expected 19 stock-only, found ${stockOnly.length}`);

const EXPECTED_ELIGIBLE = [
  "airplay-mirroring",
  "appearance",
  "connectivity-caml",
  "display-brightness",
  "focus",
  "low-power",
  "media-controls-volume",
  "mute",
  "orientation-lock",
  "replaykit",
  "shazam",
  "springboard-ringer",
  "timer",
];
const actualEligible = eligible.map((capability) => capability.id).sort();
assert(
  JSON.stringify(actualEligible) === JSON.stringify([...EXPECTED_ELIGIBLE].sort()),
  "eligible set does not match the accepted 21D50 Plampy map",
);

// ---- stock-only disposition classes present in the catalog ----
const classes = new Set<string>(capabilities.map((capability) => capability.disposition));
for (const disposition of [
  "eligible",
  "stock-only-opaque",
  "stock-only-static",
  "stock-only-inferred",
  "stock-only-unknown",
  "stock-only-missing",
]) {
  assert(classes.has(disposition), `disposition class ${disposition} does not occur in the catalog`);
}

console.log(
  "PASS: manifest parity (seed SHA-256 and source SHA-256 pinned; 30 modules / 32 capabilities / 13 eligible / 19 stock-only preserved field-for-field; target exact; all six disposition classes explicit)",
);